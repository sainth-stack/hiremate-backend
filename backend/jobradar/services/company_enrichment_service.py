"""
Company enrichment service.
Fetches company metadata from domain and enriches with AI.
"""
import json
import requests
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup

from backend.jobradar.models.application import CompanyProfile


ENRICHMENT_PROMPT = """You are a company research assistant.

Given the company domain: {domain}

And this context from the company website:
{context}

Extract and return ONLY a JSON object with:
- industry: string (e.g. "B2B SaaS", "E-commerce", "Healthcare")
- size_range: string (e.g. "1-10", "11-50", "51-200", "201-500", "500+")
- hq_location: string (city, country format like "San Francisco, USA" or "Bengaluru, India")
- tech_stack: array of strings (infer from domain/context, common stacks: ["Python", "React", "AWS", etc.])

If you cannot determine a field with confidence, return null for that field.
Be conservative with estimates. If the domain gives no hints, return nulls.

Return ONLY valid JSON. No explanation, no markdown, no code fences."""


def enrich_company(db: Session, domain: str) -> CompanyProfile:
    """
    Enrich company profile by domain.
    
    Strategy:
    1. Check cache (return if < 7 days old)
    2. Scrape domain for context
    3. Use AI to extract metadata
    4. Upsert profile
    """
    if not domain:
        raise ValueError("Domain is required")
    
    domain = domain.lower().strip()
    
    # Step 1: Check cache
    existing = db.query(CompanyProfile).filter(CompanyProfile.domain == domain).first()
    if existing and existing.last_enriched_at:
        age = datetime.utcnow() - existing.last_enriched_at
        if age < timedelta(days=7):
            print(f"Company profile for {domain} is fresh (cached)")
            return existing
    
    # Step 2: Scrape domain for context
    context = _scrape_domain_context(domain)
    
    # Step 3: Use AI to extract metadata
    ai_data = _extract_with_ai(domain, context)
    
    # Step 4: Upsert profile
    if existing:
        # Update existing
        if ai_data.get('industry'):
            existing.industry = ai_data['industry']
        if ai_data.get('size_range'):
            existing.size_range = ai_data['size_range']
        if ai_data.get('hq_location'):
            existing.hq_location = ai_data['hq_location']
        if ai_data.get('tech_stack'):
            existing.tech_stack = ai_data['tech_stack']
        if context.get('name'):
            existing.name = context['name']
        if context.get('description'):
            existing.description = context['description'][:500]  # Cap at 500 chars
        existing.last_enriched_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new
        new_profile = CompanyProfile(
            domain=domain,
            name=context.get('name'),
            industry=ai_data.get('industry'),
            size_range=ai_data.get('size_range'),
            hq_location=ai_data.get('hq_location'),
            description=context.get('description', '')[:500] if context.get('description') else None,
            tech_stack=ai_data.get('tech_stack'),
            last_enriched_at=datetime.utcnow()
        )
        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)
        return new_profile


def _scrape_domain_context(domain: str) -> dict:
    """
    Scrape company website for context.
    Returns: { 'name': str, 'description': str, 'raw_text': str }
    """
    result = {'name': None, 'description': None, 'raw_text': ''}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    urls = [
        f'https://{domain}',
        f'https://{domain}/about',
        f'https://www.{domain}',
    ]
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract title
                if not result['name']:
                    title_tag = soup.find('title')
                    if title_tag:
                        result['name'] = title_tag.get_text().strip()[:100]
                
                # Extract meta description
                if not result['description']:
                    meta_desc = soup.find('meta', attrs={'name': 'description'}) or \
                                soup.find('meta', attrs={'property': 'og:description'})
                    if meta_desc:
                        result['description'] = meta_desc.get('content', '').strip()[:500]
                
                # Extract visible text (first 1000 chars)
                if not result['raw_text']:
                    # Remove script and style elements
                    for script in soup(["script", "style", "nav", "footer"]):
                        script.extract()
                    text = soup.get_text(separator=' ', strip=True)
                    result['raw_text'] = ' '.join(text.split())[:1000]
                
                # If we got good data from first URL, break
                if result['name'] and result['description']:
                    break
                    
        except Exception as e:
            print(f"Failed to scrape {url}: {e}")
            continue
    
    return result


def _extract_with_ai(domain: str, context: dict) -> dict:
    """
    Use AI to extract company metadata.
    Returns: { 'industry': str, 'size_range': str, 'hq_location': str, 'tech_stack': list }
    """
    from backend.jobradar.services.llm_factory import LLMFactory
    
    # Build context string
    context_parts = []
    if context.get('name'):
        context_parts.append(f"Company name: {context['name']}")
    if context.get('description'):
        context_parts.append(f"Description: {context['description']}")
    if context.get('raw_text'):
        context_parts.append(f"Website excerpt: {context['raw_text'][:500]}")
    
    context_str = '\n'.join(context_parts) if context_parts else "No additional context available."
    
    prompt = ENRICHMENT_PROMPT.format(domain=domain, context=context_str)
    
    try:
        provider = LLMFactory.get_provider()
        raw = provider.generate(
            system_prompt="",
            user_prompt=prompt,
            feature="company_enrichment"
        )
        
        # Parse JSON response
        data = json.loads(raw.strip())
        
        # Validate and sanitize
        result = {
            'industry': data.get('industry'),
            'size_range': data.get('size_range'),
            'hq_location': data.get('hq_location'),
            'tech_stack': data.get('tech_stack') if isinstance(data.get('tech_stack'), list) else []
        }
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"AI enrichment JSON parse error for {domain}: {e}")
        return {'industry': None, 'size_range': None, 'hq_location': None, 'tech_stack': []}
    except Exception as e:
        print(f"AI enrichment error for {domain}: {e}")
        return {'industry': None, 'size_range': None, 'hq_location': None, 'tech_stack': []}
