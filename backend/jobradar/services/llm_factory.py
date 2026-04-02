from backend.app.core.config import settings
from backend.jobradar.services.llm_base import LLMProvider
from backend.jobradar.services.providers.gemini import GeminiProvider
from backend.jobradar.services.providers.claude import ClaudeProvider
from backend.jobradar.services.providers.gpt import GPTProvider
from backend.jobradar.services.providers.mistral import MistralProvider


class LLMFactory:
    _instance: LLMProvider = None
    _instance_provider: str = None

    @classmethod
    def get_provider(cls) -> LLMProvider:
        provider_name = settings.ai_provider.lower()
        if cls._instance is None or cls._instance_provider != provider_name:
            cls._instance = None
            cls._instance_provider = provider_name
            if provider_name == "gemini":
                cls._instance = GeminiProvider()
            elif provider_name == "claude":
                cls._instance = ClaudeProvider()
            elif provider_name == "gpt":
                cls._instance = GPTProvider()
            elif provider_name == "mistral":
                cls._instance = MistralProvider()
            else:
                raise ValueError(f"Unsupported AI provider: {provider_name}")
        return cls._instance
