// ─── Accordion UI Component ────────────────────────────────────────────────
// Depends on: ACCORDION_ICONS, QUESTION_UI_ICONS, RESUME_FIELD_CHECK_SVG (icons.js)
//             escapeHtml, getText (utils.js)
//             getApiBase, getAuthHeaders, fetchWithAuthRetry,
//             getAutofillContextFromApi, fetchResumesFromApi,
//             openResumeGeneratorUrl, scrapeFields, getFieldKeys (content.js)

/** Same profile fields as Profile tab — from `GET .../autofill/context` → `profile`. */
function buildResumeAccordionFieldRows(flat) {
  const f = flat || {};
  const location = [f.city, f.country].filter(Boolean).join(", ") || "—";
  const fullName = [f.firstName, f.lastName].filter(Boolean).join(" ") || f.name || "—";
  return [
    ["Full name", fullName],
    ["Location", location],
    ["Email", f.email || "—"],
    ["Phone", f.phone || "—"],
    ["LinkedIn", f.linkedin || "—"],
    ["GitHub", f.github || "—"],
    ["Portfolio", f.portfolio || "—"],
  ];
}

/** Reusable accordion component. opts: { id, iconBg, iconColor, iconSvg, title, showHelpIcon, statusText, statusCheckmark } */
function createAccordionItem(opts) {
  const id = escapeHtml(opts.id || "accordion");
  const iconBg = escapeHtml(opts.iconBg || "#e0e7ff");
  const iconColor = opts.iconColor != null ? escapeHtml(String(opts.iconColor)) : "";
  const iconSvg = opts.iconSvg || ACCORDION_ICONS.document;
  const title = escapeHtml(opts.title || "");
  const showHelpIcon = !!opts.showHelpIcon;
  const statusText = escapeHtml(opts.statusText || "");
  const statusCheckmark = !!opts.statusCheckmark;
  const checkMarkHtml = statusCheckmark
    ? `<span class="ja-accordion-check" aria-hidden="true">${QUESTION_UI_ICONS.accordionHeaderCheck}</span>`
    : "";
  const iconStyle = iconColor ? `background:${iconBg};color:${iconColor}` : `background:${iconBg}`;
  return `
    <div class="ja-accordion-item" data-accordion-id="${id}">
      <button type="button" class="ja-accordion-header" aria-expanded="false" aria-controls="ja-accordion-body-${id}" id="ja-accordion-trigger-${id}">
        <span class="ja-accordion-icon" style="${iconStyle}">${iconSvg}</span>
        <span class="ja-accordion-title-wrap">
          <span class="ja-accordion-title">${title}</span>
          ${showHelpIcon ? '<span class="ja-accordion-help" title="Help">?</span>' : ""}
        </span>
        ${statusText || statusCheckmark ? `<span class="ja-accordion-status">${statusText ? `<span class="ja-accordion-status-text">${statusText}</span>` : ""}${checkMarkHtml}</span>` : ""}
        <span class="ja-accordion-chevron" aria-hidden="true">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
            <path d="M5 8l5 5 5-5"/>
          </svg>
        </span>
      </button>
      <div class="ja-accordion-body" id="ja-accordion-body-${id}" role="region" aria-labelledby="ja-accordion-trigger-${id}" hidden>
        <div class="ja-accordion-content"></div>
      </div>
    </div>
  `;
}

function renderAccordions(containerEl, items, rootEl) {
  if (!containerEl) return;
  containerEl.innerHTML = items.map((item) => createAccordionItem(item)).join("");
  containerEl.querySelectorAll(".ja-accordion-header").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = btn.closest(".ja-accordion-item");
      const body = item?.querySelector(".ja-accordion-body");
      const isExpanded = btn.getAttribute("aria-expanded") === "true";
      const expanding = !isExpanded;
      btn.setAttribute("aria-expanded", expanding);
      if (body) body.hidden = !expanding;
      item?.classList.toggle("expanded", expanding);
      if (expanding && rootEl) {
        const id = item?.dataset?.accordionId || item?.querySelector("[data-accordion-id]")?.dataset?.accordionId;
        const contentEl = item?.querySelector(".ja-accordion-content");
        if (id && contentEl) loadAccordionContent(id, contentEl, rootEl);
      }
    });
  });
}

async function loadAccordionContent(id, contentEl, rootEl) {
  if (id === "resume") {
    await loadResumeAccordionContent(contentEl, rootEl);
  } else if (id === "cover-letter") {
    await loadCoverLetterAccordionContent(contentEl, rootEl);
  } else if (id === "unique-questions" || id === "common-questions") {
    await loadQuestionsAccordionContent(id, contentEl, rootEl);
  }
}

async function loadResumeAccordionContent(contentEl, rootEl) {
  contentEl.innerHTML = "<p class=\"ja-score-text\">Loading...</p>";

  try {
    // Use cached resumes from initial load if available
    const resumes = window.__OPSBRAIN_RESUMES__?.length
      ? window.__OPSBRAIN_RESUMES__
      : await fetchResumesFromApi();

    if (resumes.length === 0) {
      contentEl.innerHTML = `
        <div class="ja-resume-empty">
          <p class="ja-score-text" style="margin:0 0 10px">No resumes yet. Upload one in your OpsBrain profile.</p>
          <button type="button" class="ja-map-answers-btn" style="width:100%;justify-content:center;">Open Profile</button>
        </div>
      `;
      contentEl.querySelector(".ja-map-answers-btn")?.addEventListener("click", openResumeGeneratorUrl);
      return;
    }

    const { hm_selected_resume_id } = await chrome.storage.local.get(["hm_selected_resume_id"]);
    const storedId = hm_selected_resume_id ? parseInt(hm_selected_resume_id, 10) : null;

    const defaultResume = resumes.find((r) => r.is_default) || resumes[0];
    let selectedId = storedId && resumes.some((r) => r.id === storedId) ? storedId : defaultResume?.id;

    const selectId = "ja-accordion-resume-select";

    let flat = {};
    try {
      const ctx = await getAutofillContextFromApi();
      flat = ctx.profile || {};
    } catch (_) { }

    const resumeFieldRows = buildResumeAccordionFieldRows(flat);

    contentEl.innerHTML = `
      <div class="ja-resume-accordion-row">
        <select class="ja-resume-select" id="${selectId}" style="flex:1;margin-bottom:0;">
          ${resumes.map((r) => `
            <option value="${r.id}" ${r.id === selectedId ? "selected" : ""}>
              ${escapeHtml(r.resume_name || `Resume ${r.id}`)}${r.is_default ? " ★" : ""}
            </option>
          `).join("")}
        </select>
        <button type="button" class="ja-map-answers-btn" id="ja-resume-preview-btn" style="flex-shrink:0;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="ja-q-svg" style="width:13px;height:13px"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          Preview
        </button>
      </div>
      <p class="ja-resume-preview-hint" style="margin-top:6px;">Resume shown above is selected for autofill.</p>
      <div class="ja-resume-card">
        ${resumeFieldRows.map(([label, value]) => `
          <div class="ja-resume-row">
            <span class="ja-resume-label">${escapeHtml(label)}</span>
            <div class="ja-resume-value-wrap">
              <span class="ja-resume-value">${escapeHtml(value)}</span>
              <span class="ja-check-icon">${RESUME_FIELD_CHECK_SVG}</span>
            </div>
          </div>
        `).join("")}
      </div>
    `;

    // Save selection when changed
    contentEl.querySelector(`#${selectId}`)?.addEventListener("change", (e) => {
      const newId = parseInt(e.target.value, 10);
      selectedId = newId;
      chrome.storage.local.set({ hm_selected_resume_id: String(newId) });
    });

    contentEl.querySelector("#ja-resume-preview-btn")?.addEventListener("click", async () => {
      const sel = contentEl.querySelector(`#${selectId}`);
      const id = sel ? parseInt(sel.value, 10) : selectedId;
      if (!id) return;
      const btn = contentEl.querySelector("#ja-resume-preview-btn");
      if (btn) { btn.disabled = true; btn.textContent = "Loading..."; }
      try {
        const apiBase = await getApiBase();
        const headers = await getAuthHeaders();
        const res = await fetchWithAuthRetry(`${apiBase}/resume/${id}/file`, { headers });
        if (res.ok) {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          window.open(url, "_blank");
        }
      } catch (_) { }
      if (btn) { btn.disabled = false; btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> Preview`; }
    });

  } catch (err) {
    contentEl.innerHTML = "<p class=\"ja-score-text\">Failed to load resumes.</p>";
  }
}

async function loadCoverLetterAccordionContent(contentEl, rootEl, forceRegenerate = false) {
  contentEl.innerHTML = "<p class=\"ja-score-text\">Loading...</p>";
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const currentJobUrl = forceRegenerate ? `${window.location.href}#regenerate=${Date.now()}` : window.location.href;
    const pageHtml = await getPageHtmlForKeywordsApi?.().catch(() => "") || "";
    const jobTitle = document.title?.split(/[|\-–—]/)[0]?.trim() || "";
    const _clRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/cover-letter/upsert`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ job_url: currentJobUrl, page_html: pageHtml, job_title: jobTitle }),
    });
    const coverLetterData = await _clRes.json();
    const letter = coverLetterData?.content || "";
    const displayTitle = coverLetterData?.job_title || jobTitle;
    if (letter) {
      contentEl.innerHTML = `
        <div class="ja-cover-letter-preview ja-cover-box">
          ${displayTitle ? `<p class="ja-cover-letter-job">${escapeHtml(displayTitle)}</p>` : ""}
          <div class="ja-cover-letter-text">
            ${escapeHtml(letter).replace(/\n/g, "<br>")}
          </div>
        </div>
        <div class="ja-btn-row">
          <button type="button" class="ja-btn" id="ja-generate-cover-letter">
            <svg class="ja-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M15 4V2"></path>
              <path d="M15 10V8"></path>
              <path d="M19 6h2"></path>
              <path d="M13 6h-2"></path>
              <path d="M5 20l14-14"></path>
            </svg>
            Regenerate
          </button>
          <button class="ja-btn">
            <svg class="ja-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.1 2.1 0 113 3L7 19l-4 1 1-4 12.5-12.5z"></path>
            </svg>
            Edit
          </button>
          <button class="ja-btn-icon">
            <svg class="ja-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <rect x="9" y="9" width="13" height="13" rx="2"></rect>
              <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"></path>
            </svg>
          </button>
        </div>
      `;
    } else {
      contentEl.innerHTML = `
        <p class="ja-score-text">No cover letter yet. Generate one based on your profile and this job.</p>
        <button type="button" class="ja-action" id="ja-generate-cover-letter">Generate Cover Letter</button>
      `;
    }
    contentEl.querySelector("#ja-generate-cover-letter")?.addEventListener("click", async () => {
      const btn = contentEl.querySelector("#ja-generate-cover-letter");
      if (btn) btn.disabled = true;
      contentEl.querySelector(".ja-cover-letter-preview")?.remove();
      const statusP = contentEl.querySelector(".ja-score-text") || contentEl.appendChild(document.createElement("p"));
      statusP.className = "ja-score-text";
      statusP.textContent = "Generating...";
      try {
        await loadCoverLetterAccordionContent(contentEl, rootEl, true);
      } catch (_) {
        statusP.textContent = "Generation failed.";
      }
      if (btn) btn.disabled = false;
    });
  } catch (_) {
    contentEl.innerHTML = "<p class=\"ja-score-text\">No cover letter. Click Generate to create one.</p><button type=\"button\" class=\"ja-action\" id=\"ja-generate-cover-letter\">Generate</button>";
    contentEl.querySelector("#ja-generate-cover-letter")?.addEventListener("click", () => loadCoverLetterAccordionContent(contentEl, rootEl));
  }
}

// Quick DOM scan — labels only, no scrolling, no option loading.
// Used for display. Full scrape (SCRAPE_ALL_FRAMES) happens only on Map Answers click.
function _quickScanFieldLabels() {
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
  return fields;
}

/** Render unique-questions cards or common-questions table (no footer stats — those live in widget footer). */
function renderQuestionsHtml(id, renderList, mappings) {
  if (id === "unique-questions") {
    const cards = renderList.map((f) => {
      const m = mappings ? (mappings[f.index] || {}) : {};
      const val = m.value != null ? String(m.value).trim() : "";
      const label = f.label || f.name || f.placeholder || `Field ${f.index + 1}`;
      const hasAnswer = mappings && val.length > 0;
      const qRow = `
          <div class="ja-uq-qrow">
            <span class="ja-uq-help">${QUESTION_UI_ICONS.helpCircle}</span>
            <p class="ja-uq-question">${escapeHtml(label)}</p>
          </div>`;
      let body = "";
      if (hasAnswer) {
        body = `
          <div class="ja-uq-body">
            <p class="ja-uq-answer">${escapeHtml(val)}</p>
            <div class="ja-uq-foot">
              <span class="ja-badge ja-badge-ai">${QUESTION_UI_ICONS.sparkles}<span>AI Generated</span></span>
              <button type="button" class="ja-uq-textbtn">Edit</button>
            </div>
          </div>`;
      } else {
        body = `
          <div class="ja-uq-body ja-uq-body-empty">
            <span class="ja-badge ja-badge-need">Needs Answer</span>
          </div>`;
      }
      return `<div class="ja-uq-card">${qRow}${body}</div>`;
    }).join("");
    return renderList.length
      ? `<div class="ja-uq-stack">${cards}</div>`
      : "<p class=\"ja-score-text\">No questions in this category.</p>";
  }
  // common-questions — SaaS-style field navigator
  const rows = renderList.map((f, i) => {
    const label = f.label || f.name || f.placeholder || `Field ${f.index + 1}`;
    const isLast = i === renderList.length - 1;
    const fieldIdAttr = f.id ? ` data-field-id="${escapeHtml(f.id)}"` : "";
    const fieldNameAttr = f.name ? ` data-field-name="${escapeHtml(f.name)}"` : "";
    return `<div class="ja-cq-item ja-cq-row-clickable${isLast ? "" : " ja-cq-item-b"}"${fieldIdAttr}${fieldNameAttr}>
      <span class="ja-cq-item-label">${escapeHtml(label)}</span>
      <span class="ja-cq-item-arrow" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3l5 5-5 5"/></svg></span>
    </div>`;
  }).join("");
  if (!renderList.length) return "<p class=\"ja-score-text\">No questions in this category.</p>";
  return `<div class="ja-cq-panel">
    <div class="ja-cq-panel-head">
      <span class="ja-cq-panel-count">${renderList.length} field${renderList.length !== 1 ? "s" : ""} on this page</span>
      <span class="ja-cq-panel-hint">Click to navigate</span>
    </div>
    <div class="ja-cq-items">${rows}</div>
  </div>`;
}

/** Attach click-to-scroll handlers to common-question rows that have field identifiers. */
function attachFieldScrollHandlers(contentEl) {
  contentEl.querySelectorAll(".ja-cq-row-clickable, .ja-cq-item").forEach((row) => {
    row.addEventListener("click", () => {
      const fieldId = row.dataset.fieldId;
      const fieldName = row.dataset.fieldName;
      let el = null;
      if (fieldId) el = document.getElementById(fieldId);
      if (!el && fieldName) el = document.querySelector(`[name="${CSS.escape(fieldName)}"]`);
      if (!el) return;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      try { el.focus({ preventScroll: true }); } catch (_) { }
      const origOutline = el.style.outline;
      const origOffset = el.style.outlineOffset;
      el.style.outline = "2px solid #2563eb";
      el.style.outlineOffset = "2px";
      setTimeout(() => { el.style.outline = origOutline; el.style.outlineOffset = origOffset; }, 1500);
    });
  });
}

/**
 * Fetch AI mappings for unique/common question accordions.
 * @param {{ auto?: boolean }} options — if auto, used for Common Questions (no Map button; runs on expand).
 */
async function runAccordionMapAnswers(id, contentEl, rootEl, options = {}) {
  const { auto = false } = options;
  const btn = contentEl.querySelector(`#ja-map-answers-${id}`);
  const statusWrap = rootEl?.querySelector(`[data-accordion-id="${id}"]`)?.querySelector(".ja-accordion-status-text");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="ja-map-spinner"></span><span>Mapping...</span>`;
  }

  try {
    let fields = window.__OPSBRAIN_SCRAPED_FIELDS__ || [];
    try {
      if (window.self === window.top) {
        const scrapeRes = await chrome.runtime.sendMessage({ type: "SCRAPE_ALL_FRAMES", scope: "all" });
        if (scrapeRes?.ok && scrapeRes.fields?.length) {
          fields = scrapeRes.fields.filter((f) => f.type !== "option" && f.label);
          window.__OPSBRAIN_SCRAPED_FIELDS__ = fields;
        }
      }
    } catch (_) { }

    const ctx = await getAutofillContextFromApi();
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const mapRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/form-fields/map`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        fields: fields.slice(0, 50).map((f) => ({ ...f, id: null })),
        profile: ctx?.profile || {},
        custom_answers: ctx?.customAnswers || {},
        resume_text: ctx?.resumeText || "",
        sync_llm: true,
      }),
    });

    if (!mapRes.ok) {
      let errMsg = "Failed to load answers";
      try {
        const errBody = await mapRes.json();
        const d = errBody?.detail;
        errMsg = typeof d === "string" ? d : Array.isArray(d) ? (d[0]?.msg || String(d[0] || d)) : errMsg;
      } catch (_) { }
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `${QUESTION_UI_ICONS.sparkles}<span>Retry Map Answers</span>`;
      }
      if (auto) {
        contentEl.querySelector(".ja-cq-mapping-loading")?.remove();
        const errEl = contentEl.querySelector(".ja-map-err") || (() => {
          const p = document.createElement("p");
          p.className = "ja-score-text ja-map-err";
          contentEl.insertBefore(p, contentEl.firstChild);
          return p;
        })();
        errEl.textContent = errMsg;
      } else {
        const errEl = contentEl.querySelector(".ja-map-err") || (() => {
          const p = document.createElement("p");
          p.className = "ja-score-text ja-map-err";
          btn?.parentElement?.appendChild(p);
          return p;
        })();
        errEl.textContent = errMsg;
      }
      return;
    }

    const mapData = await mapRes.json();
    const mappings = mapData?.mappings || {};

    const commonKeys = ["firstname", "lastname", "email", "phone", "address", "linkedin", "github", "portfolio", "resume", "coverletter", "country", "city"];
    const isCommonF = (f) => {
      const keys = getFieldKeys({ label: f.label, name: f.name, id: f.id, placeholder: f.placeholder });
      return commonKeys.some((k) => keys.some((fk) => fk.includes(k) || k.includes(fk)));
    };
    const mappedList = (id === "common-questions"
      ? fields.filter(isCommonF)
      : fields.filter((f) => !isCommonF(f))
    ).slice(0, 15);

    const filled = mappedList.filter((f) => {
      const m = mappings[f.index];
      return m?.value != null && String(m.value).trim() !== "";
    }).length;

    contentEl.innerHTML = renderQuestionsHtml(id, mappedList, mappings);
    if (id === "common-questions") attachFieldScrollHandlers(contentEl);

    if (statusWrap) statusWrap.textContent = `${filled}/${mappedList.length}`;
  } catch (_) {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `${QUESTION_UI_ICONS.sparkles}<span>Retry Map Answers</span>`;
    }
  } finally {
    contentEl.querySelector(".ja-cq-mapping-loading")?.remove();
  }
}

async function loadQuestionsAccordionContent(id, contentEl, rootEl) {
  // ── Step 1: Get fields (use cached from initial quick scan, or quick scan fresh) ──
  let fields = window.__OPSBRAIN_SCRAPED_FIELDS__ || [];

  if (!fields.length) {
    // Quick scan — no scrolling, no SCRAPE_ALL_FRAMES, no option loading
    fields = _quickScanFieldLabels();
    window.__OPSBRAIN_SCRAPED_FIELDS__ = fields;
  }

  if (!fields.length) {
    contentEl.innerHTML = "<p class=\"ja-score-text\">No application form detected. Click &quot;Apply&quot; or navigate to the application form to see questions.</p>";
    return;
  }

  // ── Step 2: Categorize fields ──────────────────────────────────────────────
  const commonKeys = ["firstname", "lastname", "email", "phone", "address", "linkedin", "github", "portfolio", "resume", "coverletter", "country", "city"];
  const isCommon = (f) => {
    const keys = getFieldKeys({ label: f.label, name: f.name, id: f.id, placeholder: f.placeholder });
    return commonKeys.some((k) => keys.some((fk) => fk.includes(k) || k.includes(fk)));
  };
  const list = (id === "common-questions" ? fields.filter(isCommon) : fields.filter(f => !isCommon(f))).slice(0, 15);

  if (!list.length) {
    contentEl.innerHTML = "<p class=\"ja-score-text\">No questions in this category.</p>";
    return;
  }

  const statusWrap = rootEl?.querySelector(`[data-accordion-id="${id}"]`)?.querySelector(".ja-accordion-status-text");
  if (statusWrap) statusWrap.textContent = `0/${list.length}`;

  if (id === "common-questions") {
    contentEl.innerHTML = renderQuestionsHtml(id, list, null);
    attachFieldScrollHandlers(contentEl);
    contentEl.querySelector(".ja-cq-editall")?.addEventListener("click", openResumeGeneratorUrl);
    return;
  }

  contentEl.innerHTML = `
    ${renderQuestionsHtml(id, list, null)}
    <div class="ja-map-btn-row">
      <button type="button" class="ja-map-answers-btn" id="ja-map-answers-${id}">
        ${QUESTION_UI_ICONS.sparkles}<span>Map Answers</span>
      </button>
    </div>`;

  contentEl.querySelector(`#ja-map-answers-${id}`)?.addEventListener("click", () => {
    void runAccordionMapAnswers(id, contentEl, rootEl, { auto: false });
  });
}
