// ─── API Service — Auth & Fetch ────────────────────────────────────────────
// Depends on: LOGIN_PAGE_ORIGINS, DEFAULT_LOGIN_PAGE_URL (consts.js)
//             logInfo, logWarn (utils.js)
//             AUTOFILL_CTX_KEY defined in autofill-context.js (loaded after this file,
//             but only referenced at call-time, so safe)

/**
 * proxyFetch — routes a fetch through the background service worker.
 *
 * Content script fetch() calls are blocked by the host page's CSP (e.g.
 * LinkedIn's connect-src blocks requests to our backend).  The background
 * SW is not subject to page CSP, so we relay through it via messaging.
 *
 * Returns a Response-compatible object with .ok, .status, .json(),
 * .text(), and .blob() — same interface as the native Response.
 */
async function proxyFetch(url, options) {
  const result = await chrome.runtime.sendMessage({
    type: "PROXY_FETCH",
    url,
    options: {
      method: (options && options.method) || "GET",
      headers: (options && options.headers) || {},
      body: (options && options.body != null) ? options.body : undefined,
    },
  });
  if (!result) throw new Error("proxyFetch: no response from background");
  if (!result.ok && result.error && result.status === 0) throw new Error(result.error);
  const { ok, status, bodyType, body, contentType } = result;
  return {
    ok,
    status,
    json: async function () { return JSON.parse(body); },
    text: async function () { return body; },
    blob: async function () {
      if (bodyType === "arraybuffer") {
        return new Blob([new Uint8Array(body)], { type: contentType || "application/octet-stream" });
      }
      return new Blob([body], { type: contentType || "text/plain" });
    },
  };
}

async function getApiBase() {
  if (window.__CONFIG__?.getApiBase) return window.__CONFIG__.getApiBase();
  try {
    const data = await chrome.storage.local.get(["apiBase"]);
    return data.apiBase || "https://opsbrainai.com/api";
  } catch (_) {
    return "https://opsbrainai.com/api";
  }
}

/** Build auth refresh URL - handles apiBase with or without /api suffix. */
function getRefreshUrl(apiBase) {
  const base = String(apiBase || "").replace(/\/+$/, "");
  if (base.endsWith("/api")) return `${base}/auth/refresh`;
  return `${base}${base ? "/" : ""}api/auth/refresh`;
}

/** Mutex: only one refresh in flight; others wait and reuse the result. */
let _refreshInFlight = null;

/** Refresh token via API (only on 401). Returns new token or null. */
async function refreshTokenViaApi() {
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = (async () => {
    try {
      const data = await chrome.storage.local.get(["accessToken", "apiBase"]);
      const oldToken = data.accessToken;
      if (!oldToken) {
        logWarn("refreshTokenViaApi: No token in storage, cannot refresh");
        return null;
      }
      const apiBase = data.apiBase || "https://opsbrainai.com/api";
      const baseNoApi = apiBase.replace(/\/api\/?$/, "");
      const urlsToTry = [
        getRefreshUrl(apiBase),
        `${apiBase}/auth/refresh`,
        `${baseNoApi}/api/auth/refresh`,
        baseNoApi.replace(/:\d+/, ":8001") + "/api/auth/refresh",
        baseNoApi.replace(/:\d+/, ":8000") + "/api/auth/refresh",
      ];
      for (const refreshUrl of [...new Set(urlsToTry)]) {
        try {
          logInfo("Attempting token refresh", { url: refreshUrl });
          const res = await proxyFetch(refreshUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${oldToken}` },
          });
          if (res.ok) {
            const json = await res.json();
            const newToken = json.access_token || json.accessToken;
            if (newToken) {
              await chrome.storage.local.set({ accessToken: newToken });
              try {
                await chrome.runtime.sendMessage({ type: "SYNC_TOKEN_TO_HIREMATE_TAB", token: newToken });
              } catch (_) { }
              if (LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o)) {
                try {
                  localStorage.setItem("token", newToken);
                  localStorage.setItem("access_token", newToken);
                } catch (_) { }
              }
              logInfo("Token refreshed via API and synced to chrome.storage + localStorage");
              return newToken;
            }
            logWarn("Refresh returned 200 but no access_token in response", { keys: Object.keys(json || {}) });
          } else {
            const errBody = await res.text().catch(() => "");
            logWarn("Refresh failed", { url: refreshUrl, status: res.status, body: errBody?.slice(0, 200) });
          }
        } catch (err) {
          logWarn("Refresh request error", { url: refreshUrl, error: String(err) });
          continue;
        }
      }
      logWarn("All refresh attempts failed");
      return null;
    } finally {
      _refreshInFlight = null;
    }
  })();
  return _refreshInFlight;
}

/** Get auth headers. Sync token from open HireMate tab only. Refresh happens only on 401. */
async function getAuthHeaders() {
  try {
    const syncRes = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
    if (syncRes?.ok && syncRes?.token) {
      await chrome.storage.local.set({ accessToken: syncRes.token });
    }
  } catch (_) { }
  let token = null;
  if (window.__SECURITY_MANAGER__?.getToken) {
    try { token = await window.__SECURITY_MANAGER__.getToken(); } catch (_) { }
  }
  if (!token) {
    const data = await chrome.storage.local.get(["accessToken"]);
    token = data.accessToken || null;
  }
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

/** Normalize headers to plain object (handles Headers instance). */
function toPlainHeaders(headers) {
  if (!headers) return {};
  if (headers instanceof Headers) return Object.fromEntries(headers.entries());
  return typeof headers === "object" ? { ...headers } : {};
}

/** Fetch interceptor: on 401 → refresh token, persist, retry once with new token. */
async function fetchWithAuthRetry(url, options = {}) {
  const t0 = Date.now();
  let res = await proxyFetch(url, options);
  logInfo("fetchWithAuthRetry: first attempt", { path: url?.split("/").slice(-2).join("/"), status: res.status, ms: Date.now() - t0 });
  if (res.status === 401) {
    logInfo("401 received, attempting token refresh", { url: url?.slice(-50) });
    let newToken = null;
    newToken = await refreshTokenViaApi();
    if (!newToken) {
      try {
        const syncRes = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
        if (syncRes?.ok && syncRes?.token) {
          newToken = syncRes.token;
          await chrome.storage.local.set({ accessToken: newToken });
        }
      } catch (_) { }
    }
    if (!newToken) {
      // AUTOFILL_CTX_KEY defined in autofill-context.js
      await chrome.storage.local.remove([AUTOFILL_CTX_KEY]);
    }
    if (newToken) {
      const base = toPlainHeaders(options.headers);
      const retryOptions = { ...options, headers: { ...base, Authorization: `Bearer ${newToken}` } };
      res = await proxyFetch(url, retryOptions);
      logInfo("fetchWithAuthRetry: retry result", { status: res.status, ms: Date.now() - t0 });
      if (res.status === 401) {
        logWarn("Retry still returned 401 after refresh");
      }
    }
  }
  return res;
}
