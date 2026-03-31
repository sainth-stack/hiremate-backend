/**
 * workday-step-manager.js
 * Manages Workday multi-step wizard navigation and per-step autofill.
 * Inject this into the page alongside scraper.js and filler.js.
 */
(function () {
  "use strict";

  const LOG = "[OpsBrain][workday-steps]";
  const log = (msg, meta) => meta !== undefined
    ? console.info(LOG, msg, meta)
    : console.info(LOG, msg);

  // Only run the full step manager in the top frame.
  // Sub-frames (iframes) get a lightweight no-op stub so content.js can
  // call startWorkdayAutofill safely without duplicate observers or
  // history-patching that breaks the host page's React Router.
  if (window.self !== window.top) {
    window.__OPSBRAIN_WORKDAY_STEPS__ = {
      startWorkdayAutofill: async () => {},
      handleCurrentStep: async () => {},
      getCurrentStepInfo: () => ({}),
      startWatching: () => {},
      stopWatching: () => {},
      getState: () => ({}),
    };
    log("Workday step manager loaded (iframe — stub only)");
    return;
  }

  // ─── STATE ────────────────────────────────────────────────────
  // Persisted across SPA navigations via closure (lives in content script)
  const state = {
    profileData: null,       // { values: {label: value}, resumeData: {...} } — set once at start
    filledSteps: new Set(),  // track which step URLs we already filled
    isRunning: false,
    observer: null,
    lastUrl: "",
    lastStepHash: "",
  };

  // ─── STEP DETECTION ───────────────────────────────────────────

  function getCurrentStepInfo(doc) {
    doc = doc || document;
    const url = (doc.defaultView?.location?.href || "").toLowerCase();
    const scraper = window.__OPSBRAIN_SCRAPER__;

    // Step 0: resume upload page
    if (scraper?.isWorkdayResumeOnlyStep?.(doc)) {
      return { step: 0, name: "resume_upload", shouldFill: false, shouldContinue: true };
    }

    // Step 6+: review/submit page — never auto-fill or auto-submit
    const heading = (doc.querySelector("h1,h2")?.textContent || "").toLowerCase();
    if (/review|submit|confirm|summary/.test(heading)) {
      return { step: 99, name: "review", shouldFill: false, shouldContinue: false };
    }

    // All other steps: fill fields
    return { step: 1, name: "form_step", shouldFill: true, shouldContinue: false };
  }

  function getStepKey(doc) {
    // Unique key for the current step — used to prevent double-filling
    const url = doc?.defaultView?.location?.href || window.location.href;
    // Use URL path + normalized heading (collapse whitespace to avoid re-trigger on React re-renders)
    const heading = (doc?.querySelector("h1,h2")?.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40);
    return `${url}|||${heading}`;
  }

  // ─── WAIT FOR STEP TO SETTLE ──────────────────────────────────
  // After SPA navigation, Workday takes 300–1500ms to render the new step's fields.

  async function waitForStepToSettle(doc, maxMs) {
    maxMs = maxMs || 4000;
    const start = Date.now();
    let lastCount = -1;
    let stableMs = 0;

    while (Date.now() - start < maxMs) {
      // Count visible interactive elements — wait until count is stable for 300ms
      const inputs = Array.from(doc.querySelectorAll(
        '[data-automation-id*="textInput"],[data-automation-id*="dropdown"],' +
        '[data-automation-id*="checkbox"],[data-automation-id*="radioButton"],' +
        'input[type="text"],input[type="email"],input[type="tel"],select,textarea,' +
        'input[type="file"],[class*="drop-zone"],[class*="dropzone"]'
      )).filter(el => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      });

      if (inputs.length === lastCount && inputs.length > 0) {
        stableMs += 100;
        if (stableMs >= 300) {
          log("Step settled", { inputCount: inputs.length, ms: Date.now() - start });
          return true;
        }
      } else {
        stableMs = 0;
        lastCount = inputs.length;
      }
      await new Promise(r => setTimeout(r, 100));
    }
    log("waitForStepToSettle: timeout, proceeding anyway");
    return false;
  }

  // ─── FIND CONTINUE BUTTON ─────────────────────────────────────

  function findContinueButton(doc) {
    const selectors = [
      "[data-automation-id='bottom-navigation-next-button']",
      "[data-automation-id='wd-CommandButton_uic_nextButton']",
      "button[data-automation-id*='continueButton']",
      "button[data-automation-id*='nextButton']",
      "button[data-automation-id*='next-button']",
      "button[data-automation-id*='continue']",
    ];
    for (const sel of selectors) {
      const btn = doc.querySelector(sel);
      if (btn && !btn.disabled) {
        const r = btn.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) return btn;
      }
    }
    // Last resort: bottom-right visible button
    const allBtns = Array.from(doc.querySelectorAll("button:not([disabled])"))
      .filter(b => {
        const r = b.getBoundingClientRect();
        const text = (b.textContent || "").trim().toLowerCase();
        // Must look like a "next" button, not "back" or "cancel"
        return r.width > 0 && r.height > 0 && r.top > window.innerHeight * 0.5
          && (text.includes("next") || text.includes("continue") || text.includes("save"));
      })
      .sort((a, b) => b.getBoundingClientRect().right - a.getBoundingClientRect().right);
    return allBtns[0] || null;
  }

  // ─── PER-STEP HANDLER ─────────────────────────────────────────

  async function handleCurrentStep(doc) {
    doc = doc || document;
    const stepKey = getStepKey(doc);
    const stepInfo = getCurrentStepInfo(doc);

    log("handleCurrentStep", { stepKey: stepKey.slice(0, 80), stepInfo });

    // Don't process the same step twice
    if (state.filledSteps.has(stepKey)) {
      log("Step already processed, skipping", { stepKey: stepKey.slice(0, 60) });
      return;
    }

    // ── Step 0: Resume upload ──────────────────────────────────
    if (stepInfo.step === 0) {
      state.filledSteps.add(stepKey);
      notifyStepToWidget("Resume Upload", "starting");
      const filler = window.__OPSBRAIN_FILLER__;
      if (filler?.handleWorkdayResumeStep) {
        await filler.handleWorkdayResumeStep(state.profileData?.resumeData, doc);
        notifyStepToWidget("Resume Upload", "filled");
        log("Resume step done — waiting for next step to load");
        // Navigation happens automatically after Continue click
        // Fallback: re-check after 2s in case MutationObserver/History API missed the transition
        setTimeout(() => {
          const newKey = getStepKey(doc);
          if (!state.filledSteps.has(newKey)) {
            log("Fallback: re-checking step after resume");
            handleCurrentStep(doc);
          }
        }, 2000);
        setTimeout(() => {
          const newKey = getStepKey(doc);
          if (!state.filledSteps.has(newKey)) {
            log("Fallback: second re-check after resume");
            handleCurrentStep(doc);
          }
        }, 4500);
      }
      return;
    }

    // ── Step 99: Review — do nothing ──────────────────────────
    if (stepInfo.step === 99) {
      notifyStepToWidget("Review & Submit", "review");
      log("Review step — not auto-filling or submitting");
      return;
    }

    // ── Normal form step ──────────────────────────────────────
    if (!stepInfo.shouldFill) return;
    if (!state.profileData) {
      notifyStepToWidget("Error", "error", { error: "No profile data" });
      log("No profileData available — cannot fill");
      return;
    }

    state.filledSteps.add(stepKey);
    const stepHeading = (doc.querySelector("h1,h2")?.textContent || "Form").trim().slice(0, 50);
    notifyStepToWidget(stepHeading, "starting", { fieldCount: 0 });

    // 1. Wait for the step's fields to render
    await waitForStepToSettle(doc);

    // 2. Scrape fields on this step
    const scraper = window.__OPSBRAIN_SCRAPER__;
    let scrapeResult;
    try {
      scrapeResult = await scraper.getScrapedFieldsWithExpandedOptions({ document: doc });
    } catch (e) {
      log("Scrape error", { error: String(e) });
      return;
    }

    if (!scrapeResult.fields.length) {
      notifyStepToWidget(stepHeading, "error", { error: "No fields found" });
      log("No fields found on this step");
      return;
    }
    notifyStepToWidget(stepHeading, "filling", { fieldCount: scrapeResult.fields.length });
    log("Fields scraped", { count: scrapeResult.fields.length });

    // 3. Get mappings from LLM API (for custom questions) + cache, merge with direct profile matches
    const values = await getMappingsForWorkdayStep(scrapeResult.fields, state.profileData, doc);
    log("Values matched", { matchCount: Object.keys(values).length });

    // 4. Fill fields
    const filler = window.__OPSBRAIN_FILLER__;
    const result = await filler.fillWithValuesHumanLike({
      fieldsForFrame: scrapeResult.fields,
      values,
      resumeData: state.profileData.resumeData,
    });
    log("Fill result", result);
    const filled = result?.filledCount ?? 0;
    if (filled > 0) {
      chrome.storage.local.get(["hm_autofill_total_fields"]).then((stored) => {
        const prev = stored.hm_autofill_total_fields || 0;
        chrome.storage.local.set({ hm_autofill_total_fields: prev + filled });
      }).catch(() => {});
    }
    notifyStepToWidget(stepHeading, "filled", { filledCount: filled });

    // 5. Small pause so user can see what was filled, then continue
    await new Promise(r => setTimeout(r, 800));
    // NOTE: Do NOT auto-click Continue on form steps by default.
    // Let the user review and click Continue themselves,
    // OR set autoContinue: true in profileData to enable it.
    if (state.profileData.autoContinue) {
      const btn = findContinueButton(doc);
      if (btn) {
        await filler.humanScrollTo(btn);
        await new Promise(r => setTimeout(r, 300));
        await filler.humanClick(btn);
        log("Auto-clicked Continue");
      }
    }
  }

  // ─── MAPPINGS (LLM + cache + direct profile) ───────────────────
  async function getMappingsForWorkdayStep(fields, profileData, doc) {
    const direct = matchValuesToFields(fields, profileData?.values);
    const context = profileData?.context;
    if (!context) return direct;

    const fetchMappings = window.__FETCH_MAPPINGS_FROM_API__;
    if (!fetchMappings) return direct;

    doc = doc || document;
    const domain = (doc?.defaultView?.location?.href || "").replace(/^https?:\/\//, "").split("/")[0] || "";
    const fps = fields.map((f) => f.fingerprint).filter(Boolean);
    let cachedByFp = {};
    try {
      const res = await chrome.runtime.sendMessage({ type: "GET_CACHED_MAPPINGS_BY_FP", payload: { fps, domain } });
      if (res?.ok && res.data) cachedByFp = res.data;
    } catch (_) {}

    const missFields = fields.filter((f) => !cachedByFp[f.fingerprint]);
    let apiMappings = {};
    if (missFields.length > 0) {
      try {
        apiMappings = await fetchMappings(missFields, context);
        const useCache = true;
        if (useCache) {
          const toCache = {};
          for (const f of missFields) {
            const m = apiMappings[f.fingerprint] ?? apiMappings[String(f.index)];
            if (m && m.value !== undefined) toCache[f.fingerprint] = m;
          }
          if (Object.keys(toCache).length > 0) {
            chrome.runtime.sendMessage({ type: "SET_CACHED_MAPPINGS_BY_FP", payload: { mappingsByFp: toCache, domain } }).catch(() => {});
          }
        }
      } catch (e) {
        log("Map API error, using direct matches only", { error: String(e) });
      }
    }

    const result = {};
    for (const field of fields) {
      const idx = String(field.frameLocalIndex ?? field.index);
      const cached = cachedByFp[field.fingerprint];
      const api = apiMappings[field.fingerprint] ?? apiMappings[String(field.index)];
      const mapped = cached ?? api;
      let val = mapped?.value;
      if (val === undefined || val === null || val === "") val = direct[idx];
      if (field.type === "file" || field.atsFieldType === "resume") val = val || "RESUME_FILE";
      if (val !== undefined && val !== null && val !== "") result[idx] = val;
    }
    return result;
  }

  // ─── VALUE MATCHING ───────────────────────────────────────────
  function matchValuesToFields(fields, profileValues) {
    if (!profileValues) return {};
    const result = {};

    for (const field of fields) {
      const idx = String(field.frameLocalIndex ?? field.index);

      // 1. Direct atsFieldType match
      const atsVal = profileValues[field.atsFieldType];
      if (atsVal !== undefined && atsVal !== null && atsVal !== "") {
        result[idx] = atsVal;
        continue;
      }

      // 2. Normalized label match
      const normLabel = (field.label || "")
        .toLowerCase().trim()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_|_$/g, "");
      const labelVal = profileValues[normLabel] || profileValues[field.label];
      if (labelVal !== undefined && labelVal !== null && labelVal !== "") {
        result[idx] = labelVal;
        continue;
      }

      // 3. Resume file field
      if (field.type === "file" || field.atsFieldType === "resume") {
        result[idx] = "RESUME_FILE";
      }
    }

    return result;
  }

  // ─── SPA NAVIGATION WATCHER ───────────────────────────────────
  // Workday uses History API pushState for step transitions.
  // We watch both URL changes and DOM mutations.

  function startWatching(doc) {
    doc = doc || document;
    if (state.observer) {
      state.observer.disconnect();
      state.observer = null;
    }

    state.lastUrl = doc.defaultView?.location?.href || "";
    state.lastStepHash = getStepKey(doc);

    // 1. Watch URL changes via MutationObserver on <body> (catches React re-renders)
    let debounceTimer = null;
    state.observer = new MutationObserver(() => {
      const currentUrl = doc.defaultView?.location?.href || "";
      const currentHash = getStepKey(doc);

      if (currentUrl !== state.lastUrl || currentHash !== state.lastStepHash) {
        state.lastUrl = currentUrl;
        state.lastStepHash = currentHash;

        // Debounce — wait for Workday to finish rendering the new step
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
          log("SPA navigation detected — handling new step");
          await handleCurrentStep(doc);
        }, 600); // 600ms debounce gives Workday time to render
      }
    });

    state.observer.observe(doc.body || doc.documentElement, {
      childList: true,
      subtree: true,
      attributes: false,
      characterData: false,
    });

    // NOTE: We intentionally do NOT patch window.history.pushState/replaceState.
    // Content scripts share browser API objects with the page, so patching history
    // is visible to the page's React Router and causes hydration mismatches (React
    // error #418). The MutationObserver above already catches URL changes via DOM
    // mutations triggered by every SPA navigation.
    log("Watching for Workday step navigation");
  }

  function stopWatching() {
    if (state.observer) {
      state.observer.disconnect();
      state.observer = null;
    }
    state.isRunning = false;
    log("Stopped watching");
  }

  // ─── PUBLIC API ───────────────────────────────────────────────

  /**
   * startWorkdayAutofill — main entry point
   *
   * Call this ONCE from content.js when the user clicks the extension button.
   *
   * @param {object} profileData — {
   *   values: { first_name, last_name, email, phone, ... },
   *   resumeData: { buffer: ArrayBuffer, name: string },
   *   autoContinue: boolean  // optional: auto-click Continue after filling
   * }
   */
  function notifyStepToWidget(stepName, phase, extra) {
    try {
      const target = window.top || window;
      target.postMessage({
        type: "OPSBRAIN_WORKDAY_STEP",
        stepName,
        phase,
        ...extra,
      }, "*");
    } catch (_) {}
  }

  async function startWorkdayAutofill(profileData, options = {}) {
    let forceRetry = options.forceRetry === true;
    if (state.isRunning && !forceRetry) {
      log("Already running — retrying current step");
      forceRetry = true;
    }
    if (state.isRunning && forceRetry) {
      state.profileData = profileData;
      const doc = document;
      const currentKey = getStepKey(doc);
      state.filledSteps.delete(currentKey);
      notifyStepToWidget("Retrying...", "retry", { stepKey: currentKey });
      await handleCurrentStep(doc);
      return;
    }
    state.isRunning = true;
    state.profileData = profileData;
    state.filledSteps.clear();

    log("Starting Workday autofill", {
      hasResume: !!profileData?.resumeData,
      valueKeys: Object.keys(profileData?.values || {}).slice(0, 10),
    });

    startWatching(document);
    await handleCurrentStep(document);
  }

  // ─── EXPORTS ──────────────────────────────────────────────────
  window.__OPSBRAIN_WORKDAY_STEPS__ = {
    startWorkdayAutofill,
    handleCurrentStep,
    getCurrentStepInfo,
    startWatching,
    stopWatching,
    getState: () => ({ ...state, observer: !!state.observer }),
  };

  log("Workday step manager loaded");
})();
