"""
LLM-powered LinkedIn cold message generation.
"""
from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger

logger = get_logger("services.linkedin_cold_msg")

_SYSTEM_PROMPT = """
You are a professional networking assistant helping users write concise, genuine LinkedIn cold messages.

Message structure (follow exactly):
1. "Hi [recipient first name], Hope you're doing well."
2. One sentence: why you're reaching out — mention the specific role or company if provided.
3. One sentence: sender's concrete background. Use the EXACT years, skills, and role from Sender data if provided.
4. One sentence: the specific ask (referral, intro call, advice, etc.).
5. "Thanks for your help in advance."

CRITICAL rules — violation is not acceptable:
- NEVER use placeholder text like [your field], [X years], [specific area], [your role], etc.
- If Sender data is provided: use the real name, real years, real skills, real role — verbatim.
- If a detail is missing from Sender data: omit it or use a natural generic phrase ("with my background in software engineering") — never use brackets.
- Separate each sentence/paragraph with a blank line (two newlines) so the message is easy to read.
- Write in first person on behalf of the sender.
- Match the tone: "professional" = formal but friendly, "casual" = relaxed, "warm" = empathetic.
- Output ONLY the message text. No subject line, no preamble, no quotes, no markdown.
""".strip()


def _get_llm():
    """Return ChatOpenAI if API key set, else None."""
    if not (getattr(settings, "openai_api_key", None) or "").strip():
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=getattr(settings, "openai_model", "gpt-4o-mini") or "gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.7,
        )
    except Exception as e:
        logger.warning("LLM init failed: %s", e)
        return None


async def generate_comment(
    post_content: str | None = None,
    post_author: str | None = None,
    user_intent: str | None = None,
    sender_profile_summary: str | None = None,
    tone: str = "professional",
) -> str:
    """Generate a LinkedIn post comment via LLM."""
    from langchain_core.messages import SystemMessage, HumanMessage

    llm = _get_llm()
    if not llm:
        raise RuntimeError("LLM service unavailable (no API key)")

    system = """Write a LinkedIn comment that sounds like a real person typed it quickly.

Rules:
- 1–3 short sentences. Casual and direct — the way a person actually talks.
- React naturally to what the post actually says. No generic filler.
- Don't start with "Great post!", "Love this!", or any hollow opener.
- Don't sound like a press release. No corporate phrases like "leverage synergies", "thought leadership", "actionable insights".
- If the sender has real experience relevant to the post, mention it briefly and naturally. No brackets or placeholders.
- No forced question at the end unless it flows naturally.
- Output ONLY the comment. No quotes, no explanation.
""".strip()

    parts = []
    if post_author:
        parts.append(f"Post author: {post_author}")
    if post_content:
        parts.append(f"Post content:\n{post_content[:1000]}")
    if user_intent:
        parts.append(f"My angle / what I want to say: {user_intent}")
    if sender_profile_summary:
        parts.append(f"My profile (use my real details):\n{sender_profile_summary}")
    parts.append(f"Tone: {tone}")

    response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content="\n\n".join(parts))])
    logger.info("Generated comment (%d chars)", len(response.content))
    return response.content.strip()


async def generate_job_answer(
    field_label: str | None = None,
    job_title: str | None = None,
    company: str | None = None,
    user_intent: str | None = None,
    sender_profile_summary: str | None = None,
    tone: str = "professional",
) -> str:
    """Generate a job application field answer via LLM."""
    from langchain_core.messages import SystemMessage, HumanMessage

    llm = _get_llm()
    if not llm:
        raise RuntimeError("LLM service unavailable (no API key)")

    system = """You are helping a job seeker fill in a LinkedIn job application field.

Rules:
- Answer the exact question/field directly.
- Use the applicant's REAL data (name, role, skills, years) — NEVER use placeholders like [X years] or [your skill].
- Cover letter: 3–4 short paragraphs — opening hook, relevant experience, why this company/role, closing ask.
- Short answer / textarea: 2–4 punchy sentences.
- "Why this role/company?": make it specific to the job title and company name provided.
- Output ONLY the answer text. No labels, no preamble, no quotes.
""".strip()

    parts = []
    if field_label:
        parts.append(f"Field / Question: {field_label}")
    if job_title:
        parts.append(f"Job title: {job_title}")
    if company:
        parts.append(f"Company: {company}")
    if user_intent:
        parts.append(f"Additional guidance: {user_intent}")
    if sender_profile_summary:
        parts.append(f"Applicant profile (use real details):\n{sender_profile_summary}")
    parts.append(f"Tone: {tone}")

    response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content="\n\n".join(parts))])
    logger.info("Generated job answer (%d chars)", len(response.content))
    return response.content.strip()


async def generate_cold_message(
    user_intent: str,
    recipient_name: str | None = None,
    company: str | None = None,
    sender_summary: str | None = None,
    thread_context: str | None = None,
    tone: str = "professional",
) -> str:
    """Generate cold message via LLM. Raises RuntimeError if LLM unavailable."""
    from langchain_core.messages import SystemMessage, HumanMessage

    llm = _get_llm()
    if not llm:
        raise RuntimeError("LLM service unavailable (no API key)")

    parts = [f"Intent: {user_intent}"]
    if recipient_name:
        parts.append(f"Recipient: {recipient_name}")
    if company:
        parts.append(f"Company: {company}")
    if sender_summary:
        parts.append(f"Sender: {sender_summary[:400]}")
    if thread_context:
        parts.append(f"Context: {thread_context[:800]}")
    parts.append(f"Tone: {tone}")

    user_prompt = "\n".join(parts)
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_prompt)]

    logger.info("Generating cold message for recipient=%s company=%s", recipient_name, company)
    response = await llm.ainvoke(messages)
    text = response.content.strip()
    logger.info("Generated %d chars", len(text))
    return text
