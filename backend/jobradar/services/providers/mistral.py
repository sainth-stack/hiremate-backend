"""
Mistral provider — stub.
Requires: pip install mistralai
"""
from backend.app.core.config import settings
from backend.jobradar.services.llm_base import LLMProvider


class MistralProvider(LLMProvider):
    def __init__(self):
        from mistralai import Mistral
        self._client = Mistral(api_key=settings.mistral_api_key)
        print(f"MISTRAL: Initialized with model {settings.mistral_model}")

    def _complete(self, system: str, user: str) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        response = self._client.chat.complete(
            model=settings.mistral_model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    def chat(self, messages: list[dict], system_instruction: str, user_id: str = None) -> str:
        mistral_messages = [{"role": "system", "content": system_instruction}]
        for m in messages:
            role = "user" if m.get("role") == "user" else "assistant"
            mistral_messages.append({"role": role, "content": str(m.get("content", ""))})

        response = self._client.chat.complete(
            model=settings.mistral_model,
            messages=mistral_messages,
        )
        return response.choices[0].message.content
