"""
Production-grade resume template registry.
Template IDs must match the keys in TEMPLATE_MAP in resume_generator.py.
"""
from typing import TypedDict


class ColorScheme(TypedDict):
    id: str
    label: str
    primary: str
    accent: str
    bg: str


class ResumeTemplate(TypedDict):
    id: str
    name: str
    category: str       # 'classic' | 'modern' | 'minimal' | 'executive' | 'academic' | 'creative'
    ats_score: int      # 0-100
    best_for: list[str]
    premium: bool
    fonts: list[str]
    color_schemes: list[ColorScheme]
    layout: str         # 'single_column' | 'two_column' | 'sidebar'
    description: str


TEMPLATES: list[ResumeTemplate] = [
    {
        "id": "classic",
        "name": "Classic",
        "category": "classic",
        "ats_score": 98,
        "best_for": ["all", "ats-optimized", "corporate", "finance"],
        "premium": False,
        "layout": "single_column",
        "description": "Clean, traditional layout optimised for ATS scanners.",
        "fonts": ["Times New Roman", "Georgia", "Garamond", "Palatino"],
        "color_schemes": [
            {"id": "default", "label": "Classic Black", "primary": "#000000", "accent": "#000000", "bg": "#ffffff"},
            {"id": "navy",    "label": "Navy",          "primary": "#0d2b4e", "accent": "#0d2b4e", "bg": "#ffffff"},
        ],
    },
    {
        "id": "professional",
        "name": "Professional",
        "category": "classic",
        "ats_score": 96,
        "best_for": ["tech", "engineering", "ats-optimized", "corporate", "startup"],
        "premium": False,
        "layout": "single_column",
        "description": "Clean sans-serif layout with navy section headers. Role-first experience format.",
        "fonts": ["Calibri", "Arial", "Helvetica", "Lato", "Segoe UI", "Verdana"],
        "color_schemes": [
            {"id": "navy",    "label": "Navy",    "primary": "#1a3a5c", "accent": "#1a3a5c", "bg": "#ffffff"},
            {"id": "slate",   "label": "Slate",   "primary": "#1e293b", "accent": "#1e293b", "bg": "#ffffff"},
            {"id": "teal",    "label": "Teal",    "primary": "#0f4c5c", "accent": "#0f4c5c", "bg": "#ffffff"},
            {"id": "indigo",  "label": "Indigo",  "primary": "#1e1b4b", "accent": "#1e1b4b", "bg": "#ffffff"},
        ],
    },
    {
        "id": "minimalist",
        "name": "Minimalist",
        "category": "minimal",
        "ats_score": 99,
        "best_for": ["ats-optimized", "consulting", "finance", "law"],
        "premium": False,
        "layout": "single_column",
        "description": "Ultra-clean, whitespace-driven — maximum ATS compatibility.",
        "fonts": ["Helvetica", "Arial", "Calibri", "Verdana"],
        "color_schemes": [
            {"id": "mono",  "label": "Monochrome", "primary": "#000000", "accent": "#000000", "bg": "#ffffff"},
            {"id": "slate", "label": "Slate",       "primary": "#1e293b", "accent": "#475569", "bg": "#ffffff"},
        ],
    },
    {
        "id": "modern",
        "name": "Modern",
        "category": "modern",
        "ats_score": 88,
        "best_for": ["tech", "engineering", "data-science", "startup"],
        "premium": False,
        "layout": "two_column",
        "description": "Contemporary two-column design favoured by tech companies.",
        "fonts": ["Inter", "Roboto", "DM Sans", "Poppins", "Lato"],
        "color_schemes": [
            {"id": "dark",    "label": "Charcoal", "primary": "#2d3748", "accent": "#4a5568", "bg": "#ffffff"},
            {"id": "blue",    "label": "Blue",     "primary": "#1e40af", "accent": "#3b82f6", "bg": "#ffffff"},
            {"id": "emerald", "label": "Emerald",  "primary": "#064e3b", "accent": "#10b981", "bg": "#f0fdf4"},
        ],
    },
    {
        "id": "executive",
        "name": "Executive",
        "category": "executive",
        "ats_score": 95,
        "best_for": ["leadership", "management", "c-suite", "corporate"],
        "premium": False,
        "layout": "single_column",
        "description": "Dark navy header communicates seniority and authority.",
        "fonts": ["Georgia", "Times New Roman", "Garamond", "Palatino"],
        "color_schemes": [
            {"id": "navy",   "label": "Navy",    "primary": "#0f2952", "accent": "#0f2952", "bg": "#ffffff"},
            {"id": "forest", "label": "Forest",  "primary": "#1a3a2a", "accent": "#1a3a2a", "bg": "#ffffff"},
            {"id": "slate",  "label": "Slate",   "primary": "#1e293b", "accent": "#334155", "bg": "#ffffff"},
        ],
    },
    {
        "id": "harvard",
        "name": "Harvard",
        "category": "academic",
        "ats_score": 96,
        "best_for": ["academic", "research", "consulting", "law"],
        "premium": False,
        "layout": "single_column",
        "description": "Academic serif style modelled on Harvard career services guidelines.",
        "fonts": ["Times New Roman", "Garamond", "Palatino", "Georgia"],
        "color_schemes": [
            {"id": "default", "label": "Black",  "primary": "#000000", "accent": "#000000", "bg": "#ffffff"},
            {"id": "crimson", "label": "Crimson","primary": "#7b0000", "accent": "#7b0000", "bg": "#ffffff"},
        ],
    },
    {
        "id": "elegant",
        "name": "Elegant",
        "category": "creative",
        "ats_score": 90,
        "best_for": ["design", "marketing", "creative", "media"],
        "premium": True,
        "layout": "single_column",
        "description": "Refined typography and subtle accents for creative professionals.",
        "fonts": ["Georgia", "Garamond", "Lato", "Raleway"],
        "color_schemes": [
            {"id": "gold",   "label": "Gold",    "primary": "#1a1a1a", "accent": "#b8860b", "bg": "#ffffff"},
            {"id": "rose",   "label": "Rose",    "primary": "#1a1a1a", "accent": "#be185d", "bg": "#ffffff"},
        ],
    },
    {
        "id": "impact",
        "name": "Impact",
        "category": "creative",
        "ats_score": 82,
        "best_for": ["design", "marketing", "sales", "creative"],
        "premium": True,
        "layout": "two_column",
        "description": "Bold, high-contrast layout that stands out in creative industries.",
        "fonts": ["Inter", "Roboto", "Montserrat", "Poppins"],
        "color_schemes": [
            {"id": "dark",   "label": "Dark",   "primary": "#111827", "accent": "#f59e0b", "bg": "#ffffff"},
            {"id": "purple", "label": "Purple", "primary": "#1e1b4b", "accent": "#8b5cf6", "bg": "#ffffff"},
        ],
    },
]

# Fast lookup by ID
_TEMPLATE_INDEX: dict[str, ResumeTemplate] = {t["id"]: t for t in TEMPLATES}


def get_template(template_id: str) -> ResumeTemplate | None:
    """Return template metadata by ID, or None if not found."""
    return _TEMPLATE_INDEX.get(template_id)


def list_templates() -> list[ResumeTemplate]:
    """Return all available templates."""
    return TEMPLATES
