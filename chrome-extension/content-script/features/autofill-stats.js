// ─── Autofill Stats & Time Tracking ───────────────────────────────────────
// Depends on: AUTOFILL_TIME_SAVED_KEY, AVG_SECONDS_PER_FIELD (consts.js)
//             QUESTION_UI_ICONS (icons.js)
//             formatRelativeTimeFromIso (utils.js)
//             getApiBase, getAuthHeaders, fetchWithAuthRetry (defined in content.js)

/** Record autofill usage for dynamic time-saved display (~10 sec per field) */
async function recordAutofillFieldsFilled(count) {
  if (!count || count < 1) return;
  try {
    const stored = await chrome.storage.local.get([AUTOFILL_TIME_SAVED_KEY]);
    const prev = stored[AUTOFILL_TIME_SAVED_KEY] || 0;
    await chrome.storage.local.set({ [AUTOFILL_TIME_SAVED_KEY]: prev + count });
    const root = typeof document !== "undefined" && document.getElementById?.(INPAGE_ROOT_ID);
    if (root) await updateSavedTimeDisplay(root);
  } catch (_) { }
}

/** Idle hero copy: always "You have saved X minute(s) by autofilling so far 🔥" with bold minutes. */
async function getMinutesSavedHeroHtml() {
  try {
    const stored = await chrome.storage.local.get([AUTOFILL_TIME_SAVED_KEY]);
    const total = stored[AUTOFILL_TIME_SAVED_KEY] || 0;
    const mins = Math.max(0, Math.round((total * AVG_SECONDS_PER_FIELD) / 60));
    const minutePhrase = mins === 1 ? "1 minute" : `${mins} minutes`;
    return `You have saved <strong class="ja-hero-minutes-strong">${escapeHtml(minutePhrase)}</strong> by autofilling so far 🔥`;
  } catch (_) {
    return `You have saved <strong class="ja-hero-minutes-strong">${escapeHtml("0 minutes")}</strong> by autofilling so far 🔥`;
  }
}

function statusAreaHasFillResults(statusEl) {
  if (!statusEl) return false;
  const html = statusEl.innerHTML || "";
  const text = (statusEl.textContent || "").trim();
  return html.includes("ja-status-bullets") || /✓\s*Filled\s+\d+/.test(text) || /Fields need attention/.test(text);
}

/** Update idle hero minutes (call on mount / after fills / when idle). Single `#ja-status` only — no duplicate rows. */
async function updateSavedTimeDisplay(root) {
  const statusEl = root?.querySelector?.("#ja-status");
  const progressBlock = root?.querySelector?.("#ja-autofill-progress-block");
  const html = await getMinutesSavedHeroHtml();
  const isProgressVisible = progressBlock && !progressBlock.hasAttribute("hidden");
  if (isProgressVisible) return;
  if (statusEl && !statusAreaHasFillResults(statusEl)) {
    statusEl.innerHTML = html;
    statusEl.className = "ja-status ja-autofill-hero-sub ja-autofill-hero-saved";
  }
}

/** Footer stats (Last fill / applications filled): GET /api/chrome-extension/summary when signed in; else chrome.storage fallback.
 *  Deduped: API is called at most once per 5 minutes to prevent multiple rapid calls from widget-auth re-renders. */
async function updateAutofillFooterStats(root) {
  const now = Date.now();
  if (window.__HM_FOOTER_STATS_TS__ && now - window.__HM_FOOTER_STATS_TS__ < 300_000) return;
  window.__HM_FOOTER_STATS_TS__ = now;
  const lastEl = root?.querySelector?.("#ja-autofill-last-fill");
  const appsEl = root?.querySelector?.("#ja-autofill-apps-filled");
  if (!lastEl && !appsEl) return;

  let hasToken = false;
  try {
    const t = await chrome.storage.local.get(["accessToken"]);
    hasToken = !!t.accessToken;
  } catch (_) { }
  if (!hasToken) {
    try {
      const res = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
      if (res?.ok && res?.token) hasToken = true;
    } catch (_) { }
  }

  if (hasToken) {
    try {
      const apiBase = await getApiBase();
      const headers = await getAuthHeaders();
      if (headers.Authorization) {
        const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/summary`, { headers });
        if (res.ok) {
          const data = await res.json().catch(() => ({}));
          const apps = data.applications_filled;
          const lastIso = data.last_fill_time;
          if (lastEl) {
            const rel = formatRelativeTimeFromIso(lastIso);
            lastEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.clock}</span> Last fill: ${rel}`;
          }
          if (appsEl && typeof apps === "number" && Number.isFinite(apps)) {
            appsEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.layers}</span> ${apps} application${apps === 1 ? "" : "s"} filled`;
          }
          return;
        }
      }
    } catch (_) { }
  }

  try {
    const s = await chrome.storage.local.get(["hm_autofill_last_fill_label", "hm_autofill_apps_count"]);
    if (lastEl) {
      if (s.hm_autofill_last_fill_label) {
        lastEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.clock}</span> ${String(s.hm_autofill_last_fill_label)}`;
      } else {
        lastEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.clock}</span> Last fill: —`;
      }
    }
    if (appsEl) {
      if (typeof s.hm_autofill_apps_count === "number" && Number.isFinite(s.hm_autofill_apps_count)) {
        const n = s.hm_autofill_apps_count;
        appsEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.layers}</span> ${n} application${n === 1 ? "" : "s"} filled`;
      } else {
        appsEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.layers}</span> — applications filled`;
      }
    }
  } catch (_) {
    if (lastEl) {
      lastEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.clock}</span> Last fill: —`;
    }
    if (appsEl) {
      appsEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.layers}</span> — applications filled`;
    }
  }
}
