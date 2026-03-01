"""
Parity tests: ensure compute_field_fingerprint() produces the same hash
as the JavaScript implementation. Expected values from generate_expected_fps.js.
"""
import pytest
from backend.app.utils.fingerprint import compute_field_fingerprint

PARITY_CASES = [
    ({"label": "Email Address", "type": "email", "options": []}, "63f7d866455be7051296c8481faf4f52"),
    ({"label": "First Name", "type": "text", "options": []}, "45f4978ac1745bb1bce038713de057bc"),
    ({"label": "Phone Number", "type": "tel", "options": []}, "1145787cf3ecf62a67931f1decd07d5e"),
    (
        {"label": "Current Location", "type": "select", "options": ["United States", "Canada", "United Kingdom"]},
        "daf5f70ca031659f3e64d79137d37d54",
    ),
    ({"label": "", "type": "text", "options": []}, "52b667b6a7a77b51c85dec1555777c81"),
    ({"label": "Are you authorized to work?", "type": "radio", "options": ["Yes", "No"]}, "4fa890e6879685bf12ac16f22e019fd0"),
]


def test_fingerprint_not_empty():
    """Smoke: fingerprints are non-empty 32-char hex strings."""
    for field, _ in PARITY_CASES:
        fp = compute_field_fingerprint(field)
        assert len(fp) == 32, f"Expected 32-char hex, got {len(fp)} for {field}"
        assert all(c in "0123456789abcdef" for c in fp), f"Non-hex chars: {fp}"


def test_fingerprint_deterministic():
    """Same input always produces same output."""
    for field, _ in PARITY_CASES:
        assert compute_field_fingerprint(field) == compute_field_fingerprint(field)


def test_fingerprint_sensitive_to_label():
    """Different labels produce different fingerprints."""
    fp1 = compute_field_fingerprint({"label": "Email", "type": "email", "options": []})
    fp2 = compute_field_fingerprint({"label": "Email Address", "type": "email", "options": []})
    assert fp1 != fp2


def test_fingerprint_insensitive_to_label_case():
    """Label normalization: case should not matter."""
    fp1 = compute_field_fingerprint({"label": "Email Address", "type": "email", "options": []})
    fp2 = compute_field_fingerprint({"label": "EMAIL ADDRESS", "type": "email", "options": []})
    assert fp1 == fp2


def test_fingerprint_options_order_insensitive():
    """Options are sorted, so order should not affect fingerprint."""
    fp1 = compute_field_fingerprint({"label": "Country", "type": "select", "options": ["USA", "Canada"]})
    fp2 = compute_field_fingerprint({"label": "Country", "type": "select", "options": ["Canada", "USA"]})
    assert fp1 == fp2


def test_fingerprint_matches_javascript():
    """
    CRITICAL: Python output must exactly match JavaScript SubtleCrypto output.
    Run node chrome-extension/tests/generate_expected_fps.js to regenerate expected values.
    """
    for field, expected in PARITY_CASES:
        fp = compute_field_fingerprint(field)
        assert fp == expected, (
            f"FINGERPRINT MISMATCH — Python vs JS divergence!\n"
            f"Field: {field}\n"
            f"Python: {fp}\n"
            f"JS:     {expected}\n"
        )
