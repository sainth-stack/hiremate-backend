let ACCESS_TOKEN = null;
const DEFAULT_API_BASE = "http://localhost:8000/api";
const DEFAULT_LOGIN_PAGE_URL = "http://localhost:5173/login";
const LOG_PREFIX = "[JobAutofill][popup]";
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
              await chrome.storage.local.set({ accessToken: newToken });
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
      await chrome.storage.local.set({ accessToken: syncRes.token });
    }
  } catch (_) {}
  let token = ACCESS_TOKEN || (await chrome.storage.local.get(["accessToken"])).accessToken;
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
          await chrome.storage.local.set({ accessToken: newToken });
        }
      } catch (_) {}
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
    await chrome.storage.local.set({ accessToken: ACCESS_TOKEN });

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
    await chrome.storage.local.set({ accessToken: ACCESS_TOKEN });

    showApp();
  } catch (err) {
    error.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
}

async function handleLogout() {
  ACCESS_TOKEN = null;
  await chrome.storage.local.remove(["accessToken"]);
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

let DATA_LOADED = false;

async function loadAndCacheAutofillData() {
  if (DATA_LOADED) {
    const cached = await chrome.storage.local.get(["profile", "customAnswers", "resumeText"]);
    if (cached.profile && cached.customAnswers) {
      logInfo("Using cached autofill data");
      return {
        profile: cached.profile,
        customAnswers: cached.customAnswers,
        resumeText: cached.resumeText || ""
      };
    }
  }

  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/autofill/data`, { headers });
    
    if (!res.ok) {
      logWarn("Failed to fetch autofill data from API", { status: res.status });
      return { profile: {}, customAnswers: {}, resumeText: "" };
    }
    
    const data = await res.json();
    const profile = data.profile || {};
    const customAnswers = data.custom_answers || {};
    const resumeText = (data.resume_text || "").trim();
    const resumeFileName = data.resume_file_name;
    const resumeUrl = data.resume_url;
    
    // Cache data in storage
    await chrome.storage.local.set({ profile, customAnswers, resumeText });
    
    // Load and upload resume file via backend (backend proxies S3 to avoid CORS)
    if (resumeFileName || resumeUrl) {
      try {
        const path = resumeFileName ? `/chrome-extension/autofill/resume/${resumeFileName.split("/").pop()}` : "/chrome-extension/autofill/resume";
        const resumeRes = await fetchWithAuthRetry(`${apiBase}${path}`, { headers });
        if (resumeRes.ok) {
          const resumeBuffer = await resumeRes.arrayBuffer();
          const fileName = resumeFileName?.split("/").pop()?.split("?")[0] || resumeUrl?.split("/").pop()?.split("?")[0] || "resume.pdf";
          await chrome.runtime.sendMessage({
            type: "SAVE_RESUME",
            payload: {
              buffer: Array.from(new Uint8Array(resumeBuffer)),
              name: fileName
            }
          });
          logInfo("Resume uploaded to IndexedDB from API", { fileName });
        }
      } catch (resumeErr) {
        logWarn("Failed to upload resume from API", { error: String(resumeErr) });
      }
    }
    
    logInfo("Loaded autofill data from API", {
      profileKeys: Object.keys(profile).length,
      profileKeysPreview: Object.keys(profile).slice(0, 10),
      customAnswerKeys: Object.keys(customAnswers).length,
      resumeTextLen: resumeText.length,
      resumeFile: resumeFileName
    });
    
    DATA_LOADED = true;
    return { profile, customAnswers, resumeText };
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

function showProgress(stage, detail = "", isActive = false) {
  const card = document.getElementById("progress-card");
  const stageEl = document.getElementById("progress-stage");
  const detailEl = document.getElementById("progress-detail");
  if (!card || !stageEl || !detailEl) return;
  card.classList.remove("hidden");
  card.classList.toggle("active", !!isActive);
  stageEl.textContent = stage;
  detailEl.textContent = detail;
}

function showMappingProgress(fields, mappings) {
  const container = document.getElementById("mapping-progress");
  if (!container) return;
  
  container.classList.remove("hidden");
  container.innerHTML = "<h4>AI Mapping Results</h4>";
  
  const list = document.createElement("div");
  list.className = "mapping-list";
  
  fields.forEach((field, idx) => {
    const mapData = mappings[String(field.index)] || mappings[field.index];
    if (!mapData) return;
    
    const div = document.createElement("div");
    div.className = "mapping-row";
    
    const confidence = mapData.confidence || 0;
    const confidenceClass = confidence > 0.9 ? "high" : confidence > 0.7 ? "medium" : "low";
    
    div.innerHTML = `
      <div class="mapping-row-top">
        <span class="mapping-label">${field.label || field.name || "Field " + field.index}</span>
        <span class="mapping-confidence ${confidenceClass}">${Math.round(confidence * 100)}%</span>
      </div>
      <div class="mapping-value">${mapData.value || "(empty)"}</div>
    `;
    list.appendChild(div);
  });
  
  container.appendChild(list);
}

function hideMappingProgress() {
  const container = document.getElementById("mapping-progress");
  if (container) container.classList.add("hidden");
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

let CURRENT_FIELDS = [];

// -- Core Logic --

/** Send message to a specific frame; inject content script in that frame and retry once if needed. */
async function sendMessageToFrame(tabId, frameId, message) {
  try {
    return await chrome.tabs.sendMessage(tabId, message, { frameId });
  } catch (e) {
    if (!e?.message?.includes("Receiving end does not exist")) throw e;
    await chrome.scripting.executeScript({ target: { tabId, frameIds: [frameId] }, files: ["content.js"] });
    return await chrome.tabs.sendMessage(tabId, message, { frameId });
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

function buildValuesByFrame(fields, mappings) {
  const valuesByFrame = {};
  for (const field of fields) {
    const mapData = mappings[String(field.index)] || mappings[field.index];
    let value = mapData?.value;

    // Always attempt resume upload for file fields.
    if ((field.type || "").toLowerCase() === "file" && !value) value = "RESUME_FILE";
    if (value === undefined || value === null || value === "") continue;

    const frameId = String(field.frameId ?? 0);
    const localKey = String(field.frameLocalIndex ?? field.index);
    if (!valuesByFrame[frameId]) valuesByFrame[frameId] = {};
    valuesByFrame[frameId][localKey] = value;
  }
  return valuesByFrame;
}

async function fillMappedValuesForTab(tabId, fields, mappings) {
  const resumeRes = await chrome.runtime.sendMessage({ type: "GET_RESUME" });
  const resumeData = resumeRes?.ok ? resumeRes.data || null : null;
  const valuesByFrame = buildValuesByFrame(fields, mappings);
  const totalValues = Object.values(valuesByFrame).reduce(
    (sum, frameVals) => sum + Object.keys(frameVals).length,
    0
  );
  logInfo("Auto-filling mapped values", {
    frames: Object.keys(valuesByFrame).length,
    totalValues,
    hasResume: !!resumeData,
    valuesByFramePreview: Object.entries(valuesByFrame).map(([fid, vals]) => ({
      frameId: fid,
      valueCount: Object.keys(vals).length
    }))
  });

  const fillResponses = await sendMessageToAllFrames(tabId, (frameId) => ({
    type: "FILL_WITH_VALUES",
    payload: {
      values: valuesByFrame[String(frameId)] || {},
      resumeData,
      scope: "current_document"
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

async function trackAutofillUsed(pageUrl) {
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    await fetchWithAuthRetry(`${apiBase}/chrome-extension/autofill/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        page_url: pageUrl || "",
        company_name: null,
        job_url: pageUrl || null,
        job_title: null,
      }),
    });
  } catch (e) {
    logWarn("Failed to track autofill", { error: String(e) });
  }
}

document.getElementById("process-and-fill").addEventListener("click", async () => {
  const btn = document.getElementById("process-and-fill");
  btn.disabled = true;
  hideMappingProgress();
  showProgress("Preparing scan", "Connecting to active tab...", true);
  showStatus("Scraping page...", "loading");

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error("No active tab");
    logInfo("Starting scrape + map flow", { tabId: tab.id, url: tab.url || "" });

    trackAutofillUsed(tab.url || "");

    // Kick off context loading in parallel with DOM scraping for lower end-to-end latency.
    const contextPromise = getLLMMappingContext();

    // 1. Scrape all frames and merge (retry for JS-rendered forms).
    let fields = [];
    for (let attempt = 0; attempt < 3; attempt++) {
      showProgress("Scanning fields", attempt > 0 ? `Waiting for form... (attempt ${attempt + 1}/3)` : "Collecting input fields across all frames...", true);
      if (attempt > 0) await new Promise((r) => setTimeout(r, 1500 + attempt * 800));
      const scrapeResponses = await sendMessageToAllFrames(tab.id, () => ({
        type: "SCRAPE_FIELDS",
        payload: { scope: "all" }
      }));
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
    logInfo("DOM scrape response received", {
      fieldCount: fields.length,
      requiredFields: fields.filter((f) => !!f.required).length,
      framesScanned: scrapeResponses.length,
      framesWithFields: scrapeResponses.filter((r) => r.ok && r.res?.ok && (r.res.fields || []).length > 0).length,
    });

    CURRENT_FIELDS = fields;
    
    // 2. Load context from API
    showStatus("Loading profile data from API...", "loading");
    showProgress("Loading profile", "Fetching candidate profile and saved answers...", true);
    const context = await contextPromise;
    
    if (Object.keys(context.profile || {}).length === 0 && Object.keys(context.customAnswers || {}).length === 0) {
      showProgress("Profile unavailable", "Unable to fetch profile/custom answers from API.", false);
      showStatus("⚠ Failed to load profile data from API.", "error");
      btn.disabled = false;
      logWarn("API returned empty profile/custom answers data");
      return;
    }
    
    showStatus("Analyzing with AI...", "loading");
    showProgress("AI mapping", `Analyzing ${fields.length} fields with optimized routing...`, true);
    logInfo("Sending mapping request", {
      fieldCount: fields.length,
      profileKeys: Object.keys(context.profile || {}).length,
      customAnswers: Object.keys(context.customAnswers || {}).length,
      resumeTextLength: (context.resumeText || "").length
    });
    const cacheKey = getMappingCacheKey(fields, context);
    let mappings = getCachedMapping(cacheKey);
    if (mappings) {
      logInfo("Using cached mapping result", { fieldCount: Object.keys(mappings).length });
      showStatus("Using recent mapping result...");
    } else {
      const apiBase = await getApiBase();
      const headers = await getAuthHeaders();
      const mapRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/form-fields/map`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          fields: fields.map((field) => ({
            ...field,
            id: null
          })),
          profile: context.profile,
          custom_answers: context.customAnswers,
          resume_text: context.resumeText
        }),
      });

      if (!mapRes.ok) {
        throw new Error(`LLM mapping failed (${mapRes.status}).`);
      }
      const data = await mapRes.json();
      mappings = data.mappings || {};
      setCachedMapping(cacheKey, mappings);
    }
    logInfo("Mapping API response", {
      mappedFields: Object.keys(mappings).length,
      mappingsSample: Object.entries(mappings).slice(0, 5).map(([k, v]) => ({
        key: k,
        value: v?.value,
        confidence: v?.confidence
      }))
    });

    if (Object.keys(mappings).length === 0) {
      throw new Error("LLM mapping returned empty result.");
    }

    // Show mapping results first
    showMappingProgress(CURRENT_FIELDS, mappings);
    showStatus("Mapping complete. Filling form...", "info");

    // 3. Auto-fill directly (LLM-only flow)
    showProgress("Filling form", "Applying mapped values to detected inputs...", true);
    showStatus("Filling form...", "loading");
    const fillResult = await fillMappedValuesForTab(tab.id, CURRENT_FIELDS, mappings);
    showProgress("Completed", `Filled ${fillResult.totalFilled} fields successfully.`, false);
    showStatus(`✓ Filled ${fillResult.totalFilled} fields${fillResult.totalResumes > 0 ? " + uploaded resume" : ""}!`, "success");
    btn.disabled = false;
    logInfo("Fill completed successfully", fillResult);

  } catch (err) {
    showProgress("Failed", "Please retry after checking page access/API.", false);
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
