"""
Claude provider — implementation with token usage tracking.
Requires: pip install anthropic
"""
from typing import AsyncGenerator
from backend.app.core.config import settings
from backend.app.services.usage_service import record_token_usage
from backend.jobradar.services.llm_base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(self):
        import anthropic
        self._client = anthropic.Anthropic(api_key=settings.claude_api_key)
        print(f"CLAUDE: Initialized with model {settings.claude_model}")

    def _complete(
        self,
        system: str,
        user: str,
        user_id: int = None,
        email: str = None,
        feature: str = None,
        json_mode: bool = False
    ) -> str:
        # Note: Claude uses 'system' as a top-level param, not a message role
        response = self._client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=system or "",
            messages=[{"role": "user", "content": user}],
        )
        
        # Log usage
        if hasattr(response, 'usage'):
            record_token_usage(
                model=settings.claude_model,
                provider="anthropic",
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                user_id=user_id,
                email=email,
                feature=feature
            )
            
        return response.content[0].text

    async def generate_stream(
        self,
        system: str,
        user: str,
        user_id: int = None,
        email: str = None,
        feature: str = None
    ) -> AsyncGenerator[str, None]:
        # Minimal stub for Claude streaming
        with self._client.messages.stream(
            model=settings.claude_model,
            max_tokens=4096,
            system=system or "",
            messages=[{"role": "user", "content": user}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    def chat(self, messages: list[dict], system_instruction: str, user_id: int = None, email: str = None, feature: str = None) -> str:
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
        
        # Log usage
        if hasattr(response, 'usage'):
            record_token_usage(
                model=settings.claude_model,
                provider="anthropic",
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                user_id=user_id,
                email=email,
                feature=feature or "agent_chat"
            )
            
        return response.content[0].text
