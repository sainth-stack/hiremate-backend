import json
from openai import OpenAI
from backend.app.core.config import settings
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
        self._client = OpenAI(api_key=settings.openai_api_key)
        print(f"GPT: Initialized with model {settings.openai_model}")

    # ── Required by base ─────────────────────────────────────────────────────

    def _complete(self, system: str, user: str) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        response = self._client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=messages,
        )
        return response.choices[0].message.content

    # ── Agentic chat with OpenAI tool-calling ────────────────────────────────

    def chat(self, messages: list[dict], system_instruction: str, user_id: str = None) -> str:
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
        return final.choices[0].message.content or ""
