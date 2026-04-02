"""
Claude provider — stub.
Requires: pip install anthropic
"""
from backend.app.core.config import settings
from backend.jobradar.services.llm_base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(self):
        import anthropic
        self._client = anthropic.Anthropic(api_key=settings.claude_api_key)
        print(f"CLAUDE: Initialized with model {settings.claude_model}")

    def _complete(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=system or "",
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    def chat(self, messages: list[dict], system_instruction: str, user_id: str = None) -> str:
        claude_messages = [
            {"role": "user" if m.get("role") == "user" else "assistant", "content": str(m.get("content", ""))}
            for m in messages
        ]
        response = self._client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=system_instruction,
            messages=claude_messages,
        )
        return response.content[0].text
