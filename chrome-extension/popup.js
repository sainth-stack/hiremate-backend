let ACCESS_TOKEN = null;
const DEFAULT_API_BASE = "http://localhost:8000/api";
const DEFAULT_LOGIN_PAGE_URL = "http://localhost:5173/login";
const LOG_PREFIX = "[Autofill][popup]";
const MAPPING_CACHE_TTL_MS = 5 * 60 * 1000;
const MAPPING_CACHE = new Map();

function logInfo(message, meta) {
  if (meta !== undefined) console.info(LOG_PREFIX, message, meta);
  else console.info(LOG_PREFIX, message);
}

function logWarn(message, meta) {
  if (meta !== undefined) console.warn(LOG_PREFIX, message, meta);
  else console.warn(LOG_PREFIX, message);
}

async function getApiBase() {
  const data = await chrome.storage.local.get(["apiBase"]);
  return data.apiBase || DEFAULT_API_BASE;
}

function getRefreshUrl(apiBase) {
  const base = String(apiBase || "").replace(/\/+$/, "");
  if (base.endsWith("/api")) return `${base}/auth/refresh`;
  return `${base}${base ? "/" : ""}api/auth/refresh`;
}

let _refreshInFlight = null;

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
      const apiBase = data.apiBase || DEFAULT_API_BASE;
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
          const res = await fetch(refreshUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${oldToken}` },
          });
          if (res.ok) {
            const json = await res.json();
            const newToken = json.access_token || json.accessToken;
            if (newToken) {
              ACCESS_TOKEN = newToken;
              if (window.__SECURITY_MANAGER__?.storeToken) {
                await window.__SECURITY_MANAGER__.storeToken(newToken);
              } else {
                await chrome.storage.local.set({ accessToken: newToken });
              }
              try {
                await chrome.runtime.sendMessage({ type: "SYNC_TOKEN_TO_HIREMATE_TAB", token: newToken });
              } catch (_) {}
              logInfo("Token refreshed via API and synced");
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

/** Get auth headers. Sync from tab only. Refresh happens only on 401 (in fetchWithAuthRetry). */
async function getAuthHeaders() {
  try {
    const syncRes = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
    if (syncRes?.ok && syncRes?.token) {
      ACCESS_TOKEN = syncRes.token;
      if (window.__SECURITY_MANAGER__?.storeToken) {
        await window.__SECURITY_MANAGER__.storeToken(syncRes.token);
      } else {
        await chrome.storage.local.set({ accessToken: syncRes.token });
      }
    }
  } catch (_) {}
  let token = ACCESS_TOKEN;
  if (!token && window.__SECURITY_MANAGER__?.getToken) {
    try { token = await window.__SECURITY_MANAGER__.getToken(); } catch (_) {}
  }
  if (!token) token = (await chrome.storage.local.get(["accessToken"])).accessToken;
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

function toPlainHeaders(headers) {
  if (!headers) return {};
  if (headers instanceof Headers) return Object.fromEntries(headers.entries());
  return typeof headers === "object" ? { ...headers } : {};
}

/** Fetch interceptor: on 401 → refresh token, persist to chrome.storage + HireMate localStorage, retry once with new token. */
async function fetchWithAuthRetry(url, options = {}) {
  let res = await fetch(url, options);
  if (res.status === 401) {
    logInfo("401 received, attempting token refresh", { url });
    let newToken = await refreshTokenViaApi();
    if (!newToken) {
      try {
        const syncRes = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
        if (syncRes?.ok && syncRes?.token) {
          newToken = syncRes.token;
          ACCESS_TOKEN = newToken;
          if (window.__SECURITY_MANAGER__?.storeToken) {
            await window.__SECURITY_MANAGER__.storeToken(newToken);
          } else {
            await chrome.storage.local.set({ accessToken: newToken });
          }
        }
      } catch (_) {}
    }
    if (!newToken) {
      await chrome.storage.local.remove([AUTOFILL_CTX_KEY]);
    }
    if (newToken) {
      const base = toPlainHeaders(options.headers);
      res = await fetch(url, { ...options, headers: { ...base, Authorization: `Bearer ${newToken}` } });
    }
  }
  return res;
}

// -- Auth Logic --

async function checkAuth() {
  const data = await chrome.storage.local.get(["accessToken"]);
  ACCESS_TOKEN = data.accessToken || null;
  if (ACCESS_TOKEN) {
    showApp();
  } else {
    showLogin();
  }
}

function showLogin() {
  document.getElementById("login-section").classList.remove("hidden");
  document.getElementById("app-section").classList.add("hidden");
}

function showApp() {
  document.getElementById("login-section").classList.add("hidden");
  document.getElementById("app-section").classList.remove("hidden");
  loadProfile(); // Load profile after login
}

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;
  const btn = document.getElementById("login-btn");
  const error = document.getElementById("login-error");

  btn.disabled = true;
  error.textContent = "";

  try {
    const apiBase = await getApiBase();
    const res = await fetch(`${apiBase}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Login failed");
    }

    const data = await res.json();
    ACCESS_TOKEN = data.access_token;
    if (window.__SECURITY_MANAGER__?.storeToken) {
      await window.__SECURITY_MANAGER__.storeToken(ACCESS_TOKEN);
    } else {
      await chrome.storage.local.set({ accessToken: ACCESS_TOKEN });
    }

    showApp();
  } catch (err) {
    error.textContent = err.message || "Invalid email or password";
  } finally {
    btn.disabled = false;
  }
}

async function handleSignup(e) {
  e.preventDefault();
  const name = document.getElementById("signup-name").value;
  const email = document.getElementById("signup-email").value;
  const password = document.getElementById("signup-password").value;
  const btn = document.getElementById("signup-btn");
  const error = document.getElementById("signup-error");

  btn.disabled = true;
  error.textContent = "";

  try {
    const apiBase = await getApiBase();
    const [first, ...rest] = (name || "").trim().split(/\s+/);
    const firstName = first || "";
    const lastName = rest.join(" ") || "";
    const res = await fetch(`${apiBase}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, first_name: firstName, last_name: lastName }),
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Signup failed");
    }

    const data = await res.json();
    ACCESS_TOKEN = data.access_token;
    if (window.__SECURITY_MANAGER__?.storeToken) {
      await window.__SECURITY_MANAGER__.storeToken(ACCESS_TOKEN);
    } else {
      await chrome.storage.local.set({ accessToken: ACCESS_TOKEN });
    }

    showApp();
  } catch (err) {
    error.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
}

async function handleLogout() {
  ACCESS_TOKEN = null;
  await chrome.storage.local.remove(["accessToken", AUTOFILL_CTX_KEY]);
  showLogin();
}

// -- Profile Logic --

function normalizeKey(text) {
  return text.replace(/\s+/g, " ").trim().toLowerCase();
}

async function loadProfile() {
  // Profile data is fetched from API during fill operation
  logInfo("Profile will be fetched from API on demand");
}

function buildResumeTextFromProfile(profile) {
  const sections = [
    profile.summary,
    profile.experience,
    profile.education,
    profile.skills,
    profile.title,
    profile.company
  ].filter(Boolean);
  return sections.join("\n\n");
}

const AUTOFILL_CTX_KEY = "hm_autofill_ctx";
const AUTOFILL_CTX_TTL = 10 * 60 * 1000;
const FIELD_MAPPINGS_TTL = 7 * 86400 * 1000; // 7 days

let DATA_LOADED = false;

async function loadAndCacheAutofillData() {
  const tLoad = Date.now();
  logInfo("loadAndCacheAutofillData: entry");
  if (DATA_LOADED) {
    const cached = await chrome.storage.local.get([AUTOFILL_CTX_KEY, "profile", "customAnswers", "resumeText"]);
    const ctx = cached[AUTOFILL_CTX_KEY]?.data;
    if (cached.profile && cached.customAnswers) {
      logInfo("loadAndCacheAutofillData: using cached data", { ms: Date.now() - tLoad });
      return {
        profile: cached.profile,
        customAnswers: cached.customAnswers,
        resumeText: cached.resumeText || "",
        resumeName: ctx?.resume_name || null,
        resumeUrl: ctx?.resume_url || null,
      };
    }
  }

  try {
    logInfo("loadAndCacheAutofillData: fetching apiBase + headers");
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    logInfo("loadAndCacheAutofillData: got apiBase", { apiBase, hasAuth: !!headers?.Authorization });
    const _stored = await chrome.storage.local.get(AUTOFILL_CTX_KEY);
    const _cached = _stored[AUTOFILL_CTX_KEY];
    let autofillCtx;
    if (_cached && (Date.now() - _cached.ts) < AUTOFILL_CTX_TTL) {
      logInfo("loadAndCacheAutofillData: using IndexedDB cache", { ms: Date.now() - tLoad });
      autofillCtx = _cached.data;
    } else {
      logInfo("loadAndCacheAutofillData: fetching /autofill/context");
      const _res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/autofill/context`, { headers });
      logInfo("loadAndCacheAutofillData: context response", { status: _res?.status, ok: _res?.ok, ms: Date.now() - tLoad });
      if (!_res.ok) {
        logWarn("Failed to fetch autofill context from API", { status: _res.status });
        return { profile: {}, customAnswers: {}, resumeText: "" };
      }
      autofillCtx = await _res.json();
      await chrome.storage.local.set({ [AUTOFILL_CTX_KEY]: { data: autofillCtx, ts: Date.now() } });
    }
    const profile = autofillCtx.profile || {};
    const customAnswers = autofillCtx.custom_answers || {};
    const resumeText = (autofillCtx.resume_text || "").trim();
    const resumeUrl = autofillCtx.resume_url;

    await chrome.storage.local.set({ profile, customAnswers, resumeText });

    const resumeFilename = resumeUrl ? (resumeUrl.split("/").pop() || "").split("?")[0] : null;
    if (resumeFilename) {
      // Don't block: fetch resume in background so "Loading profile..." doesn't hang on large PDFs
      fetchWithAuthRetry(
        `${apiBase}/chrome-extension/autofill/resume/${encodeURIComponent(resumeFilename)}`,
        { headers }
      ).then((resumeRes) => {
        if (resumeRes.ok) return resumeRes.arrayBuffer();
        return null;
      }).then((buf) => {
        if (buf) {
          chrome.runtime.sendMessage({
            type: "SAVE_RESUME",
            payload: { buffer: Array.from(new Uint8Array(buf)), name: resumeFilename }
          });
          logInfo("Resume uploaded to IndexedDB from API", { fileName: resumeFilename });
        }
      }).catch((resumeErr) => logWarn("Failed to upload resume from API", { error: String(resumeErr) }));
    }

    logInfo("Loaded autofill data from API", {
      profileKeys: Object.keys(profile).length,
      customAnswerKeys: Object.keys(customAnswers).length,
      resumeTextLen: resumeText.length,
    });
    DATA_LOADED = true;
    return {
      profile,
      customAnswers,
      resumeText,
      resumeName: autofillCtx.resume_name || null,
      resumeUrl: resumeUrl || null,
    };
  } catch (err) {
    logWarn("Failed to load autofill data from API", { error: String(err) });
    return { profile: {}, customAnswers: {}, resumeText: "" };
  }
}

async function getLLMMappingContext() {
  return await loadAndCacheAutofillData();
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

// -- UI Helpers --
function showStatus(msg, type = "info") {
  const el = document.getElementById("process-status");
  el.textContent = msg;
  el.className = "status " + type; // "info", "error", "success"
}

function showProgress(stage, detail = "", isActive = false, percent = 0) {
  const card = document.getElementById("progress-card");
  const stageEl = document.getElementById("progress-stage");
  const detailEl = document.getElementById("progress-detail");
  const barEl = document.getElementById("progress-bar");
  const percentEl = document.getElementById("progress-percent");
  if (!card || !stageEl) return;
  card.classList.remove("hidden");
  card.classList.toggle("active", !!isActive);
  stageEl.textContent = stage;
  if (detailEl) detailEl.textContent = detail;
  if (barEl) barEl.style.width = Math.min(100, Math.max(0, percent)) + "%";
  if (percentEl) percentEl.textContent = Math.round(percent) + "%";
}

function showMappingProgress(fields, mappings) {
  const container = document.getElementById("mapping-progress");
  if (!container) return;
  
  container.classList.remove("hidden");
  container.innerHTML = "<h4>AI Mapping Results</h4>";
  
  const list = document.createElement("div");
  list.className = "mapping-list";
  
  const fillableTags = new Set(["input", "select", "textarea"]);
  const nonFillableTags = new Set(["div", "span", "ul", "li"]);
  
  fields.forEach((field) => {
    const mapData = mappings[field.fingerprint] ?? mappings[String(field.index)] ?? mappings[field.index];
    if (!mapData) return;
    
    const tag = (field.tag || field.tagName || field.type || "").toLowerCase();
    const isFillable = fillableTags.has(tag) || (tag === "input" && (field.type || "text") !== "hidden");
    const hasValue = mapData.value != null && mapData.value !== "";
    
    if (nonFillableTags.has(tag) && !hasValue) return;
    
    const div = document.createElement("div");
    div.className = "mapping-row";
    
    const confidence = mapData.confidence || 0;
    const confidenceClass = confidence > 0.9 ? "high" : confidence > 0.7 ? "medium" : "low";
    const displayValue = hasValue ? String(mapData.value).slice(0, 80) + (String(mapData.value).length > 80 ? "…" : "") : "(empty)";
    
    div.innerHTML = `
      <div class="mapping-row-top">
        <span class="mapping-label">${(field.label || field.name || "Field " + field.index || "").toString().slice(0, 50)}</span>
        <span class="mapping-confidence ${confidenceClass}">${Math.round(confidence * 100)}%</span>
      </div>
      <div class="mapping-value">${displayValue}</div>
    `;
    list.appendChild(div);
  });
  
  container.appendChild(list);
}

function hideMappingProgress() {
  const container = document.getElementById("mapping-progress");
  if (container) container.classList.add("hidden");
}

function showProfileGapTip(missingLabels) {
  const top = [...new Set(missingLabels)].slice(0, 3);
  if (!top.length) return;
  document.getElementById("opsbrain-gap-tip")?.remove();
  const tip = document.createElement("div");
  tip.id = "opsbrain-gap-tip";
  tip.style.cssText = "background:#FFF8E7;border:1px solid #F5A623;border-radius:6px;padding:8px 10px;margin:8px 0;font-size:12px;color:#7A5200;line-height:1.4;";
  const fieldList = top.map((f) => `<strong>${escapeHtml(f)}</strong>`).join(", ");
  tip.innerHTML = `💡 Add ${fieldList} to your profile to autofill ${top.length} more field${top.length > 1 ? "s" : ""} next time. <a href="#" id="opsbrain-gap-tip-open" style="margin-left:6px;color:#F5A623;text-decoration:underline;">Update Profile</a> <span id="opsbrain-gap-tip-dismiss" style="float:right;cursor:pointer;font-weight:bold;">✕</span>`;
  const container = document.querySelector(".process-section") || document.getElementById("app-section") || document.body;
  container.prepend(tip);
  document.getElementById("opsbrain-gap-tip-dismiss")?.addEventListener("click", () => tip.remove());
  document.getElementById("opsbrain-gap-tip-open")?.addEventListener("click", (e) => {
    e.preventDefault();
    getApiBase().then((apiBase) => {
      const base = apiBase.replace(/\/api\/?$/, "") || "http://localhost:5173";
      chrome.tabs.create({ url: `${base}/profile` });
    });
  });
}

function getMappingCacheKey(fields, context) {
  const compactFields = fields.map((field) => ({
    index: field.index,
    label: field.label || "",
    name: field.name || "",
    type: field.type || "",
    required: !!field.required,
    placeholder: field.placeholder || ""
  }));
  return JSON.stringify({
    fields: compactFields,
    profile: context.profile || {},
    customAnswers: context.customAnswers || {},
    resumeText: context.resumeText || ""
  });
}

function getCachedMapping(cacheKey) {
  const cached = MAPPING_CACHE.get(cacheKey);
  if (!cached) return null;
  if (Date.now() - cached.ts > MAPPING_CACHE_TTL_MS) {
    MAPPING_CACHE.delete(cacheKey);
    return null;
  }
  return cached.mappings;
}

function setCachedMapping(cacheKey, mappings) {
  if (MAPPING_CACHE.size > 30) {
    const oldestKey = MAPPING_CACHE.keys().next().value;
    if (oldestKey) MAPPING_CACHE.delete(oldestKey);
  }
  MAPPING_CACHE.set(cacheKey, { ts: Date.now(), mappings });
}

// Layer 1: Per-fingerprint cache in chrome.storage.local
async function getCachedMappingsByFp(fps) {
  if (!fps?.length) return {};
  try {
    const key = "hm_field_mappings";
    const stored = await chrome.storage.local.get([key]);
    const all = stored[key] || {};
    const now = Date.now();
    const out = {};
    for (const fp of fps) {
      const rec = all[fp];
      if (rec && rec.cached_at && (now - rec.cached_at) < FIELD_MAPPINGS_TTL) {
        out[fp] = rec.mapping;
      }
    }
    return out;
  } catch (_) {
    return {};
  }
}

async function setCachedMappingsByFp(mappingsByFp) {
  if (!mappingsByFp || Object.keys(mappingsByFp).length === 0) return;
  try {
    const key = "hm_field_mappings";
    const stored = await chrome.storage.local.get([key]);
    const all = stored[key] || {};
    const now = Date.now();
    for (const [fp, mapping] of Object.entries(mappingsByFp)) {
      if (mapping && mapping.value !== undefined) {
        all[fp] = { mapping, cached_at: now };
      }
    }
    const keys = Object.keys(all);
    if (keys.length > 500) {
      const sorted = keys.map((k) => ({ k, t: all[k].cached_at })).sort((a, b) => a.t - b.t);
      for (let i = 0; i < sorted.length - 400; i++) {
        delete all[sorted[i].k];
      }
    }
    await chrome.storage.local.set({ [key]: all });
  } catch (_) {}
}

let CURRENT_FIELDS = [];

// -- Core Logic --

/** Send message to a specific frame; inject content script in that frame and retry once if needed. */
async function sendMessageToFrame(tabId, frameId, message) {
  try {
    const res = await chrome.tabs.sendMessage(tabId, message, { frameId });
    logInfo("sendMessageToFrame: ok", { tabId, frameId, type: message?.type });
    return res;
  } catch (e) {
    logInfo("sendMessageToFrame: first attempt failed", { tabId, frameId, error: e?.message?.slice(0, 80) });
    if (!e?.message?.includes("Receiving end does not exist")) throw e;
    logInfo("sendMessageToFrame: injecting and retrying", { tabId, frameId });
    await chrome.scripting.executeScript({ target: { tabId, frameIds: [frameId] }, files: ["config.js", "security-manager.js", "content-script/requestManager.js", "content-script/cacheManager.js", "content-script/error-handler.js", "content-script/pageDetector.js", "content-script/formWatcher.js", "content-script/selectorResolver.js", "content-script/professionalWidget.js", "content-script/fieldScraper.js", "content-script/humanFiller.js", "content.js"] });
    const res = await chrome.tabs.sendMessage(tabId, message, { frameId });
    logInfo("sendMessageToFrame: retry ok", { tabId, frameId });
    return res;
  }
}

async function getAllFrameIds(tabId) {
  try {
    const frames = await chrome.webNavigation.getAllFrames({ tabId });
    const ids = (frames || []).map((f) => f.frameId).filter((id) => id !== undefined && id !== null);
    if (ids.length > 0) return Array.from(new Set(ids));
  } catch (e) {
    logWarn("Could not enumerate frames, defaulting to top frame only", { error: String(e) });
  }
  return [0];
}

async function sendMessageToAllFrames(tabId, messageBuilder) {
  const frameIds = await getAllFrameIds(tabId);
  logInfo("sendMessageToAllFrames: frameIds", { tabId, frameIds });
  const promises = frameIds.map(async (frameId) => {
    try {
      const message = typeof messageBuilder === "function" ? messageBuilder(frameId) : messageBuilder;
      const res = await sendMessageToFrame(tabId, frameId, message);
      return { frameId, ok: true, res };
    } catch (err) {
      return { frameId, ok: false, err: String(err) };
    }
  });
  return Promise.all(promises);
}

const EDUCATION_ATS = new Set(["school", "degree", "major", "graduation_year"]);
const EMPLOYMENT_ATS = new Set(["company", "job_title", "start_date", "end_date"]);

function buildValuesByFrame(fields, mappings, limits = {}) {
  const maxEducationBlocks = limits.maxEducationBlocks ?? 999;
  const maxEmploymentBlocks = limits.maxEmploymentBlocks ?? 999;
  const occurrenceByFp = {};

  const valuesByFrame = {};
  for (const field of fields) {
    const mapData = mappings[field.fingerprint] ?? mappings[String(field.index)] ?? mappings[field.index];
    let value = mapData?.value;

    // Always attempt resume upload for file fields.
    if ((field.type || "").toLowerCase() === "file" && !value) value = "RESUME_FILE";
    if (value === undefined || value === null || value === "") continue;

    const ats = (field.atsFieldType || "").toLowerCase();
    const fp = field.fingerprint;
    if (fp && (EDUCATION_ATS.has(ats) || EMPLOYMENT_ATS.has(ats))) {
      const seen = occurrenceByFp[fp] ?? 0;
      occurrenceByFp[fp] = seen + 1;
      const maxBlocks = EDUCATION_ATS.has(ats) ? maxEducationBlocks : maxEmploymentBlocks;
      if (seen >= maxBlocks) continue;
    }

    const frameId = String(field.frameId ?? 0);
    const localKey = String(field.frameLocalIndex ?? field.index);
    if (!valuesByFrame[frameId]) valuesByFrame[frameId] = {};
    valuesByFrame[frameId][localKey] = value;
  }
  return valuesByFrame;
}

/** Build field metadata per frame for selector-based element resolution during fill */
function buildFieldsByFrame(fields) {
  const fieldsByFrame = {};
  for (const field of fields) {
    const frameId = String(field.frameId ?? 0);
    if (!fieldsByFrame[frameId]) fieldsByFrame[frameId] = [];
    const localKey = String(field.frameLocalIndex ?? field.index);
    fieldsByFrame[frameId].push({
      index: localKey,
      frameLocalIndex: field.frameLocalIndex ?? field.index,
      selector: field.selector || null,
      id: field.domId || field.id || null,
      domId: field.domId || field.id || null,
      label: field.label || null,
      type: field.type || null,
      tag: field.tag || null,
      atsFieldType: field.atsFieldType || null,
      options: field.options || [],
      fingerprint: field.fingerprint,
    });
  }
  return fieldsByFrame;
}

function sanitizeResumeFilename(displayName) {
  if (!displayName || typeof displayName !== "string") return null;
  const s = displayName.replace(/\s*\(default\)\s*/gi, "").replace(/\s+/g, "_").replace(/[^\w\-_.]/g, "");
  return s ? (s.endsWith(".pdf") ? s : s + ".pdf") : null;
}

async function fillMappedValuesForTab(tabId, fields, mappings, context = null) {
  const resumeRes = await chrome.runtime.sendMessage({ type: "GET_RESUME" });
  let resumeData = resumeRes?.ok ? resumeRes.data || null : null;
  if (resumeData && context?.resumeName) {
    const displayName = sanitizeResumeFilename(context.resumeName);
    if (displayName) resumeData = { ...resumeData, name: displayName };
  }
  const educations = context?.profile?.educations || [];
  const experiences = context?.profile?.experiences || [];
  const limits = {
    maxEducationBlocks: educations.length > 0 ? educations.length : 999,
    maxEmploymentBlocks: experiences.length > 0 ? experiences.length : 999,
  };
  const valuesByFrame = buildValuesByFrame(fields, mappings, limits);
  const fieldsByFrame = buildFieldsByFrame(fields);
  const totalValues = Object.values(valuesByFrame).reduce(
    (sum, frameVals) => sum + Object.keys(frameVals).length,
    0
  );
  logInfo("Fill: dispatching to frames", {
    frames: Object.keys(valuesByFrame).length,
    totalValues,
    hasResume: !!resumeData,
    perFrame: Object.entries(valuesByFrame).map(([fid, vals]) => ({
      frameId: fid,
      count: Object.keys(vals).length,
      indices: Object.keys(vals).slice(0, 8),
    })),
  });

  const lastFill = { fields, mappings };
  const fillResponses = await sendMessageToAllFrames(tabId, (frameId) => ({
    type: "FILL_WITH_VALUES",
    payload: {
      values: valuesByFrame[String(frameId)] || {},
      fieldsForFrame: fieldsByFrame[String(frameId)] || [],
      resumeData,
      scope: "current_document",
      lastFill,
    }
  }));
  
  let totalFilled = 0;
  let totalResumes = 0;
  fillResponses.forEach((resp) => {
    if (resp.ok && resp.res?.ok) {
      totalFilled += resp.res.filledCount || 0;
      totalResumes += resp.res.resumeUploadCount || 0;
    }
  });
  
  logInfo("Fill operation completed", {
    totalFieldsFilled: totalFilled,
    totalResumeUploads: totalResumes,
    framesProcessed: fillResponses.length
  });
  
  return { totalFilled, totalResumes };
}

function trackAutofillUsed(pageUrl) {
  const url = pageUrl || "";
  getApiBase().then((apiBase) =>
    getAuthHeaders().then((headers) => {
      if (!headers?.Authorization) return;
      fetch(`${apiBase}/activity/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ event_type: "autofill_used", page_url: url }),
      }).catch((e) => logWarn("Failed to track autofill", { error: String(e) }));
    })
  );
}

document.getElementById("process-and-fill").addEventListener("click", async () => {
  const btn = document.getElementById("process-and-fill");
  btn.disabled = true;
  hideMappingProgress();
  const t0 = Date.now();
  logInfo("STEP 0: Autofill started", { ts: t0 });

  showProgress("Preparing scan", "Connecting to active tab...", true);
  showStatus("Scraping page...", "loading");

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error("No active tab");
    logInfo("STEP 1: Active tab obtained", { tabId: tab.id, url: tab.url || "", ms: Date.now() - t0 });

    trackAutofillUsed(tab.url || "");

    showStatus("Loading profile data from API...", "loading");
    showProgress("Loading profile", "Fetching candidate profile and saved answers...", true, 10);
    logInfo("STEP 2: Starting token refresh + context load", { ms: Date.now() - t0 });
    try { await refreshTokenViaApi(); } catch (_) {}
    logInfo("STEP 2a: Token refresh done", { ms: Date.now() - t0 });
    const context = await getLLMMappingContext();
    logInfo("STEP 2b: Context loaded", { profileKeys: Object.keys(context?.profile || {}).length, ms: Date.now() - t0 });
    const experiences = context?.profile?.experiences || [];
    const educations = context?.profile?.educations || [];
    const preExpandEmployment = Math.max(0, experiences.length - 1);
    const preExpandEducation = Math.max(0, educations.length - 1);

    // 1. Scrape all frames and merge (with Add another expansion + dropdown options)
    let fields = [];
    logInfo("STEP 3: Starting scrape (sendMessageToAllFrames)", { preExpandEmployment, preExpandEducation, ms: Date.now() - t0 });
    for (let attempt = 0; attempt < 3; attempt++) {
      showProgress("Scanning fields", attempt > 0 ? `Waiting for form... (attempt ${attempt + 1}/3)` : "Collecting input fields across all frames...", true, 25);
      if (attempt > 0) await new Promise((r) => setTimeout(r, 1500 + attempt * 800));
      const scrapePayload = {
        scope: "all",
        expandSelectOptions: true,
        preExpandEmployment,
        preExpandEducation,
        maxEducationBlocks: educations.length || 999,
        maxEmploymentBlocks: experiences.length || 999,
      };
      logInfo("STEP 3a: Sending SCRAPE_FIELDS to all frames", { attempt: attempt + 1, ms: Date.now() - t0 });
      const scrapeResponses = await sendMessageToAllFrames(tab.id, () => ({
        type: "SCRAPE_FIELDS",
        payload: scrapePayload,
      }));
      logInfo("STEP 3b: Scrape responses received", { responseCount: scrapeResponses?.length, okCount: scrapeResponses?.filter((r) => r.ok).length, ms: Date.now() - t0 });
      const mergedFields = [];
      let globalIndex = 0;
      for (const item of scrapeResponses) {
        if (!item.ok || !item.res?.ok) continue;
        const frameFields = item.res.fields || [];
        for (const field of frameFields) {
          mergedFields.push({
            ...field,
            index: globalIndex,
            frameId: item.frameId,
            frameLocalIndex: field.index,
            domId: field.id || null,
          });
          globalIndex += 1;
        }
      }
      fields = mergedFields;
      if (fields.length > 0) break;
    }
    if (fields.length === 0) throw new Error("No form fields found. Click \"Apply\" on a job to open the application form, then try again.");
    logInfo("Scrape complete: fields received", {
      fieldCount: fields.length,
      requiredFields: fields.filter((f) => !!f.required).length,
      framesScanned: scrapeResponses.length,
      framesWithFields: scrapeResponses.filter((r) => r.ok && r.res?.ok && (r.res.fields || []).length > 0).length,
    });
    logInfo("Scraped fields (index | label | type | required)", {
      fields: fields.slice(0, 25).map((f) => ({
        i: f.index,
        label: (f.label || f.name || f.id || "?").toString().slice(0, 50),
        type: f.type || f.tag,
        req: !!f.required,
      })),
    });

    CURRENT_FIELDS = fields;

    if (Object.keys(context.profile || {}).length === 0 && Object.keys(context.customAnswers || {}).length === 0) {
      showProgress("Profile unavailable", "Unable to fetch profile/custom answers from API.", false);
      showStatus("⚠ Failed to load profile data from API.", "error");
      btn.disabled = false;
      logWarn("API returned empty profile/custom answers data");
      return;
    }
    
    showStatus("Analyzing with AI...", "loading");
    showProgress("AI mapping", `Analyzing ${fields.length} fields with optimized routing...`, true, 50);
    const fps = fields.map((f) => f.fingerprint).filter(Boolean);
    const cachedByFp = await getCachedMappingsByFp(fps);
    const missFields = fields.filter((f) => cachedByFp[f.fingerprint] === undefined);
    logInfo("Layer 1 cache", { fps: fps.length, hits: Object.keys(cachedByFp).length, misses: missFields.length });

    let serverMappings = {};
    if (missFields.length > 0) {
      const apiBase = await getApiBase();
      const headers = await getAuthHeaders();
      const mapRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/form-fields/map`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          fields: missFields.map((field) => ({ ...field, id: null })),
          profile: context.profile,
          custom_answers: context.customAnswers,
          resume_text: context.resumeText
        }),
      });
      if (!mapRes.ok) {
        throw new Error(`LLM mapping failed (${mapRes.status}).`);
      }
      const data = await mapRes.json();
      serverMappings = data.mappings || {};
      const toCache = {};
      for (const f of missFields) {
        const m = serverMappings[f.fingerprint] ?? serverMappings[String(f.index)];
        if (m && m.value !== undefined) {
          toCache[f.fingerprint] = m;
        }
      }
      await setCachedMappingsByFp(toCache);
      if (data.unfilled_profile_keys?.length > 0) {
        showProfileGapTip(data.unfilled_profile_keys);
      }
    } else {
      logInfo("Layer 1 full hit - no server call");
    }
    const mappings = { ...cachedByFp, ...serverMappings };
    logInfo("Mapping complete: API response received", {
      mappedFields: Object.keys(mappings).length,
    });
    logInfo("Mapping results (index | value | confidence | reason)", {
      mappings: Object.entries(mappings).slice(0, 20).map(([k, v]) => ({
        idx: k,
        value: v?.value != null ? String(v.value).slice(0, 40) : null,
        conf: v?.confidence,
        reason: (v?.reason || "").slice(0, 50),
      })),
    });

    if (Object.keys(mappings).length === 0) {
      throw new Error("LLM mapping returned empty result.");
    }

    // Show mapping results first
    showMappingProgress(CURRENT_FIELDS, mappings);
    showStatus("Mapping complete. Filling form...", "info");

    showProgress("Filling form", "Applying mapped values to detected inputs...", true, 75);
    showStatus("Filling form...", "loading");
    const valuesByFramePreview = CURRENT_FIELDS.reduce((acc, f) => {
      const fid = String(f.frameId ?? 0);
      acc[fid] = (acc[fid] || 0) + 1;
      return acc;
    }, {});
    logInfo("Filling: sending to content script", {
      fieldsToFill: CURRENT_FIELDS.length,
      valuesByFrame: valuesByFramePreview,
    });
    const fillResult = await fillMappedValuesForTab(tab.id, CURRENT_FIELDS, mappings, context);
    showProgress("Completed", `Filled ${fillResult.totalFilled} fields successfully.`, false, 100);
    showStatus(`✓ Filled ${fillResult.totalFilled} fields${fillResult.totalResumes > 0 ? " + uploaded resume" : ""}!`, "success");
    btn.disabled = false;
    logInfo("Fill completed", {
      totalFilled: fillResult.totalFilled,
      resumeUploads: fillResult.totalResumes,
    });

  } catch (err) {
    const barEl = document.getElementById("progress-bar");
    if (barEl) barEl.classList.add("error");
    showProgress("Failed", "Please retry after checking page access/API.", false, 0);
    showStatus(err.message || "Failed to map/fill with LLM.", "error");
    logWarn("Scan and fill failed", { error: String(err) });
    btn.disabled = false;
  }
});

async function init() {
  document.getElementById("login-form")?.addEventListener("submit", handleLogin);
  document.getElementById("signup-form")?.addEventListener("submit", handleSignup);
  document.getElementById("logout-btn")?.addEventListener("click", handleLogout);
  document.getElementById("login-via-website")?.addEventListener("click", async () => {
    const data = await chrome.storage.local.get(["loginPageUrl"]);
    const url = data.loginPageUrl || DEFAULT_LOGIN_PAGE_URL;
    chrome.tabs.create({ url });
  });
  document.getElementById("go-signup")?.addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("login-form").classList.add("hidden");
    document.getElementById("signup-form").classList.remove("hidden");
  });
  document.getElementById("go-login")?.addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("signup-form").classList.add("hidden");
    document.getElementById("login-form").classList.remove("hidden");
  });
  await checkAuth();
  
  // Auto-trigger widget on popup open
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) {
      await chrome.tabs.sendMessage(tab.id, { type: "SHOW_WIDGET" }).catch(() => {
        // Content script not injected, inject it
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ["content.js"]
        }).then(() => {
          chrome.tabs.sendMessage(tab.id, { type: "SHOW_WIDGET" });
        });
      });
    }
  } catch (err) {
    logWarn("Failed to show widget", { error: String(err) });
  }
  
  logInfo("Extension popup initialized");
}

init();
