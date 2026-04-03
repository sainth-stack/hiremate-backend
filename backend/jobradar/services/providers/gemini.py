import json
from google import genai
from google.genai import types
from backend.app.core.config import settings
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

    def _complete(self, system: str, user: str) -> str:
        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system or None,
                response_mime_type="application/json",
            ),
        )
        return response.text

    # ── Agentic chat with Gemini tool-calling ────────────────────────────────

    def chat(self, messages: list[dict], system_instruction: str, user_id: str = None) -> str:
        from backend.jobradar.services.chat_tool import fetch_raw_email, search_gmail_inbox

        contents = []
        for m in messages:
            contents.append({
                "role": "user" if m.get("role") == "user" else "model",
                "parts": [{"text": str(m.get("content", ""))}],
            })

        tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="fetch_raw_email",
                        description=(
                            "MANDATORY: Use this tool to read the actual live email thread for a company. "
                            "Trigger this if the user asks for details, specifics, next steps, or drafts of "
                            "follow-ups that require reading the email body beyond the summary metadata."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "company_name": types.Schema(
                                    type="STRING",
                                    description="The exact or approximate company name mentioned in the user's query.",
                                )
                            },
                            required=["company_name"],
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="search_gmail_inbox",
                        description=(
                            "Searches the entire live Gmail inbox for any query string. "
                            "Use this if a company is NOT in the provided database summary to find relevant email threads."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "query": types.Schema(
                                    type="STRING",
                                    description="The Gmail search query (e.g. 'Glassdoor', 'from:recruiter@google.com').",
                                )
                            },
                            required=["query"],
                        ),
                    ),
                ]
            )
        ]

        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools,
            ),
        )

        for _ in range(2):
            if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
                break

            tool_call = None
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    tool_call = part.function_call
                    break

            if not tool_call:
                break

            print(f"AGENT: Gemini requested tool: {tool_call.name} with args: {tool_call.args}")

            if tool_call.name == "fetch_raw_email":
                tool_result = fetch_raw_email(user_id, tool_call.args["company_name"])
            elif tool_call.name == "search_gmail_inbox":
                tool_result = search_gmail_inbox(user_id, tool_call.args["query"])
            else:
                tool_result = f"Error: Tool '{tool_call.name}' not implemented."

            contents.append(response.candidates[0].content)
            contents.append(types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(
                        name=tool_call.name,
                        response={"result": tool_result},
                    )
                ],
            ))

            response = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools,
                ),
            )

        return response.text
