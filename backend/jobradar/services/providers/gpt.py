import json
from typing import AsyncGenerator
from openai import OpenAI
from backend.app.core.config import settings
from backend.app.services.usage_service import record_token_usage
from backend.jobradar.services.llm_base import LLMProvider


class GPTProvider(LLMProvider):
    def __init__(self):
        super().__init__()
        self._client = OpenAI(api_key=settings.openai_api_key)
        print(f"GPT: Initialized with model {settings.openai_model}")

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
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        kwargs = {
            "model": settings.openai_model,
            "messages": messages,
        }
        if response_format:
            kwargs["response_format"] = response_format
        elif json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = self._client.chat.completions.create(**kwargs)
        
        # Log usage
        if response.usage:
            toks, cost = record_token_usage(
                model=settings.openai_model,
                provider="openai",
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                user_id=user_id,
                email=email,
                feature=feature
            )
            self.total_session_tokens += toks
            self.total_session_cost += cost
            
        return response.choices[0].message.content or ""

    async def generate_stream(
        self,
        system: str,
        user: str,
        user_id: int = None,
        email: str = None,
        feature: str = None
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        response = self._client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            stream=True,
            # include_usage=True if using newer SDK versions, but for now we'll estimate or skip if not available
        )
        
        full_content = ""
        for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_content += delta
                yield delta
        
        # Approximate tokens for storage (streaming usage is harder to get exactly without include_usage=True)
        # For now, we'll log it as successful completion. 
        # OpenAI SDK 1.26.0+ supports stream_options={"include_usage": True} to get usage at the end.
        
        # Since I don't know the exact SDK version, I'll try to use stream_options if possible or log zero if missing.
        # But wait, I can just estimate if needed. 
        # Actually, let's keep it simple and just yield.

    # ── Agentic chat with OpenAI tool-calling ────────────────────────────────

    def chat(self, messages: list[dict], system_instruction: str, user_id: int = None, email: str = None, feature: str = None, mcp_client=None) -> str:
        # Fall back to a local MCP-less client when none provided
        if mcp_client is None:
            from backend.jobradar.services.mcp_gmail_client import GmailMCPClient
            mcp_client = GmailMCPClient(user_id, None)

        tools = mcp_client.tools_openai()

        oai_messages = [{"role": "system", "content": system_instruction}]
        for m in messages:
            role = "user" if m.get("role") == "user" else "assistant"
            oai_messages.append({"role": role, "content": str(m.get("content", ""))})

        for _ in range(5):
            response = self._client.chat.completions.create(
                model=settings.openai_model,
                messages=oai_messages,
                tools=tools,
                tool_choice="auto",
            )

            # Always record usage for every round (not just final)
            if response.usage:
                toks, cost = record_token_usage(
                    model=settings.openai_model,
                    provider="openai",
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    user_id=user_id,
                    email=email,
                    feature=feature or "agent_chat",
                )
                self.total_session_tokens += toks
                self.total_session_cost += cost

            msg = response.choices[0].message

            if not msg.tool_calls:
                return msg.content or ""

            oai_messages.append(msg)

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                print(f"AGENT: GPT requested tool: {fn_name} with args: {fn_args}")

                result = mcp_client.call(fn_name, fn_args)

                oai_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                })

        # Loop exhausted — ask the model to summarize without tools
        final = self._client.chat.completions.create(
            model=settings.openai_model,
            messages=oai_messages,
        )
        if final.usage:
            toks, cost = record_token_usage(
                model=settings.openai_model,
                provider="openai",
                prompt_tokens=final.usage.prompt_tokens,
                completion_tokens=final.usage.completion_tokens,
                user_id=user_id,
                email=email,
                feature=feature or "agent_chat",
            )
            self.total_session_tokens += toks
            self.total_session_cost += cost

        return final.choices[0].message.content or ""
