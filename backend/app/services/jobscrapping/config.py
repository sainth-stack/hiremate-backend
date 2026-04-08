"""
Load and validate portals YAML (+ optional legacy JSON), merge public_urls.

Convention: total_filtered in API responses matches filtered_out (title_filter drops).
Later: optional config hot reload without process restart (not implemented).
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from backend.app.core.config import settings

# Defaults when `settings` block is missing (see plan.md)
DEFAULT_SETTINGS: dict[str, Any] = {
    "concurrency": 8,
    "retries": 3,
    "company_timeout_sec": 45,
    "job_detail_timeout_sec": 12,
    "http_timeout_sec": 30,
    "circuit_breaker_max_consecutive_failures": 10,
    "listing_max_scroll_rounds": 15,
    "listing_max_load_more_rounds": 15,
    "listing_max_pages": 20,
    "deep_enrich_enabled": False,
    "deep_enrich_max_jobs": 20,
}


class PortalsConfigError(ValueError):
    """Invalid portals / merged config."""


def _find_default_config_path() -> Path:
    """
    Resolution order:
    1. ``PORTALS_CONFIG`` env (``.yml`` / ``.yaml`` / ``.json``).
    2. ``company.json`` next to this package (bundled career + public feeds).
    3. ``company_source.yml`` next to this package (optional YAML instead of JSON).
    4. Walk parents for ``data/portals.yml`` or ``data/portals.example.yml``.
    """
    if settings.portals_config and settings.portals_config.strip():
        p = Path(settings.portals_config).expanduser().resolve()
        if not p.is_file():
            raise PortalsConfigError(f"PORTALS_CONFIG path not found: {p}")
        return p
    here = Path(__file__).resolve().parent
    bundled_json = here / "company.json"
    if bundled_json.is_file():
        return bundled_json
    bundled_yaml = here / "company_source.yml"
    if bundled_yaml.is_file():
        return bundled_yaml
    for parent in [here] + list(here.parents):
        for name in ("portals.yml", "portals.example.yml"):
            candidate = parent / "data" / name
            if candidate.is_file():
                return candidate
    raise PortalsConfigError(
        "No portals config found. Add app/services/jobscrapping/company.json, "
        "set PORTALS_CONFIG, or add data/portals.yml under the repo."
    )


def _find_default_portals_path() -> Path:
    """Alias for :func:`_find_default_config_path` (YAML-centric name)."""
    return _find_default_config_path()


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise PortalsConfigError(f"Top-level YAML must be a mapping: {path}")
    return data


def _load_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise PortalsConfigError(f"Top-level JSON must be an object: {path}")
    return data


def _normalize_config_structure(data: dict[str, Any]) -> dict[str, Any]:
    """
    Allow ``company.json`` to group career sources under ``career_pages``:
    ``{ "career_pages": { "tracked_companies": [...] }, "public_urls": [...] }``
    flattens to the shape expected by validation and scrapers.
    """
    cp = data.get("career_pages")
    if isinstance(cp, dict):
        if "tracked_companies" in cp:
            data["tracked_companies"] = cp["tracked_companies"]
        for key in ("title_filter", "search_queries", "settings"):
            if key in cp and key not in data:
                data[key] = cp[key]
    return data


def _load_config_file(path: Path) -> dict[str, Any]:
    suf = path.suffix.lower()
    if suf in (".json",):
        data = _load_json(path)
    elif suf in (".yml", ".yaml"):
        data = _load_yaml(path)
    else:
        # Default: try YAML (e.g. extensionless path)
        data = _load_yaml(path)
    return _normalize_config_structure(data)


def _load_legacy_json() -> dict[str, Any]:
    if not settings.job_sources_config or not settings.job_sources_config.strip():
        return {}
    p = Path(settings.job_sources_config).expanduser().resolve()
    if not p.is_file():
        raise PortalsConfigError(f"JOB_SOURCES_CONFIG path not found: {p}")
    raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise PortalsConfigError("Legacy job sources JSON must be an object at root.")
    return data


def _merge_public_urls(yaml_data: dict[str, Any], legacy: dict[str, Any]) -> None:
    y_urls = yaml_data.get("public_urls")
    if y_urls is None:
        y_urls = []
        yaml_data["public_urls"] = y_urls
    if not isinstance(y_urls, list):
        raise PortalsConfigError("public_urls in YAML must be a list.")
    seen = {_public_url_key(e) for e in y_urls if isinstance(e, dict)}
    for e in legacy.get("public_urls") or []:
        if not isinstance(e, dict):
            raise PortalsConfigError("legacy public_urls entries must be objects.")
        k = _public_url_key(e)
        if k not in seen:
            y_urls.append(deepcopy(e))
            seen.add(k)


def _public_url_key(entry: dict[str, Any]) -> tuple[str, str]:
    url = (entry.get("url") or "").strip()
    name = (entry.get("name") or "").strip()
    return (url, name)


def merge_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Return merged settings: YAML `settings` overlaid on DEFAULT_SETTINGS."""
    out = deepcopy(DEFAULT_SETTINGS)
    block = data.get("settings")
    if block is None:
        return out
    if not isinstance(block, dict):
        raise PortalsConfigError("`settings` must be a mapping.")
    for k, v in block.items():
        if k in out and v is not None:
            out[k] = v
        elif k not in out:
            out[k] = v
    return out


def validate_merged_config(data: dict[str, Any]) -> None:
    """Fail fast before any ingestion run."""
    tf = data.get("title_filter")
    if tf is None or not isinstance(tf, dict):
        raise PortalsConfigError("Missing or invalid `title_filter` section.")
    pos = tf.get("positive")
    neg = tf.get("negative")
    if not isinstance(pos, list) or not all(isinstance(x, str) for x in pos):
        raise PortalsConfigError("`title_filter.positive` must be a list of strings.")
    match_all = bool(tf.get("match_all", False))
    if not pos and not match_all:
        raise PortalsConfigError(
            "`title_filter.positive` must be non-empty unless `title_filter.match_all` is true."
        )
    if neg is None:
        tf["negative"] = []
    elif not isinstance(neg, list) or not all(isinstance(x, str) for x in neg):
        raise PortalsConfigError("`title_filter.negative` must be a list of strings.")
    sb = tf.get("seniority_boost")
    if sb is None:
        tf["seniority_boost"] = []
    elif not isinstance(sb, list) or not all(isinstance(x, str) for x in sb):
        raise PortalsConfigError("`title_filter.seniority_boost` must be a list of strings.")

    sq = data.get("search_queries")
    if sq is not None:
        if not isinstance(sq, list):
            raise PortalsConfigError("`search_queries` must be a list.")
        for i, item in enumerate(sq):
            if not isinstance(item, dict):
                raise PortalsConfigError(f"search_queries[{i}] must be a mapping.")

    companies = data.get("tracked_companies")
    if companies is None:
        data["tracked_companies"] = []
        companies = data["tracked_companies"]
    if not isinstance(companies, list):
        raise PortalsConfigError("`tracked_companies` must be a list.")
    for i, row in enumerate(companies):
        if not isinstance(row, dict):
            raise PortalsConfigError(f"tracked_companies[{i}] must be a mapping.")
        name = row.get("name")
        if not name or not str(name).strip():
            raise PortalsConfigError(f"tracked_companies[{i}] needs a non-empty `name`.")
        enabled = row.get("enabled", True)
        if enabled is False:
            continue
        cu = row.get("careers_url")
        if not cu or not str(cu).strip():
            raise PortalsConfigError(
                f"tracked_companies entry {name!r}: `careers_url` is required for "
                "enabled companies (career-pages ingest uses Playwright on this URL; "
                "scan_method is informational only)."
            )

    pub = data.get("public_urls") or []
    if not isinstance(pub, list):
        raise PortalsConfigError("`public_urls` must be a list.")
    for i, row in enumerate(pub):
        if not isinstance(row, dict):
            raise PortalsConfigError(f"public_urls[{i}] must be a mapping.")
        url = row.get("url")
        if not url or not str(url).strip():
            raise PortalsConfigError(f"public_urls[{i}] needs a non-empty `url`.")


def load_merged_config() -> dict[str, Any]:
    """
    Load config from PORTALS_CONFIG, bundled ``company.json`` (or ``company_source.yml``), or YAML under ``data/``;
    merge legacy ``JOB_SOURCES_CONFIG`` ``public_urls``; merge settings defaults; validate.
    """
    path = _find_default_config_path()
    data = _load_config_file(path)
    legacy = _load_legacy_json()
    _merge_public_urls(data, legacy)
    data["_config_path"] = str(path)
    data["settings"] = merge_settings(data)
    validate_merged_config(data)
    return data
