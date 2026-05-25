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
        json_mode: bool = False,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        # Note: Claude uses 'system' as a top-level param, not a message role
        kwargs = {
            "model": settings.claude_model,
            "max_tokens": max_tokens if max_tokens is not None else 4096,
            "system": system or "",
            "messages": [{"role": "user", "content": user}],
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        
        response = self._client.messages.create(**kwargs)
        
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

    def chat(self, messages: list[dict], system_instruction: str, user_id: int = None, email: str = None, feature: str = None, mcp_client=None) -> str:
        if mcp_client is None:
            from backend.jobradar.services.mcp_gmail_client import GmailMCPClient
            mcp_client = GmailMCPClient(user_id, None)

        tools = mcp_client.tools_claude()

        claude_messages = [
            {
                "role": "user" if m.get("role") == "user" else "assistant",
                "content": str(m.get("content", "")),
            }
            for m in messages
        ]

        for _ in range(5):
            response = self._client.messages.create(
                model=settings.claude_model,
                max_tokens=2048,
                system=system_instruction,
                messages=claude_messages,
                tools=tools,
            )

            # Record usage for every round
            if hasattr(response, "usage"):
                record_token_usage(
                    model=settings.claude_model,
                    provider="anthropic",
                    prompt_tokens=response.usage.input_tokens,
                    completion_tokens=response.usage.output_tokens,
                    user_id=user_id,
                    email=email,
                    feature=feature or "agent_chat",
                )

            if response.stop_reason != "tool_use":
                # No tool call — extract the text reply
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            # Append assistant turn with all content blocks (text + tool_use)
            claude_messages.append({"role": "assistant", "content": response.content})

            # Execute each tool call and collect results
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                print(f"AGENT: Claude requested tool: {block.name} with args: {block.input}")
                result = mcp_client.call(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

            claude_messages.append({"role": "user", "content": tool_results})

        # Loop exhausted — return whatever text is available
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""
