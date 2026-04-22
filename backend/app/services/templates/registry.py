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
        "id": "classic_professional",
        "name": "Classic Professional",
        "category": "classic",
        "ats_score": 97,
        "best_for": ["retail", "operations", "customer-service", "corporate", "ats-optimized"],
        "premium": False,
        "layout": "single_column",
        "description": "Traditional resume with strong section separators and clean professional typography.",
        "fonts": ["Calibri", "Arial", "Helvetica", "Segoe UI", "Verdana"],
        "color_schemes": [
            {"id": "gray-red", "label": "Gray + Red", "primary": "#5f5f5f", "accent": "#e87b7b", "bg": "#ffffff"},
            {"id": "slate",    "label": "Slate",      "primary": "#4b5563", "accent": "#94a3b8", "bg": "#ffffff"},
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
        "id": "modern_sidebar",
        "name": "Modern Sidebar",
        "category": "modern",
        "ats_score": 86,
        "best_for": ["marketing", "product", "design", "creative", "startup"],
        "premium": False,
        "layout": "sidebar",
        "description": "Contemporary sidebar layout with visual hierarchy and timeline sections.",
        "fonts": ["Segoe UI", "Inter", "Roboto", "Lato", "Helvetica"],
        "color_schemes": [
            {"id": "sky",      "label": "Sky Blue",   "primary": "#5f86bb", "accent": "#9ab0ce", "bg": "#eef1f5"},
            {"id": "slate",    "label": "Slate Blue", "primary": "#556b8a", "accent": "#93a5be", "bg": "#edf1f5"},
            {"id": "charcoal", "label": "Charcoal",   "primary": "#4f5561", "accent": "#8f9aab", "bg": "#f2f4f7"},
        ],
    },
    {
        "id": "modern_two_column",
        "name": "modrens",
        "category": "modern",
        "ats_score": 89,
        "best_for": ["sales", "operations", "customer-service", "retail", "startup"],
        "premium": False,
        "layout": "two_column",
        "description": "Balanced two-column layout with clean section dividers and strong readability.",
        "fonts": ["Arial", "Helvetica", "Calibri", "Segoe UI", "Verdana"],
        "color_schemes": [
            {"id": "teal",  "label": "Teal",  "primary": "#0d6f84", "accent": "#d4e2e8", "bg": "#f3f3f3"},
            {"id": "slate", "label": "Slate", "primary": "#425466", "accent": "#d7dee6", "bg": "#f6f7f9"},
        ],
    },
    {
        "id": "modren_3",
        "name": "modren 3",
        "category": "modern",
        "ats_score": 87,
        "best_for": ["retail", "sales", "customer-service", "operations"],
        "premium": False,
        "layout": "sidebar",
        "description": "Light blue sidebar with portrait header and split-tone name styling.",
        "fonts": ["Georgia", "Times New Roman", "Garamond", "Palatino"],
        "color_schemes": [
            {"id": "sky", "label": "Sky Blue", "primary": "#6ba3c7", "accent": "#a9c9e2", "bg": "#ffffff"},
        ],
    },
    {
        "id": "modren_4",
        "name": "modren 4",
        "category": "modern",
        "ats_score": 85,
        "best_for": ["creative", "marketing", "design", "startup"],
        "premium": False,
        "layout": "two_column",
        "description": "Decorative side accent with centered photo and airy two-column body.",
        "fonts": ["Segoe UI", "Helvetica", "Arial", "Calibri"],
        "color_schemes": [
            {"id": "blue", "label": "Blue", "primary": "#2563eb", "accent": "#e5e7eb", "bg": "#ffffff"},
        ],
    },
    {
        "id": "modren_5",
        "name": "modren 5",
        "category": "classic",
        "ats_score": 92,
        "best_for": ["corporate", "finance", "consulting", "ats-optimized"],
        "premium": False,
        "layout": "single_column",
        "description": "Serif resume with centered header and ruled section introductions.",
        "fonts": ["Times New Roman", "Georgia", "Garamond", "Palatino"],
        "color_schemes": [
            {"id": "navy", "label": "Navy", "primary": "#1e3a5f", "accent": "#c5c5c5", "bg": "#ffffff"},
        ],
    },
    {
        "id": "modren_6",
        "name": "modren 6",
        "category": "modern",
        "ats_score": 86,
        "best_for": ["corporate", "operations", "tech", "startup"],
        "premium": False,
        "layout": "two_column",
        "description": "Bold top band with sidebar column and vertical accent rail.",
        "fonts": ["Arial", "Helvetica", "Calibri", "Segoe UI"],
        "color_schemes": [
            {"id": "navy", "label": "Navy", "primary": "#0f2d52", "accent": "#94a3b8", "bg": "#ffffff"},
        ],
    },
    {
        "id": "modren_7",
        "name": "modren 7",
        "category": "classic",
        "ats_score": 91,
        "best_for": ["legal", "consulting", "academic", "corporate"],
        "premium": False,
        "layout": "two_column",
        "description": "Asymmetric layout with a narrow label column for headings and dates.",
        "fonts": ["Georgia", "Times New Roman", "Garamond", "Palatino"],
        "color_schemes": [
            {"id": "blue", "label": "Blue", "primary": "#1e4d7b", "accent": "#d1d5db", "bg": "#ffffff"},
        ],
    },
    {
        "id": "modren_8",
        "name": "modren 8",
        "category": "classic",
        "ats_score": 90,
        "best_for": ["corporate", "operations", "retail", "government"],
        "premium": False,
        "layout": "two_column",
        "description": "Centered serif header with split skills grid and timeline-friendly rows.",
        "fonts": ["Times New Roman", "Georgia", "Garamond", "Palatino"],
        "color_schemes": [
            {"id": "navy", "label": "Navy", "primary": "#1a365d", "accent": "#cbd5e1", "bg": "#ffffff"},
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
        "id": "elegant_traditional",
        "name": "Elegant Traditional",
        "category": "classic",
        "ats_score": 94,
        "best_for": ["legal", "consulting", "corporate", "education", "government"],
        "premium": False,
        "layout": "single_column",
        "description": "Traditional serif resume with formal headings and dotted leader lines.",
        "fonts": ["Times New Roman", "Georgia", "Garamond", "Palatino"],
        "color_schemes": [
            {"id": "mono",   "label": "Monochrome", "primary": "#222222", "accent": "#c6c6c6", "bg": "#ffffff"},
            {"id": "slate",  "label": "Slate",      "primary": "#2f3a47", "accent": "#a8b0ba", "bg": "#ffffff"},
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
