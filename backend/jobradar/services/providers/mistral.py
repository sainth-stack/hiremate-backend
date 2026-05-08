"""
Mistral provider — implementation with token usage tracking.
Requires: pip install mistralai
"""
from typing import AsyncGenerator
from backend.app.core.config import settings
from backend.app.services.usage_service import record_token_usage
from backend.jobradar.services.llm_base import LLMProvider


class MistralProvider(LLMProvider):
    def __init__(self):
        from mistralai import Mistral
        self._client = Mistral(api_key=settings.mistral_api_key)
        print(f"MISTRAL: Initialized with model {settings.mistral_model}")

    def _complete(
        self,
        system: str,
        user: str,
        user_id: int = None,
        email: str = None,
        feature: str = None,
        json_mode: bool = False,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        kwargs = {
            "model": settings.mistral_model,
            "messages": messages,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = self._client.chat.complete(**kwargs)
        
        # Log usage
        if hasattr(response, 'usage'):
            record_token_usage(
                model=settings.mistral_model,
                provider="mistral",
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                user_id=user_id,
                email=email,
                feature=feature
            )
            
        return response.choices[0].message.content

    async def generate_stream(
        self,
        system: str,
        user: str,
        user_id: int = None,
        email: str = None,
        feature: str = None
    ) -> AsyncGenerator[str, None]:
        # Minimal stub for Mistral streaming
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        response = self._client.chat.stream(
            model=settings.mistral_model,
            messages=messages,
        )
        
        async for chunk in response:
            delta = chunk.data.choices[0].delta.content
            if delta:
                yield delta

    def chat(self, messages: list[dict], system_instruction: str, user_id: int = None, email: str = None, feature: str = None) -> str:
        mistral_messages = [{"role": "system", "content": system_instruction}]
        for m in messages:
            role = "user" if m.get("role") == "user" else "assistant"
            mistral_messages.append({"role": role, "content": str(m.get("content", ""))})

        response = self._client.chat.complete(
            model=settings.mistral_model,
            messages=mistral_messages,
        )
        
        # Log usage
        if hasattr(response, 'usage'):
            record_token_usage(
                model=settings.mistral_model,
                provider="mistral",
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                user_id=user_id,
                email=email,
                feature=feature or "agent_chat"
            )
            
        return response.choices[0].message.content
