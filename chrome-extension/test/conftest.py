"""Pytest configuration for field scraper tests."""
import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def playwright():
    """Provide Playwright instance for the test session."""
    with sync_playwright() as p:
        yield p
