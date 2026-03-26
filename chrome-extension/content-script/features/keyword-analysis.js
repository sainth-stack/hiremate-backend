// ─── Keyword Analysis Feature ──────────────────────────────────────────────
// Depends on: INPAGE_ROOT_ID (consts.js)
//             KEYWORD_TAB_ICONS (icons.js)
//             logWarn, escapeHtml (utils.js)
//             getApiBase, getAuthHeaders, fetchWithAuthRetry (api-service.js)
//             isCareerPage, isJobDetailPage, isJobPageViaLLM (page-detection.js)
//             keywordGaugeDashArray, keywordMatchTheme, renderKeywordMatchChip (keyword-match.js)
//             openResumeGeneratorUrl (job-form.js)
//             fetchResumesFromApi (profile-panel.js)

const KEYWORD_MATCH_ROOT_ID = "ja-keyword-match-root";

// ─── Searchable resume dropdown helpers ────────────────────────────────────

/**
 * Populate the custom dropdown list and sync its trigger label.
 * @param {Element} root - widget root
 * @param {{ id: number, resume_name?: string, is_default?: boolean }[]} resumes
 * @param {string} selectedValue - currently selected option value (string)
 */
function populateResumeDropdown(root, resumes, selectedValue) {
  const list = root?.querySelector("#ja-rs-list");
  const triggerText = root?.querySelector("#ja-rs-trigger-text");
  const empty = root?.querySelector("#ja-rs-empty");
  if (!list) return;

  list.innerHTML = "";
  resumes.forEach((r) => {
    const li = document.createElement("li");
    li.className = "ja-rs-option" + (String(r.id) === String(selectedValue) ? " ja-rs-option--selected" : "");
    li.setAttribute("role", "option");
    li.dataset.value = String(r.id);
    const name = escapeHtml(r.resume_name || `Resume ${r.id}`);
    li.innerHTML = `<span class="ja-rs-option-name" style="overflow:hidden;text-overflow:ellipsis;flex:1">${name}</span>${r.is_default ? '<span class="ja-rs-badge-default">Default</span>' : ""}`;
    list.appendChild(li);
  });

  if (triggerText) {
    const sel = resumes.find((r) => String(r.id) === String(selectedValue));
    triggerText.textContent = sel ? (sel.resume_name || `Resume ${sel.id}`) : "Select resume…";
  }
  if (empty) empty.hidden = resumes.length > 0;
}

/**
 * Wire up open/close, search filtering, and item selection for the dropdown.
 * Must be called once per widget mount (idempotent via dataset flag).
 * @param {Element} root
 * @param {() => void} onSelect - called when a new resume is chosen
 */
function initResumeDropdown(root, onSelect) {
  const dropdown = root?.querySelector("#ja-rs-dropdown");
  if (!dropdown || dropdown.dataset.rsInit) return;
  dropdown.dataset.rsInit = "1";

  const trigger = root.querySelector("#ja-rs-trigger");
  const panel = root.querySelector("#ja-rs-panel");
  const searchInput = root.querySelector("#ja-rs-search");
  const list = root.querySelector("#ja-rs-list");
  const emptyEl = root.querySelector("#ja-rs-empty");
  const selectEl = root.querySelector("#ja-resume-select");

  const open = () => {
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    searchInput.value = "";
    filterList("");
    searchInput.focus();
  };
  const close = () => {
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
  };
  const toggle = () => (panel.hidden ? open() : close());

  const filterList = (q) => {
    const lc = q.toLowerCase();
    let visible = 0;
    list.querySelectorAll(".ja-rs-option").forEach((li) => {
      const match = li.dataset.value && li.textContent.toLowerCase().includes(lc);
      li.style.display = match ? "" : "none";
      if (match) visible++;
    });
    if (emptyEl) emptyEl.hidden = visible > 0;
  };

  trigger.addEventListener("click", (e) => { e.stopPropagation(); toggle(); });
  searchInput.addEventListener("input", () => filterList(searchInput.value));
  searchInput.addEventListener("click", (e) => e.stopPropagation());

  list.addEventListener("click", (e) => {
    const li = e.target.closest(".ja-rs-option");
    if (!li) return;
    const val = li.dataset.value;
    if (!val) return;

    list.querySelectorAll(".ja-rs-option").forEach((o) => o.classList.remove("ja-rs-option--selected"));
    li.classList.add("ja-rs-option--selected");

    const triggerText = root.querySelector("#ja-rs-trigger-text");
    if (triggerText) triggerText.textContent = li.querySelector(".ja-rs-option-name")?.textContent || li.textContent.trim();

    if (selectEl) {
      selectEl.value = val;
      try { chrome.storage.local.set({ hm_selected_resume_id: val }); } catch (_) {}
      selectEl.dispatchEvent(new Event("change", { bubbles: true }));
    }
    close();
    if (typeof onSelect === "function") onSelect(val);
  });

  document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target)) close();
  }, true);

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { close(); trigger.focus(); }
  });
}

/** Get page HTML from all frames (main + iframes). */
async function getPageHtmlForKeywordsApi() {
  try {
    const res = await chrome.runtime.sendMessage({ type: "GET_ALL_FRAMES_HTML" });
    if (res?.ok && res.html) return res.html;
  } catch (_) { }
  try {
    const el = document.documentElement || document.body;
    if (!el) return null;
    const html = (el.outerHTML || el.innerHTML || "").slice(0, 1500000);
    return html && html.length > 100 ? html : null;
  } catch (_) {
    return null;
  }
}

/** Fetch job description via keywords/analyze. */
async function fetchJobDescriptionFromKeywordsApi(url) {
  if (!url || !url.startsWith("http")) return null;
  try {
    const pageHtml = await getPageHtmlForKeywordsApi();
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const body = { url, page_html: pageHtml || undefined };
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/keywords/analyze`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.job_description && data.job_description.length >= 50 ? data.job_description : null;
  } catch (e) {
    logWarn("fetchJobDescriptionFromKeywordsApi failed", { url: url?.slice(0, 80), error: String(e) });
    return null;
  }
}

async function runKeywordAnalysisAndMaybeShowWidget() {
  if (window.self !== window.top) return;
  if (document.getElementById(KEYWORD_MATCH_ROOT_ID) || document.getElementById("opsbrain-match-widget")) return;
  if (/workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(window.location.href)) return;

  const url = window.location.href;
  const urlSuggestsJob = isCareerPage(url);
  if (!urlSuggestsJob) {
    if (window.__PAGE_DETECTOR__ && !window.__PAGE_DETECTOR__.shouldShowWidget()) return;
    const snippet = (document.body?.innerText || document.body?.textContent || "").replace(/\s+/g, " ").slice(0, 800);
    const llmSaysJob = await isJobPageViaLLM(url, document.title, snippet);
    if (llmSaysJob !== true) return;
  }

  setTimeout(async () => {
    const cacheKey = `keyword_analysis:${url}`;
    const requestManager = window.__REQUEST_MANAGER__;
    const cacheManager = window.__CACHE_MANAGER__;

    const fetchAndShow = async () => {
      const pageHtml = await getPageHtmlForKeywordsApi();
      const apiBase = await getApiBase();
      const headers = await getAuthHeaders();
      const body = { url, page_html: (pageHtml || "").slice(0, 50000) };
      const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/keywords/analyze`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) return null;
      const data = await res.json();
      if ((data.total_keywords || 0) === 0) return null;
      if (cacheManager) {
        try { await cacheManager.set("keywordAnalysis", { url, result: data }); } catch (_) { }
      }
      return data;
    };

    try {
      let data = null;
      if (cacheManager) {
        try {
          const cached = await cacheManager.get("keywordAnalysis", url);
          const CACHE_TTL = (window.__CONFIG__?.get?.("cacheTTL")?.keywordAnalysis) || 30 * 60 * 1000;
          if (cached?.result && cached?.timestamp && Date.now() - cached.timestamp < CACHE_TTL) {
            if (window.__CONFIG__?.log) window.__CONFIG__.log("[Keyword] Cache hit");
            data = cached.result;
          }
        } catch (_) { }
      }
      if (!data) {
        data = requestManager?.dedupedRequest
          ? await requestManager.dedupedRequest(cacheKey, fetchAndShow, 30 * 60 * 1000)
          : await fetchAndShow();
      }
      if (!data || (data.percent || 0) < 60) return;
      if (window.__PROFESSIONAL_WIDGET__) {
        const Widget = window.__PROFESSIONAL_WIDGET__;
        const widget = new Widget();
        widget.create(data);
      } else {
        mountKeywordMatchWidgetWithData({ matched: data.matched_count, total: data.total_keywords, percent: data.percent });
      }
    } catch (_) { }
  }, 2000);
}

function mountKeywordMatchWidgetWithData({ matched, total, percent }) {
  if (document.getElementById(KEYWORD_MATCH_ROOT_ID)) return;

  const root = document.createElement("div");
  root.id = KEYWORD_MATCH_ROOT_ID;
  root.innerHTML = `
    <style>
      #${KEYWORD_MATCH_ROOT_ID} {
        all: initial;
        position: fixed; right: 20px; top: 50%; transform: translateY(-50%);
        z-index: 2147483646;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 15px;
      }
      #${KEYWORD_MATCH_ROOT_ID} * { box-sizing: border-box; }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-card {
        width: 180px; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 16px; text-align: center;
        margin: 0 auto; cursor: pointer; transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-card:hover { box-shadow: 0 8px 28px rgba(14,165,233,0.2); border-color: #0ea5e9; transform: translateY(-2px); }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-circle {
        width: 64px; height: 64px; margin: 0 auto 12px; border-radius: 50%;
        background: conic-gradient(#0ea5e9 ${percent * 3.6}deg, #e5e7eb ${percent * 3.6}deg);
        display: flex; align-items: center; justify-content: center;
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-circle-inner {
        width: 52px; height: 52px; border-radius: 50%; background: #fff;
        display: flex; align-items: center; justify-content: center;
        font-size: 15px; font-weight: 700; color: #0ea5e9;
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-title { font-size: 14px; font-weight: 600; color: #111; margin-bottom: 4px; }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-desc { font-size: 12px; color: #6b7280; }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-tag { display: inline-block; margin-top: 8px; font-size: 11px; color: #0ea5e9; font-weight: 600; text-decoration: underline; cursor: pointer; }
    </style>
    <div class="ja-kw-card">
      <div class="ja-kw-circle"><div class="ja-kw-circle-inner">${percent}%</div></div>
      <div class="ja-kw-title">Resume Match</div>
      <div class="ja-kw-desc">${percent}% – ${matched} of ${total} keywords in your resume.</div>
      <span class="ja-kw-tag">OpsBrain</span>
    </div>
  `;
  document.documentElement.appendChild(root);

  const card = root.querySelector(".ja-kw-card");
  const hiremateLink = root.querySelector(".ja-kw-tag");
  card?.addEventListener("click", (e) => {
    if (e.target === hiremateLink || hiremateLink?.contains(e.target)) return;
    mountInPageUI();
    const widget = document.getElementById(INPAGE_ROOT_ID);
    if (widget) {
      const cardEl = widget.querySelector(".ja-card");
      if (cardEl) cardEl.classList.remove("collapsed");
      const keywordsTab = widget.querySelector('[data-tab="keywords"]');
      if (keywordsTab) keywordsTab.click();
    }
  });
  hiremateLink?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    openResumeGeneratorUrl();
  });
}

async function loadKeywordsIntoPanel(root) {
  const container = root?.querySelector("#ja-keyword-analysis");
  const card = root?.querySelector("#ja-keyword-card");
  const selectEl = root?.querySelector("#ja-resume-select");
  if (!container) return;

  const keywordsListEl = root?.querySelector("#ja-keyword-keywords-list");
  const skeletonHtml = `
    <div class="ja-kw-skeleton-score">
      <div class="ja-kw-skel-circle ja-kw-skel"></div>
      <div class="ja-kw-skel-copy">
        <div class="ja-kw-skel-badge ja-kw-skel"></div>
        <div class="ja-kw-skel-line ja-kw-skel-line-w80 ja-kw-skel"></div>
        <div class="ja-kw-skel-line ja-kw-skel-line-w55 ja-kw-skel"></div>
      </div>
    </div>
    <div class="ja-kw-skel-tip"></div>`;
  const skeletonListHtml = `
    <div class="ja-kw-priority-block">
      <div class="ja-kw-skel-section-head">
        <div class="ja-kw-skel-dot ja-kw-skel"></div>
        <div class="ja-kw-skel-htitle ja-kw-skel"></div>
        <div class="ja-kw-skel-meta ja-kw-skel"></div>
      </div>
      <div class="ja-kw-chip-grid">
        ${Array(8).fill('<div class="ja-kw-skel-chip ja-kw-skel"></div>').join("")}
      </div>
    </div>
    <div class="ja-kw-priority-block">
      <div class="ja-kw-skel-section-head">
        <div class="ja-kw-skel-dot ja-kw-skel"></div>
        <div class="ja-kw-skel-htitle ja-kw-skel"></div>
        <div class="ja-kw-skel-meta ja-kw-skel"></div>
      </div>
      <div class="ja-kw-chip-grid">
        ${Array(4).fill('<div class="ja-kw-skel-chip ja-kw-skel"></div>').join("")}
      </div>
    </div>`;
  container.innerHTML = skeletonHtml;
  if (keywordsListEl) keywordsListEl.innerHTML = skeletonListHtml;

  try {
    const resumes = await fetchResumesFromApi();
    if (resumes.length === 0) {
      container.innerHTML = `
        <p class="ja-score-text">Please upload resume in profile to analyze keywords.</p>
        <button type="button" class="ja-action ja-upload-resume-btn" style="margin-top:8px;">Upload Resume</button>
      `;
      container.querySelector(".ja-upload-resume-btn")?.addEventListener("click", () => openResumeGeneratorUrl());
      if (card) card.classList.remove("ja-loading");
      return;
    }

    if (selectEl) {
      const prevSelection = selectEl.value ? parseInt(selectEl.value, 10) : null;
      const validIds = new Set(resumes.map((r) => r.id));
      selectEl.innerHTML = "";
      let defaultId = null;
      resumes.forEach((r, idx) => {
        const opt = document.createElement("option");
        opt.value = r.id;
        opt.textContent = r.resume_name || `Resume ${idx + 1}`;
        if (r.is_default) { defaultId = r.id; }
        selectEl.appendChild(opt);
      });
      const { hm_selected_resume_id } = await chrome.storage.local.get(["hm_selected_resume_id"]);
      const storedId = hm_selected_resume_id != null ? parseInt(hm_selected_resume_id, 10) : null;
      if (storedId && validIds.has(storedId)) selectEl.value = String(storedId);
      else if (prevSelection && validIds.has(prevSelection)) selectEl.value = String(prevSelection);
      else if (defaultId !== null) selectEl.value = String(defaultId);
      else if (resumes.length) selectEl.value = String(resumes[0].id);
    }

    // Sync custom searchable dropdown UI
    populateResumeDropdown(root, resumes, selectEl?.value || "");
    initResumeDropdown(root, () => { /* change event on hidden select triggers reload */ });

    const selectedId = selectEl?.value ? parseInt(selectEl.value, 10) : null;
    const resumeId = selectedId && selectedId > 0 ? selectedId : null;

    container.innerHTML = skeletonHtml;
    if (keywordsListEl) keywordsListEl.innerHTML = skeletonListHtml;
    const pageHtml = await getPageHtmlForKeywordsApi();
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const body = { url: window.location.href, page_html: pageHtml || undefined };
    if (resumeId) body.resume_id = resumeId;

    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/keywords/analyze`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let errMsg = "Unable to analyze keywords.";
      try {
        const errData = await res.json();
        errMsg = errData.detail || errMsg;
        if (typeof errMsg === "object" && errMsg.msg) errMsg = errMsg.msg;
      } catch (_) { }
      container.innerHTML = `<p class="ja-score-text">${escapeHtml(String(errMsg))}</p>`;
      if (keywordsListEl) keywordsListEl.innerHTML = "";
      if (card) card.classList.remove("ja-loading");
      return;
    }
    const data = await res.json();
    const high = data.high_priority || [];
    const low = data.low_priority || [];
    const total = data.total_keywords || 0;
    const matched = data.matched_count || 0;
    const percent = data.percent || 0;
    const highMatched = high.filter((i) => i.matched).length;
    const lowMatched = low.filter((i) => i.matched).length;
    const apiMessage = data.message || "";
    const theme = keywordMatchTheme(percent, total);
    const dashArr = keywordGaugeDashArray(percent);
    const pctRounded = Math.round(percent);
    const highHtml = high.map(renderKeywordMatchChip).join("");
    const lowHtml = low.map(renderKeywordMatchChip).join("");
    const quickFromApi = Array.isArray(data.quick_suggestions) ? data.quick_suggestions.filter(Boolean) : [];
    const quickPills = quickFromApi.length > 0
      ? quickFromApi.slice(0, 8)
      : high.filter((k) => !k.matched).slice(0, 4).map((k) => k.keyword);
    const suggestionsHtml = quickPills
      .map((kw) => `<button type="button" class="ja-kw-suggest-pill">+ ${escapeHtml(typeof kw === "string" ? kw : kw.keyword || String(kw))}</button>`)
      .join("");

    container.innerHTML = total === 0
      ? `<div class="ja-kw-score-card-inner ja-kw-score-empty">
          <p class="ja-score-text">${escapeHtml(apiMessage || "No technical skills found in the job description. Scroll down for the full requirements section.")}</p>
        </div>`
      : `<div class="ja-kw-score-card-inner">
          <div class="ja-kw-score-main">
            <div class="ja-kw-gauge-circle-wrap" aria-hidden="true">
              <svg class="ja-kw-gauge-circle" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="34" fill="none" stroke="#e5e7eb" stroke-width="6" />
                <circle cx="40" cy="40" r="34" fill="none" stroke="${theme.stroke}" stroke-width="6" stroke-linecap="round"
                  stroke-dasharray="${dashArr}" transform="rotate(-90 40 40)" />
              </svg>
              <div class="ja-kw-gauge-circle-label">
                <span class="ja-kw-pct-num" style="color:${theme.color}">${pctRounded}%</span>
                <span class="ja-kw-pct-sub">MATCH</span>
              </div>
            </div>
            <div class="ja-kw-score-copy">
              <div class="ja-kw-badge-row">
                <span class="ja-kw-status-badge" style="color:${theme.color};background:${theme.badgeBg}">${theme.label}</span>
              </div>
              <p class="ja-kw-line ja-kw-line-muted">
                <strong class="ja-kw-strong">${matched}</strong> of <strong class="ja-kw-strong">${total}</strong> keywords matched.
              </p>
              <div class="ja-kw-hilo">
                <span class="ja-kw-hilo-item">High: <strong class="ja-kw-strong">${highMatched}/${high.length}</strong></span>
                <span class="ja-kw-hilo-item">Low: <strong class="ja-kw-strong">${lowMatched}/${low.length}</strong></span>
              </div>
            </div>
          </div>
          <div class="ja-kw-tip-bar">
            ${KEYWORD_TAB_ICONS.lightbulb}
            <p class="ja-kw-tip-text">Aim for <strong>70%+</strong> match rate. Click &quot;Tailor&quot; to auto-optimize your resume.</p>
          </div>
        </div>`;

    if (keywordsListEl) {
      if (!high.length && !low.length) {
        keywordsListEl.innerHTML = "";
      } else {
        keywordsListEl.innerHTML = `
          ${high.length ? `<div class="ja-kw-priority-block">
            <div class="ja-kw-priority-head">
              <span class="ja-kw-priority-head-left"><span class="ja-kw-dot ja-kw-dot-high"></span><span class="ja-kw-priority-name">High Priority</span></span>
              <span class="ja-kw-priority-meta">${highMatched}/${high.length} matched</span>
            </div>
            <div class="ja-kw-chip-grid">${highHtml}</div>
          </div>` : ""}
          ${low.length ? `<div class="ja-kw-priority-block">
            <div class="ja-kw-priority-head">
              <span class="ja-kw-priority-head-left"><span class="ja-kw-dot ja-kw-dot-low"></span><span class="ja-kw-priority-name">Low Priority</span></span>
              <span class="ja-kw-priority-meta">${lowMatched}/${low.length} matched</span>
            </div>
            <div class="ja-kw-chip-grid">${lowHtml}</div>
          </div>` : ""}
          ${suggestionsHtml ? `<div class="ja-kw-suggest-card">
            <div class="ja-kw-suggest-head">${KEYWORD_TAB_ICONS.trendingUp}<span class="ja-kw-suggest-title">Quick Suggestions</span></div>
            <p class="ja-kw-suggest-sub">Add these missing keywords to boost your score:</p>
            <div class="ja-kw-suggest-pills">${suggestionsHtml}</div>
          </div>` : ""}
        `;
      }
    }
    if (root && data.job_id != null) {
      root.dataset.lastJobId = String(data.job_id);
      root.dataset.lastJobUrl = window.location.href;
    }
  } catch (err) {
    logWarn("Keyword analysis failed", { error: String(err) });
    container.innerHTML = "<p class=\"ja-score-text\">Unable to analyze. Please try again.</p>";
    if (root) {
      const kwList = root.querySelector("#ja-keyword-keywords-list");
      if (kwList) kwList.innerHTML = "";
    }
  } finally {
    if (card) card.classList.remove("ja-loading");
  }
}
