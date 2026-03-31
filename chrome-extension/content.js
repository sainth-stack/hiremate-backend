function mountInPageUI() {
  if (window.self !== window.top) return;
  const existing = document.getElementById(INPAGE_ROOT_ID);
  if (existing) {
    existing.classList.remove("collapsed");
    updateWidgetAuthUI(existing);
    if (isCareerPage()) trackCareerPageView();
    updateSavedTimeDisplay(existing);
    return;
  }

  const root = document.createElement("div");
  root.id = INPAGE_ROOT_ID;
  if (typeof window.__HM_PREACT_MOUNT_INPAGE__ === "function") {
    document.documentElement.appendChild(root);
    window.__HM_PREACT_MOUNT_INPAGE__(root);
    return;
  }
  mountInPageUILegacyInto(root);
  document.documentElement.appendChild(root);
  initColdEmailRadio();
}

function mountInPageUILegacyInto(root) {
  root.innerHTML = `${getWidgetStylesBase()}${getWidgetStylesComponents()}${getWidgetHTML()}`;
  document.documentElement.appendChild(root);

  updateWidgetAuthUI(root);
  if (isCareerPage()) trackCareerPageView();
  updateSavedTimeDisplay(root);

  // Render autofill accordions (Resume, Cover Letter, Unique Questions, Common Questions)
  const accordionsContainer = root.querySelector("#ja-autofill-accordions");
  if (accordionsContainer) {
    renderAccordions(accordionsContainer, [
      { id: "resume", iconBg: "#e9d5ff", iconSvg: ACCORDION_ICONS.document, title: "Resume", showHelpIcon: true },
      { id: "cover-letter", iconBg: "#fed7aa", iconSvg: ACCORDION_ICONS.coverLetter, title: "Cover Letter", statusText: "No Field Found" },
      { id: "unique-questions", iconBg: "#ede9fe", iconColor: "#7c3aed", iconSvg: ACCORDION_ICONS.star, title: "Unique Questions", statusText: "0/0", statusCheckmark: true },
      { id: "common-questions", iconBg: "#d1fae5", iconColor: "#15803d", iconSvg: ACCORDION_ICONS.person, title: "Common Questions", statusText: "0/0", statusCheckmark: true },
    ], root);
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes.accessToken) {
      updateWidgetAuthUI(root);
    }
  });

  // Re-check auth when user switches back to this tab (e.g. after logging in on HireMate)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      updateWidgetAuthUI(root);
    }
  });

  const autoAdvanceWrap = root.querySelector("#ja-auto-advance-wrap");
  if (autoAdvanceWrap) {
    const isWorkday = /workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(window.location.href);
    autoAdvanceWrap.style.display = isWorkday ? "flex" : "none";
    const autoAdvanceCheck = autoAdvanceWrap?.querySelector('input[type="checkbox"]');
    if (isWorkday && autoAdvanceCheck) autoAdvanceCheck.checked = true;
  }

  const CACHE_ENABLED_KEY = "hm_cache_enabled";
  const cacheEnableWrap = root.querySelector("#ja-cache-enable-wrap");
  const cacheEnableCheck = root.querySelector("#ja-cache-enable");
  if (cacheEnableWrap && cacheEnableCheck) {
    chrome.storage.local.get([CACHE_ENABLED_KEY]).then((stored) => {
      const enabled = stored[CACHE_ENABLED_KEY] !== false;
      cacheEnableCheck.checked = enabled;
    });
    cacheEnableCheck.addEventListener("change", () => {
      chrome.storage.local.set({ [CACHE_ENABLED_KEY]: cacheEnableCheck.checked });
    });
  }

  const statusEl = root.querySelector("#ja-status");
  const statusArea = root.querySelector("#ja-status-area");
  const progressBar = root.querySelector("#ja-progress");
  const progressBlock = root.querySelector("#ja-autofill-progress-block");
  const setAutofillProgressUI = (showProgress) => {
    if (showProgress) {
      progressBlock?.removeAttribute("hidden");
    } else {
      progressBlock?.setAttribute("hidden", "");
    }
  };
  const runBtn = root.querySelector("#ja-run");
  const stopBtn = root.querySelector("#ja-stop");
  const skipNextBtn = root.querySelector("#ja-skip-next");
  const fillControls = root.querySelector("#ja-fill-controls");
  const continueBtn = root.querySelector("#ja-continue-fill");
  const closeBtn = root.querySelector("#ja-close");
  const openBtn = root.querySelector("#ja-open");
  const dragHandle = root.querySelector("#ja-drag-handle");

  // Tab switching
  root.querySelectorAll(".ja-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      root.querySelectorAll(".ja-tab").forEach((t) => t.classList.remove("active"));
      root.querySelectorAll(".ja-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      const panel = root.querySelector("#ja-panel-" + tab.dataset.tab);
      if (panel) panel.classList.add("active");
      if (tab.dataset.tab === "profile") loadProfileIntoPanel(root);
      if (tab.dataset.tab === "keywords") loadKeywordsIntoPanel(root);
    });
  });

  root.querySelector("#ja-profile-refresh")?.addEventListener("click", () => loadProfileIntoPanel(root));
  root.querySelector("#ja-profile-edit")?.addEventListener("click", async () => {
    const data = await chrome.storage.local.get(["loginPageUrl"]);
    const base = data.loginPageUrl ? new URL(data.loginPageUrl).origin : "https://opsbrainai.com";
    chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url: `${base}/profile` });
  });
  root.querySelector("#ja-profile-preview")?.addEventListener("click", async () => {
    const ctx = root._profileCtx;
    if (!ctx) return;
    try {
      const got = await fetchProfileResumeBlob(ctx);
      if (!got) return;
      const url = URL.createObjectURL(got.blob);
      window.open(url, "_blank");
    } catch (_) { }
  });
  root.addEventListener("click", (e) => {
    const btn = e.target.closest(".ja-prof-copy");
    if (!btn || !root.contains(btn)) return;
    e.preventDefault();
    e.stopPropagation();
    const text = btn.getAttribute("data-copy") || "";
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      btn.classList.add("ja-prof-copy--done");
      setTimeout(() => btn.classList.remove("ja-prof-copy--done"), 1500);
    }).catch(() => { });
  });

  // Resume select change -> re-run keyword analysis
  root.addEventListener("change", (e) => {
    if (e.target.id === "ja-resume-select") loadKeywordsIntoPanel(root);
  });

  // Tailor Resume -> open /resume-generator
  root.querySelector("#ja-tailor-resume-btn")?.addEventListener("click", () => openResumeGeneratorUrl());

  // Update Job Description -> show form panel
  root.querySelector("#ja-update-jd-btn")?.addEventListener("click", async () => {
    const view = root.querySelector("#ja-keywords-view");
    const formPanel = root.querySelector("#ja-job-form-panel");
    if (view && formPanel) {
      view.style.display = "none";
      formPanel.style.display = "block";
      await prefillJobForm(root);
    }
  });

  // Go Back from job form
  root.querySelector("#ja-job-go-back")?.addEventListener("click", () => {
    const view = root.querySelector("#ja-keywords-view");
    const formPanel = root.querySelector("#ja-job-form-panel");
    if (view && formPanel) {
      formPanel.style.display = "none";
      view.style.display = "block";
    }
  });

  // Save Job form submit
  root.querySelector("#ja-job-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    await saveJobFromForm(root);
  });

  const setStatus = (text, type = "", asHtml = false) => {
    if (!statusEl) return;
    if (asHtml) statusEl.innerHTML = text;
    else statusEl.textContent = text;
    statusEl.className = `ja-status ja-autofill-hero-sub ${type}`.trim();
    statusArea?.classList.toggle("loading", type === "loading");
  };

  const setProgress = (percent) => {
    const p = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    if (progressBar) progressBar.style.width = `${p}%`;
    const pctEl = root.querySelector("#ja-progress-text");
    if (pctEl) pctEl.textContent = `${p}%`;
  };

  // Dragging (vertical only, stays on right side)
  let isDragging = false;
  let dragStartY = 0;
  let initialTop = 80;
  let didDrag = false;

  const startDrag = (e) => {
    if (e.target.closest('button') && !e.target.closest('#ja-open')) return;
    isDragging = true;
    didDrag = false;
    dragStartY = e.clientY;
    initialTop = parseInt(root.style.top) || 80;
  };

  dragHandle?.addEventListener("mousedown", startDrag);
  openBtn?.addEventListener("mousedown", startDrag);

  document.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    e.preventDefault();
    didDrag = true;
    const deltaY = e.clientY - dragStartY;
    let newTop = initialTop + deltaY;
    const minH = root.classList.contains("collapsed") ? 48 : root.offsetHeight;
    const maxY = window.innerHeight - minH - 20;
    newTop = Math.max(20, Math.min(newTop, maxY));
    root.style.top = newTop + "px";
    root.style.right = "20px";
    root.style.left = "auto";
  });

  document.addEventListener("mouseup", () => {
    if (isDragging) {
      initialTop = parseInt(root.style.top) || 80;
    }
    isDragging = false;
  });

  closeBtn?.addEventListener("click", () => root.classList.add("collapsed"));
  openBtn?.addEventListener("click", (e) => {
    if (didDrag) return;
    root.classList.remove("collapsed");
  });

  // Report Issue button — opens the web app in a new tab
  root.querySelector("#ja-report-issue")?.addEventListener("click", async () => {
    const data = await chrome.storage.local.get(["loginPageUrl"]);
    const base = data.loginPageUrl ? new URL(data.loginPageUrl).origin : "https://opsbrainai.com";
    chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url: `${base}/report-issue` });
  });

  // ─── Initial load: quick field scan + parallel API calls ─────────────────
  (async () => {
    // 1. Quick DOM scan — just labels, NO scrolling, NO option loading, NO iframes
    //    Full scrape (with scrolling/options/pre-expand) happens only on Autofill click.
    try {
      const SKIP_TYPES = new Set(["hidden", "submit", "button", "reset", "image", "file"]);
      const seen = new Set();
      const fields = [];
      document.querySelectorAll("input, select, textarea").forEach((el) => {
        if (SKIP_TYPES.has((el.type || "").toLowerCase())) return;
        if (!el.offsetParent && el.type !== "radio" && el.type !== "checkbox") return;
        let label = el.labels?.[0]?.textContent?.trim() || "";
        if (!label) label = el.getAttribute("aria-label")?.trim() || "";
        if (!label) {
          const lbId = el.getAttribute("aria-labelledby");
          if (lbId) label = document.getElementById(lbId)?.textContent?.trim() || "";
        }
        if (!label) label = el.placeholder?.trim() || el.name?.trim() || "";
        if (!label) return;
        const key = label.toLowerCase() + "|" + (el.name || el.id || "");
        if (seen.has(key)) return;
        seen.add(key);
        fields.push({ label, type: el.type || el.tagName.toLowerCase(), name: el.name || "", id: el.id || "", placeholder: el.placeholder || "", index: fields.length });
      });
      window.__OPSBRAIN_SCRAPED_FIELDS__ = fields;

      if (fields.length > 0) {
        const countBadge = root.querySelector("#ja-fields-count");
        if (countBadge) countBadge.textContent = `${fields.length}/${fields.length} fields`;

        // Update Common/Unique question count badges
        const commonKeys = ["firstname", "lastname", "email", "phone", "address", "linkedin", "github", "portfolio", "resume", "coverletter", "country", "city"];
        const isCommonField = (f) => {
          const keys = getFieldKeys({ label: f.label, name: f.name, id: f.id, placeholder: f.placeholder });
          return commonKeys.some(k => keys.some(fk => fk.includes(k) || k.includes(fk)));
        };
        const common = fields.filter(isCommonField);
        const unique = fields.filter(f => !isCommonField(f));
        const uqStatus = root.querySelector('[data-accordion-id="unique-questions"] .ja-accordion-status-text');
        const cqStatus = root.querySelector('[data-accordion-id="common-questions"] .ja-accordion-status-text');
        if (uqStatus) uqStatus.textContent = `0/${unique.length}`;
        if (cqStatus) cqStatus.textContent = `0/${common.length}`;
      }
    } catch (_) {}

    // 2. Parallel: resume workspace + summary stats (guarded — run only once per mount)
    if (!window.__HM_INIT_APIS_DONE__) {
      window.__HM_INIT_APIS_DONE__ = true;
      // summary is called by widget-auth.js on mount; fetchResumesFromApi is the only new parallel call needed
      const [resumeResult, _] = await Promise.allSettled([
        fetchResumesFromApi(),
        updateAutofillFooterStats(root),   // explicit call ensures stats load even if auth fires first
      ]);
      // 3. Cache resumes globally so accordions don't need to re-fetch
      window.__OPSBRAIN_RESUMES__ = resumeResult.status === "fulfilled" ? resumeResult.value : [];
    }
  })();

  let abortRequested = false;
  let skipToNextRequested = false;

  const runOneStep = async (stepNum = 1) => {
    const t0 = Date.now();
    logInfo("runOneStep: start", { stepNum });
    setStatus(stepNum > 1 ? `Step ${stepNum} — Extracting fields...` : "Extracting form fields...", "loading");
    setProgress(5);
    setStatus("Loading profile...", "loading");
    try {
      logInfo("runOneStep: refreshTokenViaApi");
      await refreshTokenViaApi();
      logInfo("runOneStep: refreshToken done", { ms: Date.now() - t0 });
    } catch (_) { }
    logInfo("runOneStep: getAutofillContextFromApi");
    const context = await getAutofillContextFromApi();
    logInfo("runOneStep: context loaded", { profileKeys: Object.keys(context?.profile || {}).length, ms: Date.now() - t0 });
    const experiences = context?.profile?.experiences || [];
    const educations = context?.profile?.educations || [];
    const preExpandEmployment = Math.max(0, experiences.length - 1);
    const preExpandEducation = Math.max(0, educations.length - 1);
    let fields = [];
    for (let attempt = 0; attempt < 3; attempt++) {
      if (attempt > 0) {
        setStatus(`Waiting for form to load... (attempt ${attempt + 1}/3)`, "loading");
        await new Promise((r) => setTimeout(r, 1500 + attempt * 1000));
      }
      logInfo("runOneStep: sending SCRAPE_ALL_FRAMES", { attempt: attempt + 1 });
      const scrapeRes = await chrome.runtime.sendMessage({
        type: "SCRAPE_ALL_FRAMES",
        scope: "all",
        preExpandEmployment,
        preExpandEducation,
        maxEducationBlocks: educations.length || 999,
        maxEmploymentBlocks: experiences.length || 999,
      });
      logInfo("runOneStep: SCRAPE_ALL_FRAMES response", { ok: scrapeRes?.ok, fieldCount: scrapeRes?.fields?.length ?? 0 });
      if (scrapeRes?.ok && scrapeRes.fields?.length) {
        fields = scrapeRes.fields;
        break;
      }
    }
    if (!fields.length) throw new Error("No form fields found. Click \"Apply\" on a job to open the application form, then try again.");

    setStatus(`Found ${fields.length} fields — loading profile & resume...`, "loading");
    setProgress(15);
    let resumeData = await getResumeFromBackground();
    if (!resumeData && (context.resumeUrl || context.resumeFileName)) {
      resumeData = await fetchResumeFromContext(context);
    }
    if (!resumeData) resumeData = await getStaticResume();
    if (resumeData && context?.resumeName) {
      const displayName = sanitizeResumeFilename(context.resumeName);
      if (displayName) resumeData = { ...resumeData, name: displayName };
    }

    setStatus("Mapping fields with AI...", "loading");
    setProgress(35);
    const domain = location.hostname;
    const fps = fields.map((f) => f.fingerprint).filter(Boolean);
    const useCache = root.querySelector("#ja-cache-enable")?.checked !== false;
    let cachedByFp = {};
    if (useCache) {
      try {
        const res = await chrome.runtime.sendMessage({ type: "GET_CACHED_MAPPINGS_BY_FP", payload: { fps, domain } });
        if (res?.ok && res.data) cachedByFp = res.data;
      } catch (_) { }
    }
    const missFields = fields.filter((f) => !cachedByFp[f.fingerprint]);
    let mappings = {};
    for (const f of fields) {
      const m = cachedByFp[f.fingerprint];
      if (m) {
        mappings[f.fingerprint] = m;
        mappings[String(f.index)] = m;
      }
    }
    if (missFields.length > 0) {
      const apiMappings = await fetchMappingsFromApi(missFields, context);
      Object.assign(mappings, apiMappings);
      if (useCache) {
        const toCache = {};
        for (const f of missFields) {
          const m = apiMappings[f.fingerprint] ?? apiMappings[String(f.index)];
          if (m && m.value !== undefined) toCache[f.fingerprint] = m;
        }
        if (Object.keys(toCache).length > 0) {
          chrome.runtime.sendMessage({ type: "SET_CACHED_MAPPINGS_BY_FP", payload: { mappingsByFp: toCache, domain } }).catch(() => { });
        }
      }
    }
    if (!Object.keys(mappings).length) throw new Error("No mapping returned");

    setStatus("Preparing to fill...", "loading");
    setProgress(50);

    const maxEdu = educations.length > 0 ? educations.length : 999;
    const maxEmp = experiences.length > 0 ? experiences.length : 999;
    const valuesByFrame = buildValuesByFrameWithLimits(fields, mappings, maxEdu, maxEmp);
    const fieldsByFrame = buildFieldsByFrame(fields);
    const lastFill = { fields, mappings };

    const fillRes = await chrome.runtime.sendMessage({
      type: "FILL_ALL_FRAMES",
      payload: { valuesByFrame, fieldsByFrame, resumeData, lastFill },
    });

    if (!fillRes?.ok) throw new Error(fillRes?.error || "Fill failed");
    return { filledCount: fillRes.totalFilled || 0, resumeUploadCount: fillRes.totalResumes || 0, failedCount: 0, failedFields: [] };
  };

  const doContinueAndAdvance = async () => {
    const docs = getDocuments(true);
    let btn = null;
    for (const doc of docs) {
      btn = findContinueButton(doc);
      if (btn) break;
    }
    if (btn) {
      // Capture user-filled values before advancing (Workday multi-step: store for learning)
      await captureAndStoreCurrentStepFeedback();
      btn.click();
      await delay(3500);
      return true;
    }
    return false;
  };

  const scrollToField = (field) => {
    if (!field?.isConnected) return;
    scrollFieldIntoView(field);
    try {
      field.focus();
    } catch (_) { }
  };

  const runFlow = async (isContinueFromErrors = false) => {
    if (!runBtn) return;
    setAutofillProgressUI(true);
    setProgress(0);
    const SESSION_ID = crypto.randomUUID();
    window.__OPSBRAIN_SESSION_ID__ = SESSION_ID;
    runBtn.disabled = true;
    runBtn.style.display = "none";
    fillControls?.classList.add("visible");
    continueBtn?.style.setProperty("display", "none");
    abortRequested = false;
    skipToNextRequested = false;
    const saveAppliedBtn = root.querySelector("#ja-save-applied");
    if (saveAppliedBtn) {
      saveAppliedBtn.textContent = "Save & Mark Applied";
      saveAppliedBtn.disabled = false;
    }

    trackAutofillUsed();

    const scraper = window.__OPSBRAIN_SCRAPER__ || window.__HIREMATE_FIELD_SCRAPER__;
    const platform = scraper?.detectPlatform?.(document) || "unknown";
    const isWorkday = platform === "workday";

    // Workday: use step manager (multi-step SPA wizard)
    if (isWorkday) {
      const stepManager = window.__OPSBRAIN_WORKDAY_STEPS__;
      if (!stepManager) {
        setStatus("Workday step manager not loaded. Reload the page.", "error");
        runBtn.disabled = false;
        runBtn.style.display = "";
        fillControls?.classList.remove("visible");
        setAutofillProgressUI(false);
        updateSavedTimeDisplay(root);
        return;
      }
      try {
        setStatus("Loading profile & resume for Workday...", "loading");
        setProgress(15);
        await refreshTokenViaApi();
        const context = await getAutofillContextFromApi();
        let resumeData = await getResumeFromBackground();
        if (!resumeData && (context.resumeUrl || context.resumeFileName)) {
          resumeData = await fetchResumeFromContext(context);
        }
        if (!resumeData) resumeData = await getStaticResume();
        if (resumeData && context?.resumeName) {
          const displayName = sanitizeResumeFilename(context.resumeName);
          if (displayName) resumeData = { ...resumeData, name: displayName };
        }
        const profileValues = buildProfileValuesForWorkday(context);
        const autoContinue = root.querySelector("#ja-auto-advance")?.checked ?? false;
        setStatus("Starting Workday autofill...", "loading");
        setProgress(50);
        const profileData = {
          values: profileValues,
          resumeData,
          autoContinue,
          context: { profile: context.profile, customAnswers: context.customAnswers || {}, resumeText: context.resumeText || "" },
        };
        await chrome.runtime.sendMessage({
          type: "START_WORKDAY_AUTOFILL",
          payload: { profileData },
        });
        setProgress(100);
        setStatus("Workday autofill started. Fill steps as they appear.", "success");
      } catch (err) {
        setProgress(0);
        setStatus(err?.message || "Workday autofill failed", "error");
        logWarn("Workday autofill failed", { error: String(err) });
      } finally {
        runBtn.disabled = false;
        runBtn.style.display = "";
        fillControls?.classList.remove("visible");
        setAutofillProgressUI(false);
        updateSavedTimeDisplay(root);
      }
      return;
    }

    const autoAdvance = root.querySelector("#ja-auto-advance")?.checked;
    const maxSteps = 8;
    let totalFilled = 0;
    let totalResumes = 0;
    let totalFailed = 0;
    let lastFailedFields = [];

    try {
      for (let step = 1; step <= maxSteps; step++) {
        if (abortRequested) {
          setStatus("Stopped", "success");
          break;
        }
        const result = await runOneStep(step);
        totalFilled += result.filledCount;
        totalResumes += result.resumeUploadCount;
        totalFailed += result.failedCount;
        lastFailedFields = result.failedFields || [];

        setProgress(100);
        const bullets = [];
        if (totalFilled > 0) bullets.push(`✓ Filled ${totalFilled} field${totalFilled === 1 ? "" : "s"}`);
        if (totalResumes > 0) bullets.push(`✓ Uploaded resume`);
        if (totalFailed > 0) {
          if (lastFailedFields.length > 0) {
            const fieldItems = lastFailedFields.map((ff, idx) => {
              const label = String(ff.label || `Field ${idx + 1}`).replace(/</g, "&lt;").replace(/>/g, "&gt;");
              return `<li class="ja-failed-field-item"><button type="button" class="ja-failed-field-link" data-failed-index="${idx}">⚠ ${label}</button></li>`;
            }).join("");
            bullets.push(`<span class="ja-fields-need-attention">Fields need attention:</span><ul class="ja-failed-fields-list">${fieldItems}</ul>`);
          } else {
            bullets.push(`⚠ ${totalFailed} field${totalFailed === 1 ? "" : "s"} need attention`);
          }
        }
        const statusHtml = bullets.length > 0 ? `<ul class="ja-status-bullets">${bullets.map((b) => `<li>${b}</li>`).join("")}</ul>` : "Done";
        setStatus(statusHtml, "success", true);

        const quickSaveRow = root.querySelector("#ja-quick-save-row");
        if (quickSaveRow) quickSaveRow.style.display = totalFilled > 0 ? "block" : "none";

        if (lastFailedFields.length > 0) {
          root.querySelectorAll(".ja-failed-field-link").forEach((btn, idx) => {
            btn.onclick = () => {
              const ff = lastFailedFields[idx];
              if (ff?.element?.isConnected) scrollToField(ff.element);
            };
          });
        }

        if (!autoAdvance || !isWorkday || step >= maxSteps) break;

        const hasUnfilledFields = result.failedCount > 0;

        if (hasUnfilledFields) {
          bullets.push('<span class="ja-note">Fix the highlighted fields, then click Continue filling</span>');
          setStatus(`<ul class="ja-status-bullets">${bullets.map((b) => `<li>${b}</li>`).join("")}</ul>`, "success", true);
          if (lastFailedFields.length > 0) {
            root.querySelectorAll(".ja-failed-field-link").forEach((btn, idx) => {
              btn.onclick = () => {
                const ff = lastFailedFields[idx];
                if (ff?.element?.isConnected) scrollToField(ff.element);
              };
            });
          }
          continueBtn?.style.setProperty("display", "block");
          break;
        }

        const advanced = await doContinueAndAdvance();
        if (!advanced) break;

        setStatus(`Step ${step} done — advancing to next...`, "loading");
      }
    } catch (err) {
      setProgress(0);
      setStatus(err?.message || "Autofill failed", "error");
      logWarn("In-page autofill failed", { error: String(err) });
    } finally {
      runBtn.disabled = false;
      runBtn.style.display = "";
      fillControls?.classList.remove("visible");
      setAutofillProgressUI(false);
      updateSavedTimeDisplay(root);
      const qsr = root.querySelector("#ja-quick-save-row");
      if (qsr) qsr.style.display = "none";
    }
  };

  async function quickSaveAsApplied() {
    const btn = root.querySelector("#ja-save-applied");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Saving...";
    }
    setStatus("Saving to tracker...", "loading");
    try {
      const apiBase = await getApiBase();
      const headers = await getAuthHeaders();
      const { company, position, location } = extractCompanyAndPosition();
      const payload = {
        company: company || "",
        position_title: position || "",
        location: location || "",
        job_posting_url: window.location.href || null,
        application_status: "applied",
      };
      const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setStatus("Saved to tracker.", "success");
        if (btn) btn.textContent = "Saved!";
      } else {
        setStatus("Save failed. Try Save Job Instead.", "error");
        if (btn) {
          btn.disabled = false;
          btn.textContent = "Save & Mark Applied";
        }
      }
    } catch (err) {
      logWarn("Quick save as applied failed", { error: String(err) });
      setStatus("Save failed. Try Save Job Instead.", "error");
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Save & Mark Applied";
      }
    }
  }

  root.querySelector("#ja-save-applied")?.addEventListener("click", quickSaveAsApplied);

  root.querySelector("#ja-save-job-instead")?.addEventListener("click", async () => {
    root.querySelectorAll(".ja-tab").forEach((t) => t.classList.remove("active"));
    root.querySelectorAll(".ja-panel").forEach((p) => p.classList.remove("active"));
    const kwTab = root.querySelector('[data-tab="keywords"]');
    const kwPanel = root.querySelector("#ja-panel-keywords");
    if (kwTab) kwTab.classList.add("active");
    if (kwPanel) kwPanel.classList.add("active");
    loadKeywordsIntoPanel(root);
    const view = root.querySelector("#ja-keywords-view");
    const formPanel = root.querySelector("#ja-job-form-panel");
    if (view && formPanel) {
      view.style.display = "none";
      formPanel.style.display = "block";
      await prefillJobForm(root);
      const statusSelect = root.querySelector("#ja-job-status");
      if (statusSelect) statusSelect.value = "I have not yet applied";
    }
  });

  runBtn?.addEventListener("click", () => runFlow(false));

  stopBtn?.addEventListener("click", () => {
    abortRequested = true;
    chrome.runtime.sendMessage({ type: "STOP_WORKDAY_AUTOFILL" }).catch(() => { });
    window.__OPSBRAIN_WORKDAY_STEPS__?.stopWatching();
  });

  skipNextBtn?.addEventListener("click", () => {
    skipToNextRequested = true;
  });

  continueBtn?.addEventListener("click", async () => {
    continueBtn.style.display = "none";
    setStatus("Advancing to next step...", "loading");
    const advanced = await doContinueAndAdvance();
    if (advanced) {
      runFlow(false);
    } else {
      setStatus("Continue button not found. Click it manually.", "error");
    }
  });
}

// ── Settings Panel + Cold Email Toggle ──────────────────────────────────
function initColdEmailRadio() {
  const STORAGE_KEY = "hm_cold_agent_mode";
  const root = document.getElementById(INPAGE_ROOT_ID);
  if (!root) return;

  const settingsBtn = root.querySelector("#ja-open-settings");
  const settingsPanel = root.querySelector("#ja-settings-panel");
  const settingsBack = root.querySelector("#ja-settings-back");
  const coldToggle = root.querySelector("#hm-cold-toggle");
  const tabs = root.querySelector(".ja-tabs");
  const body = root.querySelector(".ja-body");

  if (!settingsBtn || !settingsPanel || !settingsBack || !coldToggle) return;

  // Restore saved toggle state
  chrome.storage.local.get([STORAGE_KEY], (result) => {
    const mode = result[STORAGE_KEY] || "standard";
    coldToggle.checked = mode === "cold";
    if (mode === "cold" && window.__HM_COLD_EMAIL__?.isLinkedInMessagingPage?.()) {
      window.__HM_COLD_EMAIL__.stopColdEmailModule();
      window.__HM_COLD_EMAIL__.startColdEmailModule();
    }
  });

  // Open settings
  settingsBtn.addEventListener("click", () => {
    settingsPanel.style.display = "flex";
    if (tabs) tabs.style.display = "none";
    if (body) body.style.display = "none";
  });

  // Back to main
  settingsBack.addEventListener("click", () => {
    settingsPanel.style.display = "none";
    if (tabs) tabs.style.display = "";
    if (body) body.style.display = "";
  });

  // Toggle cold email mode
  coldToggle.addEventListener("change", () => {
    const mode = coldToggle.checked ? "cold" : "standard";
    chrome.storage.local.set({ [STORAGE_KEY]: mode });
    if (mode === "cold") {
      // Stop first to reset internal state, then start fresh
      window.__HM_COLD_EMAIL__?.stopColdEmailModule?.();
      window.__HM_COLD_EMAIL__?.startColdEmailModule?.();
    } else {
      window.__HM_COLD_EMAIL__?.stopColdEmailModule?.();
    }
  });
}

window.__HM_MOUNT_INPAGE_INTO__ = mountInPageUILegacyInto;

// Auto-start cold email module on LinkedIn without requiring the widget to open
if (location.hostname.includes("linkedin.com")) {
  chrome.storage.local.get(["hm_cold_agent_mode"], function (result) {
    if (result["hm_cold_agent_mode"] === "cold") {
      setTimeout(function () {
        if (window.__HM_COLD_EMAIL__) {
          window.__HM_COLD_EMAIL__.stopColdEmailModule();
          window.__HM_COLD_EMAIL__.startColdEmailModule();
        }
      }, 600);
    }
  });
}

// Sync token from website when user logs in on HireMate frontend.
// Content scripts share the page's origin and can read localStorage directly—no inline script injection (avoids CSP violations).
function syncTokenFromWebsite() {
  if (!LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o)) return;
  try {
    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    if (token) {
      chrome.storage.local.set({ accessToken: token });
      logInfo("Token synced from website");
    }
  } catch (e) { }
}
if (LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o)) {
  syncTokenFromWebsite();
  setTimeout(syncTokenFromWebsite, 2000);
  setTimeout(syncTokenFromWebsite, 5000);
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  logInfo("Received message", { type: msg?.type || "unknown" });

  if (msg.type === "SHOW_WIDGET") {
    mountInPageUI();
    if (isCareerPage() && !/workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(window.location.href)) {
      runKeywordAnalysisAndMaybeShowWidget();
    }
    const widget = document.getElementById(INPAGE_ROOT_ID);
    if (widget) {
      const card = widget.querySelector(".ja-card");
      if (card) card.classList.remove("collapsed");
    }
    sendResponse({ ok: true });
    return true;
  }

  if (msg.type === "STOP_WORKDAY_AUTOFILL") {
    window.__OPSBRAIN_WORKDAY_STEPS__?.stopWatching();
    sendResponse({ ok: true });
    return true;
  }

  if (msg.type === "START_WORKDAY_AUTOFILL") {
    const profileData = msg.payload?.profileData;
    if (!profileData) {
      sendResponse({ ok: false, error: "Missing profileData" });
      return true;
    }
    const url = (typeof location !== "undefined" && location?.href) || "";
    const isWorkdayFrame = /workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(url);
    // Only run in the frame that has the form — avoids duplicate runs across iframes that trigger definition API bursts
    const hasForm = document.body && (
      document.querySelector('[id*="primaryQuestionnaire"]') ||
      document.querySelector('[data-automation-id*="formField"]') ||
      document.querySelector('[data-automation-id*="textInput"]')
    );
    const stepManager = window.__OPSBRAIN_WORKDAY_STEPS__;
    if (stepManager && isWorkdayFrame && hasForm) {
      stepManager.startWorkdayAutofill(profileData).then(() => sendResponse({ ok: true })).catch((e) => sendResponse({ ok: false, error: String(e) }));
    } else {
      sendResponse({ ok: true });
    }
    return true;
  }

  if (msg.type === "SCRAPE_FIELDS") {
    const payload = msg.payload || {};
    const tScrape = Date.now();
    logInfo("SCRAPE_FIELDS received", { scope: payload.scope, frameId: typeof window !== "undefined" ? "(content)" : "?", url: location?.href?.slice(0, 60) });
    scrapeFields(payload)
      .then((result) => {
        logInfo("SCRAPE_FIELDS done", { fieldCount: result?.fields?.length || 0, ms: Date.now() - tScrape });
        sendResponse({ ok: true, ...result });
      })
      .catch((e) => {
        logWarn("SCRAPE_FIELDS failed", { error: String(e), ms: Date.now() - tScrape });
        sendResponse({ ok: false, error: String(e) });
      });
    return true;
  }

  if (msg.type === "FILL_WITH_VALUES") {
    const p = msg.payload || {};
    if (p.lastFill) {
      window.__OPSBRAIN_LAST_FILL__ = p.lastFill;
    }
    logInfo("Fill: received FILL_WITH_VALUES", {
      valueCount: Object.keys(p.values || {}).length,
      hasResume: !!p.resumeData,
      scope: p.scope,
    });
    const FILL_TIMEOUT_MS = 90000; // 90s max - prevents indefinite hang
    const startFill = Date.now();
    const payloadWithAbort = {
      ...p,
      shouldAbort: p.shouldAbort
        ? () => p.shouldAbort() || Date.now() - startFill > FILL_TIMEOUT_MS - 5000
        : () => Date.now() - startFill > FILL_TIMEOUT_MS - 5000,
    };
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Fill timed out after 90s — try fewer fields or refresh")), FILL_TIMEOUT_MS)
    );
    Promise.race([fillWithValues(payloadWithAbort), timeoutPromise])
      .then((result) => {
        if (result?.filledCount > 0) recordAutofillFieldsFilled(result.filledCount);
        sendResponse({ ok: true, ...result });
      })
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (msg.type === "FILL_FORM") {
    fillFormRuleBased(msg.payload || {})
      .then((result) => {
        if (result?.filledCount > 0) recordAutofillFieldsFilled(result.filledCount);
        sendResponse({ ok: true, ...result });
      })
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  return false;
});

// Workday step updates from step manager (can come from iframe via postMessage)
window.addEventListener("message", (e) => {
  if (e?.data?.type !== "OPSBRAIN_WORKDAY_STEP") return;
  const root = document.getElementById(INPAGE_ROOT_ID);
  if (!root) return;
  // Keep Autofill tab active during Workday autofill — prevent switching to Keywords/Profile
  const autofillTab = root.querySelector('[data-tab="autofill"]');
  const autofillPanel = root.querySelector("#ja-panel-autofill");
  if (autofillTab && autofillPanel && !autofillTab.classList.contains("active")) {
    root.querySelectorAll(".ja-tab").forEach((t) => t.classList.remove("active"));
    root.querySelectorAll(".ja-panel").forEach((p) => p.classList.remove("active"));
    autofillTab.classList.add("active");
    autofillPanel.classList.add("active");
  }
  const statusEl = root.querySelector("#ja-status");
  const statusArea = root.querySelector("#ja-status-area");
  if (!statusEl) return;
  const { stepName, phase, fieldCount, filledCount, error } = e.data;
  let text = stepName || "Workday";
  if (phase === "starting") text = `Step: ${text} — starting...`;
  else if (phase === "filling") text = `Step: ${text} — filling ${fieldCount || 0} fields`;
  else if (phase === "filled") text = `✓ ${text} — filled ${filledCount ?? "✓"}`;
  else if (phase === "review") text = `Step: ${text} — review & submit manually`;
  else if (phase === "retry") text = `Retrying: ${text}`;
  else if (phase === "error") text = `⚠ ${text}${error ? `: ${error}` : ""}`;
  statusEl.textContent = text;
  statusEl.className = `ja-status ja-autofill-hero-sub ${phase === "error" ? "error" : phase === "filled" || phase === "review" ? "success" : "loading"}`.trim();
  statusArea?.classList.toggle("loading", phase === "starting" || phase === "filling" || phase === "retry");
});

// Test hook: when page dispatches 'scraper-test-request', run scrape and respond
document.addEventListener("scraper-test-request", async () => {
  try {
    const { fields } = await scrapeFields({ scope: "all" });
    const elements = getFillableFields(true, true);
    document.dispatchEvent(new CustomEvent("scraper-test-response", {
      detail: { ok: true, fields, elementCount: elements.length },
    }));
  } catch (e) {
    document.dispatchEvent(new CustomEvent("scraper-test-response", {
      detail: { ok: false, error: String(e) },
    }));
  }
});

function looksLikeJobApplicationForm() {
  const fillable = getFillableFields(false);
  if (fillable.length < 2) return false;
  const jobKeywords = ["name", "email", "resume", "cv", "phone", "apply", "linkedin", "experience"];
  let matchCount = 0;
  let hasResumeField = false;
  for (const el of fillable) {
    const meta = getFieldMeta(el);
    const text = getFieldKeys(meta).join(" ").toLowerCase();
    if ((el.type || "").toLowerCase() === "file" && (text.includes("resume") || text.includes("cv"))) {
      hasResumeField = true;
    }
    if (jobKeywords.some((kw) => text.includes(kw))) matchCount++;
  }
  return hasResumeField || matchCount >= 2;
}

function isJobFormPage() {
  const hasApplicationForm = looksLikeJobApplicationForm();
  const bodyText = (document.body?.innerText || document.body?.textContent || "").trim();
  const hasSubstantialContent = bodyText.length >= 400;

  if (hasApplicationForm) return true;

  if (isJobListingPage()) return false;

  return isJobDetailPage() && hasSubstantialContent;
}


function tryAutoOpenPopup() {
  if (window.self !== window.top) return;
  if (window.__PAGE_DETECTOR__ && !window.__PAGE_DETECTOR__.shouldShowWidget()) return;
  if (!isJobFormPage()) return;
  mountInPageUI();
  if (window.__FORM_WATCHER__) window.__FORM_WATCHER__.start();
  attachSubmitFeedbackListener();
  const widget = document.getElementById(INPAGE_ROOT_ID);
  if (widget) {
    const card = widget.querySelector(".ja-card");
    if (card) card.classList.remove("collapsed");
  }
  if (!/workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(window.location.href)) {
    runKeywordAnalysisAndMaybeShowWidget();
  }
}

const initAutoOpen = () => {
  tryAutoOpenPopup();
  setTimeout(tryAutoOpenPopup, 1500);
  setTimeout(tryAutoOpenPopup, 4000);
  retryPendingSubmission();
};

document.addEventListener("opsbrain-form-changed", () => {
  if (window.__REQUEST_MANAGER__) window.__REQUEST_MANAGER__.clearCache("form_fields:" + location.href);
});

window.addEventListener("message", (e) => {
  if (e.source !== window || e.data?.type !== "HIREMATE_PROFILE_SAVED") return;
  const origin = window.location.origin;
  if (LOGIN_PAGE_ORIGINS.some((o) => origin === o || origin.startsWith(o.replace(/\/$/, "") + "/"))) {
    chrome.runtime.sendMessage({ type: "INVALIDATE_MAPPING_CACHE" }).catch(() => { });
    logInfo("Profile saved — mapping cache invalidated");
  }
});

window.addEventListener("HIREMATE_RESUME_SAVED", (e) => {
  const resumeId = e.detail?.resumeId;
  if (resumeId != null) {
    chrome.runtime.sendMessage({ type: "RESUME_SAVED_FROM_TAILOR", resumeId }).catch(() => { });
  }
});

let _lastUrl = location.href;
const _urlObserver = new MutationObserver(() => {
  const current = location.href;
  if (current !== _lastUrl) {
    _lastUrl = current;
    if (window.__PAGE_DETECTOR__) window.__PAGE_DETECTOR__.reset();
    // Reset scraper's platform cache so the new URL is re-evaluated
    if (window.__OPSBRAIN_SCRAPER__?.resetPlatform) window.__OPSBRAIN_SCRAPER__.resetPlatform();
    if (window.__REQUEST_MANAGER__) window.__REQUEST_MANAGER__.clearCache("form_fields:" + current);
    tryAutoOpenPopup();
  }
});
if (document.body) _urlObserver.observe(document.body, { childList: true, subtree: true });

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => setTimeout(initAutoOpen, 500));
} else {
  setTimeout(initAutoOpen, 500);
}
