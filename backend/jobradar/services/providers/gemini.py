import json
from typing import AsyncGenerator
from google import genai
from google.genai import types
from backend.app.core.config import settings
from backend.app.services.usage_service import record_token_usage
from backend.jobradar.services.llm_base import LLMProvider


class GeminiProvider(LLMProvider):
    def __init__(self):
        if settings.use_vertex_ai:
            self._client = genai.Client(
                vertexai=True,
                project=settings.vertex_project_id,
                location=settings.vertex_location,
            )
            print(f"GEMINI: Using Vertex AI (project={settings.vertex_project_id}, location={settings.vertex_location})")
        else:
            self._client = genai.Client(api_key=settings.gemini_api_key)
            print("GEMINI: Using Gemini API key")

    # ── Required by base ─────────────────────────────────────────────────────

    def _complete(
        self,
        system: str,
        user: str,
        user_id: int = None,
        email: str = None,
        feature: str = None,
        json_mode: bool = False,
        temperature: float = None,
        max_tokens: int = None,
        response_format: dict = None,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
        )
        if json_mode or (response_format and response_format.get("type") == "json_object"):
            config.response_mime_type = "application/json"
        if temperature is not None:
            config.temperature = temperature
        if max_tokens is not None:
            config.max_output_tokens = max_tokens

        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=user,
            config=config,
        )
        
        # Log usage
        if response.usage_metadata:
            record_token_usage(
                model=settings.gemini_model,
                provider="google",
                prompt_tokens=response.usage_metadata.prompt_token_count,
                completion_tokens=response.usage_metadata.candidates_token_count,
                user_id=user_id,
                email=email,
                feature=feature
            )
            
        return response.text

    async def generate_stream(
        self,
        system: str,
        user: str,
        user_id: int = None,
        email: str = None,
        feature: str = None
    ) -> AsyncGenerator[str, None]:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
        )
        
        response = self._client.models.generate_content_stream(
            model=settings.gemini_model,
            contents=user,
            config=config,
        )
        
        full_content = ""
        prompt_tokens = 0
        completion_tokens = 0
        
        async for chunk in response:
            if chunk.text:
                full_content += chunk.text
                yield chunk.text
            
            # Gemini typically provides usage at the end or in each chunk
            if chunk.usage_metadata:
                prompt_tokens = chunk.usage_metadata.prompt_token_count
                completion_tokens = chunk.usage_metadata.candidates_token_count

        # Log usage after stream completes
        if prompt_tokens > 0 or completion_tokens > 0:
            record_token_usage(
                model=settings.gemini_model,
                provider="google",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                user_id=user_id,
                email=email,
                feature=feature
            )

    # ── Agentic chat with Gemini tool-calling ────────────────────────────────

    def chat(self, messages: list[dict], system_instruction: str, user_id: int = None, email: str = None, feature: str = None, mcp_client=None) -> str:
        if mcp_client is None:
            from backend.jobradar.services.mcp_gmail_client import GmailMCPClient
            mcp_client = GmailMCPClient(user_id, None)

        tools = mcp_client.tools_gemini()

        contents = []
        for m in messages:
            contents.append({
                "role": "user" if m.get("role") == "user" else "model",
                "parts": [{"text": str(m.get("content", ""))}],
            })

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tools,
        )

        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=config,
        )

        for _ in range(5):
            # Record usage for each round
            if response.usage_metadata:
                record_token_usage(
                    model=settings.gemini_model,
                    provider="google",
                    prompt_tokens=response.usage_metadata.prompt_token_count or 0,
                    completion_tokens=response.usage_metadata.candidates_token_count or 0,
                    user_id=user_id,
                    email=email,
                    feature=feature or "agent_chat",
                )

            # Extract function call if present
            tool_call = None
            if (
                response.candidates
                and response.candidates[0].content
                and response.candidates[0].content.parts
            ):
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        tool_call = part.function_call
                        break

            if not tool_call:
                break

            print(f"AGENT: Gemini requested tool: {tool_call.name} with args: {tool_call.args}")

            tool_result = mcp_client.call(tool_call.name, dict(tool_call.args))

            contents.append(response.candidates[0].content)
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=tool_call.name,
                            response={"result": tool_result},
                        )
                    ],
                )
            )

            response = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=config,
            )

        # Extract text safely — final response may still be a function_call with no text
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    return part.text
        return ""
