// ─── Autofill Context Service ──────────────────────────────────────────────
// Depends on: logInfo, logWarn (utils.js)
//             getApiBase, getAuthHeaders, fetchWithAuthRetry (api-service.js)

const AUTOFILL_CTX_KEY = "hm_autofill_ctx";
const AUTOFILL_CTX_TTL = 10 * 60 * 1000; // 10 minutes

async function getAutofillContextFromApi() {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const _stored = await chrome.storage.local.get(AUTOFILL_CTX_KEY);
  const _cached = _stored[AUTOFILL_CTX_KEY];
  let autofillCtx;
  if (_cached && (Date.now() - _cached.ts) < AUTOFILL_CTX_TTL) {
    autofillCtx = _cached.data;
  } else {
    const _res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/autofill/context?nocache=1`, { headers });
    if (!_res.ok) throw new Error(`Profile load failed (${_res.status})`);
    autofillCtx = await _res.json();
    await chrome.storage.local.set({ [AUTOFILL_CTX_KEY]: { data: autofillCtx, ts: Date.now() } });
  }
  return {
    profile: autofillCtx.profile || {},
    profileDetail: null,
    customAnswers: autofillCtx.custom_answers || {},
    resumeText: autofillCtx.resume_text || "",
    resumeName: autofillCtx.resume_name || null,
    resumeFileName: autofillCtx.resume_url ? (autofillCtx.resume_url.split("/").pop() || "").split("?")[0] : null,
    resumeUrl: autofillCtx.resume_url || null,
  };
}

/** Sanitize resume display name to valid filename (e.g. "Sainath Reddy (default)" → "Sainath_Reddy_Resume.pdf"). */
function sanitizeResumeFilename(displayName) {
  if (!displayName || typeof displayName !== "string") return null;
  const s = displayName.replace(/\s*\(default\)\s*/gi, "").replace(/\s+/g, "_").replace(/[^\w\-_.]/g, "");
  if (!s) return null;
  return s.endsWith(".pdf") ? s : s + ".pdf";
}

/** Fetch resume from API (backend proxies S3/local file). Uses resume_url from context. */
async function fetchResumeFromContext(context) {
  const resumeUrl = context?.resumeUrl || context?.resume_url;
  const resumeFilename = resumeUrl ? (resumeUrl.split("/").pop() || "").split("?")[0] : null;
  if (!resumeFilename) return null;
  try {
    const existing = await chrome.runtime.sendMessage({ type: "GET_RESUME" }).then((r) => (r?.ok ? r.data : null)).catch(() => null);
    const existingHash = existing?.hash;

    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const resumeRes = await fetchWithAuthRetry(
      `${apiBase}/chrome-extension/autofill/resume/${encodeURIComponent(resumeFilename)}`,
      { headers }
    );
    if (!resumeRes.ok) return null;
    const resumeBuffer = await resumeRes.arrayBuffer();
    const buffer = Array.from(new Uint8Array(resumeBuffer));

    const hashInput = buffer.slice(0, 512).join(",");
    const hash = btoa(hashInput).slice(0, 32);

    if (existingHash && existingHash === hash && existing?.buffer?.length === buffer.length) {
      logInfo("Resume unchanged, using cached version", { fileName: resumeFilename });
      const displayName = context?.resumeName ? sanitizeResumeFilename(context.resumeName) : null;
      return { buffer: existing.buffer, name: displayName || resumeFilename, hash };
    }

    await chrome.runtime.sendMessage({
      type: "SAVE_RESUME",
      payload: { buffer, name: resumeFilename, hash },
    });
    const displayName = context?.resumeName ? sanitizeResumeFilename(context.resumeName) : null;
    const fillName = displayName || resumeFilename;
    logInfo("Resume fetched and saved from context", { fileName: fillName, bytes: buffer.length });
    return { buffer, name: fillName, hash };
  } catch (e) {
    logWarn("Failed to fetch resume from context", e);
    return null;
  }
}

async function getStaticResume() {
  return null;
}
