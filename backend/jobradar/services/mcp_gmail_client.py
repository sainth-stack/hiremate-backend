"""
Gmail MCP Client -- unified Gmail tool interface for the chat agent.

On connect(), fetches the live tool list from Google's Gmail MCP server
(https://gmailmcp.googleapis.com/mcp/v1) and stores it in self._tools.
All schema converters (tools_openai/gemini/claude) derive from self._tools,
so tool names and parameters are always in sync with what the server exposes.

When the MCP server is unreachable, self._tools falls back to _FALLBACK_TOOLS
which mirrors the current Google schema -- used only to keep the LLM functional
while tool calls are routed through the direct Gmail API.
"""
import httpx

from backend.app.core.logging_config import get_logger

logger = get_logger("services.mcp_gmail")

# Reference URL for documentation — the actual URL used at runtime comes from
# settings.gmail_mcp_server_url (.env: GMAIL_MCP_SERVER_URL=https://gmailmcp.googleapis.com/mcp/v1)
# Leave that setting empty to disable MCP entirely and use direct Gmail API.

# Used ONLY when the MCP server is unreachable.
# Names/params mirror Google's current schema so the fallback stays compatible.
_FALLBACK_TOOLS = [
    {
        "name": "search_threads",
        "description": (
            "Search the user's Gmail inbox for threads matching a query. "
            "Use this when a company is NOT in the application list, or to find any "
            "email thread before fetching its full content with get_thread."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query (e.g. 'from:recruiter@google.com', 'Glassdoor interview').",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_thread",
        "description": (
            "MANDATORY: Fetch the full email conversation for a specific thread. "
            "Use this to read the actual email body when the user asks for details, "
            "next steps, or wants to draft a follow-up. "
            "If a company is in the application list, use its email_thread_id directly. "
            "Otherwise call search_threads first to find the thread_id."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "thread_id": {
                    "type": "string",
                    "description": "The Gmail thread ID (from application data or search_threads results).",
                }
            },
            "required": ["thread_id"],
        },
    },
]


class GmailMCPClient:
    """
    Per-request Gmail tool client.

    Usage:
        client = GmailMCPClient(user_id, db).connect()
        reply  = llm.chat(messages, system, mcp_client=client)
        result = client.call("get_thread", {"thread_id": "abc123"})
    """

    def __init__(self, user_id: int, db):
        self.user_id = user_id
        self.db = db
        self._access_token: str | None = None
        self._mcp_available = False
        self._user = None  # stored during connect() for token refresh
        # Start with fallback; replaced with live server schemas on successful connect()
        self._tools: list[dict] = _FALLBACK_TOOLS

    def connect(self) -> "GmailMCPClient":
        """
        Fetch the live tool list from Google's Gmail MCP server.
        On success: self._tools = live schemas from server (fully dynamic).
        On failure: self._tools stays as _FALLBACK_TOOLS, calls go direct.

        Requires GMAIL_MCP_SERVER_URL to be set in .env to attempt MCP.
        Without it, always uses direct Gmail API (safe default).
        """
        from backend.app.core.config import settings

        if not settings.gmail_mcp_server_url:
            print(f"[MCP] ⏭️  Skipped for user_id={self.user_id} — GMAIL_MCP_SERVER_URL not set, using direct Gmail API")
            return self

        if not self.db:
            return self

        from backend.app.models.user import User
        from backend.app.services.google_oauth import get_credentials_for_user

        user = self.db.query(User).filter(User.id == self.user_id).first()
        if not user or not user.google_access_token:
            return self

        self._user = user  # keep reference for token refresh on 401

        try:
            creds = get_credentials_for_user(self.db, user)
            self._access_token = creds.token

            result = self._rpc("tools/list")
            server_tools = result.get("result", {}).get("tools", [])

            if server_tools:
                self._tools = server_tools          # live schemas replace fallback
                self._mcp_available = True
                print(f"[MCP] ✅ Connected for user_id={self.user_id} — {len(server_tools)} tools: {[t.get('name') for t in server_tools]}")
                logger.info(
                    "Gmail MCP connected for user_id=%s (%d tools: %s)",
                    self.user_id,
                    len(server_tools),
                    [t.get("name") for t in server_tools],
                )
            else:
                print(f"[MCP] ⚠️  Connected for user_id={self.user_id} but server returned no tools — using direct Gmail API")
        except Exception as exc:
            print(f"[MCP] ❌ Unavailable for user_id={self.user_id}: {exc} — using direct Gmail API")
            logger.warning(
                "Gmail MCP unavailable for user_id=%s: %s -- using direct Gmail API",
                self.user_id, exc,
            )

        return self

    # -- Tool schema converters (all derived from self._tools) -----------------

    def tools_openai(self) -> list[dict]:
        """Return live tool definitions in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                },
            }
            for t in self._tools
        ]

    def tools_gemini(self):
        """Return live tool definitions in Gemini FunctionDeclaration format."""
        from google.genai import types as genai_types

        declarations = []
        for t in self._tools:
            schema = t.get("inputSchema", {})
            props = {
                name: genai_types.Schema(
                    type=prop.get("type", "string").upper(),
                    description=prop.get("description", ""),
                )
                for name, prop in schema.get("properties", {}).items()
            }
            declarations.append(
                genai_types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=genai_types.Schema(
                        type="OBJECT",
                        properties=props,
                        required=schema.get("required", []),
                    ),
                )
            )
        return [genai_types.Tool(function_declarations=declarations)]

    def tools_claude(self) -> list[dict]:
        """Return live tool definitions in Anthropic Claude format."""
        return [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("inputSchema", {"type": "object", "properties": {}}),
            }
            for t in self._tools
        ]

    # -- Tool execution --------------------------------------------------------

    def _refresh_token(self) -> bool:
        """
        Force-refresh the Google OAuth access token and update self._access_token.
        Uses get_credentials_for_user() which persists the new token to the DB.
        Returns True if the token was successfully refreshed.
        """
        if not self.db or not self._user:
            return False
        try:
            from backend.app.services.google_oauth import get_credentials_for_user
            from google.auth.transport.requests import Request

            creds = get_credentials_for_user(self.db, self._user)
            # Force a refresh regardless of expiry (bypasses the missing-expiry bug)
            if creds.refresh_token:
                creds.refresh(Request())
                # Persist refreshed token to DB
                from backend.app.services.google_oauth import encrypt
                self._user.google_access_token = encrypt(creds.token)
                self.db.commit()
                self.db.refresh(self._user)
                self._access_token = creds.token
                print(f"[MCP] 🔄 Token refreshed successfully for user_id={self.user_id}")
                return True
            print(f"[MCP] ⚠️  No refresh token available for user_id={self.user_id}")
            return False
        except Exception as exc:
            print(f"[MCP] ❌ Token refresh failed for user_id={self.user_id}: {exc}")
            return False

    def call(self, name: str, arguments: dict) -> str:
        """Execute a tool. Uses MCP server if connected, else falls back to direct API."""
        _MCP_ERROR_SIGNALS = (
            "does not have permission",
            "permission_denied",
            "caller does not have",
            "forbidden",
            "unauthorized",
            "access denied",
        )

        if self._mcp_available:
            print(f"[MCP] 🔧 Calling tool via MCP server: {name}({arguments})")
            try:
                result = self._call_mcp(name, arguments)
                # MCP may return 200 OK but embed a permission/error message in the body
                if any(sig in result.lower() for sig in _MCP_ERROR_SIGNALS):
                    print(f"[MCP] ⚠️  Tool '{name}' returned permission error in body — disabling MCP for this session")
                    print(f"[MCP] 📄 Error content: {result[:200]}")
                    self._mcp_available = False
                else:
                    print(f"[MCP] ✅ Tool '{name}' returned {len(result)} chars via MCP")
                    print(f"[MCP] 📄 Result preview: {result[:300]}")
                    return result
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    print(f"[MCP] 🔄 401 Unauthorized — refreshing token and retrying...")
                    if self._refresh_token():
                        try:
                            result = self._call_mcp(name, arguments)
                            print(f"[MCP] ✅ Tool '{name}' succeeded after token refresh")
                            return result
                        except Exception as retry_exc:
                            print(f"[MCP] ❌ Tool '{name}' failed even after refresh: {retry_exc} — disabling MCP for this session")
                            self._mcp_available = False
                    else:
                        print(f"[MCP] ❌ Token refresh failed — disabling MCP for this session")
                        self._mcp_available = False
                else:
                    print(f"[MCP] ❌ Tool '{name}' failed on MCP ({exc.response.status_code}) — disabling MCP for this session")
                    logger.warning("MCP tool call '%s' failed, disabling MCP for session: %s", name, exc)
                    self._mcp_available = False
            except Exception as exc:
                print(f"[MCP] ❌ Tool '{name}' failed on MCP: {exc} — disabling MCP for this session")
                logger.warning("MCP tool call '%s' failed, disabling MCP for session: %s", name, exc)
                self._mcp_available = False

        print(f"[DIRECT] 🔧 Calling tool via direct Gmail API: {name}({arguments})")
        result = self._call_direct(name, arguments)
        print(f"[DIRECT] ✅ Tool '{name}' returned {len(result)} chars via direct API")
        print(f"[DIRECT] 📄 Result preview: {result[:300]}")
        return result

    def _call_mcp(self, name: str, arguments: dict) -> str:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        content = result.get("result", {}).get("content", [])
        if isinstance(content, list):
            return "\n".join(
                c.get("text", "") for c in content if c.get("type") == "text"
            )
        return str(content)

    def _call_direct(self, name: str, arguments: dict) -> str:
        """
        Direct Gmail API fallback.
        Maps by tool name. If Google renames a tool in a future server version,
        only this method needs updating -- the schema converters stay automatic.
        """
        if name == "search_threads":
            from backend.jobradar.services.chat_tool import search_gmail_inbox
            return search_gmail_inbox(self.user_id, arguments.get("query", ""))

        if name == "get_thread":
            from backend.app.db.session import SessionLocal
            from backend.app.models.user import User
            from backend.app.services.google_oauth import get_credentials_for_user
            from backend.jobradar.services.gmail_service import get_thread_messages

            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == self.user_id).first()
                if not user:
                    return "Authentication Error: User not found."
                creds = get_credentials_for_user(db, user)
                messages = get_thread_messages(creds, arguments["thread_id"])
                if not messages:
                    return "No messages found in this thread."
                compiled = []
                for i, msg in enumerate(messages, start=1):
                    compiled.append(
                        f"--- Email #{i} ---\n"
                        f"From: {msg.get('from', 'Unknown')}\n"
                        f"Date: {msg.get('date', 'Unknown')}\n"
                        f"Subject: {msg.get('subject', '')}\n"
                        f"Body:\n{msg.get('body', '').strip()}\n"
                    )
                return "\n".join(compiled)
            except Exception as exc:
                return f"Gmail API Error: {exc}"
            finally:
                db.close()

        # Unknown tool -- only hit if Google adds new tools the fallback doesn't cover yet
        logger.warning("No direct fallback for tool '%s' -- MCP required for this tool", name)
        return f"Tool '{name}' requires an active Gmail MCP connection and is unavailable offline."

    def _rpc(self, method: str, params: dict = None) -> dict:
        from backend.app.core.config import settings

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }
        resp = httpx.post(
            settings.gmail_mcp_server_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
