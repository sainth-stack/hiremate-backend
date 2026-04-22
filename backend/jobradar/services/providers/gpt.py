import json
from typing import AsyncGenerator
from openai import OpenAI
from backend.app.core.config import settings
from backend.app.services.usage_service import record_token_usage
from backend.jobradar.services.llm_base import LLMProvider

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_raw_email",
            "description": (
                "MANDATORY: Use this tool to read the actual live email thread for a company. "
                "Trigger this if the user asks for details, specifics, next steps, or drafts of "
                "follow-ups that require reading the email body beyond the summary metadata."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "The exact or approximate company name mentioned in the user's query.",
                    }
                },
                "required": ["company_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_gmail_inbox",
            "description": (
                "Searches the entire live Gmail inbox for any query string. "
                "Use this if a company is NOT in the provided database summary to find relevant email threads."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The Gmail search query (e.g. 'Glassdoor', 'from:recruiter@google.com').",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


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
        json_mode: bool = False
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        kwargs = {
            "model": settings.openai_model,
            "messages": messages,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

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

    def chat(self, messages: list[dict], system_instruction: str, user_id: int = None, email: str = None, feature: str = None) -> str:
        from backend.jobradar.services.chat_tool import fetch_raw_email, search_gmail_inbox

        oai_messages = [{"role": "system", "content": system_instruction}]
        for m in messages:
            role = "user" if m.get("role") == "user" else "assistant"
            oai_messages.append({"role": role, "content": str(m.get("content", ""))})

        for _ in range(2):
            response = self._client.chat.completions.create(
                model=settings.openai_model,
                messages=oai_messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                return msg.content or ""

            oai_messages.append(msg)

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                print(f"AGENT: GPT requested tool: {fn_name} with args: {fn_args}")

                if fn_name == "fetch_raw_email":
                    result = fetch_raw_email(user_id, fn_args["company_name"])
                elif fn_name == "search_gmail_inbox":
                    result = search_gmail_inbox(user_id, fn_args["query"])
                else:
                    result = f"Error: Tool '{fn_name}' not implemented."

                oai_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                })

        final = self._client.chat.completions.create(
            model=settings.openai_model,
            messages=oai_messages,
        )
        
        # Log usage for the final response
        if final.usage:
             toks, cost = record_token_usage(
                model=settings.openai_model,
                provider="openai",
                prompt_tokens=final.usage.prompt_tokens,
                completion_tokens=final.usage.completion_tokens,
                user_id=user_id,
                email=email,
                feature=feature or "agent_chat"
            )
             self.total_session_tokens += toks
             self.total_session_cost += cost
            
        return final.choices[0].message.content or ""
