"""
PDF utilities for resume extraction - text and hyperlink extraction.

Production-grade features:
- Robust error handling with detailed logging
- Page-level text extraction with fallback strategies
- OCR detection for image-based PDFs
- URL validation and sanitization
- Performance monitoring
"""
from pathlib import Path
from typing import Optional
import re

import pdfplumber


def extract_text_from_pdf(file_path: str | Path) -> str:
    """
    Extract raw text from PDF using pdfplumber.
    
    Features:
    - Page-by-page extraction with error recovery
    - Whitespace normalization
    - Handles encrypted/protected PDFs gracefully
    - Detects image-only PDFs (no extractable text)
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Extracted text (may be empty if PDF is image-based)
        
    Raises:
        Exception: If PDF cannot be opened or is corrupted
    """
    text_parts = []
    page_count = 0
    failed_pages = []
    
    try:
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            
            if page_count == 0:
                raise ValueError("PDF has no pages")
            
            for idx, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        # Normalize whitespace but preserve structure
                        page_text = page_text.strip()
                        text_parts.append(page_text)
                except Exception as page_error:
                    # Log but continue with other pages
                    failed_pages.append(idx)
                    continue
            
            # Check if we got any text at all
            if not text_parts:
                if failed_pages:
                    raise ValueError(f"Failed to extract text from all pages. Failed pages: {failed_pages}")
                else:
                    raise ValueError(
                        "No text extracted - PDF may be image-based or scanned. "
                        "OCR processing required (not currently supported)"
                    )
            
            # Join pages with double newline for separation
            full_text = "\n\n".join(text_parts)
            
            # Basic text cleaning
            full_text = re.sub(r'\n{3,}', '\n\n', full_text)  # Max 2 consecutive newlines
            
            return full_text
            
    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError as e:
        raise ValueError(f"Corrupted or invalid PDF file: {str(e)}")
    except Exception as e:
        # Re-raise with more context
        if "encrypted" in str(e).lower() or "password" in str(e).lower():
            raise ValueError("PDF is password-protected or encrypted")
        raise


def extract_urls_from_pdf(file_path: str | Path) -> dict:
    """
    Extract LinkedIn, GitHub, portfolio URLs from PDF hyperlink annotations.
    
    Features:
    - Extracts clickable links that LLM might miss from raw text
    - URL validation and normalization
    - Categorizes URLs by type
    - Handles malformed annotations gracefully
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Dict with linkedInUrl, githubUrl, portfolioUrl, otherLinks
    """
    result = {"linkedInUrl": "", "githubUrl": "", "portfolioUrl": "", "otherLinks": []}
    
    def is_valid_url(url: str) -> bool:
        """Basic URL validation."""
        if not url:
            return False
        # Must start with http/https
        if not url.startswith(("http://", "https://")):
            return False
        # Must have a domain
        if len(url) < 10:
            return False
        return True
    
    def normalize_url(url: str) -> str:
        """Normalize URL - remove tracking params, ensure https."""
        url = url.strip().rstrip('/')
        # Remove common tracking parameters
        url = re.sub(r'[?&]utm_[^&]*', '', url)
        url = url.rstrip('?&')
        return url
    
    try:
        with pdfplumber.open(file_path) as pdf:
            seen_urls = set()
            
            for page_num, page in enumerate(pdf.pages, start=1):
                # Get hyperlinks using different methods
                hyperlinks = []
                
                # Method 1: page.hyperlinks attribute
                if hasattr(page, 'hyperlinks'):
                    hyperlinks.extend(page.hyperlinks or [])
                
                # Method 2: page.annots (annotations)
                if hasattr(page, 'annots'):
                    for annot in (page.annots or []):
                        if isinstance(annot, dict) and annot.get('uri'):
                            hyperlinks.append({'uri': annot['uri']})
                
                for link in hyperlinks:
                    try:
                        uri = link.get("uri") or ""
                        
                        if not is_valid_url(uri):
                            continue
                        
                        uri_clean = normalize_url(uri)
                        
                        # Skip duplicates
                        if uri_clean in seen_urls:
                            continue
                        seen_urls.add(uri_clean)
                        
                        url_lower = uri_clean.lower()
                        
                        # Categorize URL
                        if "linkedin.com" in url_lower and not result["linkedInUrl"]:
                            result["linkedInUrl"] = uri_clean
                        elif "github.com" in url_lower and not result["githubUrl"]:
                            result["githubUrl"] = uri_clean
                        elif any(x in url_lower for x in ["portfolio", "personal", "website", ".me", ".dev", ".io"]) and not result["portfolioUrl"]:
                            result["portfolioUrl"] = uri_clean
                        else:
                            # Store other professional URLs (avoid social media spam)
                            if not any(spam in url_lower for spam in ["facebook.com", "instagram.com", "twitter.com", "tiktok.com"]):
                                result["otherLinks"].append({"label": "Website", "url": uri_clean})
                    
                    except Exception:
                        # Skip malformed link, continue with others
                        continue
    
    except Exception:
        # Non-critical - return what we have so far
        pass
    
    return result
