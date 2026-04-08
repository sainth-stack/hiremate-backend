"""
Title relevance filter from portals YAML.

Rule: at least one positive keyword matches the title (case-insensitive substring)
and no negative keyword matches.

`seniority_boost` lists terms that signal relevance for ranking later; they do not
affect pass/fail for MVP.

Risk: strict keyword lists drop good roles when wording differs (e.g. "Software Engineer II"
vs "Backend Developer"). Synonyms / fuzzy matching are planned later (not MVP).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TitleFilterConfig:
    positive: list[str]
    negative: list[str]
    seniority_boost: list[str]
    # When True, any non-empty title passes unless it hits a negative keyword (positive list ignored).
    match_all: bool = False


def parse_title_filter(data: dict[str, Any]) -> TitleFilterConfig:
    tf = data.get("title_filter") or {}
    return TitleFilterConfig(
        positive=[str(x).lower() for x in (tf.get("positive") or [])],
        negative=[str(x).lower() for x in (tf.get("negative") or [])],
        seniority_boost=[str(x).lower() for x in (tf.get("seniority_boost") or [])],
        match_all=bool(tf.get("match_all", False)),
    )


def title_passes_filter(title: str, cfg: TitleFilterConfig) -> bool:
    if not title or not title.strip():
        return False
    t = title.lower()
    if cfg.match_all:
        if any(n in t for n in cfg.negative):
            return False
        return True
    if not cfg.positive:
        return False
    if not any(p in t for p in cfg.positive):
        return False
    if any(n in t for n in cfg.negative):
        return False
    return True


def seniority_boost_hits(title: str, cfg: TitleFilterConfig) -> list[str]:
    """Terms from seniority_boost present in title (for downstream ranking)."""
    if not title:
        return []
    t = title.lower()
    return [s for s in cfg.seniority_boost if s in t]
