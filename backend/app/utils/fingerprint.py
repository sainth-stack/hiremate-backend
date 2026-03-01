"""Field fingerprint computation - must match JS client exactly (alphabetical key order)."""
import hashlib
import json
import re


def normalize_label(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compute_field_fingerprint(field: dict) -> str:
    """
    Compute SHA-256 fingerprint for form field.
    CRITICAL: Key order must be alphabetical to match Python's sort_keys=True.
    Produces: {"label":..., "options":..., "type":...}
    """
    label = normalize_label(
        field.get("label") or field.get("placeholder") or field.get("name") or ""
    )
    ftype = (field.get("type") or "").lower().strip()
    options_raw = field.get("options") or []
    options = sorted([normalize_label(o) for o in options_raw])
    payload = json.dumps(
        {"label": label, "options": options, "type": ftype},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
