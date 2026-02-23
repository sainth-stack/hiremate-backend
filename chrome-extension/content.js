const FIELD_MAP = {
  name: ["name", "full name", "first name", "last name", "candidate name", "legal name"],
  email: ["email", "e-mail", "email address"],
  phone: ["phone", "mobile", "telephone", "cell", "contact number"],
  linkedin: ["linkedin", "linkedin url", "linkedin profile"],
  github: ["github", "github url", "github profile"],
  portfolio: ["portfolio", "portfolio url", "website", "personal website"],
  location: ["location", "current location", "city", "address"],
  skills: ["skills", "skill", "technical skills", "key skills", "technologies"],
  experience: ["experience", "work experience", "employment", "summary", "about you"],
  education: ["education", "degree", "university", "college", "school"],
  company: ["current company", "company"],
  title: ["title", "job title", "current title", "position"],
  resume: ["resume", "cv", "upload", "attach", "cover letter", "paste your resume"],
};

const TEXTLIKE_INPUT_TYPES = new Set([
  "",
  "text",
  "email",
  "tel",
  "url",
  "search",
  "number",
  "date",
  "datetime-local",
  "month",
  "week",
  "time",
  "password",
]);

const IGNORE_INPUT_TYPES = new Set(["submit", "button", "hidden", "image", "reset", "range", "color"]);
const FIELD_SELECTOR = [
  "input",
  "textarea",
  "select",
  '[contenteditable="true"]',
  '[contenteditable=""]',
  '[contenteditable]',
  '[role="textbox"]',
  '[role="combobox"]',
  '[role="searchbox"]',
  '[role="spinbutton"]',
  ".ql-editor",
].join(",");

const LOG_PREFIX = "[JobAutofill][content]";
const INPAGE_ROOT_ID = "job-autofill-inpage-root";
const LOGIN_PAGE_ORIGINS = [
  "http://localhost:5173",
  "http://127.0.0.1:5173",
  "http://localhost:5174",
  "http://127.0.0.1:5174",
  "https://hiremate.ai",
  "https://www.hiremate.ai",
  "https://app.hiremate.ai",
  "https://hiremate.com",
  "https://www.hiremate.com",
];
const DEFAULT_LOGIN_PAGE_URL = "http://localhost:5173/login";

function logInfo(message, meta) {
  if (meta !== undefined) console.info(LOG_PREFIX, message, meta);
  else console.info(LOG_PREFIX, message);
}
function logWarn(message, meta) {
  if (meta !== undefined) console.warn(LOG_PREFIX, message, meta);
  else console.warn(LOG_PREFIX, message);
}

function normalizeKey(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function getText(el) {
  if (!el) return "";
  return (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
}

function escapeHtml(s) {
  if (!s) return "";
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

const ACCORDION_ICONS = {
  document: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>',
  coverLetter: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>',
  person: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>',
};

/** Reusable accordion component. opts: { id, iconBg, iconSvg, title, showHelpIcon, statusText, statusCheckmark } */
function createAccordionItem(opts) {
  const id = escapeHtml(opts.id || "accordion");
  const iconBg = escapeHtml(opts.iconBg || "#e0e7ff");
  const iconSvg = opts.iconSvg || ACCORDION_ICONS.document;
  const title = escapeHtml(opts.title || "");
  const showHelpIcon = !!opts.showHelpIcon;
  const statusText = escapeHtml(opts.statusText || "");
  const statusCheckmark = !!opts.statusCheckmark;
  return `
    <div class="ja-accordion-item" data-accordion-id="${id}">
      <button type="button" class="ja-accordion-header" aria-expanded="false" aria-controls="ja-accordion-body-${id}" id="ja-accordion-trigger-${id}">
        <span class="ja-accordion-icon" style="background:${iconBg}">${iconSvg}</span>
        <span class="ja-accordion-title-wrap">
          <span class="ja-accordion-title">${title}</span>
          ${showHelpIcon ? '<span class="ja-accordion-help" title="Help">?</span>' : ""}
        </span>
        ${statusText || statusCheckmark ? `<span class="ja-accordion-status">${statusCheckmark ? '<span class="ja-accordion-check">✓</span>' : ""}${statusText ? `<span class="ja-accordion-status-text">${statusText}</span>` : ""}</span>` : ""}
        <span class="ja-accordion-chevron" aria-hidden="true">▼</span>
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
    const resumes = await fetchResumesFromApi();
    if (resumes.length === 0) {
      contentEl.innerHTML = `
        <p class="ja-score-text">No resumes yet. Upload in your OpsBrain profile.</p>
        <button type="button" class="ja-action" style="margin-top:8px;">Open Profile</button>
      `;
      contentEl.querySelector(".ja-action")?.addEventListener("click", () => openResumeGeneratorUrl());
      return;
    }
    const defaultResume = resumes.find((r) => r.is_default) || resumes[0];
    const selectedId = defaultResume?.id ?? resumes[0]?.id;
    const selectId = "ja-accordion-resume-select";
    contentEl.innerHTML = `
      <div class="ja-resume-accordion-row">
        <select class="ja-resume-select" id="${selectId}">
          ${resumes.map((r) => `<option value="${r.id}" ${r.id === selectedId ? "selected" : ""}>${escapeHtml(r.resume_name || `Resume ${r.id}`)}</option>`).join("")}
        </select>
        <button type="button" class="ja-action ja-upload-preview">Preview</button>
      </div>
      <p class="ja-resume-preview-hint">Default selected resume shown above. Click Preview to open PDF.</p>
    `;
    contentEl.querySelector(".ja-upload-preview")?.addEventListener("click", async () => {
      const sel = contentEl.querySelector(`#${selectId}`);
      const id = sel ? parseInt(sel.value, 10) : selectedId;
      if (!id || id <= 0) return;
      try {
        const apiBase = await getApiBase();
        const headers = await getAuthHeaders();
        const res = await fetchWithAuthRetry(`${apiBase}/resume/${id}/file`, { headers });
        if (res.ok) {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          window.open(url, "_blank");
        }
      } catch (_) {}
    });
  } catch (err) {
    contentEl.innerHTML = "<p class=\"ja-score-text\">Failed to load resumes.</p>";
  }
}

async function loadCoverLetterAccordionContent(contentEl, rootEl) {
  contentEl.innerHTML = "<p class=\"ja-score-text\">Loading...</p>";
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    let data = null;
    try {
      const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/cover-letter`, { headers });
      data = res.ok ? await res.json() : null;
    } catch (_) {
      data = null;
    }
    const letter = data?.content || "";
    const jobTitle = data?.job_title || "";
    if (letter) {
      contentEl.innerHTML = `
        <div class="ja-cover-letter-preview">
          ${jobTitle ? `<p class="ja-cover-letter-job">${escapeHtml(jobTitle)}</p>` : ""}
          <div class="ja-cover-letter-text">${escapeHtml(letter).replace(/\n/g, "<br>")}</div>
        </div>
        <button type="button" class="ja-action" id="ja-generate-cover-letter">Regenerate</button>
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
        let jobDescription = "";
        let jobTitle = document.title?.split(/[|\-–—]/)[0]?.trim() || "";
        try {
          const pageHtml = await getPageHtmlForKeywordsApi?.();
          if (pageHtml) {
            const analyzeRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/keywords/analyze`, {
              method: "POST",
              headers: { ...headers, "Content-Type": "application/json" },
              body: JSON.stringify({ url: window.location.href, page_html: pageHtml }),
            });
            if (analyzeRes.ok) {
              const ad = await analyzeRes.json();
              jobDescription = ad.job_description || "";
              jobTitle = jobTitle || ad.job_title || "";
            }
          }
        } catch (_) {}
        const genRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/cover-letter/generate`, {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({ job_description: jobDescription, job_title: jobTitle }),
        });
        if (genRes.ok) {
          const genData = await genRes.json();
          await loadCoverLetterAccordionContent(contentEl, rootEl);
        } else {
          statusP.textContent = "Generation failed.";
        }
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

async function loadQuestionsAccordionContent(id, contentEl, rootEl) {
  contentEl.innerHTML = "<p class=\"ja-score-text\">Scanning page for form fields...</p>";
  try {
    let fields = [];
    if (window.self === window.top) {
      const scrapeRes = await chrome.runtime.sendMessage({ type: "SCRAPE_ALL_FRAMES", scope: "all" });
      fields = scrapeRes?.ok ? (scrapeRes.fields || []) : [];
    } else {
      const scraped = scrapeFields({ scope: "all" });
      fields = scraped?.fields || [];
    }
    if (!fields || fields.length === 0) {
      contentEl.innerHTML = "<p class=\"ja-score-text\">No application form detected. Click &quot;Apply&quot; or navigate to the application form to see questions.</p>";
      return;
    }
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
      }),
    });
    if (!mapRes.ok) {
      let errMsg = "Failed to load mappings";
      try {
        const errBody = await mapRes.json();
        const d = errBody?.detail;
        errMsg = typeof d === "string" ? d : Array.isArray(d) ? (d[0]?.msg || String(d[0] || d)) : errMsg;
      } catch (_) {}
      contentEl.innerHTML = `<p class="ja-score-text">${escapeHtml(String(errMsg))} (${mapRes.status})</p>`;
      return;
    }
    const mapData = await mapRes.json();
    const mappings = mapData?.mappings || {};
    const commonKeys = ["firstname", "lastname", "email", "phone", "address", "linkedin", "github", "portfolio", "resume", "coverletter", "country", "city"];
    const isCommon = (f) => {
      const keys = getFieldKeys({ label: f.label, name: f.name, id: f.id, placeholder: f.placeholder });
      return commonKeys.some((k) => keys.some((fk) => fk.includes(k) || k.includes(fk)));
    };
    const common = fields.filter(isCommon);
    const unique = fields.filter((f) => !isCommon(f));
    const list = id === "common-questions" ? common : unique;
    const filled = list.filter((f) => {
      const m = mappings[f.index];
      return m?.value != null && String(m.value).trim() !== "";
    }).length;
    const total = list.length;
    const itemHtml = list.slice(0, 15).map((f) => {
      const m = mappings[f.index] || {};
      const val = m.value != null ? String(m.value).trim() : "";
      const label = f.label || f.name || f.placeholder || `Field ${f.index + 1}`;
      // Derive display type: select, date, textarea, or input
      let displayType = "input";
      if (f.tag === "select") displayType = "select";
      else if (f.tag === "textarea") displayType = "textarea";
      else if (f.type === "date" || f.type === "datetime-local" || f.type === "month") displayType = "date";
      const typeBadge = `<span class="ja-field-type-badge ja-field-type-${displayType}">${displayType}</span>`;
      return `<div class="ja-question-row">${typeBadge}<span class="ja-question-label">${escapeHtml(label)}</span><span class="ja-question-value">${escapeHtml(val || "—")}</span></div>`;
    }).join("");
    contentEl.innerHTML = itemHtml ? `<div class="ja-questions-list">${itemHtml}</div>` : "<p class=\"ja-score-text\">No questions in this category.</p>";
    const statusWrap = rootEl?.querySelector(`[data-accordion-id="${id}"]`)?.querySelector(".ja-accordion-status-text");
    if (statusWrap) statusWrap.textContent = `Filled (${filled}/${total})`;
  } catch (err) {
    contentEl.innerHTML = "<p class=\"ja-score-text\">Failed to load questions.</p>";
  }
}

function isVisible(el) {
  if (!el || !el.ownerDocument || !el.isConnected) return false;
  if (el.getAttribute("aria-hidden") === "true" || el.hidden) return false;

  const style = el.ownerDocument.defaultView?.getComputedStyle(el);
  if (!style) return false;
  if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
  if (el.getClientRects().length === 0) return false;
  return true;
}

function getAllRoots(doc) {
  const roots = [];
  const seen = new Set();
  function addRoot(root) {
    if (!root || seen.has(root)) return;
    seen.add(root);
    roots.push(root);
    try {
      const all = root.querySelectorAll ? root.querySelectorAll("*") : [];
      for (const el of all) {
        if (el.shadowRoot) addRoot(el.shadowRoot);
      }
    } catch (_) {}
  }
  addRoot(doc);
  return roots;
}

function getDocuments(includeNestedDocuments = true) {
  const docs = [];
  const queue = [document];
  const seen = new Set();
  if (!includeNestedDocuments) return [document];
  while (queue.length > 0) {
    const doc = queue.shift();
    if (!doc || seen.has(doc)) continue;
    seen.add(doc);
    docs.push(doc);

    const iframes = Array.from(doc.querySelectorAll("iframe, frame"));
    for (const frame of iframes) {
      try {
        if (frame.contentDocument) queue.push(frame.contentDocument);
      } catch (_) {
        // Ignore cross-origin frames.
      }
    }
  }
  return docs;
}

function isFillable(field, includeHidden = false) {
  if (!field || !field.ownerDocument || !field.isConnected) return false;
  const tag = (field.tagName || "").toLowerCase();
  const type = (field.type || "").toLowerCase();

  if (tag === "input" && type === "file") {
    if (field.disabled || field.getAttribute("aria-disabled") === "true") return false;
    return true;
  }

  if (!includeHidden && !isVisible(field)) return false;
  if (field.disabled || field.readOnly) return false;
  if (field.getAttribute("aria-disabled") === "true") return false;

  const role = (field.getAttribute("role") || "").toLowerCase();

  if (tag === "input") {
    if (IGNORE_INPUT_TYPES.has(type)) return false;
    return true;
  }

  if (tag === "textarea" || tag === "select") return true;
  if (field.isContentEditable) return true;
  if (role === "textbox" || role === "combobox" || role === "searchbox" || role === "spinbutton") return true;
  if (tag === "div" || tag === "span") {
    const ce = field.getAttribute("contenteditable");
    if (ce === "true" || ce === "") return true;
  }

  return false;
}

function getClosestQuestionText(field) {
  const container = field.closest(
    ".field,.form-group,.formField,.question,.application-question,.input-wrapper,.input-group,li,section,div"
  );
  if (!container) return "";
  const candidates = container.querySelectorAll("label,legend,h1,h2,h3,h4,strong,p,span");
  for (const candidate of candidates) {
    if (candidate.contains(field)) continue;
    const txt = getText(candidate);
    if (txt && txt.length <= 180) return txt;
  }
  return "";
}

function getLabelText(field) {
  const doc = field.ownerDocument || document;

  if (field.id) {
    try {
      const label = doc.querySelector(`label[for="${CSS.escape(field.id)}"]`);
      if (label) {
        const txt = getText(label);
        if (txt) return txt;
      }
    } catch (_) {
      // Ignore invalid selectors.
    }
  }

  const parentLabel = field.closest("label");
  if (parentLabel) {
    const clone = parentLabel.cloneNode(true);
    const controls = clone.querySelectorAll(FIELD_SELECTOR);
    controls.forEach((el) => el.remove());
    const txt = getText(clone);
    if (txt) return txt;
  }

  const ariaLabel = field.getAttribute("aria-label");
  if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim();

  const labelledBy = field.getAttribute("aria-labelledby");
  if (labelledBy) {
    const ids = labelledBy.split(/\s+/).filter(Boolean);
    const txt = ids
      .map((id) => {
        const el = doc.getElementById(id);
        return el ? getText(el) : "";
      })
      .filter(Boolean)
      .join(" ");
    if (txt) return txt;
  }

  const placeholder = field.getAttribute("placeholder");
  if (placeholder && placeholder.trim()) return placeholder.trim();

  const questionText = getClosestQuestionText(field);
  if (questionText) return questionText;

  const name = field.getAttribute("name");
  if (name && name.trim()) return name.trim();
  const id = field.getAttribute("id");
  if (id && id.trim()) return id.trim();
  return "";
}

function getFieldMeta(field) {
  const tag = (field.tagName || "").toLowerCase();
  const role = (field.getAttribute("role") || "").toLowerCase();
  let type = (field.type || "").toLowerCase();

  if (tag === "select") type = "select";
  if (tag === "textarea") type = "textarea";
  if (!type && field.isContentEditable) type = "contenteditable";
  if (!type && role) type = role;

  return {
    tag,
    role,
    type,
    label: getLabelText(field),
    name: field.getAttribute("name") || "",
    id: field.getAttribute("id") || "",
    placeholder: field.getAttribute("placeholder") || "",
    required: !!field.required || field.getAttribute("aria-required") === "true",
  };
}

function isInsideExtensionWidget(el) {
  if (!el?.ownerDocument) return false;
  const doc = el.ownerDocument;
  if (doc !== document) return false;
  const widget = document.getElementById(INPAGE_ROOT_ID);
  return !!(widget && widget.contains(el));
}

function getFillableFields(includeNestedDocuments = true, includeHidden = false) {
  const out = [];
  const seen = new Set();
  let totalCandidates = 0;
  const docs = getDocuments(includeNestedDocuments);

  for (const doc of docs) {
    const roots = getAllRoots(doc);
    for (const root of roots) {
      try {
        const candidates = Array.from(root.querySelectorAll(FIELD_SELECTOR));
        for (const el of candidates) {
          if (seen.has(el)) continue;
          if (isInsideExtensionWidget(el)) continue;
          seen.add(el);
          totalCandidates += 1;
          if (isFillable(el, includeHidden)) out.push(el);
        }
      } catch (_) {}
    }
  }
  if (totalCandidates > 0 && out.length === 0) {
    logWarn("Found form candidates but all filtered out", { totalCandidates, includeHidden, docCount: docs.length });
  }
  return out;
}

function dispatchFrameworkEvents(field) {
  const tag = (field.tagName || "").toLowerCase();
  // Selects handle their own events in setNativeValue to avoid double-firing
  if (tag === "select") return;
  field.dispatchEvent(new Event("focus", { bubbles: true }));
  try {
    field.dispatchEvent(new InputEvent("input", { bubbles: true, composed: true, inputType: "insertText" }));
  } catch (_) {
    field.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
  }
  field.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
  field.dispatchEvent(new Event("blur", { bubbles: true }));
}

function focusWithoutScroll(field) {
  try {
    field.focus({ preventScroll: true });
    return;
  } catch (_) {
    // Fallback for older browsers.
  }
  const doc = field.ownerDocument || document;
  const view = doc.defaultView || window;
  const x = view.scrollX;
  const y = view.scrollY;
  field.focus();
  view.scrollTo(x, y);
}

function setNativeValue(field, nextValue) {
  const value = String(nextValue ?? "");
  const tag = (field.tagName || "").toLowerCase();

  if (field.isContentEditable || tag === "div" || tag === "span") {
    focusWithoutScroll(field);
    field.textContent = value;
    dispatchFrameworkEvents(field);
    return true;
  }

  if (tag === "select") {
    const valStr = normalizeKey(value);
    const options = Array.from(field.options || []).filter(opt => {
      // Skip placeholder options like "Select...", "Choose...", empty options
      const optText = normalizeKey(opt.text);
      const optValue = normalizeKey(opt.value);
      return optValue !== "" && 
             !optText.startsWith("select") && 
             !optText.startsWith("choose") && 
             !optText.startsWith("pick");
    });
    
    if (options.length === 0) {
      logWarn("Select dropdown has no valid options", {
        field: field.name || field.id || field.placeholder
      });
      return false;
    }
    
    // Try exact match first (case-insensitive)
    let match = options.find((opt) => 
      String(opt.value).toLowerCase() === value.toLowerCase() ||
      opt.text.toLowerCase() === value.toLowerCase()
    );
    
    // Special handling for Yes/No questions
    if (!match && (valStr === "yes" || valStr === "no" || valStr === "none")) {
      match = options.find((opt) => {
        const optText = normalizeKey(opt.text);
        const optValue = normalizeKey(opt.value);
        return optText === valStr || optValue === valStr;
      });
    }
    
    // Try normalized text/value match
    if (!match) {
      match = options.find((opt) => normalizeKey(opt.text) === valStr || normalizeKey(opt.value) === valStr);
    }
    
    // Try partial contains match (both ways)
    if (!match) {
      match = options.find((opt) => {
        const optText = normalizeKey(opt.text);
        const optValue = normalizeKey(opt.value);
        return optText.includes(valStr) || valStr.includes(optText) || 
               optValue.includes(valStr) || valStr.includes(optValue);
      });
    }
    
    // Try first word match (for cases like "Male" matching "Male / पुरुष")
    if (!match && valStr) {
      const firstWord = valStr.split(/\s+/)[0];
      match = options.find((opt) => {
        const optText = normalizeKey(opt.text).split(/\s+/)[0];
        return optText === firstWord || optText.includes(firstWord) || firstWord.includes(optText);
      });
    }
    
    if (!match) {
      logWarn("Select dropdown match failed", {
        field: field.name || field.id || field.placeholder,
        value,
        availableOptions: options.map(opt => ({ text: opt.text, value: opt.value })).slice(0, 10)
      });
      return false;
    }

    // Step 1: Focus and simulate opening the dropdown
    focusWithoutScroll(field);
    field.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
    field.dispatchEvent(new MouseEvent("mouseup",  { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
    field.dispatchEvent(new MouseEvent("click",    { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));

    // Step 2: Set value using the native prototype setter so React/Vue get the real DOM change
    const nativeSetter = Object.getOwnPropertyDescriptor(
      Object.getPrototypeOf(field), "value"
    )?.set || Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
    if (nativeSetter) {
      nativeSetter.call(field, match.value);
    } else {
      field.value = match.value;
    }

    // Step 3: Fool React's _valueTracker so it detects the value as changed
    // (React skips onChange if tracker thinks value didn't change)
    try {
      const tracker = field._valueTracker;
      if (tracker) {
        tracker.setValue(field.value === match.value ? "" : field.value);
      }
    } catch (_) {}

    // Step 4: Simulate clicking the matching <option> element
    try {
      match.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
      match.dispatchEvent(new MouseEvent("mouseup",   { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
      match.dispatchEvent(new MouseEvent("click",     { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
    } catch (_) {}

    // Step 5: Fire change + blur so all framework listeners fire
    field.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    field.dispatchEvent(new Event("blur",   { bubbles: true }));

    logInfo("Select dropdown filled", {
      field: field.name || field.id,
      matchedOption: { text: match.text, value: match.value }
    });
    return true;
  }

  if (tag === "input") {
    const inputType = (field.type || "").toLowerCase();
    if (inputType === "checkbox") {
      const shouldCheck = value === "true" || value === "1" || value === "yes" || value === "on";
      field.checked = shouldCheck;
      dispatchFrameworkEvents(field);
      return true;
    }
    if (inputType === "radio") {
      const own = normalizeKey(field.value);
      const wanted = normalizeKey(value);
      if (own && wanted && own !== wanted) return false;
      field.checked = true;
      dispatchFrameworkEvents(field);
      return true;
    }
    if (inputType === "date" || inputType === "datetime-local" || inputType === "month") {
      const formattedDate = formatDateForInput(value);
      focusWithoutScroll(field);
      field.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      const proto = Object.getPrototypeOf(field);
      const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
      if (descriptor?.set) descriptor.set.call(field, formattedDate);
      else field.value = formattedDate;
      try { if (field._valueTracker) field._valueTracker.setValue(""); } catch (_) {}
      dispatchFrameworkEvents(field);
      return true;
    }

    // Regular text/email/tel/number input — simulate click then type
    focusWithoutScroll(field);
    field.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    const nativeSetter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(field), "value")?.set
      || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    if (nativeSetter) nativeSetter.call(field, value);
    else field.value = value;
    try { if (field._valueTracker) field._valueTracker.setValue(""); } catch (_) {}
    dispatchFrameworkEvents(field);
    return true;
  }

  if (tag === "textarea") {
    focusWithoutScroll(field);
    field.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    const nativeSetter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(field), "value")?.set
      || Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    if (nativeSetter) nativeSetter.call(field, value);
    else field.value = value;
    try { if (field._valueTracker) field._valueTracker.setValue(""); } catch (_) {}
    dispatchFrameworkEvents(field);
    return true;
  }

  const role = (field.getAttribute("role") || "").toLowerCase();
  if (role === "textbox" || role === "combobox") {
    focusWithoutScroll(field);
    field.textContent = value;
    dispatchFrameworkEvents(field);
    return true;
  }

  return false;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const AUTOFILL_FAILED_CLASS = "ja-autofill-failed";
function ensureFailHighlightStyle(doc = document) {
  const id = "ja-autofill-fail-style";
  if (doc.getElementById(id)) return;
  const style = doc.createElement("style");
  style.id = id;
  style.textContent = `.${AUTOFILL_FAILED_CLASS} { outline: 2px solid #dc2626 !important; box-shadow: 0 0 0 2px #dc2626 !important; }`;
  (doc.head || doc.documentElement).appendChild(style);
}

function openDropdownForSelection(field) {
  try {
    const tag = (field.tagName || "").toLowerCase();
    const role = (field.getAttribute("role") || "").toLowerCase();
    if (tag === "select" || role === "combobox") {
      field.focus();
      field.click();
      field.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    }
  } catch (_) {}
}

function highlightFailedField(field) {
  const doc = field.ownerDocument || document;
  ensureFailHighlightStyle(doc);
  field.classList.add(AUTOFILL_FAILED_CLASS);
  openDropdownForSelection(field);
}

const SCROLL_DURATION_MS = 200;
const SCROLL_WAIT_AFTER_MS = 50;

async function scrollFieldIntoView(field) {
  const rect = field.getBoundingClientRect();
  const vh = window.innerHeight;
  if (rect.top >= 0 && rect.bottom <= vh) return;
  try {
    field.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
  } catch (_) {
    field.scrollIntoView({ block: "center" });
  }
  await delay(SCROLL_DURATION_MS + SCROLL_WAIT_AFTER_MS);
}

function formatDateForInput(value) {
  if (!value) return value;
  const str = String(value).trim();
  if (!str) return value;
  const isoMatch = str.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) return `${isoMatch[1]}-${isoMatch[2]}-${isoMatch[3]}`;
  const dmyMatch = str.match(/(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/);
  if (dmyMatch) {
    const [, a, b, y] = dmyMatch;
    return `${y}-${b.padStart(2, "0")}-${a.padStart(2, "0")}`;
  }
  return value;
}

function getMimeTypeForResume(fileName) {
  const ext = (fileName || "").toLowerCase().split(".").pop();
  const mimeMap = {
    pdf: "application/pdf",
    doc: "application/msword",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    txt: "text/plain",
    rtf: "application/rtf",
  };
  return mimeMap[ext] || "application/pdf";
}

async function fillFileInput(field, resumeData) {
  if (!resumeData?.buffer) return false;
  const fileName = resumeData.name || "resume.pdf";
  const mimeType = getMimeTypeForResume(fileName);
  const blob = new Blob([new Uint8Array(resumeData.buffer)], { type: mimeType });
  const file = new File([blob], fileName, { type: mimeType });
  const dt = new DataTransfer();
  dt.items.add(file);
  try {
    field.files = dt.files;
    dispatchFrameworkEvents(field);
    return field.files?.length > 0;
  } catch (e) {
    logWarn("fillFileInput failed (some sites block programmatic file assignment)", { error: String(e) });
    return false;
  }
}

function findContinueButton(doc = document) {
  const sel = 'button, [role="button"], input[type="submit"], [data-automation-id="continueButton"]';
  for (const el of doc.querySelectorAll(sel)) {
    const text = (el.textContent || el.innerText || el.value || "").trim().toLowerCase();
    if (text.includes("continue") || text === "next") return el;
  }
  for (const el of doc.querySelectorAll("*")) {
    if (!el.shadowRoot) continue;
    for (const sh of el.shadowRoot.querySelectorAll(sel)) {
      const text = (sh.textContent || sh.innerText || sh.value || "").trim().toLowerCase();
      if (text.includes("continue") || text === "next") return sh;
    }
  }
  return null;
}

function scrapeFields(options = {}) {
  const includeNestedDocuments = options.scope !== "current_document";
  logInfo("Starting DOM scrape for fillable fields", { scope: options.scope });
  let fillable = getFillableFields(includeNestedDocuments || true, true);
  if (fillable.length === 0) {
    fillable = getFillableFields(true, false);
  }
  if (fillable.length === 0) {
    fillable = getFillableFields(true, true);
  }
  const fields = fillable.map((el, index) => {
    const meta = getFieldMeta(el);
    const options =
      meta.tag === "select"
        ? Array.from(el.options || [])
            .map((o) => (o.text || "").trim())
            .filter(Boolean)
        : null;

    return {
      index,
      label: meta.label || null,
      name: meta.name || null,
      id: meta.id || null,
      placeholder: meta.placeholder || null,
      required: meta.required,
      type: meta.type || null,
      tag: meta.tag || null,
      role: meta.role || null,
      options,
    };
  });
  const preview = fields.slice(0, 15).map((f) => ({
    index: f.index,
    type: f.type,
    label: f.label,
    id: f.id,
    name: f.name,
    required: f.required,
  }));
  logInfo("DOM scrape completed", {
    totalFields: fields.length,
    requiredFields: fields.filter((f) => f.required).length,
    preview,
  });
  return { fields };
}

function isEmptyField(field) {
  const tag = (field.tagName || "").toLowerCase();
  if (field.isContentEditable) return !normalizeKey(getText(field));
  if (tag === "input") {
    const type = (field.type || "").toLowerCase();
    if (type === "checkbox" || type === "radio") return !field.checked;
    return !String(field.value || "").trim();
  }
  if (tag === "textarea") return !String(field.value || "").trim();
  if (tag === "select") return !String(field.value || "").trim();
  return !normalizeKey(getText(field));
}

function getFieldKeys(meta) {
  const sources = [
    meta.label,
    meta.name,
    meta.id,
    meta.placeholder,
    meta.type,
    meta.role,
    meta.tag,
  ].filter(Boolean);
  return sources.map((s) => normalizeKey(s)).filter(Boolean);
}

function pickRuleBasedValue(meta, profile, customAnswers) {
  const keys = getFieldKeys(meta);
  const allText = keys.join(" ");

  const customEntries = Object.entries(customAnswers || {});
  for (const [question, answer] of customEntries) {
    const normQ = normalizeKey(question);
    if (!normQ || !answer) continue;
    if (keys.includes(normQ) || allText.includes(normQ) || normQ.includes(allText)) return answer;
  }

  for (const [profileKey, aliases] of Object.entries(FIELD_MAP)) {
    if (!profile?.[profileKey]) continue;
    const match = aliases.some((alias) => {
      const normAlias = normalizeKey(alias);
      return keys.includes(normAlias) || allText.includes(normAlias);
    });
    if (match) return profile[profileKey];
  }

  if (meta.tag === "input" && TEXTLIKE_INPUT_TYPES.has(meta.type)) {
    if (meta.type === "email" && profile?.email) return profile.email;
    if (meta.type === "tel" && profile?.phone) return profile.phone;
    if (meta.type === "url") {
      if (allText.includes("linkedin") && profile?.linkedin) return profile.linkedin;
      if (allText.includes("github") && profile?.github) return profile.github;
      if (profile?.portfolio) return profile.portfolio;
    }
  }

  if (meta.tag === "textarea" && profile?.experience) {
    if (allText.includes("experience") || allText.includes("summary") || allText.includes("about")) {
      return profile.experience;
    }
  }

  return null;
}

async function getResumeFromBackground() {
  try {
    const res = await chrome.runtime.sendMessage({ type: "GET_RESUME" });
    if (res?.ok) return res.data || null;
  } catch (_) {
    // Ignore resume retrieval errors for non-file fields.
  }
  return null;
}

async function fillWithValues(payload) {
  const includeNestedDocuments = payload.scope !== "current_document";
  const { values = {}, resumeData, onProgress, shouldAbort, shouldSkip } = payload;
  logInfo("Starting mapped fill", { providedValues: Object.keys(values).length });
  let fillable = getFillableFields(includeNestedDocuments, false);
  if (fillable.length === 0) fillable = getFillableFields(true, true);
  const effectiveResumeData = resumeData || (await getResumeFromBackground()) || (await getStaticResume());
  const fillDelay = 60 + Math.floor(Math.random() * 60);
  let filledCount = 0;
  let resumeUploadCount = 0;
  let failedCount = 0;
  const failedFields = [];

  const indexed = fillable.map((el, i) => ({ element: el, originalIndex: i }));

  const totalToFill = indexed.length;
  for (let idx = 0; idx < indexed.length; idx++) {
    if (shouldAbort?.()) break;
    if (shouldSkip?.()) continue;
    const { element: field, originalIndex: i } = indexed[idx];
    const id = field.getAttribute("id");
    let val;

    await scrollFieldIntoView(field);

    const meta = getFieldMeta(field);
    const fieldLabel = meta.label || meta.name || meta.placeholder || getClosestQuestionText(field) || `Field ${i + 1}`;
    const isResumeField =
      (field.type || "").toLowerCase() === "file" &&
      (getFieldKeys(meta).join(" ").includes("resume") || getFieldKeys(meta).join(" ").includes("cv"));
    const progressMessage = isResumeField
      ? "Filling resume..."
      : `Filling field ${idx + 1} of ${totalToFill}`;
    if (onProgress) {
      onProgress({
        phase: "filling",
        current: idx + 1,
        total: totalToFill,
        message: progressMessage,
        label: fieldLabel,
      });
    }

    if (id && values[id] !== undefined) {
      val = typeof values[id] === "object" && values[id] !== null ? values[id].value : values[id];
    } else if (values[i] !== undefined) {
      val = typeof values[i] === "object" && values[i] !== null ? values[i].value : values[i];
    }

    if ((field.type || "").toLowerCase() === "file") {
      const fieldKeysText = getFieldKeys(meta).join(" ");
      const looksLikeResumeField = fieldKeysText.includes("resume") || fieldKeysText.includes("cv");
      const shouldUploadResume = val === "RESUME_FILE" || looksLikeResumeField;
      if (shouldUploadResume && effectiveResumeData) {
        const ok = await fillFileInput(field, effectiveResumeData);
        if (ok) {
          resumeUploadCount += 1;
          logInfo("Filled resume field", { index: i, label: meta.label });
        } else {
          failedCount += 1;
          highlightFailedField(field);
          failedFields.push({ element: field, label: fieldLabel });
        }
      } else if (shouldUploadResume) {
        failedCount += 1;
        highlightFailedField(field);
        failedFields.push({ element: field, label: fieldLabel });
        logWarn("Resume field found but no resume data available", {
          index: i,
          id: id || null,
          label: meta.label || null,
        });
      }
      await delay(fillDelay);
      continue;
    }

    if (val === undefined || val === null || val === "") {
      if (meta.required) {
        failedCount += 1;
        highlightFailedField(field);
        failedFields.push({ element: field, label: fieldLabel });
      }
      await delay(fillDelay);
      continue;
    }

    const success = setNativeValue(field, val);
    if (success) {
      filledCount += 1;
      logInfo("Filled field", { index: i, label: meta.label, value: String(val).substring(0, 50) });
    } else {
      failedCount += 1;
      highlightFailedField(field);
      failedFields.push({ element: field, label: fieldLabel });
    }
    await delay(fillDelay);
  }
  logInfo("Mapped fill completed", {
    totalFillable: fillable.length,
    textFieldsFilled: filledCount,
    resumeUploads: resumeUploadCount,
    failedCount,
  });
  return { filledCount, resumeUploadCount, failedCount, failedFields };
}

async function fillFormRuleBased(payload = {}) {
  const includeNestedDocuments = payload.scope !== "current_document";
  logInfo("Starting rule-based fill");
  const [{ profile = {}, customAnswers = {} }, resumeData] = await Promise.all([
    chrome.storage.local.get(["profile", "customAnswers"]),
    getResumeFromBackground(),
  ]);

  const fillable = getFillableFields(includeNestedDocuments);
  const fillDelay = 60 + Math.floor(Math.random() * 60);
  let filledCount = 0;
  let resumeUploadCount = 0;

  for (const field of fillable) {
    if (!isEmptyField(field)) continue;

    const meta = getFieldMeta(field);
    if (meta.type === "file") {
      const shouldUseResume = getFieldKeys(meta).join(" ").includes("resume");
      if (shouldUseResume && resumeData) {
        const ok = await fillFileInput(field, resumeData);
        if (ok) {
          filledCount += 1;
          resumeUploadCount += 1;
        }
      }
      await delay(fillDelay);
      continue;
    }

    const val = pickRuleBasedValue(meta, profile, customAnswers);
    if (!val) continue;

    const ok = setNativeValue(field, val);
    if (ok) {
      filledCount += 1;
      await delay(fillDelay);
    }
  }

  logInfo("Rule-based fill completed", {
    totalFillable: fillable.length,
    totalFilled: filledCount,
    resumeUploads: resumeUploadCount,
  });
  return { filledCount };
}

function isCareerPage(urlStr = window.location.href) {
  const url = String(urlStr || "").toLowerCase();
  return (
    url.includes("/careers") ||
    url.includes("careers.") ||
    url.includes("jobs.") ||
    url.includes("/jobs") ||
    url.includes("/apply") ||
    url.includes("/job/") ||
    url.includes("greenhouse.io") ||
    url.includes("lever.co") ||
    url.includes("myworkdayjobs.com") ||
    url.includes("workday.com") ||
    url.includes("smartrecruiters.com") ||
    url.includes("icims.com") ||
    url.includes("ashbyhq.com") ||
    url.includes("bamboohr.com") ||
    url.includes("jobvite.com") ||
    url.includes("recruit") ||
    url.includes("talent")
  );
}

/** Content hint: page shows multiple job listings (cards/links). */
function hasListingPageContent() {
  const body = document.body;
  if (!body) return false;
  const sel = [
    "a[href*='job']",
    "a[href*='career']",
    "a[href*='position']",
    "[data-job-id]",
    "[data-testid*='job-card']",
    "[class*='job-card']",
    "[class*='job-listing']",
    "[class*='position-card']",
  ].join(",");
  const matches = body.querySelectorAll(sel);
  const jobLikeCount = Array.from(matches).filter((el) => {
    const text = (el.textContent || "").trim();
    const href = (el.getAttribute("href") || "").toLowerCase();
    return text.length >= 10 && text.length < 120 && (href.includes("job") || href.includes("detail") || href.includes("position"));
  }).length;
  const headings = body.querySelectorAll("h2, h3, h4");
  const multiTitle = headings.length >= 4 && Array.from(headings).filter((h) => (h.textContent || "").trim().length >= 5 && (h.textContent || "").trim().length < 100).length >= 3;
  return jobLikeCount >= 5 || multiTitle;
}

/** Content hint: page has single JD (Apply button + JD keywords). */
function hasJobDetailContent() {
  const body = document.body;
  if (!body) return false;
  const text = (body.innerText || body.textContent || "").toLowerCase();
  if (text.length < 400) return false;
  const jdKeywords = ["responsibilities", "requirements", "qualifications", "experience", "about the role", "what you will"];
  const jdScore = jdKeywords.filter((k) => text.includes(k)).length;
  const hasApply =
    /apply|submit application|apply now/i.test(text) ||
    !!body.querySelector('a[href*="apply"]') ||
    !!body.querySelector("[class*='apply']") ||
    Array.from(body.querySelectorAll("a, button")).some((el) => /^\s*apply\s*$/i.test((el.textContent || "").trim()));
  return jdScore >= 2 && hasApply;
}

/** True when page is a job LISTING (many jobs). No popup. Works across all career sites. */
function isJobListingPage(urlStr = window.location.href) {
  try {
    const path = new URL(urlStr || "").pathname.toLowerCase().replace(/\/+$/, "") || "/";
    const listingPaths = [
      "/jobs",
      "/careers",
      "/positions",
      "/opportunities",
      "/vacancies",
      "/openings",
      "/open-positions",
      "/current-openings",
      "/jobs/all",
      "/jobs/search",
      "/careers/all",
      "/careers/search",
      "/positions/all",
      "/opportunities/all",
      "/join",
      "/join-us",
      "/work-with-us",
    ];
    if (listingPaths.some((p) => path === p)) return true;
    if (/\/jobs\/?$|\/careers\/?$|\/positions\/?$/.test(path)) return true;
    if (path === "/" && /jobs\.|careers\.|greenhouse\.|lever\.|workday\.|ashbyhq\.|bamboohr\.|icims\.|smartrecruiters\./i.test(urlStr || "")) return true;
    if (hasListingPageContent() && !isJobDetailPage(urlStr)) return true;
    return false;
  } catch (_) {
    return false;
  }
}

/** True when page is a single JD. Popup allowed. Works across all career sites. */
function isJobDetailPage(urlStr = window.location.href) {
  const url = (urlStr || "").toLowerCase();
  try {
    const path = new URL(urlStr || "").pathname.toLowerCase();
    const search = new URL(urlStr || "").search.toLowerCase();

    if (path === "/jobs" || path === "/jobs/" || path === "/careers" || path === "/careers/") return false;

    const hasJdInPath = /\/(detail|job|position|opportunity|vacancy|posting|role|opening)\/?([^/]|$)/.test(path);
    const hasJdInQuery = /[?&](gh_jid|jid|job_id|jobid|position_id|opportunity_id|posting_id|req_id|reqid|id)=/.test(search);
    const hasNestedJobPath =
      /\/jobs\/[^/]+\/detail/.test(path) ||
      (/\/careers\/[^/]+/.test(path) && !/\/careers\/(all|search)\/?$/.test(path)) ||
      /\/job\/[^/]+|\/position\/[^/]+|\/opportunity\/[^/]+|\/posting\/[^/]+|\/role\/[^/]+|\/vacancy\/[^/]+/.test(path);
    const atsJdPattern = /(greenhouse|lever|workday|ashbyhq|bamboohr|icims|smartrecruiters|jobvite)[^/]*\/[^/]+\/[^/\s]+/.test(url);

    if (hasJdInPath || hasJdInQuery || hasNestedJobPath || atsJdPattern) return true;

    if (isCareerPage(urlStr) && hasJobDetailContent()) return true;
    return false;
  } catch (_) {
    return false;
  }
}

async function isJobPageViaLLM(url, title, snippet) {
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/job-page-detect`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ url: url || "", title: title || "", snippet: (snippet || "").slice(0, 800) }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.is_job_page === true;
  } catch (_) {
    return null;
  }
}

const KEYWORD_MATCH_ROOT_ID = "ja-keyword-match-root";

/** Get page HTML from all frames (main + iframes) - works for Greenhouse embeds, Lever, etc. */
async function getPageHtmlForKeywordsApi() {
  try {
    const res = await chrome.runtime.sendMessage({ type: "GET_ALL_FRAMES_HTML" });
    if (res?.ok && res.html) return res.html;
  } catch (_) {}
  try {
    const el = document.documentElement || document.body;
    if (!el) return null;
    const html = (el.outerHTML || el.innerHTML || "").slice(0, 1500000);
    return html && html.length > 100 ? html : null;
  } catch (_) {
    return null;
  }
}

/** Fetch job description via keywords/analyze (sends client-scraped page_html from all frames). */
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
  if (document.getElementById(KEYWORD_MATCH_ROOT_ID)) return;

  const url = window.location.href;
  const urlSuggestsJob = isCareerPage(url);
  if (!urlSuggestsJob) {
    const snippet = (document.body?.innerText || document.body?.textContent || "").replace(/\s+/g, " ").slice(0, 800);
    const llmSaysJob = await isJobPageViaLLM(url, document.title, snippet);
    if (llmSaysJob !== true) return;
  }

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
    if (!res.ok) return;

    const data = await res.json();
    const matched = data.matched_count || 0;
    const total = data.total_keywords || 0;
    if (total === 0) return;

    const percent = data.percent || 0;
    mountKeywordMatchWidgetWithData({ matched, total, percent });
  } catch (_) {}
}

function mountKeywordMatchWidgetWithData({ matched, total, percent }) {
  if (document.getElementById(KEYWORD_MATCH_ROOT_ID)) return;

  const root = document.createElement("div");
  root.id = KEYWORD_MATCH_ROOT_ID;
  root.innerHTML = `
    <style>
      #${KEYWORD_MATCH_ROOT_ID} {
        all: initial;
        position: fixed;
        right: 20px;
        top: 50%;
        transform: translateY(-50%);
        z-index: 2147483646;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 14px;
      }
      #${KEYWORD_MATCH_ROOT_ID} * { box-sizing: border-box; }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-card {
        width: 180px;
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        padding: 16px;
        text-align: center;
        margin: 0 auto;
        cursor: pointer;
        transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-card:hover {
        box-shadow: 0 8px 28px rgba(14,165,233,0.2);
        border-color: #0ea5e9;
        transform: translateY(-2px);
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-circle {
        width: 64px;
        height: 64px;
        margin: 0 auto 12px;
        border-radius: 50%;
        background: conic-gradient(#0ea5e9 ${percent * 3.6}deg, #e5e7eb ${percent * 3.6}deg);
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-circle-inner {
        width: 52px;
        height: 52px;
        border-radius: 50%;
        background: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 700;
        color: #0ea5e9;
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-title { font-size: 13px; font-weight: 600; color: #111; margin-bottom: 4px; }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-desc { font-size: 11px; color: #6b7280; }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-tag { display: inline-block; margin-top: 8px; font-size: 10px; color: #0ea5e9; font-weight: 600; text-decoration: underline; cursor: pointer; }
    </style>
    <div class="ja-kw-card">
      <div class="ja-kw-circle" id="ja-kw-circle"><div class="ja-kw-circle-inner" id="ja-kw-percent">${percent}%</div></div>
      <div class="ja-kw-title">Resume Match</div>
      <div class="ja-kw-desc" id="ja-kw-desc">${percent}% – ${matched} of ${total} keywords in your resume.</div>
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

async function getApiBase() {
  try {
    const data = await chrome.storage.local.get(["apiBase"]);
    return data.apiBase || "http://localhost:8000/api";
  } catch (_) {
    return "http://localhost:8000/api";
  }
}

async function openResumeGeneratorUrl() {
  const data = await chrome.storage.local.get(["loginPageUrl"]);
  const base = data.loginPageUrl ? new URL(data.loginPageUrl).origin : "http://localhost:5173";
  let url = `${base}/resume-generator`;
  try {
    const pageHtml = await getPageHtmlForKeywordsApi();
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    if (pageHtml && pageHtml.length > 100 && headers?.Authorization) {
      const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/tailor-context`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          page_html: pageHtml,
          url: window.location.href,
          job_title: document.querySelector("h1, [data-automation-id='jobTitle'], .job-title, [class*='job-title']")?.textContent?.trim?.()?.slice(0, 100) || "",
        }),
      });
      if (res.ok) url = `${base}/resume-generator?tailor=1`;
    }
  } catch (err) {
    logWarn("Tailor context save failed", { error: String(err) });
  }
  chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url });
}

/** Build auth refresh URL - handles apiBase with or without /api suffix. */
function getRefreshUrl(apiBase) {
  const base = String(apiBase || "").replace(/\/+$/, "");
  if (base.endsWith("/api")) return `${base}/auth/refresh`;
  return `${base}${base ? "/" : ""}api/auth/refresh`;
}

/** Mutex: only one refresh in flight; others wait and reuse the result. */
let _refreshInFlight = null;

/** Refresh token via API (only on 401). Returns new token or null. Tries multiple URL patterns (404 can mean wrong path/port). */
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
      const apiBase = data.apiBase || "http://localhost:8000/api";
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
              await chrome.storage.local.set({ accessToken: newToken });
              try {
                await chrome.runtime.sendMessage({ type: "SYNC_TOKEN_TO_HIREMATE_TAB", token: newToken });
              } catch (_) {}
              if (LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o)) {
                try {
                  localStorage.setItem("token", newToken);
                  localStorage.setItem("access_token", newToken);
                } catch (_) {}
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

/** Get auth headers. Sync token from open HireMate tab only. Refresh happens only on 401 (in fetchWithAuthRetry). */
async function getAuthHeaders() {
  try {
    const syncRes = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
    if (syncRes?.ok && syncRes?.token) {
      await chrome.storage.local.set({ accessToken: syncRes.token });
    }
  } catch (_) {}
  const data = await chrome.storage.local.get(["accessToken"]);
  const token = data.accessToken || null;
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

/** Fetch interceptor: on 401 → refresh token, persist to chrome.storage + HireMate localStorage, retry once with new token. */
async function fetchWithAuthRetry(url, options = {}) {
  let res = await fetch(url, options);
  if (res.status === 401) {
    logInfo("401 received, attempting token refresh", { url });
    let newToken = null;
    newToken = await refreshTokenViaApi();
    if (!newToken) {
      try {
        const syncRes = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
        if (syncRes?.ok && syncRes?.token) {
          newToken = syncRes.token;
          await chrome.storage.local.set({ accessToken: newToken });
        }
      } catch (_) {}
    }
    if (newToken) {
      const base = toPlainHeaders(options.headers);
      const retryOptions = { ...options, headers: { ...base, Authorization: `Bearer ${newToken}` } };
      res = await fetch(url, retryOptions);
      if (res.status === 401) {
        logWarn("Retry still returned 401 after refresh");
      }
    }
  }
  return res;
}

function makeCopyable(el, text) {
  if (!el || !text) return;
  el.classList.add("ja-copyable");
  el.addEventListener("click", () => {
    navigator.clipboard.writeText(text).catch(() => {});
  });
}

async function loadProfileIntoPanel(root) {
  const nameEl = root?.querySelector("#ja-profile-name");
  const contactEl = root?.querySelector("#ja-profile-contact");
  const educationEl = root?.querySelector("#ja-profile-education");
  const experienceEl = root?.querySelector("#ja-profile-experience");
  const uploadsEl = root?.querySelector("#ja-profile-uploads");
  const linksEl = root?.querySelector("#ja-profile-links");
  const skillsEl = root?.querySelector("#ja-profile-skills");
  const languagesEl = root?.querySelector("#ja-profile-languages");
  const avatarEl = root?.querySelector("#ja-profile-avatar");
  const titleEl = root?.querySelector("#ja-profile-title");

  const setHtml = (el, html) => {
    if (el) el.innerHTML = html || "—";
  };
  const setText = (el, text) => {
    if (el) el.textContent = text || "—";
  };

  try {
    const ctx = await getAutofillContextFromApi();
    const flat = ctx.profile || {};
    const detail = ctx.profileDetail;

    const fullName = [flat.firstName, flat.lastName].filter(Boolean).join(" ") || flat.name || "—";
    setText(nameEl, fullName);
    setText(titleEl, flat.title || flat.professionalHeadline || "");
    // Avatar initials
    try {
      if (avatarEl) {
        const initials = (fullName || "")
          .split(" ")
          .filter(Boolean)
          .slice(0, 2)
          .map((s) => s[0]?.toUpperCase() || "")
          .join("");
        avatarEl.textContent = initials || (flat.name || flat.firstName || "—").charAt(0).toUpperCase();
      }
    } catch (_) {}

    const location = [flat.city, flat.country].filter(Boolean).join(", ") || "—";
    const contactHtml = `
      <div class="ja-profile-line ja-copyable" data-copy="${escapeHtml(location === "—" ? "" : location)}">${escapeHtml(location)}</div>
      <div class="ja-profile-line ja-copyable" data-copy="${escapeHtml(flat.email || "")}">${escapeHtml(flat.email || "—")}</div>
      <div class="ja-profile-line ja-copyable" data-copy="${escapeHtml(flat.phone || "")}">${escapeHtml(flat.phone || "—")}</div>
    `;
    setHtml(contactEl, contactHtml);
    contactEl?.querySelectorAll(".ja-copyable").forEach((node) => {
      makeCopyable(node, node.dataset.copy ?? node.innerText.trim());
    });

    const educations = detail?.educations ?? flat.educations ?? [];
    if (educations.length) {
      const eduHtml = educations
        .map(
          (e) => `
        <div class="ja-edu-item ja-copyable" data-copy="${escapeHtml(
          `${e.institution || ""}\n${e.degree || ""} ${e.fieldOfStudy || ""}\n${e.startYear || ""} - ${e.endYear || ""}`
        )}">
          <div class="ja-edu-institution">${escapeHtml(e.institution || "—")}</div>
          <div class="ja-edu-degree">${escapeHtml(e.degree || "")}${e.fieldOfStudy ? " · " + escapeHtml(e.fieldOfStudy) : ""}</div>
          <div class="ja-edu-meta">${escapeHtml(e.startYear || "")} — ${escapeHtml(e.endYear || "")}</div>
        </div>
      `
        )
        .join("");
      setHtml(educationEl, eduHtml);
      educationEl?.querySelectorAll(".ja-edu-item").forEach((node) => {
        makeCopyable(node, node.dataset.copy || node.innerText);
      });
    } else {
      setText(educationEl, flat.education || "—");
    }

    const experiences = detail?.experiences ?? flat.experiences ?? [];
    if (experiences.length) {
      const expHtml = experiences
        .map(
          (e) => {
            const metaParts = [e.companyName, e.location, `${e.startDate || ""} — ${e.endDate || ""}`].filter(Boolean);
            const bullets = (e.description || "")
              .split(/\n|•/)
              .map((s) => s.trim())
              .filter(Boolean)
              .map((b) => `<li>${escapeHtml(b)}</li>`)
              .join("");
            const copyText = `${e.jobTitle || ""} at ${e.companyName || ""}\n${e.startDate || ""} — ${e.endDate || ""}\n${e.description || ""}`;
            return `
          <div class="ja-exp-item ja-copyable" data-copy="${escapeHtml(copyText)}">
            <div class="ja-exp-role">${escapeHtml(e.jobTitle || "—")}</div>
            <div class="ja-exp-company">${e.companyName ? escapeHtml(e.companyName) : ""}</div>
            <div class="ja-exp-meta">${escapeHtml(metaParts.join(" · "))}</div>
            ${bullets ? `<ul class="ja-exp-bullets">${bullets}</ul>` : ""}
          </div>
        `;
          }
        )
        .join("");
      setHtml(experienceEl, expHtml);
      experienceEl?.querySelectorAll(".ja-exp-item").forEach((node) => {
        makeCopyable(node, node.dataset.copy || node.innerText);
      });
    } else {
      setText(experienceEl, (flat.experience || flat.professionalSummary || "—").slice(0, 800) + (flat.experience && flat.experience.length > 800 ? "…" : ""));
    }

    const resumeName = ctx.resumeName || ctx.resumeFileName || (ctx.resumeUrl || "").split("/").pop() || "Resume";
    const resumeDate = detail?.resumeLastUpdated ? new Date(detail.resumeLastUpdated).toLocaleString() : "";
    const hasResume = !!(ctx.resumeUrl || ctx.resumeFileName);
    const uploadsHtml = hasResume
      ? `
      <div class="ja-upload-row">
        <div>
          <span class="ja-upload-label">Resume</span>
          ${resumeDate ? `<div class="ja-upload-meta">Uploaded: ${escapeHtml(resumeDate)}</div>` : ""}
        </div>
        <button type="button" class="ja-upload-preview" data-has-resume="true">Preview</button>
      </div>
    `
      : "No uploads";
    setHtml(uploadsEl, uploadsHtml);
    if (hasResume) {
      uploadsEl?.querySelector(".ja-upload-preview")?.addEventListener("click", async (ev) => {
        ev.preventDefault();
        try {
          const apiBase = await getApiBase();
          const headers = await getAuthHeaders();
          const path = ctx.resumeFileName
            ? `/chrome-extension/autofill/resume/${(ctx.resumeFileName || "").split("/").pop()}`
            : "/chrome-extension/autofill/resume";
          const res = await fetchWithAuthRetry(`${apiBase}${path}`, { headers });
          if (res.ok) {
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            window.open(url, "_blank");
          }
        } catch (_) {}
      });
    }

    const links = [];
    if (flat.linkedin || detail?.links?.linkedInUrl) links.push({ label: "LinkedIn", url: flat.linkedin || detail?.links?.linkedInUrl });
    if (flat.github || detail?.links?.githubUrl) links.push({ label: "Github", url: flat.github || detail?.links?.githubUrl });
    if (detail?.links?.portfolioUrl) links.push({ label: "Portfolio", url: detail.links.portfolioUrl });
    (detail?.links?.otherLinks || []).forEach((o) => {
      if (o?.url) links.push({ label: o.label || "Link", url: o.url });
    });
    if (links.length) {
      setHtml(
        linksEl,
        links.map((l) => `<div class="ja-link-row"><span class="ja-link-label">${escapeHtml(l.label)}</span><span class="ja-link-url ja-copyable" data-copy="${escapeHtml(l.url)}">${escapeHtml(l.url)}</span></div>`).join("")
      );
      linksEl?.querySelectorAll(".ja-link-url").forEach((node) => makeCopyable(node, node.dataset.copy));
    } else {
      setText(linksEl, "—");
    }

    const skills = [];
    (detail?.techSkills || []).forEach((s) => skills.push(s.name));
    (detail?.softSkills || []).forEach((s) => skills.push(s.name));
    if (skills.length === 0 && Array.isArray(flat.skills_list) && flat.skills_list.length) {
      skills.push(...flat.skills_list);
    } else if (skills.length === 0 && flat.skills) {
      skills.push(...String(flat.skills).split(",").map((s) => s.trim()).filter(Boolean));
    }
    if (skills.length) {
      const chips = skills.map((s) => `<span class="ja-skill-chip ja-copyable" data-copy="${escapeHtml(s)}">${escapeHtml(s)}</span>`).join("");
      setHtml(skillsEl, `<div class="ja-skill-list">${chips}</div>`);
      skillsEl?.querySelectorAll(".ja-skill-chip").forEach((node) => makeCopyable(node, node.dataset.copy));
    } else {
      setText(skillsEl, "—");
    }

    const langs = detail?.willingToWorkIn || [];
    setHtml(languagesEl, langs.length ? `<div class="ja-skill-list">${langs.map((l) => `<span class="ja-skill-chip">${escapeHtml(l)}</span>`).join("")}</div>` : (flat.country ? escapeHtml(flat.country) : "—"));
  } catch (_) {
    setText(nameEl, "Sign in to load profile");
    setHtml(contactEl, "<div class=\"ja-profile-line\">—</div>");
    setText(educationEl, "—");
    setText(experienceEl, "—");
    setText(uploadsEl, "—");
    setText(linksEl, "—");
    setText(skillsEl, "—");
    setText(languagesEl, "—");
  }
}

function extractCompanyAndPosition() {
  const title = document.title || "";
  const url = window.location.href || "";
  let company = "";
  let position = "";
  let location = "";

  // 1. Extract company from URL (Greenhouse, Lever, Workday, etc.)
  try {
    const u = new URL(url);
    const path = (u.pathname || "").replace(/^\/+|\/+$/g, "");
    const segments = path.split("/").filter(Boolean);
    if (u.hostname.includes("greenhouse.io") && segments.length >= 1) {
      company = segments[0];
    } else if (u.hostname.includes("lever.co") && segments.length >= 1) {
      company = segments[0];
    } else if (u.hostname.includes("jobs.workday.com") && segments.length >= 2) {
      company = segments[0];
    } else if (u.hostname.includes("ashbyhq.com") && segments.length >= 1) {
      company = segments[0];
    } else if (u.hostname.includes("bamboohr.com") && segments.length >= 1) {
      company = segments[0];
    }
    if (company) {
      company = company.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    }
  } catch (_) {}

  // 2. Try JSON-LD JobPosting on page
  if (!company || !position) {
    document.querySelectorAll('script[type="application/ld+json"]').forEach((script) => {
      try {
        const data = JSON.parse(script.textContent || "{}");
        const item = Array.isArray(data) ? data.find((i) => i["@type"] === "JobPosting") : data["@type"] === "JobPosting" ? data : null;
        if (item) {
          if (!company && item.hiringOrganization?.name) company = item.hiringOrganization.name;
          if (!position && item.title) position = item.title;
          if (!location && item.jobLocation) {
            const loc = item.jobLocation;
            location = typeof loc === "string" ? loc : loc.address?.addressLocality && loc.address?.addressCountry
              ? `${loc.address.addressLocality}, ${loc.address.addressCountry}`
              : loc.name || "";
          }
        }
      } catch (_) {}
    });
  }

  // 3. og:title — "Job Title | Company" or "Tagline | Company" (job titles usually 2+ words)
  const ogTitle = document.querySelector('meta[property="og:title"]')?.content;
  const isTagline = (t) => !t || /^(best|payment|gateway|online|financial|leading|top|number one)/i.test(t) || t.length > 55;
  const looksLikeJobTitle = (t) => t && t.length >= 5 && t.length < 80 && !isTagline(t) && t.split(/\s+/).length >= 2;
  if (ogTitle) {
    const parts = ogTitle.split(/[|\-–—]/).map((p) => p.trim()).filter(Boolean);
    if (parts.length >= 2) {
      const a = parts[0], b = parts[1];
      if (!company) company = (b.length <= 30 && b.split(/\s+/).length <= 3) ? b : (a.length <= 30 ? a : "");
      if (!position && looksLikeJobTitle(a)) position = a;
      else if (!position && looksLikeJobTitle(b)) position = b;
    } else if (!position && looksLikeJobTitle(ogTitle.trim())) {
      position = ogTitle.trim();
    }
  }

  // 4. Page content: h1 first (most reliable on job detail pages)
  const h1 = document.querySelector("h1");
  if (!position && h1) position = getText(h1);

  // 5. "Back to jobs JOB_TITLE Location Apply" pattern (Greenhouse / common ATS)
  const bodyText = document.body?.innerText?.slice(0, 1500) || "";
  if (!position && /Back to jobs\s+(.+?)\s+(?:Apply|Remote|Hybrid|Malaysia|India|Singapore|Bangalore|Kuala Lumpur)/i.test(bodyText)) {
    const m = bodyText.match(/Back to jobs\s+(.+?)\s+(?:Apply|Remote|Hybrid|Malaysia|India|Singapore|Bangalore|Kuala Lumpur|,\s*[A-Za-z]+)/i);
    if (m) {
      const candidate = m[1].trim();
      if (candidate.length >= 5 && candidate.length < 80 && !/^(payment|best|gateway|online|financial|leading|india)/i.test(candidate)) {
        position = candidate;
      }
    }
  }
  if (!position && /Back to jobs\s+(.+?)\s+Apply/i.test(bodyText)) {
    const m = bodyText.match(/Back to jobs\s+(.+?)\s+Apply/i);
    if (m && !position) {
      const candidate = m[1].trim();
      if (candidate.length >= 5 && candidate.length < 80) position = candidate;
    }
  }

  if (!company || !location) {
    if (!company && /About\s+([A-Za-z0-9&\s]+):/i.test(bodyText)) {
      const m = bodyText.match(/About\s+([A-Za-z0-9&\s]+):/i);
      if (m) company = m[1].trim();
    }
    if (!location && /([A-Za-z\s]+,\s*[A-Za-z\s]+)\s*(?:Apply|Remote|Hybrid)/i.test(bodyText)) {
      const m = bodyText.match(/([A-Za-z\s]+,\s*[A-Za-z\s]+)\s*(?:Apply|Remote|Hybrid)/i);
      if (m) location = m[1].trim();
    }
    if (!location && /([A-Za-z\s]+,\s+[A-Za-z]{2,})\s*$/.test(bodyText.slice(0, 800))) {
      const m = bodyText.slice(0, 800).match(/([A-Za-z][A-Za-z\s]+,\s*[A-Za-z]{2,})/);
      if (m && m[1].length < 50) location = m[1].trim();
    }
  }

  if (!position && ogTitle) {
    const parts = ogTitle.split(/[|\-–—]/).map((p) => p.trim()).filter(Boolean);
    for (const p of parts) {
      if (p.length >= 5 && p.length < 80 && !/^(payment|best|gateway|online|financial|leading|india|razorpay)/i.test(p)) {
        position = p;
        break;
      }
    }
  }
  if (!position && title) {
    const t = title.trim();
    if (t.length >= 5 && t.length < 80 && !/^(payment|best|gateway|online|financial)/i.test(t)) position = t;
  }
  return { company: company || "", position: position || "", location: location || "" };
}

async function prefillJobForm(root) {
  const { company, position, location } = extractCompanyAndPosition();
  const urlInput = root?.querySelector("#ja-job-url");
  const descInput = root?.querySelector("#ja-job-description");
  const companyInput = root?.querySelector("#ja-job-company");
  const positionInput = root?.querySelector("#ja-job-position");
  const locationInput = root?.querySelector("#ja-job-location");
  if (urlInput) urlInput.value = window.location.href || "";
  if (companyInput) companyInput.value = company || "";
  if (positionInput) positionInput.value = position || "";
  if (locationInput) locationInput.value = location || "";

  if (descInput) {
    descInput.placeholder = "Scraping job description...";
    descInput.value = "";
    const jobDesc = await fetchJobDescriptionFromKeywordsApi(window.location.href);
    descInput.value = jobDesc || "";
    descInput.placeholder = "Auto-detected description available.";
  }
}

async function saveJobFromForm(root) {
  const btn = root?.querySelector("#ja-job-save");
  const origText = btn?.textContent || "Save Job";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Saving...";
  }
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const payload = {
      company: root.querySelector("#ja-job-company")?.value || "",
      position_title: root.querySelector("#ja-job-position")?.value || "",
      location: root.querySelector("#ja-job-location")?.value || "",
      min_salary: root.querySelector("#ja-job-min-salary")?.value || null,
      max_salary: root.querySelector("#ja-job-max-salary")?.value || null,
      currency: root.querySelector("#ja-job-currency")?.value || "USD",
      period: root.querySelector("#ja-job-period")?.value || "Yearly",
      job_type: root.querySelector("#ja-job-type")?.value || "Full-Time",
      job_description: root.querySelector("#ja-job-description")?.value || null,
      notes: root.querySelector("#ja-job-notes")?.value || null,
      application_status: root.querySelector("#ja-job-status")?.value || "I have not yet applied",
      job_posting_url: root.querySelector("#ja-job-url")?.value || null,
    };
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const view = root.querySelector("#ja-keywords-view");
      const formPanel = root.querySelector("#ja-job-form-panel");
      if (view && formPanel) {
        formPanel.style.display = "none";
        view.style.display = "block";
      }
    }
  } catch (err) {
    logWarn("Save job failed", { error: String(err) });
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origText;
    }
  }
}

async function fetchResumesFromApi() {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const res = await fetchWithAuthRetry(`${apiBase}/resume`, { headers });
  if (!res.ok) return [];
  return res.json();
}

async function loadKeywordsIntoPanel(root) {
  const container = root?.querySelector("#ja-keyword-analysis");
  const card = root?.querySelector("#ja-keyword-card");
  const selectEl = root?.querySelector("#ja-resume-select");
  if (!container) return;

  container.innerHTML = "<p class=\"ja-score-text\">Loading profile...</p>";
  if (card) card.classList.add("ja-loading");

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
        if (r.is_default) {
          opt.textContent += " (default)";
          defaultId = r.id;
        }
        selectEl.appendChild(opt);
      });
      if (prevSelection && validIds.has(prevSelection)) {
        selectEl.value = String(prevSelection);
      } else if (defaultId !== null) {
        selectEl.value = String(defaultId);
      } else if (resumes.length) {
        selectEl.value = String(resumes[0].id);
      }
    }

    const selectedId = selectEl?.value ? parseInt(selectEl.value, 10) : null;
    const resumeId = selectedId && selectedId > 0 ? selectedId : null;

    container.innerHTML = "<p class=\"ja-score-text\">Analyzing keywords...</p>";
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
      } catch (_) {}
      container.innerHTML = `<p class="ja-score-text">${escapeHtml(String(errMsg))}</p>`;
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
    const statusLabel = total === 0 ? "No skills found" : percent >= 70 ? "Great match" : "Needs Work";
    const apiMessage = data.message || "";
    const renderItem = (item) =>
      `<div class="ja-kw-item"><span class="ja-kw-check ${item.matched ? "ja-matched" : "ja-unmatched"}">✓</span><span class="${item.matched ? "ja-kw-matched" : "ja-kw-unmatched"}">${escapeHtml(item.keyword)}</span></div>`;
    const highHtml = high.map(renderItem).join("");
    const lowHtml = low.map(renderItem).join("");
    container.innerHTML = `
      <h4>Keyword Match – ${statusLabel}</h4>
      ${total === 0 ? `<p class="ja-score-text">${escapeHtml(apiMessage || "No technical skills found in the job description. Scroll down for the full requirements section.")}</p>` : `<p class="ja-score-text"><strong>${percent}%</strong> match – Your resume has <strong>${matched} of ${total}</strong> keywords from the job description.</p>`}
      ${total > 0 ? `<p style="font-size:11px;background:#fef9c3;padding:6px 8px;border-radius:6px;margin:0 0 12px 0;">Try to get your score above <strong>70%</strong> to increase your chances!</p>` : ""}
      ${high.length ? `<div class="ja-kw-priority-section">
        <div class="ja-kw-priority-header">
          <span class="ja-kw-priority-title">High Priority Keywords</span>
          <span class="ja-kw-priority-count">${highMatched}/${high.length}</span>
        </div>
        <div class="ja-kw-grid">${highHtml}</div>
      </div>` : ""}
      ${low.length ? `<div class="ja-kw-priority-section">
        <div class="ja-kw-priority-header">
          <span class="ja-kw-priority-title">Low Priority Keywords</span>
          <span class="ja-kw-priority-count">${lowMatched}/${low.length}</span>
        </div>
        <div class="ja-kw-grid">${lowHtml}</div>
      </div>` : ""}
    `;
  } catch (err) {
    logWarn("Keyword analysis failed", { error: String(err) });
    container.innerHTML = "<p class=\"ja-score-text\">Unable to analyze. Please try again.</p>";
  } finally {
    if (card) card.classList.remove("ja-loading");
  }
}

async function getAutofillContextFromApi() {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/autofill/data`, { headers });
  if (!res.ok) {
    throw new Error(`Profile load failed (${res.status})`);
  }
  const json = await res.json();
  return {
    profile: json.profile || {},
    profileDetail: json.profile_detail || null,
    customAnswers: json.custom_answers || {},
    resumeText: json.resume_text || "",
    resumeName: json.resume_name || null,
    resumeFileName: json.resume_file_name || null,
    resumeUrl: json.resume_url || null,
  };
}

/** Fetch resume from API (backend proxies S3/local file). Always use API to avoid CORS when fetching from S3. */
async function fetchResumeFromContext(context) {
  const resumeUrl = context?.resumeUrl || context?.resume_url;
  const resumeFileName = context?.resumeFileName || context?.resume_file_name;
  if (!resumeUrl && !resumeFileName) return null;

  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const path = resumeFileName
      ? `/chrome-extension/autofill/resume/${(resumeFileName || "").split("/").pop()}`
      : "/chrome-extension/autofill/resume";
    const fetchUrl = `${apiBase}${path}`;
    const resumeRes = await fetchWithAuthRetry(fetchUrl, { headers });
    if (!resumeRes.ok) return null;

    const resumeBuffer = await resumeRes.arrayBuffer();
    const fileName = (resumeFileName || resumeUrl || "").split("/").pop()?.split("?")[0] || "resume.pdf";
    const buffer = Array.from(new Uint8Array(resumeBuffer));

    await chrome.runtime.sendMessage({
      type: "SAVE_RESUME",
      payload: { buffer, name: fileName },
    });
    logInfo("Resume fetched and saved from context", { fileName, bytes: buffer.length });
    return { buffer, name: fileName };
  } catch (e) {
    logWarn("Failed to fetch resume from context", e);
    return null;
  }
}

async function getStaticResume() {
  return null;
}

async function trackCareerPageView() {
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    if (!headers?.Authorization) return;
    const key = `ja_page_viewed_${window.location.href}`;
    if (sessionStorage.getItem(key)) return;
    const { company } = extractCompanyAndPosition();
    await fetchWithAuthRetry(`${apiBase}/chrome-extension/career-page/view`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        page_url: window.location.href || "",
        company_name: company || null,
        job_url: window.location.href || null,
        job_title: null,
      }),
    });
    sessionStorage.setItem(key, "1");
  } catch (e) {
    logWarn("Failed to track career page view", { error: String(e) });
  }
}

async function trackAutofillUsed() {
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const { company, position } = extractCompanyAndPosition();
    await fetchWithAuthRetry(`${apiBase}/chrome-extension/autofill/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        page_url: window.location.href || "",
        company_name: company || null,
        job_url: window.location.href || null,
        job_title: position || null,
      }),
    });
  } catch (e) {
    logWarn("Failed to track autofill", { error: String(e) });
  }
}

async function fetchMappingsFromApi(fields, context) {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const mapRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/form-fields/map`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({
      fields: fields.map((field) => ({ ...field, id: null })),
      profile: context.profile,
      custom_answers: context.customAnswers,
      resume_text: context.resumeText,
    }),
  });
  if (!mapRes.ok) {
    throw new Error(`AI mapping failed (${mapRes.status})`);
  }
  const mapData = await mapRes.json();
  return mapData.mappings || {};
}

async function updateWidgetAuthUI(root) {
  let data = await chrome.storage.local.get(["accessToken", "loginPageUrl"]);
  let hasToken = !!data.accessToken;

  let isHireMateOrigin = LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o);
  if (!isHireMateOrigin && data.loginPageUrl) {
    try {
      isHireMateOrigin = new URL(data.loginPageUrl).origin === window.location.origin;
    } catch {}
  }

  // 1) If no token in chrome.storage, try localStorage (when on HireMate frontend - same origin)
  if (!hasToken && isHireMateOrigin) {
    try {
      const localToken = localStorage.getItem("token") || localStorage.getItem("access_token");
      if (localToken) {
        hasToken = true;
        await chrome.storage.local.set({ accessToken: localToken });
        logInfo("Token synced from localStorage to extension storage");
      }
    } catch (e) {}
  }

  // 2) If still no token, try fetching from any open HireMate tab (works when on job sites)
  if (!hasToken) {
    try {
      const res = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
      if (res?.ok && res?.token) hasToken = true;
    } catch (e) {}
  }

  const loginUrl = data.loginPageUrl || DEFAULT_LOGIN_PAGE_URL;

  const signinCta = root?.querySelector("#ja-signin-cta");
  const autofillAuth = root?.querySelector("#ja-autofill-authenticated");
  if (signinCta) signinCta.style.display = hasToken ? "none" : "block";
  if (autofillAuth) autofillAuth.style.display = hasToken ? "block" : "none";

  const signinCtaKeywords = root?.querySelector("#ja-signin-cta-keywords");
  const keywordsAuth = root?.querySelector("#ja-keywords-authenticated");
  if (signinCtaKeywords) signinCtaKeywords.style.display = hasToken ? "none" : "block";
  if (keywordsAuth) keywordsAuth.style.display = hasToken ? "block" : "none";

  const signinCtaProfile = root?.querySelector("#ja-signin-cta-profile");
  const profileAuth = root?.querySelector("#ja-profile-authenticated");
  if (signinCtaProfile) signinCtaProfile.style.display = hasToken ? "none" : "block";
  if (profileAuth) profileAuth.style.display = hasToken ? "block" : "none";

  const signinBtns = root?.querySelectorAll(".ja-signin-to-autofill");
  signinBtns?.forEach((btn) => {
    btn.onclick = (e) => {
      e.preventDefault();
      chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url: loginUrl });
    };
  });
}

function mountInPageUI() {
  if (window.self !== window.top) return;
  const existing = document.getElementById(INPAGE_ROOT_ID);
  if (existing) {
    existing.classList.remove("collapsed");
    updateWidgetAuthUI(existing);
    if (isCareerPage()) trackCareerPageView();
    return;
  }
  
  const root = document.createElement("div");
  root.id = INPAGE_ROOT_ID;
  root.innerHTML = `
    <style>
      #${INPAGE_ROOT_ID} {
        all: initial;
        position: fixed;
        right: 20px;
        top: 80px;
        width: 380px;
        max-height: 560px;
        z-index: 2147483647;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: #1a1a1a;
        box-sizing: border-box;
      }
      #${INPAGE_ROOT_ID} * { box-sizing: border-box; }
      #${INPAGE_ROOT_ID} .ja-card {
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.12);
        overflow-y: scroll;
        display: flex;
        flex-direction: column;
        max-height: 520px;
      }
      #${INPAGE_ROOT_ID} .ja-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 14px;
        background: #fff;
        border-bottom: 1px solid #e5e7eb;
        cursor: move;
        user-select: none;
      }
      #${INPAGE_ROOT_ID} .ja-logo-wrap {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-logo-icon {
        height: 28px;
        object-fit: contain;
        flex-shrink: 0;
      }
        #${INPAGE_ROOT_ID} .ja-upload-box-up{
        margin-top:-7px;


        }
      #${INPAGE_ROOT_ID} .ja-title {
        font-size: 16px;
        font-weight: 700;
        color: #111;
        margin: 0;
      }
      #${INPAGE_ROOT_ID} .ja-head-actions {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-head-btn {
        background: none;
        border: none;
        color: #6b7280;
        font-size: 12px;
        padding: 4px 8px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-head-btn:hover { color: #111; }
      #${INPAGE_ROOT_ID} .ja-close {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        padding: 0;
        justify-content: center;
        font-size: 18px;
      }
      #${INPAGE_ROOT_ID} .ja-tabs {
        display: flex;
        padding: 0 10px 0 14px;
        gap: 4px;
        border-bottom: 1px solid #e5e7eb;
        background: #fafafa;
      }
      #${INPAGE_ROOT_ID} .ja-tab {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 10px 12px;
        font-size: 13px;
        font-weight: 500;
        color: #6b7280;
        background: none;
        border: none;
        border-bottom: 2px solid transparent;
        margin-bottom: -1px;
        cursor: pointer;
      }
      #${INPAGE_ROOT_ID} .ja-tab:hover { color: #374151; }
      #${INPAGE_ROOT_ID} .ja-tab.active {
        color: #0ea5e9;
        background: rgba(14, 165, 233, 0.08);
        border-bottom-color: #0ea5e9;
      }
      #${INPAGE_ROOT_ID} .ja-tab svg { width: 16px; height: 16px; flex-shrink: 0; }
      #${INPAGE_ROOT_ID} .ja-body {
        padding: 14px 16px;
        overflow-y: scroll;
        overflow-x: hidden;
        flex: 1;
        min-height: 0;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
        scrollbar-color: #cbd5e1 #f1f5f9;
      }
      #${INPAGE_ROOT_ID} .ja-body::-webkit-scrollbar { width: 6px; }
      #${INPAGE_ROOT_ID} .ja-body::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 3px; }
      #${INPAGE_ROOT_ID} .ja-body::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
      #${INPAGE_ROOT_ID} .ja-body::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
      #${INPAGE_ROOT_ID} .ja-panel { display: none; }
      #${INPAGE_ROOT_ID} .ja-panel.active { display: block; }
      #${INPAGE_ROOT_ID} .ja-autofill-box {
        background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 50%, #3b82f6 100%);
        border-radius: 10px;
        padding: 14px 16px;
        color: #fff;
        margin-bottom: 12px;
      }
      #${INPAGE_ROOT_ID} .ja-autofill-box h3 {
        margin: 0 0 6px 0;
        font-size: 14px;
        font-weight: 600;
        color: #fff;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-autofill-box p {
        margin: 0 0 12px 0;
        font-size: 13px;
        opacity: 0.95;
      }
      #${INPAGE_ROOT_ID} .ja-status-area { display: flex; flex-direction: column; align-items: center; margin-bottom: 12px; }
      #${INPAGE_ROOT_ID} .ja-status-loader {
        width: 36px; height: 36px; border: 3px solid rgba(255,255,255,0.3);
        border-top-color: #fff; border-radius: 50%; animation: ja-spin 0.8s linear infinite;
        margin-bottom: 8px; display: none;
      }
      #${INPAGE_ROOT_ID} .ja-status-area.loading .ja-status-loader { display: block; }
      @keyframes ja-spin { to { transform: rotate(360deg); } }
      #${INPAGE_ROOT_ID} .ja-autofill-box .ja-status { color: rgba(255,255,255,0.95); margin-bottom: 8px; min-height: 18px; font-size: 13px; text-align: center; font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-autofill-box .ja-status ul { margin: 0; padding-left: 18px; text-align: left; }
      #${INPAGE_ROOT_ID} .ja-autofill-box .ja-status li { margin: 4px 0; }
      #${INPAGE_ROOT_ID} .ja-autofill-box .ja-status .ja-note { color: #fef08a; font-weight: 500; }
      #${INPAGE_ROOT_ID} .ja-autofill-box .ja-status.loading { color: #fef08a; }
      #${INPAGE_ROOT_ID} .ja-autofill-box .ja-status.success { color: #86efac; font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-autofill-box .ja-status.error { color: #fca5a5; font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-failed-field-link { background: none; border: none; padding: 0; margin: 2px 0; color: #fef08a; cursor: pointer; font-size: inherit; font-weight: 500; text-align: left; text-decoration: underline; }
      #${INPAGE_ROOT_ID} .ja-failed-field-link:hover { color: #fff; }
      #${INPAGE_ROOT_ID} .ja-failed-fields-list { margin: 4px 0 0 12px; padding-left: 0; list-style: none; }
      #${INPAGE_ROOT_ID} .ja-fields-need-attention { display: block; margin-bottom: 4px; }
      #${INPAGE_ROOT_ID} .ja-progress {
        width: 100%;
        height: 4px;
        background: rgba(255,255,255,0.3);
        border-radius: 2px;
        margin-bottom: 10px;
        overflow: cover;
      }
      #${INPAGE_ROOT_ID} .ja-progress-bar {
        height: 100%;
        width: 0%;
        background: #fff;
        transition: width 0.3s ease;
      }
      #${INPAGE_ROOT_ID} .ja-action {
        width: 100%;
        padding: 10px 16px;
        background: #fff;
        color: #1d4ed8;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-action-row { display: flex; gap: 8px; }
      #${INPAGE_ROOT_ID} .ja-action { flex: 1; }
      #${INPAGE_ROOT_ID} .ja-action:hover { background: #f0fdfa; }
      #${INPAGE_ROOT_ID} .ja-action:disabled { opacity: 0.6; cursor: not-allowed; }
      #${INPAGE_ROOT_ID} .ja-fill-controls { display: none; gap: 8px; align-items: center; margin-top: 8px; }
      #${INPAGE_ROOT_ID} .ja-fill-controls.visible { display: flex; }
      #${INPAGE_ROOT_ID} .ja-fill-controls .ja-fill-label { font-size: 12px; color: rgba(255,255,255,0.9); font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-stop { padding: 8px 14px; background: #dc2626; color: #fff; border: none; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-stop:hover { background: #b91c1c; }
      #${INPAGE_ROOT_ID} .ja-skip-next { padding: 8px 14px; background: rgba(255,255,255,0.2); color: #fff; border: 1px solid rgba(255,255,255,0.4); border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-skip-next:hover { background: rgba(255,255,255,0.3); }
      #${INPAGE_ROOT_ID} .ja-continue-fill { width: 100%; padding: 10px 16px; background: #16a34a; color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 8px; }
      #${INPAGE_ROOT_ID} .ja-continue-fill:hover { background: #15803d; }
      #${INPAGE_ROOT_ID} .ja-auto-advance { display: flex; align-items: center; gap: 8px; margin-top: 10px; font-size: 12px; color: rgba(255,255,255,0.9); cursor: pointer; }
      #${INPAGE_ROOT_ID} .ja-auto-advance input { cursor: pointer; }
      #${INPAGE_ROOT_ID} .ja-footer-links {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-footer-link {
        background: none;
        border: none;
        color: #0284c7;
        font-size: 13px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 0;
      }
      #${INPAGE_ROOT_ID} .ja-footer-link:hover { text-decoration: underline; }
      #${INPAGE_ROOT_ID} .ja-accordions {
        margin-bottom: 12px;
        margin-top: 12px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        overflow: hidden;
        background: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-item {
        border-bottom: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-item:last-child { border-bottom: none; }
      #${INPAGE_ROOT_ID} .ja-accordion-header {
        width: 100%;
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 14px;
        background: none;
        border: none;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        color: #374151;
        text-align: left;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-header:hover { background: #f9fafb; }
      #${INPAGE_ROOT_ID} .ja-accordion-icon {
        width: 36px;
        height: 36px;
        border-radius: 8px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-icon svg {
        width: 20px;
        height: 20px;
        fill: none;
        stroke: #374151;
        stroke-width: 2;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-title-wrap {
        flex: 1;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-title { font-weight: 500; }
      #${INPAGE_ROOT_ID} .ja-accordion-help {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #9ca3af;
        color: #fff;
        font-size: 11px;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-status {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: #9ca3af;
        font-weight: 400;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-check {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #9ca3af;
        color: #fff;
        font-size: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-chevron {
        font-size: 10px;
        color: #6b7280;
        transition: transform 0.2s;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-item.expanded .ja-accordion-chevron { transform: rotate(180deg); }
      #${INPAGE_ROOT_ID} .ja-accordion-body { border-top: 1px solid #e5e7eb; }
      #${INPAGE_ROOT_ID} .ja-resume-accordion-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
      #${INPAGE_ROOT_ID} .ja-resume-accordion-row .ja-resume-select { flex: 1; padding: 6px 10px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 13px; }
      #${INPAGE_ROOT_ID} .ja-resume-preview-hint { font-size: 11px; color: #6b7280; margin: 4px 0 0 0; }
      #${INPAGE_ROOT_ID} .ja-cover-letter-preview { margin-bottom: 10px; padding: 8px; background: #f9fafb; border-radius: 6px; max-height: 200px; overflow-y: auto; font-size: 12px; line-height: 1.5; }
      #${INPAGE_ROOT_ID} .ja-cover-letter-job { font-weight: 600; margin: 0 0 6px 0; font-size: 12px; }
      #${INPAGE_ROOT_ID} .ja-cover-letter-text { white-space: pre-wrap; word-break: break-word; }
      #${INPAGE_ROOT_ID} .ja-questions-list { max-height: 240px; overflow-y: auto; }
      #${INPAGE_ROOT_ID} .ja-question-row { display: flex; align-items: center; gap: 6px; padding: 6px 0; border-bottom: 1px solid #f3f4f6; font-size: 12px; }
      #${INPAGE_ROOT_ID} .ja-question-label { flex: 0 0 40%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #374151; }
      #${INPAGE_ROOT_ID} .ja-question-value { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #6b7280; }
      #${INPAGE_ROOT_ID} .ja-field-type-badge { flex-shrink: 0; font-size: 9px; font-weight: 600; padding: 1px 5px; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.3px; }
      #${INPAGE_ROOT_ID} .ja-field-type-select   { background: #dbeafe; color: #1d4ed8; }
      #${INPAGE_ROOT_ID} .ja-field-type-date      { background: #fef9c3; color: #854d0e; }
      #${INPAGE_ROOT_ID} .ja-field-type-textarea  { background: #dcfce7; color: #166534; }
      #${INPAGE_ROOT_ID} .ja-field-type-input     { background: #f3f4f6; color: #4b5563; }
      #${INPAGE_ROOT_ID} .ja-accordion-content {
        padding: 12px 14px;
        font-size: 13px;
        color: #6b7280;
      }
      #${INPAGE_ROOT_ID} .ja-keywords-section { margin-bottom: 12px; }
      #${INPAGE_ROOT_ID} .ja-keywords-section label {
        display: block;
        font-size: 12px;
        font-weight: 600;
        color: #374151;
        margin-bottom: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-resume-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 10px;
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        margin-bottom: 10px;
      }
      #${INPAGE_ROOT_ID} .ja-resume-row span { flex: 1; font-size: 13px; color: #374151; }
      #${INPAGE_ROOT_ID} .ja-resume-row button {
        background: none;
        border: none;
        color: #0ea5e9;
        cursor: pointer;
        padding: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-resume-select {
        width: 100%;
        padding: 8px 10px;
        font-size: 13px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        background: #fff;
        margin-bottom: 10px;
      }
      #${INPAGE_ROOT_ID} .ja-update-jd-btn {
        width: 100%;
        padding: 10px;
        background: #e0f2fe;
        color: #0369a1;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        margin-top: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-update-jd-btn:hover { background: #bae6fd; }
      #${INPAGE_ROOT_ID} .ja-job-form input, #${INPAGE_ROOT_ID} .ja-job-form select, #${INPAGE_ROOT_ID} .ja-job-form textarea {
        width: 100%;
        padding: 8px 10px;
        font-size: 13px;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        margin-bottom: 10px;
      }
      #${INPAGE_ROOT_ID} .ja-job-form label { display: block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 4px; }
      #${INPAGE_ROOT_ID} .ja-job-form .ja-form-row { display: flex; gap: 10px; }
      #${INPAGE_ROOT_ID} .ja-job-form .ja-form-row > div { flex: 1; }
      #${INPAGE_ROOT_ID} .ja-job-form-actions { display: flex; gap: 8px; margin-top: 14px; }
      #${INPAGE_ROOT_ID} .ja-job-form-actions button { flex: 1; padding: 10px; border-radius: 8px; font-weight: 600; cursor: pointer; }
      #${INPAGE_ROOT_ID} .ja-go-back-btn { background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb; }
      #${INPAGE_ROOT_ID} .ja-save-job-btn { background: #2563eb; color: #fff; border: none; }
      #${INPAGE_ROOT_ID} .ja-tailor-btn {
        width: 100%;
        padding: 10px;
        background: #e0f2fe;
        color: #0369a1;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        margin-bottom: 12px;
      }
      #${INPAGE_ROOT_ID} .ja-tailor-btn:hover { background: #bae6fd; }
      #${INPAGE_ROOT_ID} .ja-keyword-card {
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 12px;
      }
      #${INPAGE_ROOT_ID} .ja-keyword-card.ja-loading { position: relative; }
      #${INPAGE_ROOT_ID} .ja-keyword-card.ja-loading::after {
        content: ""; position: absolute; top: 50%; left: 50%; margin: -12px 0 0 -12px;
        width: 24px; height: 24px; border: 2px solid #e5e7eb; border-top-color: #2563eb;
        border-radius: 50%; animation: ja-spin 0.8s linear infinite;
      }
      #${INPAGE_ROOT_ID} .ja-keyword-card h4 {
        margin: 0 0 8px 0;
        font-size: 13px;
        font-weight: 600;
        color: #111;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-keyword-card .ja-score-text { font-size: 12px; color: #6b7280; margin-bottom: 8px; }
      #${INPAGE_ROOT_ID} .ja-keyword-list {
        display: flex;
        flex-wrap: wrap;
        gap: 6px 10px;
        font-size: 12px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-matched { color: #2563eb; }
      #${INPAGE_ROOT_ID} .ja-kw-unmatched { color: #6b7280; }
      /* High/Low Priority sections - light blue bg (OpsBrain theme) */
      #${INPAGE_ROOT_ID} .ja-kw-priority-section {
        margin-bottom: 14px;
        background: rgba(96, 165, 250, 0.04);
        border: 1px solid #C5CAD1;
        border-radius: 10px;
        overflow: hidden;
      }
      #${INPAGE_ROOT_ID} .ja-kw-priority-section:last-child { margin-bottom: 0; }
      #${INPAGE_ROOT_ID} .ja-kw-priority-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 14px;
        background: rgba(96, 165, 250, 0.08);
        border-bottom: 1px solid #C5CAD1;
      }
      #${INPAGE_ROOT_ID} .ja-kw-priority-title {
        font-size: 13px;
        font-weight: 600;
        color: #0f172a;
        display: flex;
        align-items: center;
        gap: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-priority-count {
        font-size: 13px;
        font-weight: 600;
        color: #2563eb;
      }
      #${INPAGE_ROOT_ID} .ja-kw-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px 14px;
        font-size: 12px;
        padding: 12px 14px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-item {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-check {
        width: 16px;
        height: 16px;
        border-radius: 3px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-size: 10px;
        font-weight: bold;
      }
      #${INPAGE_ROOT_ID} .ja-kw-check.ja-matched {
        background: #2563eb;
      }
      #${INPAGE_ROOT_ID} .ja-kw-check.ja-unmatched {
        background: #6b7280;
      }
      #${INPAGE_ROOT_ID} .ja-panel-profile .ja-profile-authenticated {
        padding-bottom: 16px;
      }
      #${INPAGE_ROOT_ID} .ja-profile-cards {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin-bottom: 16px;
        margin-left:10px;
        margin-right:10px;
      }
      #${INPAGE_ROOT_ID} .ja-profile-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 14px 16px;
        cursor: pointer;
        transition: background 0.15s, border-color 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-profile-card:hover {
        background: #f1f5f9;
        border-color: #cbd5e1;
      }
      #${INPAGE_ROOT_ID} .ja-profile-card h4 { margin: 0 0 6px 0; font-size: 14px; font-weight: 600; color: #0f172a; }
      #${INPAGE_ROOT_ID} .ja-profile-card p { margin: 0; font-size: 12px; color: #64748b; line-height: 1; }
      #${INPAGE_ROOT_ID} .ja-copy-tip {
        background: #f8fafc;
        color: #64748b;
        padding: 10px 14px;
        margin: 0 10px 14px 10px;
        border-radius: 8px;
        font-size: 11px;
        line-height: 1.4;
        border: 1px solid #e2e8f0;
      }
      /* Profile card container: clean SaaS look */
      #${INPAGE_ROOT_ID} .ja-profile-card-container {
        background: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.08);
        border: 1px solid #e2e8f0;
        margin: 0 10px 16px 10px;
      }
      #${INPAGE_ROOT_ID} .ja-profile-section {
        padding: 14px 0;
        border-bottom: 1px solid #e2e8f0;
      }
      #${INPAGE_ROOT_ID} .ja-profile-section:first-child { padding-top: 4px; }
      #${INPAGE_ROOT_ID} .ja-profile-section:last-child { border-bottom: none; padding-bottom: 4px; }
      #${INPAGE_ROOT_ID} .ja-profile-section h4 {
        margin: 0 0 8px 0;
        font-size: 13px;
        font-weight: 600;
        color: #334155;
        letter-spacing: 0.01em;
      }
      #${INPAGE_ROOT_ID} .ja-profile-section .ja-value {
        font-size: 13px;
        color: #1e293b;
        line-height: 1;
        word-break: break-word;
      }
      #${INPAGE_ROOT_ID} .ja-profile-main { margin-top: 4px; margin-bottom:20px }
      #${INPAGE_ROOT_ID} .ja-profile-main .ja-profile-card-container { display: flex; flex-direction: column; gap: 14px; }
      #${INPAGE_ROOT_ID} .ja-profile-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        flex-wrap: wrap;
      }
      #${INPAGE_ROOT_ID} .ja-profile-name { font-size: 18px; font-weight: 700; color: #0f172a; line-height:1; }
      #${INPAGE_ROOT_ID} .ja-profile-title { font-size: 13px; color: #64748b; margin-top: 2px; }
      #${INPAGE_ROOT_ID} .ja-avatar {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg,#2563eb 0%,#3b82f6 100%);
        color: white;
        font-weight: 700;
        font-size: 16px;
        flex-shrink: 0;
      }
      #${INPAGE_ROOT_ID} .ja-profile-header-actions { display: flex; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-profile-btn {
        font-size: 11px;
        padding: 4px 10px;
        border: 1px solid #cbd5e1;
        background: #fff;
        color: #475569;
        border-radius: 6px;
        cursor: pointer;
      }
      #${INPAGE_ROOT_ID} .ja-profile-btn:hover { background: #f1f5f9; border-color: #94a3b8; }
      #${INPAGE_ROOT_ID} .ja-profile-contact {
        font-size: 13px;
        color: #475569;
        line-height: 1.4;
        margin-bottom: 20px;
        padding-bottom: 20px;
        border-bottom: 1px solid #e2e8f0;
      }
      #${INPAGE_ROOT_ID} .ja-profile-contact .ja-profile-line { margin: 2px 0; }
      #${INPAGE_ROOT_ID} .ja-profile-block {
        margin-bottom: 20px;
        padding-bottom: 20px;
        border-bottom: 1px solid #e2e8f0;
      }
      #${INPAGE_ROOT_ID} .ja-profile-block:last-child {
        margin-bottom: 0;
        padding-bottom: 0;
        border-bottom: none;
      }
      #${INPAGE_ROOT_ID} .ja-profile-block-title {
        font-size: 12px;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 10px;
      }
      #${INPAGE_ROOT_ID} .ja-profile-block-content { font-size: 13px; color: #1e293b; line-height: 1.55; margin: 0; }
      #${INPAGE_ROOT_ID} .ja-profile-block-content .ja-copyable { cursor: pointer; }
      #${INPAGE_ROOT_ID} .ja-profile-block-content .ja-copyable:hover { background: #f1f5f9; border-radius: 4px; }
      /* Experience & Education: card-style entries with clear hierarchy */
      #${INPAGE_ROOT_ID} .ja-exp-item, #${INPAGE_ROOT_ID} .ja-edu-item {
        margin-bottom: 16px;
        padding: 14px 0;
        border-bottom: 1px solid #e2e8f0;
        transition: background 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-exp-item:last-child, #${INPAGE_ROOT_ID} .ja-edu-item:last-child {
        margin-bottom: 0;
        padding-bottom: 0;
        border-bottom: none;
      }
      #${INPAGE_ROOT_ID} .ja-exp-item:hover, #${INPAGE_ROOT_ID} .ja-edu-item:hover {
        background: linear-gradient(90deg, transparent, rgba(15,23,42,0.02) 8%, transparent);
      }
      #${INPAGE_ROOT_ID} .ja-exp-role {
        font-size: 15px;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 4px;
        line-height: 1.3;
      }
      #${INPAGE_ROOT_ID} .ja-exp-company {
        font-size: 13px;
        font-weight: 500;
        color: #475569;
        margin-bottom: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-exp-meta {
        font-size: 11px;
        color: #94a3b8;
        margin-bottom: 8px;
        letter-spacing: 0.02em;
      }
      #${INPAGE_ROOT_ID} .ja-exp-bullets {
        padding-left: 18px;
        margin: 8px 0 0 0;
        color: #334155;
        font-size: 13px;
        line-height: 1.5;
      }
      #${INPAGE_ROOT_ID} .ja-exp-bullets li { margin: 4px 0; }
      #${INPAGE_ROOT_ID} .ja-edu-institution {
        font-size: 14px;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-edu-degree {
        font-size: 13px;
        color: #475569;
        margin-bottom: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-edu-meta {
        font-size: 11px;
        color: #94a3b8;
      }
      /* Skill chips: professional pill styling with consistent spacing */
      #${INPAGE_ROOT_ID} .ja-skill-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
        padding: 2px 0;
      }
      #${INPAGE_ROOT_ID} .ja-skill-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 4px 8px;
        font-size: 12px;
        font-weight: 500;
        background: #f1f5f9;
        color: #334155;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        cursor: default;
        white-space: nowrap;
      }
      #${INPAGE_ROOT_ID} .ja-profile-block-content .ja-skill-chip.ja-copyable:hover {
        background: #e2e8f0;
        border-color: #cbd5e1;
      }
      #${INPAGE_ROOT_ID} .ja-link-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
        flex-wrap: wrap;
      }
      #${INPAGE_ROOT_ID} .ja-link-row:last-child { margin-bottom: 0; }
      #${INPAGE_ROOT_ID} .ja-link-label { font-weight: 500; color: #334155; min-width: 60px; }
      #${INPAGE_ROOT_ID} .ja-link-url { color: #0284c7; word-break: break-all; }
      #${INPAGE_ROOT_ID} .ja-link-url:hover { text-decoration: underline; }
      #${INPAGE_ROOT_ID} .ja-upload-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        padding: 8px 0;
        flex-wrap: wrap;
      }
      #${INPAGE_ROOT_ID} .ja-upload-label { font-weight: 500; }
      #${INPAGE_ROOT_ID} .ja-upload-meta { font-size: 12px; color: #64748b; }
      #${INPAGE_ROOT_ID} .ja-upload-preview {
        font-size: 12px;
        color: #0284c7;
        cursor: pointer;
        background: none;
        border: none;
        padding: 0;
        text-decoration: underline;
      }
      #${INPAGE_ROOT_ID} .ja-upload-preview:hover { color: #0369a1; }
      #${INPAGE_ROOT_ID}.collapsed .ja-card { display: none; }
      #${INPAGE_ROOT_ID}.collapsed {
        width: 56px;
        height: 56px;
        min-width: 56px;
        max-height: 56px;
      }
      #${INPAGE_ROOT_ID} .ja-mini {
        display: none;
        position: absolute;
        top: 50%;
        right: 0;
        transform: translateY(-50%);
        width: 56px;
        height: 56px;
        background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
        color: white;
        border: none;
        border-radius: 50%;
        font-size: 24px;
        cursor: move;
        box-shadow: 0 8px 24px rgba(14, 165, 233, 0.4);
        align-items: center;
        justify-content: center;
        transition: transform 0.2s;
      }
      #${INPAGE_ROOT_ID} .ja-mini:hover { transform: translateY(-50%) scale(1.05); }
      #${INPAGE_ROOT_ID}.collapsed .ja-mini { display: flex; }
    </style>
    <div class="ja-card">
      <div class="ja-head" id="ja-drag-handle">
        <div class="ja-logo-wrap">
          <img class="ja-logo-icon" src="${chrome.runtime.getURL('logo.png')}" alt="OpsBrain" />
        </div>
        <div class="ja-head-actions">

          <button type="button" class="ja-close ja-head-btn" id="ja-close" title="Close">×</button>
        </div>
      </div>
      <div class="ja-tabs">
        <button type="button" class="ja-tab active" data-tab="autofill" id="ja-tab-autofill">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19l7-7 3 3-7 7-3-3z M4 4l7 7 3 3"/></svg>
          Autofill
        </button>
        <button type="button" class="ja-tab" data-tab="keywords">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          Keywords Score
        </button>
        <button type="button" class="ja-tab" data-tab="profile">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
          Profile
        </button>
      </div>
      <div class="ja-body">
        <div class="ja-panel active" id="ja-panel-autofill">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta" style="display:none">
            <h3>Sign in to autofill</h3>
            <p>Information is pulled from your OpsBrain profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill" id="ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-autofill-authenticated" id="ja-autofill-authenticated">
          <div class="ja-autofill-box">
            <h3>Autofill this job application!</h3>
            <div class="ja-status-area" id="ja-status-area">
              <div class="ja-status-loader" id="ja-status-loader"></div>
              <p class="ja-status" id="ja-status">You have saved 4 minutes by autofilling so far 🔥</p>
            </div>
            <div class="ja-progress"><div class="ja-progress-bar" id="ja-progress"></div></div>
            <div class="ja-action-row">
              <button type="button" class="ja-action" id="ja-run">Autofill this page</button>
            </div>
            <div class="ja-quick-save-row" id="ja-quick-save-row" style="display:none;margin-top:10px;">
              <button type="button" class="ja-action ja-save-applied" id="ja-save-applied">Save & Mark Applied</button>
            </div>
            <div class="ja-fill-controls" id="ja-fill-controls">
              <span class="ja-fill-label">Autofilling</span>
              <button type="button" class="ja-stop" id="ja-stop">Stop</button>
              <button type="button" class="ja-skip-next" id="ja-skip-next">⏭ Skip to next input</button>
            </div>
            <button type="button" class="ja-continue-fill" id="ja-continue-fill" style="display:none">Continue filling</button>
            <label class="ja-auto-advance" id="ja-auto-advance-wrap">
              <input type="checkbox" id="ja-auto-advance" /> Auto-advance through all steps
            </label>
          </div>
          <div class="ja-footer-links">
            <button type="button" class="ja-footer-link" id="ja-save-job-instead">Save Job Instead</button>
            <button type="button" class="ja-footer-link">Get referrals →</button>
          </div>
          <div class="ja-accordions" id="ja-autofill-accordions"></div>
          
          </div>
        </div>
        <div class="ja-panel" id="ja-panel-keywords">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta-keywords" style="display:none">
            <h3>Sign in to view keywords</h3>
            <p>Information is pulled from your OpsBrain profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-keywords-authenticated" id="ja-keywords-authenticated">
          <div class="ja-keywords-view" id="ja-keywords-view">
          <div class="ja-keywords-section">
            <label>Resume</label>
            <select class="ja-resume-select" id="ja-resume-select">
              <option value="">Loading resumes...</option>
            </select>
            <button type="button" class="ja-tailor-btn" id="ja-tailor-resume-btn">Tailor Resume</button>
            <p style="font-size:11px;color:#9ca3af;margin:0 0 8px 0;">Bold % indicates keyword coverage.</p>
          </div>
          <div class="ja-keyword-card" id="ja-keyword-card">
            <div id="ja-keyword-analysis">
              <p class="ja-score-text">Loading keyword analysis...</p>
            </div>
          </div>
          <button type="button" class="ja-update-jd-btn" id="ja-update-jd-btn">Update Job Description</button>
          </div>
          <div class="ja-job-form-panel" id="ja-job-form-panel" style="display:none">
            <h4 style="margin:0 0 10px 0;font-size:14px;">Edit Job Description</h4>
            <p style="font-size:12px;color:#6b7280;margin:0 0 12px 0;">With a job description you can view matching keywords and/or save this job to your tracker!</p>
            <form class="ja-job-form" id="ja-job-form">
              <label>Company</label>
              <input type="text" id="ja-job-company" placeholder="Company name">
              <label>Position Title</label>
              <input type="text" id="ja-job-position" placeholder="Lead Software Development Engineer">
              <label>Location</label>
              <input type="text" id="ja-job-location" placeholder="Bangalore">
              <label>Min. Salary ($)</label>
              <input type="text" id="ja-job-min-salary" placeholder="180">
              <label>Max. Salary ($)</label>
              <input type="text" id="ja-job-max-salary" placeholder="740000000">
              <label>Currency</label>
              <select id="ja-job-currency">
                <option value="USD">US Dollar (USD)</option>
                <option value="EUR">Euro (EUR)</option>
                <option value="GBP">British Pound (GBP)</option>
                <option value="INR">Indian Rupee (INR)</option>
              </select>
              <label>Period</label>
              <select id="ja-job-period">
                <option value="Yearly">Yearly</option>
                <option value="Monthly">Monthly</option>
                <option value="Hourly">Hourly</option>
              </select>
              <label>Job Type</label>
              <select id="ja-job-type">
                <option value="Full-Time">Full-Time</option>
                <option value="Part-Time">Part-Time</option>
                <option value="Contract">Contract</option>
                <option value="Internship">Internship</option>
              </select>
              <label>Application Status</label>
              <select id="ja-job-status">
                <option value="I have not yet applied">I have not yet applied</option>
                <option value="Applied">Applied</option>
                <option value="Interviewing">Interviewing</option>
                <option value="Offer">Offer</option>
                <option value="Rejected">Rejected</option>
                <option value="Withdrawn">Withdrawn</option>
              </select>
              <label>Job Description — Click to edit</label>
              <textarea id="ja-job-description" rows="6" placeholder="Auto-detected description available."></textarea>
              <label>Notes — Click to add</label>
              <textarea id="ja-job-notes" rows="2" placeholder="Add notes..."></textarea>
              <label>Job Posting URL</label>
              <input type="text" id="ja-job-url" placeholder="https://...">
              <div class="ja-job-form-actions">
                <button type="button" class="ja-go-back-btn" id="ja-job-go-back">Go Back</button>
                <button type="submit" class="ja-save-job-btn" id="ja-job-save">Save Job</button>
              </div>
            </form>
          </div>
          </div>
          </div>
        </div>
        <div class="ja-panel" id="ja-panel-profile">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta-profile" style="display:none">
            <h3>Sign in to view profile</h3>
            <p>Information is pulled from your OpsBrain profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-profile-authenticated" id="ja-profile-authenticated">
            <div class="ja-profile-cards">
              <div class="ja-profile-card"><h4>Job Matches</h4><p>Fill out my preferences →</p></div>
              <div class="ja-profile-card"><h4>Job Tracker</h4><p>Add your first job! →</p></div>
            </div>
            <div class="ja-copy-tip">Click any block of text below to copy it — handy when filling applications.</div>
            <div class="ja-profile-main" id="ja-profile-main">
              <div class="ja-profile-card-container">
                <div class="ja-profile-header">
                  <div style="display:flex;align-items:center;gap:12px">
                    <div class="ja-avatar" id="ja-profile-avatar">—</div>
                    <div>
                      <div class="ja-profile-name" id="ja-profile-name">—</div>
                      <div class="ja-profile-title" id="ja-profile-title"></div>
                    </div>
                  </div>
                  <div class="ja-profile-header-actions">
                    <button type="button" class="ja-profile-btn" id="ja-profile-refresh" title="Refresh">Refresh</button>
                    <button type="button" class="ja-profile-btn" id="ja-profile-edit" title="Edit">Edit</button>
                  </div>
                </div>
                <div class="ja-profile-contact" id="ja-profile-contact"></div>
                <div class="ja-profile-block" id="ja-profile-education-block">
                  <h4 class="ja-profile-block-title">Education</h4>
                  <div class="ja-profile-block-content" id="ja-profile-education"></div>
                </div>
                <div class="ja-profile-block" id="ja-profile-experience-block">
                  <h4 class="ja-profile-block-title">Experience</h4>
                  <div class="ja-profile-block-content" id="ja-profile-experience"></div>
                </div>
                <div class="ja-profile-block" id="ja-profile-uploads-block">
                  <h4 class="ja-profile-block-title">Uploads</h4>
                  <div class="ja-profile-block-content ja-upload-box-up" id="ja-profile-uploads" ></div>
                </div>
                <div class="ja-profile-block" id="ja-profile-links-block">
                  <h4 class="ja-profile-block-title">Links</h4>
                  <div class="ja-profile-block-content" id="ja-profile-links"></div>
                </div>
                <div class="ja-profile-block" id="ja-profile-skills-block">
                  <h4 class="ja-profile-block-title">Skills</h4>
                  <div class="ja-profile-block-content" id="ja-profile-skills"></div>
                </div>
                <div class="ja-profile-block" id="ja-profile-languages-block">
                  <h4 class="ja-profile-block-title">Languages</h4>
                  <div class="ja-profile-block-content" id="ja-profile-languages" ></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <button class="ja-mini" id="ja-open">S</button>
  `;
  document.documentElement.appendChild(root);

  updateWidgetAuthUI(root);
  if (isCareerPage()) trackCareerPageView();

  // Render autofill accordions (Resume, Cover Letter, Unique Questions, Common Questions)
  const accordionsContainer = root.querySelector("#ja-autofill-accordions");
  if (accordionsContainer) {
    renderAccordions(accordionsContainer, [
      { id: "resume", iconBg: "#e9d5ff", iconSvg: ACCORDION_ICONS.document, title: "Resume", showHelpIcon: true },
      { id: "cover-letter", iconBg: "#fed7aa", iconSvg: ACCORDION_ICONS.coverLetter, title: "Cover Letter", statusText: "No Field Found" },
      { id: "unique-questions", iconBg: "#fef08a", iconSvg: ACCORDION_ICONS.star, title: "Unique Questions", statusText: "Filled (0/0)", statusCheckmark: true },
      { id: "common-questions", iconBg: "#99f6e4", iconSvg: ACCORDION_ICONS.person, title: "Common Questions", statusText: "Filled (0/0)", statusCheckmark: true },
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
    const isWorkday = /workday\.com|myworkdayjobs\.com/i.test(window.location.href);
    autoAdvanceWrap.style.display = isWorkday ? "flex" : "none";
  }

  const statusEl = root.querySelector("#ja-status");
  const statusArea = root.querySelector("#ja-status-area");
  const progressBar = root.querySelector("#ja-progress");
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
    const base = data.loginPageUrl ? new URL(data.loginPageUrl).origin : "http://localhost:5173";
    chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url: `${base}/profile` });
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
    statusEl.className = `ja-status ${type}`.trim();
    statusArea?.classList.toggle("loading", type === "loading");
  };

  const setProgress = (percent) => {
    if (progressBar) progressBar.style.width = `${percent}%`;
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

  let abortRequested = false;
  let skipToNextRequested = false;

  const runOneStep = async (stepNum = 1) => {
    setStatus(stepNum > 1 ? `Step ${stepNum} — Extracting fields...` : "Extracting form fields...", "loading");
    setProgress(5);
    let fields = [];
    for (let attempt = 0; attempt < 3; attempt++) {
      if (attempt > 0) {
        setStatus(`Waiting for form to load... (attempt ${attempt + 1}/3)`, "loading");
        await new Promise((r) => setTimeout(r, 1500 + attempt * 1000));
      }
      const scrapeRes = await chrome.runtime.sendMessage({
        type: "SCRAPE_ALL_FRAMES",
        scope: "all",
      });
      if (scrapeRes?.ok && scrapeRes.fields?.length) {
        fields = scrapeRes.fields;
        break;
      }
    }
    if (!fields.length) throw new Error("No form fields found. Click \"Apply\" on a job to open the application form, then try again.");

    setStatus(`Found ${fields.length} fields — loading profile & resume...`, "loading");
    setProgress(15);
    const context = await getAutofillContextFromApi();
    let resumeData = await getResumeFromBackground();
    if (!resumeData && (context.resumeUrl || context.resumeFileName)) {
      resumeData = await fetchResumeFromContext(context);
    }
    if (!resumeData) resumeData = await getStaticResume();

    setStatus("Mapping fields with AI...", "loading");
    setProgress(35);
    const mappings = await fetchMappingsFromApi(fields, context);
    if (!Object.keys(mappings).length) throw new Error("No mapping returned");

    setStatus("Preparing to fill...", "loading");
    setProgress(50);

    const valuesByFrame = {};
    for (const field of fields) {
      const mapData = mappings[String(field.index)] || mappings[field.index];
      let val = mapData?.value;
      if ((field.type || "").toLowerCase() === "file" && !val) val = "RESUME_FILE";
      if (val === undefined || val === null || val === "") continue;
      const fid = String(field.frameId ?? 0);
      const localKey = String(field.frameLocalIndex ?? field.index);
      if (!valuesByFrame[fid]) valuesByFrame[fid] = {};
      valuesByFrame[fid][localKey] = val;
    }

    const fillRes = await chrome.runtime.sendMessage({
      type: "FILL_ALL_FRAMES",
      payload: { valuesByFrame, resumeData },
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
    } catch (_) {}
  };

  const runFlow = async (isContinueFromErrors = false) => {
    if (!runBtn) return;
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

    const autoAdvance = root.querySelector("#ja-auto-advance")?.checked;
    const isWorkday = /workday\.com|myworkdayjobs\.com/i.test(window.location.href);
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
        application_status: "saved",
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
  } catch (e) {}
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
    if (isCareerPage()) runKeywordAnalysisAndMaybeShowWidget();
    const widget = document.getElementById(INPAGE_ROOT_ID);
    if (widget) {
      const card = widget.querySelector(".ja-card");
      if (card) card.classList.remove("collapsed");
    }
    sendResponse({ ok: true });
    return true;
  }
  
  if (msg.type === "SCRAPE_FIELDS") {
    try {
      sendResponse({ ok: true, ...scrapeFields(msg.payload || {}) });
    } catch (e) {
      sendResponse({ ok: false, error: String(e) });
    }
    return true;
  }

  if (msg.type === "FILL_WITH_VALUES") {
    fillWithValues(msg.payload || {})
      .then((result) => sendResponse({ ok: true, ...result }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (msg.type === "FILL_FORM") {
    fillFormRuleBased(msg.payload || {})
      .then((result) => sendResponse({ ok: true, ...result }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  return false;
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
  if (!isJobFormPage()) return;
  mountInPageUI();
  const widget = document.getElementById(INPAGE_ROOT_ID);
  if (widget) {
    const card = widget.querySelector(".ja-card");
    if (card) card.classList.remove("collapsed");
  }
  runKeywordAnalysisAndMaybeShowWidget();
}

const initAutoOpen = () => {
  tryAutoOpenPopup();
  setTimeout(tryAutoOpenPopup, 1500);
  setTimeout(tryAutoOpenPopup, 4000);
};
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => setTimeout(initAutoOpen, 500));
} else {
  setTimeout(initAutoOpen, 500);
}
