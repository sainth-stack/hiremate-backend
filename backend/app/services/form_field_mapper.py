"""Map scraped form fields to profile values using LLM + heuristics."""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Any

from openai import OpenAI

from backend.app.core.config import settings
from backend.app.services.field_normalization import FieldNormalizationService

logger = logging.getLogger(__name__)
_OPENAI_CLIENT: OpenAI | None = None
_CACHE_TTL_SECONDS = 300
_CACHE_MAX_ENTRIES = 64
_MAP_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

ALIAS_MAP: dict[str, list[str]] = {
    "name": ["name", "full name", "candidate name"],
    "firstName": ["first name", "given name", "fname"],
    "lastName": ["last name", "family name", "surname", "lname"],
    "email": ["email", "e-mail"],
    "phone": ["phone", "mobile", "cell", "telephone", "contact number"],
    "linkedin": ["linkedin", "linkedin url", "linkedin profile"],
    "github": ["github", "github url", "github profile"],
    "portfolio": ["portfolio", "portfolio url", "website", "personal site"],
    "location": ["location", "current location", "city"],
    "company": ["current company", "company"],
    "title": ["title", "job title", "position"],
    "skills": ["skills", "technical skills", "technologies"],
    "experience": ["experience", "work experience", "employment", "summary"],
    "education": ["education", "degree", "university", "college", "school"],
    "coverLetter": ["cover letter"],
    "workAuthorization": ["authorized to work", "work authorization"],
    "requiresSponsorship": ["sponsorship", "visa sponsorship"],
    "salaryExpectation": ["salary expectation", "salary", "compensation"],
    "startDate": ["start date", "when can you start", "notice period"],
    "dateOfBirth": ["date of birth", "dob", "birth date", "birthday"],
    "gender": ["gender", "sex"],
}

MAP_PROMPT = """You are an expert job application autofill assistant with natural language generation capabilities.

Task:
- Map each incoming form field to the best value from candidate data.
- Candidate data includes profile fields, saved custom answers, and resume text.

**FIELD-SPECIFIC RULES:**

1. **NUMERIC FIELDS (years of experience, age, etc.):**
   - Extract ONLY the number from experience data
   - "Total Experience (in years)" → Return just the number like "3" NOT "3+ years" or text
   - If experience says "3+ years" or "3 years", return just "3"
   - If it says "5-7 years", return "6" (midpoint)

2. **DROPDOWN/SELECT FIELDS (Gender, Salutation, Yes/No, etc.):**
   - Return EXACT option text as it appears in the dropdown
   - Gender field with options ["Male", "Female", "Other"] → Return exactly "Male" not "male" or "M"
   - Salutation with options ["Mr", "Ms", "Mrs", "Dr"] → Return exactly as shown (check capitalization)
   - For Yes/No dropdowns: Return exactly "Yes" or "No" (capital Y/N)

3. **TEXT FIELDS (textarea, large text, cover letters, descriptions, "why" questions):**
   - DO NOT just copy existing text
   - GENERATE contextual, professional responses based on candidate's profile, experience, and skills
   - For cover letters: Write 2-3 paragraphs highlighting relevant experience and fit
   - For "why do you want to work here" type questions: Generate thoughtful 2-4 sentence responses
   - For compensation/salary questions: Use profile salary data or say "Open to discussion based on market rate and role scope"
   - For descriptions: Summarize relevant experience from resume in 2-3 sentences

4. **COMPANY-SPECIFIC QUESTIONS (current/previous employee, referrals, relationships):**
   - "Are you currently a [company] employee?": Answer "No" UNLESS candidate's current company matches
   - "Have you previously worked at [company]?": Answer "No" UNLESS resume mentions that company
   - "Are you related to anyone at [company]?": Answer "No" or "None"
   - "Do you know anyone at [company]?": If no referral info, say "No" or leave blank

5. **SIMPLE FIELDS (name, email, phone, dates):**
   - Use exact profile values
   - For date fields (DOB): Format as YYYY-MM-DD or as requested by field type

6. **GENERAL:**
   - Never hallucinate hard facts (company names, degree names, years) that are absent from data
   - For optional fields with weak evidence, return null
   - Make all responses natural, professional, and tailored to the field label/context

Output JSON format (use "index" as the key):
{{
  "mappings": {{
    "0": {{
      "value": "string or null",
      "confidence": 0.0,
      "reason": "short explanation"
    }},
    "1": {{ ... }},
    ...
  }}
}}

IMPORTANT: Use the field's "index" value as the mapping key (e.g., "0", "1", "2"), NOT the field name or id.

Confidence rules:
- 0.95-1.0 for exact profile/custom-answer matches
- 0.8-0.94 for strong inferred value from resume/profile context or generated text from solid data
- 0.6-0.79 for generated but reasonable answer or intelligent defaults
- <=0.5 when ambiguous or insufficient context

Candidate profile JSON:
{profile_json}

Saved custom answers JSON:
{custom_answers_json}

Resume text (possibly partial):
{resume_text}
"""


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())).strip()


def _field_key(field: dict[str, Any]) -> str:
    if field.get("id"):
        return str(field["id"])
    return str(field.get("index", ""))


def _combined_field_text(field: dict[str, Any]) -> str:
    return _norm(" ".join(
        str(field.get(k, "") or "")
        for k in ("label", "name", "id", "placeholder", "type", "normalized_key")
    ))


def _get_openai_client() -> OpenAI:
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        _OPENAI_CLIENT = OpenAI(api_key=settings.openai_api_key)
    return _OPENAI_CLIENT


def _build_cache_key(
    fields: list[dict[str, Any]],
    profile: dict[str, Any],
    custom_answers: dict[str, str],
    resume_text: str,
) -> str:
    payload = {
        "fields": fields,
        "profile": profile,
        "custom_answers": custom_answers,
        "resume_text": resume_text,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _cache_get(cache_key: str) -> dict[str, Any] | None:
    cached = _MAP_CACHE.get(cache_key)
    if not cached:
        return None
    cached_at, mappings = cached
    if (time.time() - cached_at) > _CACHE_TTL_SECONDS:
        _MAP_CACHE.pop(cache_key, None)
        return None
    return mappings


def _cache_put(cache_key: str, mappings: dict[str, Any]) -> None:
    if len(_MAP_CACHE) >= _CACHE_MAX_ENTRIES:
        oldest_key = min(_MAP_CACHE.items(), key=lambda item: item[1][0])[0]
        _MAP_CACHE.pop(oldest_key, None)
    _MAP_CACHE[cache_key] = (time.time(), mappings)


def _format_date(date_str: str, field_type: str = "") -> str | None:
    """Format date string to appropriate format based on field type."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            if field_type == "date":
                return dt.strftime('%Y-%m-%d')
            elif "mm" in field_type.lower() or "dd" in field_type.lower():
                return dt.strftime('%m/%d/%Y')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            pass
    for pattern, fmt in [
        (r'^(\d{2})[/-](\d{2})[/-](\d{4})$', '%d/%m/%Y'),
        (r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', '%d/%m/%Y'),
    ]:
        match = re.match(pattern, date_str)
        if match:
            try:
                dt = datetime.strptime(date_str.replace('-', '/'), fmt)
                if field_type == "date":
                    return dt.strftime('%Y-%m-%d')
                return dt.strftime('%d/%m/%Y')
            except ValueError:
                continue
    return date_str


def _fallback_map(
    fields: list[dict[str, Any]],
    profile: dict[str, Any],
    custom_answers: dict[str, str],
) -> dict[str, Any]:
    mappings: dict[str, Any] = {}
    normalized_custom = {_norm(k): v for k, v in (custom_answers or {}).items() if v}

    for field in fields:
        key = _field_key(field)
        field_text = _combined_field_text(field)
        value: Any = None
        reason = "No reliable local match"
        confidence = 0.35

        if str(field.get("type", "")).lower() == "file" or "resume" in field_text or "cv" in field_text:
            mappings[key] = {
                "value": "RESUME_FILE",
                "confidence": 0.99,
                "reason": "Resume file field mapped to auto-upload token",
            }
            continue

        for question, answer in normalized_custom.items():
            if not question:
                continue
            if question in field_text or field_text in question:
                value = answer
                reason = "Matched saved custom answer"
                confidence = 0.95
                break

        if value is None:
            for profile_key, aliases in ALIAS_MAP.items():
                profile_val = profile.get(profile_key)
                if not profile_val:
                    continue
                if any(_norm(alias) in field_text for alias in aliases):
                    if profile_key == "dateOfBirth" or "dob" in field_text or "birth" in field_text:
                        formatted_date = _format_date(str(profile_val), field.get("type", ""))
                        if formatted_date:
                            value = formatted_date
                            reason = f"Matched and formatted profile.{profile_key}"
                            confidence = 0.92
                            break
                    value = str(profile_val)
                    reason = f"Matched profile.{profile_key}"
                    confidence = 0.9
                    break

        mappings[key] = {"value": value, "confidence": confidence, "reason": reason}

    return mappings


def _requires_llm(field: dict[str, Any], fallback_value: dict[str, Any]) -> bool:
    field_type = str(field.get("type", "")).lower()
    field_text = _combined_field_text(field)
    confidence = float(fallback_value.get("confidence", 0.0) or 0.0)
    value = fallback_value.get("value")
    if field_type in {"textarea"}:
        return True
    if any(keyword in field_text for keyword in ("cover letter", "why ", "describe", "summary", "explain")):
        return True
    if value not in (None, "") and confidence >= 0.9:
        return False
    if field.get("required") and confidence < 0.85:
        return True
    return confidence < 0.75


def _clean_field_value(field: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    value = mapping.get("value")
    if value is None or value == "":
        return mapping
    field_label = str(field.get("label", "")).lower()
    field_type = str(field.get("type", "")).lower()
    if "experience" in field_label and ("year" in field_label or "years" in field_label):
        if isinstance(value, str):
            match = re.search(r'\d+', value)
            if match:
                return {
                    "value": match.group(0),
                    "confidence": mapping.get("confidence", 0.9),
                    "reason": f"Extracted number from: {value}"
                }
    if field_type in ("select", "combobox") and field.get("options"):
        options = field["options"]
        value_str = str(value).strip()
        if value_str in options:
            return mapping
        for option in options:
            if option.lower() == value_str.lower():
                return {
                    "value": option,
                    "confidence": mapping.get("confidence", 0.95),
                    "reason": f"Matched to dropdown option: {option}"
                }
        for option in options:
            if value_str.lower() in option.lower() or option.lower() in value_str.lower():
                return {
                    "value": option,
                    "confidence": mapping.get("confidence", 0.85),
                    "reason": f"Partial match to dropdown option: {option}"
                }
    return mapping


def _normalize_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    processed_fields = []
    for field in fields:
        normalized = field.copy()
        norm_key = FieldNormalizationService.normalize(
            label=field.get("label", ""),
            name=field.get("name", ""),
            field_id=field.get("id", ""),
        )
        if norm_key:
            normalized["normalized_key"] = norm_key
        processed_fields.append(normalized)
    return processed_fields


def map_form_fields(
    fields: list[dict[str, Any]],
    profile: dict[str, Any],
    custom_answers: dict[str, str] | None = None,
    resume_text: str | None = None,
) -> dict[str, Any]:
    started_at = time.monotonic()
    if not fields:
        return {}

    logger.info(
        "Field mapping requested fields=%d profile_keys=%d custom_answers=%d resume_text_len=%d",
        len(fields),
        len(profile or {}),
        len(custom_answers or {}),
        len((resume_text or "")),
    )

    custom_answers = custom_answers or {}
    resume_text = (resume_text or "").strip()[:8000]
    processed_fields = _normalize_fields(fields)
    fallback = _fallback_map(processed_fields, profile, custom_answers)
    cache_key = _build_cache_key(processed_fields, profile or {}, custom_answers, resume_text)
    cached_mapping = _cache_get(cache_key)
    if cached_mapping is not None:
        logger.info("Field mapping cache hit fields=%d", len(processed_fields))
        return cached_mapping

    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY missing; returning fallback mapping only")
        return fallback

    llm_fields = []
    merged: dict[str, Any] = {}
    for field in processed_fields:
        key = _field_key(field)
        fallback_value = fallback.get(key, {"value": None, "confidence": 0.3, "reason": "No mapping"})
        if _requires_llm(field, fallback_value):
            llm_fields.append(field)
        else:
            merged[key] = fallback_value

    if not llm_fields:
        logger.info("Field mapping completed using fallback only fields=%d", len(processed_fields))
        _cache_put(cache_key, fallback)
        return fallback

    client = _get_openai_client()
    fields_desc = json.dumps(llm_fields, separators=(",", ":"))
    profile_desc = json.dumps(profile or {}, separators=(",", ":"))
    custom_answers_desc = json.dumps(custom_answers, separators=(",", ":"))
    prompt = MAP_PROMPT.format(
        profile_json=profile_desc,
        custom_answers_json=custom_answers_desc,
        resume_text=resume_text or "No resume text provided.",
    )

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Form fields:\n{fields_desc}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=4096,
    )

    content = response.choices[0].message.content or "{}"
    try:
        payload = json.loads(content)
        llm_mappings = payload.get("mappings", {})
        logger.info(
            "LLM response parsed llm_mapping_keys=%d sample=%s",
            len(llm_mappings) if isinstance(llm_mappings, dict) else 0,
            json.dumps({k: v for k, v in list((llm_mappings or {}).items())[:3]}, indent=2) if isinstance(llm_mappings, dict) else "N/A"
        )
    except json.JSONDecodeError:
        logger.warning("LLM mapping response was invalid JSON; using fallback")
        llm_mappings = {}

    for field in llm_fields:
        key = _field_key(field)
        llm_value = llm_mappings.get(key) if isinstance(llm_mappings, dict) else None
        fallback_value = fallback.get(key, {"value": None, "confidence": 0.3, "reason": "No mapping"})
        if isinstance(llm_value, dict) and "value" in llm_value:
            if (fallback_value.get("confidence", 0) > llm_value.get("confidence", 0) and
                fallback_value.get("value") is not None):
                merged[key] = fallback_value
            else:
                cleaned_value = _clean_field_value(field, llm_value)
                merged[key] = cleaned_value
        else:
            merged[key] = fallback_value

    for field in processed_fields:
        key = _field_key(field)
        if key not in merged:
            merged[key] = fallback.get(key, {"value": None, "confidence": 0.3, "reason": "No mapping"})
    logger.info(
        "Field mapping completed processed_fields=%d llm_requested=%d llm_keys=%d merged_keys=%d elapsed_ms=%d",
        len(processed_fields),
        len(llm_fields),
        len(llm_mappings) if isinstance(llm_mappings, dict) else 0,
        len(merged),
        int((time.monotonic() - started_at) * 1000),
    )
    _cache_put(cache_key, merged)
    return merged
