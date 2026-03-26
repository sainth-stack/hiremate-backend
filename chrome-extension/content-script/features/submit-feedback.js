// ─── Submit Feedback Feature ───────────────────────────────────────────────
// Captures autofill values on form submit to improve future mapping accuracy.
// Depends on: logInfo, logWarn (utils.js)
//             getApiBase, getAuthHeaders (api-service.js)
//             getDocuments (dom-utils.js)

function isIntermediateStep() {
  const bodyText = (document.body?.innerText || "").toLowerCase();
  const confirmSignals = [
    "application submitted",
    "thank you for applying",
    "application received",
    "successfully submitted",
    "we have received your application",
    "application complete",
  ];
  if (confirmSignals.some((s) => bodyText.includes(s))) return false;
  const nextButtonExists = !!document.querySelector(
    'button[type="submit"][data-automation-id*="next"], ' +
    '[data-automation-id="continueButton"], [data-automation-id*="continue"], ' +
    'button[aria-label*="Next"], button[aria-label*="Continue"], ' +
    ".next-button, #nextButton, [data-testid='next-btn']"
  );
  const hasStepIndicator = !!document.querySelector(
    ".progress-steps, .step-indicator, [aria-label*='Step '], " +
    ".wday-wizard-step, [data-automation-id*='progress'], [data-automation-id*='wizard']"
  );
  const isWorkdayUrl = /workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(location.href);
  if (isWorkdayUrl && (nextButtonExists || hasStepIndicator)) return true;
  return nextButtonExists || hasStepIndicator;
}

function mergePendingFields(existing, incoming) {
  const map = {};
  [...(existing || []), ...(incoming || [])].forEach((f) => {
    if (f.fingerprint) map[f.fingerprint] = f;
  });
  return Object.values(map);
}

const PENDING_TTL_MS = 4 * 60 * 60 * 1000; // 4 hours — treat as new session if older

/** Capture current form values before advancing to next Workday step. Stores for submit-feedback on final submit. */
async function captureAndStoreCurrentStepFeedback() {
  const lastFill = window.__OPSBRAIN_LAST_FILL__;
  if (!lastFill?.fields?.length || !lastFill?.mappings) return;
  const currentSessionId = window.__OPSBRAIN_SESSION_ID__;
  const docs = getDocuments(true);
  for (const doc of docs) {
    let overlappingCount = 0;
    for (const f of lastFill.fields) {
      try {
        const sel = f.selector || (f.selectors?.[0]?.selector);
        if (sel && doc.querySelector(sel)) overlappingCount++;
      } catch (_) { }
    }
    if (overlappingCount < 2) continue;
    const currentPageFields = lastFill.fields.map((f) => {
      let el = null;
      try {
        const sel = f.selector || (f.selectors?.[0]?.selector);
        if (sel) el = doc.querySelector(sel);
      } catch (_) { }
      const domValue = el ? (el.value ?? el.textContent ?? "").trim() : null;
      const autofillVal = lastFill.mappings[f.fingerprint]?.value ?? lastFill.mappings[String(f.index)]?.value;
      return {
        fingerprint: f.fingerprint,
        label: f.label,
        type: f.type,
        options: f.options || [],
        ats_platform: window.__OPSBRAIN_ATS__ || window.__PAGE_DETECTOR__?.platform || "workday",
        selector_used: f.selector || (f.selectors?.[0]?.selector),
        selector_type: (f.selectors?.[0]?.type) || "id",
        autofill_value: autofillVal,
        submitted_value: domValue,
        was_edited: domValue != null && domValue !== autofillVal,
      };
    });
    const cacheManager = window.__CACHE_MANAGER__;
    const pending = cacheManager ? await cacheManager.getPendingSubmission().catch(() => null) : null;
    const sessionMatch = currentSessionId && pending?.sessionId === currentSessionId;
    const ttlOk = !pending?.timestamp || (Date.now() - pending.timestamp) < PENDING_TTL_MS;
    const existingFields = sessionMatch && ttlOk ? (pending?.fields || []) : [];
    const allFields = mergePendingFields(existingFields, currentPageFields);
    if (cacheManager) await cacheManager.setPendingSubmission({ url: location.href, fields: allFields, sessionId: currentSessionId, timestamp: Date.now() });
    logInfo("Workday step — stored", allFields.length, "fields before advance");
    return;
  }
}

let _submitFeedbackAttached = false;
function attachSubmitFeedbackListener() {
  if (_submitFeedbackAttached) return;
  _submitFeedbackAttached = true;
  document.addEventListener("submit", handleFormSubmitForFeedback, true);
  // Workday: capture on Continue/Next click (user may have filled manually)
  document.addEventListener("click", (e) => {
    if (!/workday\.com|myworkdayjobs\.com/i.test(location.href)) return;
    const btn = e.target?.closest?.("button, [role='button'], input[type='submit']") || e.target;
    if (!btn) return;
    const text = (btn.textContent || btn.innerText || btn.value || "").trim().toLowerCase();
    const aid = (btn.getAttribute?.("data-automation-id") || "").toLowerCase();
    if (text.includes("continue") || text.includes("next") || aid.includes("continue") || aid.includes("next")) {
      captureAndStoreCurrentStepFeedback();
    }
  }, true);
}

async function handleFormSubmitForFeedback(e) {
  const lastFill = window.__OPSBRAIN_LAST_FILL__;
  if (!lastFill?.fields?.length || !lastFill?.mappings) return;
  await new Promise((r) => setTimeout(r, 0));
  let overlappingCount = 0;
  for (const f of lastFill.fields) {
    try {
      const sel = f.selector || (f.selectors?.[0]?.selector);
      if (sel && document.querySelector(sel)) overlappingCount++;
    } catch (_) { }
  }
  if (overlappingCount < 2) return;
  const currentPageFields = lastFill.fields.map((f) => {
    let el = null;
    try {
      const sel = f.selector || (f.selectors?.[0]?.selector);
      if (sel) el = document.querySelector(sel);
    } catch (_) { }
    const domValue = el ? (el.value ?? el.textContent ?? "").trim() : null;
    const autofillVal = lastFill.mappings[f.fingerprint]?.value ?? lastFill.mappings[String(f.index)]?.value;
    return {
      fingerprint: f.fingerprint,
      label: f.label,
      type: f.type,
      options: f.options || [],
      ats_platform: window.__OPSBRAIN_ATS__ || window.__PAGE_DETECTOR__?.platform || "unknown",
      selector_used: f.selector || (f.selectors?.[0]?.selector),
      selector_type: (f.selectors?.[0]?.type) || "id",
      autofill_value: autofillVal,
      submitted_value: domValue,
      was_edited: domValue != null && domValue !== autofillVal,
    };
  });
  const cacheManager = window.__CACHE_MANAGER__;
  const pending = cacheManager ? await cacheManager.getPendingSubmission().catch(() => null) : null;
  const currentSessionId = window.__OPSBRAIN_SESSION_ID__;
  const sessionMatch = currentSessionId && pending?.sessionId === currentSessionId;
  const ttlOk = !pending?.timestamp || (Date.now() - pending.timestamp) < PENDING_TTL_MS;
  const existingFields = sessionMatch && ttlOk ? (pending?.fields || []) : [];
  const allFields = mergePendingFields(existingFields, currentPageFields);

  if (isIntermediateStep()) {
    if (cacheManager) await cacheManager.setPendingSubmission({ url: location.href, fields: allFields, sessionId: currentSessionId || undefined, timestamp: Date.now() });
    logInfo("Intermediate step — accumulated", allFields.length, "fields");
    return;
  }

  logInfo("Final submit — sending", allFields.length, "fields");
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    if (!headers?.Authorization) return;
    const payload = {
      url: location.href,
      domain: location.hostname,
      ats: window.__OPSBRAIN_ATS__ || window.__PAGE_DETECTOR__?.platform || "unknown",
      fields: allFields,
    };
    const token = headers.Authorization?.replace("Bearer ", "");
    const url = token ? `${apiBase}/chrome-extension/form-fields/submit-feedback?token=${encodeURIComponent(token)}` : `${apiBase}/chrome-extension/form-fields/submit-feedback`;
    const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
    let ok = false;
    if (navigator.sendBeacon && navigator.sendBeacon(url, blob)) {
      logInfo("Submit feedback sent via sendBeacon");
      ok = true;
    } else {
      const res = await fetch(`${apiBase}/chrome-extension/form-fields/submit-feedback`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true,
      });
      ok = res.ok;
    }
    if (cacheManager) await cacheManager.clearPendingSubmission();
    window.__OPSBRAIN_SESSION_ID__ = null;
    window.__OPSBRAIN_LAST_FILL__ = null;
    chrome.runtime.sendMessage({ type: "INVALIDATE_MAPPING_CACHE" }).catch(() => { });
  } catch (err) {
    const retryCount = (pending?.retryCount || 0) + 1;
    if (retryCount <= 3 && cacheManager) {
      await cacheManager.setPendingSubmission({
        url: location.href,
        fields: allFields,
        sessionId: currentSessionId,
        timestamp: Date.now(),
        retryCount,
      });
      logWarn("Submit feedback failed, will retry", { error: String(err), retryCount });
    } else {
      if (cacheManager) await cacheManager.clearPendingSubmission();
      logWarn("Submit feedback failed, max retries reached", { error: String(err) });
    }
  }
}

async function retryPendingSubmission() {
  const cacheManager = window.__CACHE_MANAGER__;
  if (!cacheManager) return;
  const pending = await cacheManager.getPendingSubmission().catch(() => null);
  if (!pending?.fields?.length) return;
  if (pending.timestamp && Date.now() - pending.timestamp < 30000) return;
  logInfo("Retrying pending submission", pending.fields.length, "fields");
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    if (!headers?.Authorization) return;
    const res = await fetch(`${apiBase}/chrome-extension/form-fields/submit-feedback`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        url: pending.url || location.href,
        domain: pending.url ? new URL(pending.url).hostname : location.hostname,
        ats: "unknown",
        fields: pending.fields,
      }),
    });
    await cacheManager.clearPendingSubmission();
    if (res.ok) chrome.runtime.sendMessage({ type: "INVALIDATE_MAPPING_CACHE" }).catch(() => { });
  } catch (_) { }
}
