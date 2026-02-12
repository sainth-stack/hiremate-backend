"""Field normalization for form field mapping - maps raw labels to canonical keys."""
import re
from typing import Optional


class FieldNormalizationService:
    """
    Normalizes raw form fields into canonical keys using regex and heuristics.
    This reduces the load on the LLM and improves accuracy for common fields.
    """

    PATTERNS = {
        "first_name": [r"first\s*name", r"fname", r"given\s*name"],
        "last_name": [r"last\s*name", r"lname", r"surname", r"family\s*name"],
        "full_name": [r"^name$", r"full\s*name", r"candidate\s*name"],
        "email": [r"email", r"e-mail"],
        "phone": [r"phone", r"mobile", r"cell", r"contact\s*number"],
        "linkedin": [r"linkedin"],
        "github": [r"github"],
        "portfolio": [r"portfolio", r"website", r"personal\s*site"],
        "resume": [r"resume", r"cv", r"curriculum\s*vitae"],
        "cover_letter": [r"cover\s*letter"],
    }

    @classmethod
    def normalize(cls, label: str, name: str = "", field_id: str = "") -> Optional[str]:
        """
        Attempt to match a field to a canonical key based on label, name, or id.
        Returns the canonical key if found with high confidence, else None.
        """
        text_signals = [label, name, field_id]
        for key, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                for text in text_signals:
                    if text and re.search(pattern, text, re.IGNORECASE):
                        return key
        return None
