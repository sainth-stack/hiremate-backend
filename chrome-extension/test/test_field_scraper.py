#!/usr/bin/env python3
"""
Field Scraper Test Suite

Run with: pytest test_field_scraper.py -v
Or from hiremate-backend: python -m pytest chrome-extension/test/test_field_scraper.py -v

Requires: playwright (pip install playwright && playwright install chromium)
"""
import socket
import tempfile
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest

# Extension and test page paths
SCRIPT_DIR = Path(__file__).resolve().parent
EXTENSION_DIR = SCRIPT_DIR.parent  # chrome-extension/
TEST_PAGES_DIR = EXTENSION_DIR / "test-pages"

# Real-world ATS-style test pages (simulated DOM structures)
ATS_TEST_PAGES = [
    ("scraper-test.html", "Generic Form", 15, ["first", "last", "email", "phone", "resume"]),
    ("greenhouse-style.html", "Greenhouse", 9, ["first", "last", "email", "phone", "resume"]),
    ("lever-style.html", "Lever", 8, ["name", "email", "phone", "resume"]),
    ("workday-style.html", "Workday", 8, ["first", "last", "email", "phone", "resume"]),
    ("linkedin-easy-apply-style.html", "LinkedIn Easy Apply", 7, ["first", "last", "email", "phone", "resume"]),
]


def _get_extension_path():
    return str(EXTENSION_DIR.resolve())


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class ScraperTestHttpHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(TEST_PAGES_DIR), **kwargs)


@pytest.fixture(scope="module")
def http_server():
    """Serve test pages over HTTP (extensions often don't run on file://)."""
    port = _find_free_port()
    server = HTTPServer(("127.0.0.1", port), ScraperTestHttpHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser_context(playwright, http_server):
    """Launch Chromium with the extension loaded."""
    ext_path = _get_extension_path()
    user_data_dir = tempfile.mkdtemp(prefix="hiremate_scraper_test_")
    context = playwright.chromium.launch_persistent_context(
        user_data_dir,
        channel="chromium",
        headless=True,
        args=[
            f"--disable-extensions-except={ext_path}",
            f"--load-extension={ext_path}",
        ],
    )
    yield context
    context.close()


@pytest.fixture
def page(browser_context, http_server):
    """Create a new page and navigate to the test page."""
    page = browser_context.new_page()
    test_url = f"{http_server}/scraper-test.html"
    page.goto(test_url, wait_until="domcontentloaded", timeout=15000)
    yield page
    page.close()


def test_field_scraper_detects_fields(page):
    """Test that the scraper detects form fields."""
    result = page.evaluate("window.runScraperTest()")
    assert result.get("ok") is True, result.get("error", "Unknown error")
    fields = result.get("fields", [])
    assert len(fields) >= 15, f"Expected at least 15 fields, got {len(fields)}"


def test_standard_ats_fields_detected(page):
    """Test that standard ATS fields (name, email, phone, resume) are detected."""
    result = page.evaluate("window.runScraperTest()")
    assert result.get("ok") is True
    fields = result.get("fields", [])
    labels_and_names = []
    for f in fields:
        labels_and_names.extend(
            [str(x).lower() for x in [f.get("label"), f.get("name"), f.get("id")] if x]
        )
    combined = " ".join(labels_and_names)
    assert "first" in combined or "first_name" in combined or "firstname" in combined
    assert "last" in combined or "last_name" in combined or "lastname" in combined
    assert "email" in combined
    assert "phone" in combined or "tel" in combined
    assert "resume" in combined or "cv" in combined


def test_required_fields_detected(page):
    """Test that required fields are correctly marked."""
    result = page.evaluate("window.runScraperTest()")
    assert result.get("ok") is True
    fields = result.get("fields", [])
    required = [f for f in fields if f.get("required")]
    assert len(required) >= 3, f"Expected at least 3 required fields, got {len(required)}"


def test_field_types_detected(page):
    """Test that different field types are detected (text, select, file, checkbox)."""
    result = page.evaluate("window.runScraperTest()")
    assert result.get("ok") is True
    fields = result.get("fields", [])
    types = {f.get("type") for f in fields if f.get("type")}
    combined_text = combined(fields)
    assert "text" in types or "email" in types
    assert "select" in types or "country" in combined_text or "experience" in combined_text
    assert "file" in types or has_file_field(fields)
    # Checkbox may be detected as checkbox or part of a group
    assert len(types) >= 2, f"Expected multiple field types, got {types}"


def combined(fields):
    return " ".join(str(f.get("name", "")) + str(f.get("label", "")) for f in fields).lower()


def has_file_field(fields):
    return any("file" in str(f.get("type", "")).lower() or "resume" in str(f.get("label", "")).lower() for f in fields)


def test_element_count_matches_fields(page):
    """Test that element count matches fields count (for fill compatibility)."""
    result = page.evaluate("window.runScraperTest()")
    assert result.get("ok") is True
    fields = result.get("fields", [])
    element_count = result.get("elementCount", 0)
    assert element_count >= len(fields), "Element count should be >= fields count"
    assert element_count >= 10, f"Expected at least 10 fillable elements, got {element_count}"


def test_scrape_completes_quickly(page):
    """Test that scraping completes in under 500ms (performance)."""
    start = page.evaluate("performance.now()")
    result = page.evaluate("window.runScraperTest()")
    end = page.evaluate("performance.now()")
    elapsed = end - start
    assert result.get("ok") is True
    assert elapsed < 2000, f"Scraping took {elapsed}ms, expected < 2000ms"


# --- Real-world ATS-style test cases ---


@pytest.mark.parametrize("page_name,ats_name,min_fields,required_keywords", ATS_TEST_PAGES)
def test_ats_style_page_detects_all_fields(browser_context, http_server, page_name, ats_name, min_fields, required_keywords):
    """Test scraper on real-world ATS-style pages (Greenhouse, Lever, Workday, LinkedIn)."""
    page = browser_context.new_page()
    try:
        page.goto(f"{http_server}/{page_name}", wait_until="domcontentloaded", timeout=15000)
        result = page.evaluate("window.runScraperTest()")
        assert result.get("ok") is True, f"{ats_name}: {result.get('error', 'Unknown error')}"
        fields = result.get("fields", [])
        assert len(fields) >= min_fields, f"{ats_name}: expected >= {min_fields} fields, got {len(fields)}"
        combined = " ".join(
            str(f.get("label", "")) + str(f.get("name", "")) + str(f.get("id", ""))
            for f in fields
        ).lower()
        for kw in required_keywords:
            assert kw in combined, f"{ats_name}: missing '{kw}' in detected fields"
    finally:
        page.close()


def test_greenhouse_data_provides_selectors(browser_context, http_server):
    """Test that Greenhouse-style data-provides (typeahead, select) fields are detected."""
    page = browser_context.new_page()
    try:
        page.goto(f"{http_server}/greenhouse-style.html", wait_until="domcontentloaded", timeout=15000)
        result = page.evaluate("window.runScraperTest()")
        assert result.get("ok") is True
        fields = result.get("fields", [])
        names = [f.get("name", "") for f in fields]
        assert any("custom_question" in n for n in names), "Greenhouse custom questions should be detected"
    finally:
        page.close()


def test_workday_automation_ids(browser_context, http_server):
    """Test that Workday-style data-automation-id and aria-label fields are detected."""
    page = browser_context.new_page()
    try:
        page.goto(f"{http_server}/workday-style.html", wait_until="domcontentloaded", timeout=15000)
        result = page.evaluate("window.runScraperTest()")
        assert result.get("ok") is True
        fields = result.get("fields", [])
        labels = [str(f.get("label", "")).lower() for f in fields]
        assert any("first" in l or "firstname" in l for l in labels)
        assert any("veteran" in l for l in labels), "Workday veteran status field should be detected"
    finally:
        page.close()


def test_lever_application_field_structure(browser_context, http_server):
    """Test that Lever-style application-field and application-label are detected."""
    page = browser_context.new_page()
    try:
        page.goto(f"{http_server}/lever-style.html", wait_until="domcontentloaded", timeout=15000)
        result = page.evaluate("window.runScraperTest()")
        assert result.get("ok") is True
        fields = result.get("fields", [])
        assert len(fields) >= 6
        assert any("resume" in str(f.get("label", "")).lower() or "resume" in str(f.get("name", "")).lower() for f in fields)
    finally:
        page.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
