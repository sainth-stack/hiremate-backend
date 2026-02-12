"""
PDF utilities for resume extraction - text and hyperlink extraction.
"""
from pathlib import Path

import pdfplumber


def extract_text_from_pdf(file_path: str | Path) -> str:
    """Extract raw text from PDF using pdfplumber."""
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_urls_from_pdf(file_path: str | Path) -> dict:
    """Extract LinkedIn, GitHub, portfolio URLs from PDF hyperlink annotations (clickable links)."""
    result = {"linkedInUrl": "", "githubUrl": "", "portfolioUrl": "", "otherLinks": []}
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                for link in getattr(page, "hyperlinks", []) or []:
                    uri = link.get("uri") or ""
                    if not uri or not uri.startswith("http"):
                        continue
                    uri_clean = uri.strip()
                    url_lower = uri_clean.lower()
                    if "linkedin.com" in url_lower and not result["linkedInUrl"]:
                        result["linkedInUrl"] = uri_clean
                    elif "github.com" in url_lower and not result["githubUrl"]:
                        result["githubUrl"] = uri_clean
                    elif any(x in url_lower for x in ["portfolio", "personal", "website", ".me"]) and not result["portfolioUrl"]:
                        result["portfolioUrl"] = uri_clean
    except Exception:
        pass
    return result
