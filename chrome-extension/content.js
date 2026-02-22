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
  '[role="textbox"]',
  '[role="combobox"]',
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

function renderAccordions(containerEl, items) {
  if (!containerEl) return;
  containerEl.innerHTML = items.map((item) => createAccordionItem(item)).join("");
  containerEl.querySelectorAll(".ja-accordion-header").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = btn.closest(".ja-accordion-item");
      const body = item?.querySelector(".ja-accordion-body");
      const isExpanded = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", !isExpanded);
      if (body) body.hidden = isExpanded;
      item?.classList.toggle("expanded", !isExpanded);
    });
  });
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
  const roots = [doc];
  const all = doc.querySelectorAll("*");
  for (const el of all) {
    if (el.shadowRoot) roots.push(el.shadowRoot);
  }
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

function isFillable(field) {
  if (!field || !field.ownerDocument || !field.isConnected) return false;
  const tag = (field.tagName || "").toLowerCase();
  const type = (field.type || "").toLowerCase();

  if (tag === "input" && type === "file") {
    if (field.disabled || field.getAttribute("aria-disabled") === "true") return false;
    return true;
  }

  if (!isVisible(field)) return false;
  if (field.disabled || field.readOnly) return false;
  if (field.getAttribute("aria-disabled") === "true") return false;

  const role = (field.getAttribute("role") || "").toLowerCase();

  if (tag === "input") {
    if (IGNORE_INPUT_TYPES.has(type)) return false;
    return true;
  }

  if (tag === "textarea" || tag === "select") return true;
  if (field.isContentEditable) return true;
  if (role === "textbox" || role === "combobox") return true;

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

function getFillableFields(includeNestedDocuments = true) {
  const out = [];
  const seen = new Set();
  const docs = getDocuments(includeNestedDocuments);

  for (const doc of docs) {
    const roots = getAllRoots(doc);
    for (const root of roots) {
      const candidates = Array.from(root.querySelectorAll(FIELD_SELECTOR));
      for (const el of candidates) {
        if (seen.has(el)) continue;
        seen.add(el);
        if (isFillable(el)) out.push(el);
      }
    }
  }

  return out;
}

function dispatchFrameworkEvents(field) {
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
    
    field.value = match.value;
    dispatchFrameworkEvents(field);
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
      const proto = Object.getPrototypeOf(field);
      const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
      if (descriptor?.set) descriptor.set.call(field, formattedDate);
      else field.value = formattedDate;
      dispatchFrameworkEvents(field);
      return true;
    }

    const proto = Object.getPrototypeOf(field);
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    if (descriptor?.set) descriptor.set.call(field, value);
    else field.value = value;
    dispatchFrameworkEvents(field);
    return true;
  }

  if (tag === "textarea") {
    const proto = Object.getPrototypeOf(field);
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    if (descriptor?.set) descriptor.set.call(field, value);
    else field.value = value;
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
  logInfo("Starting DOM scrape for fillable fields");
  const fillable = getFillableFields(includeNestedDocuments);
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
  const fillable = getFillableFields(includeNestedDocuments);
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

/** Fetch job description via keywords/analyze (scrapes with Playwright, returns job_description in response). */
async function fetchJobDescriptionFromKeywordsApi(url) {
  if (!url || !url.startsWith("http")) return null;
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/keywords/analyze`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
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
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/keywords/analyze`, {
      method: "POST",
      headers,
      body: JSON.stringify({ url }),
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
      <div class="ja-kw-desc" id="ja-kw-desc">${matched} of ${total} keywords are present in your resume.</div>
      <span class="ja-kw-tag">HireMate</span>
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
  const url = `${base}/resume-generator`;
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

    if (detail?.educations?.length) {
      const eduHtml = detail.educations
        .map(
          (e) => `
        <div class="ja-edu-item ja-copyable" data-copy="${escapeHtml(
          `${e.institution || ""}\n${e.degree || ""} ${e.fieldOfStudy || ""}\n${e.startYear || ""} - ${e.endYear || ""}`
        )}">
          <div><strong>${escapeHtml(e.institution || "—")}</strong></div>
          <div>${escapeHtml(e.degree || "")}${e.fieldOfStudy ? ", " + escapeHtml(e.fieldOfStudy) : ""}</div>
          <div class="ja-exp-meta">${escapeHtml(e.startYear || "")} - ${escapeHtml(e.endYear || "")}</div>
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

    if (detail?.experiences?.length) {
      const expHtml = detail.experiences
        .map(
          (e) => {
            const metaParts = [e.companyName, e.location, `${e.startDate || ""} - ${e.endDate || ""}`].filter(Boolean);
            const bullets = (e.description || "")
              .split(/\n|•/)
              .map((s) => s.trim())
              .filter(Boolean)
              .map((b) => `<li>${escapeHtml(b)}</li>`)
              .join("");
            const copyText = `${e.jobTitle || ""} at ${e.companyName || ""}\n${e.startDate || ""} - ${e.endDate || ""}\n${e.description || ""}`;
            return `
          <div class="ja-exp-item ja-copyable" data-copy="${escapeHtml(copyText)}">
            <div class="ja-exp-company">
  <strong>${escapeHtml(e.jobTitle || "—")}</strong>
  ${e.companyName ? ` at <strong>${escapeHtml(e.companyName)}</strong>` : ""}
</div>
            <div class="ja-exp-meta">${escapeHtml(metaParts.join(" • "))}</div>
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

    const resumeName = ctx.resumeFileName || (ctx.resumeUrl || "").split("/").pop() || "Resume";
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
    if (skills.length === 0 && flat.skills) skills.push(...flat.skills.split(",").map((s) => s.trim()).filter(Boolean));
    if (skills.length) {
      setHtml(skillsEl, skills.map((s) => `<span class="ja-skill-chip ja-copyable" data-copy="${escapeHtml(s)}">${escapeHtml(s)}</span>`).join(""));
      skillsEl?.querySelectorAll(".ja-skill-chip").forEach((node) => makeCopyable(node, node.dataset.copy));
    } else {
      setText(skillsEl, "—");
    }

    const langs = detail?.willingToWorkIn || [];
    setHtml(languagesEl, langs.length ? langs.map((l) => `<span class="ja-skill-chip">${escapeHtml(l)}</span>`).join("") : (flat.country ? escapeHtml(flat.country) : "—"));
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
  const ogTitle = document.querySelector('meta[property="og:title"]')?.content;
  const h1 = document.querySelector("h1");
  if (ogTitle) {
    const parts = ogTitle.split(/[|\-–—]/);
    if (parts.length >= 2) {
      company = (parts[0] || "").trim();
      position = (parts[1] || "").trim();
    } else {
      position = ogTitle.trim();
    }
  } else if (h1) {
    position = getText(h1);
  }
  if (!position && title) position = title;
  return { company, position };
}

async function prefillJobForm(root) {
  const { company, position } = extractCompanyAndPosition();
  const urlInput = root?.querySelector("#ja-job-url");
  const descInput = root?.querySelector("#ja-job-description");
  const companyInput = root?.querySelector("#ja-job-company");
  const positionInput = root?.querySelector("#ja-job-position");
  if (urlInput) urlInput.value = window.location.href || "";
  if (companyInput) companyInput.value = company || "";
  if (positionInput) positionInput.value = position || "";

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
  if (btn) btn.disabled = true;
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
      headers,
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
    if (btn) btn.disabled = false;
  }
}

async function fetchResumesFromApi() {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/resumes`, { headers });
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
    if (selectEl) {
      selectEl.innerHTML = "";
      if (resumes.length === 0) {
        selectEl.innerHTML = "<option value=\"\">No resumes – add one in profile</option>";
      } else {
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
        if (defaultId !== null) selectEl.value = String(defaultId);
        else if (resumes.length) selectEl.value = String(resumes[0].id);
      }
    }

    const selectedId = selectEl?.value ? parseInt(selectEl.value, 10) : null;
    const resumeId = selectedId && selectedId > 0 ? selectedId : null;

    container.innerHTML = "<p class=\"ja-score-text\">Scraping job description...</p>";
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const body = { url: window.location.href };
    if (resumeId) body.resume_id = resumeId;

    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/keywords/analyze`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      container.innerHTML = "<p class=\"ja-score-text\">Add resume in your HireMate profile to see keyword match.</p>";
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
    const statusLabel = percent >= 70 ? "Great match" : "Needs Work";
    const renderItem = (item) =>
      `<div class="ja-kw-item"><span class="ja-kw-check ${item.matched ? "ja-matched" : "ja-unmatched"}">✓</span><span class="${item.matched ? "ja-kw-matched" : "ja-kw-unmatched"}">${escapeHtml(item.keyword)}</span></div>`;
    const highHtml = high.map(renderItem).join("");
    const lowHtml = low.map(renderItem).join("");
    container.innerHTML = `
      <h4>Keyword Match – ${statusLabel}</h4>
      <p class="ja-score-text">Your resume has <strong>${matched} out of ${total} (${percent}%)</strong> keywords that appear in the job description.</p>
      <p style="font-size:11px;background:#fef9c3;padding:6px 8px;border-radius:6px;margin:0 0 12px 0;">Try to get your score above <strong>70%</strong> to increase your chances!</p>
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

async function fetchMappingsFromApi(fields, context) {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const mapRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/form-fields/map`, {
    method: "POST",
    headers,
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
  const existing = document.getElementById(INPAGE_ROOT_ID);
  if (existing) {
    existing.classList.remove("collapsed");
    updateWidgetAuthUI(existing);
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
        width: 24px;
        height: 24px;
        background: linear-gradient(135deg, #38bdf8 0%, #0ea5e9 100%);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-size: 14px;
        font-weight: 700;
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
      /* High/Low Priority sections - light blue bg (HireMateAI theme) */
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
        padding-bottom: 8px;
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
        background: #e0f2fe;
        color: #0369a1;
        padding: 12px 14px;
        margin:10px;
        border-radius: 8px;
        font-size: 12px;
        margin-bottom: 16px;
        line-height: 1;
        border: 1px solid #bae6fd;
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
      #${INPAGE_ROOT_ID} .ja-profile-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
       
        flex-wrap: wrap;
      }
      #${INPAGE_ROOT_ID} .ja-profile-name { font-size: 16px; font-weight: 600; color: #0f172a; padding-left:15px}
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
        line-height: 1;
        margin-bottom: 16px;
        padding-left:30px;
        
      }
      #${INPAGE_ROOT_ID} .ja-profile-contact .ja-profile-line { margin: 2px 0; }
      #${INPAGE_ROOT_ID} .ja-profile-block {
        margin-bottom: 16px;
       

        border-bottom: 1px solid #e2e8f0;
        
      }
      #${INPAGE_ROOT_ID} .ja-profile-block:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
      #${INPAGE_ROOT_ID} .ja-profile-block-title {
        font-size: 16px;
        font-weight: 600;
        color:black;
        padding-left:15px;
        padding-bottom:3px;
        
        
        
      }
      #${INPAGE_ROOT_ID} .ja-profile-block-content { font-size: 13px; color: #1e293b; line-height: 1; 
  padding-left: 30px; margin-bottom:5px;
      }
      #${INPAGE_ROOT_ID} .ja-profile-block-content .ja-copyable { cursor: pointer; padding: 2px 0; }
      #${INPAGE_ROOT_ID} .ja-profile-block-content .ja-copyable:hover { background: #f1f5f9; border-radius: 4px; }
      #${INPAGE_ROOT_ID} .ja-edu-item, #${INPAGE_ROOT_ID} .ja-exp-item { margin-bottom: 14px; }
      #${INPAGE_ROOT_ID} .ja-edu-item:last-child, #${INPAGE_ROOT_ID} .ja-exp-item:last-child { margin-bottom: 0; }
      #${INPAGE_ROOT_ID} .ja-exp-company { font-weight: 600; color: #0f172a; margin-bottom: 2px; }
      #${INPAGE_ROOT_ID} .ja-exp-meta { font-size: 12px; color: #64748b; margin-bottom: 6px; }
      #${INPAGE_ROOT_ID} .ja-exp-bullets { padding-left: 16px; margin: 0; }
      #${INPAGE_ROOT_ID} .ja-exp-bullets li { margin: 4px 0; }
      #${INPAGE_ROOT_ID} .ja-skill-chip {
        display: inline-block;
        padding: 3px 8px;
        margin: 2px 4px 2px 0;
        font-size: 11px;
        background: #e2e8f0;
        color: #334155;
        border-radius: 6px;
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
          <div class="ja-logo-icon">H</div>
          <span class="ja-title">HireMate</span>
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
            <p>Information is pulled from your HireMate profile</p>
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
            <button type="button" class="ja-footer-link">Save Job Instead</button>
            <button type="button" class="ja-footer-link">Get referrals →</button>
          </div>
          <div class="ja-accordions" id="ja-autofill-accordions"></div>
          
          </div>
        </div>
        <div class="ja-panel" id="ja-panel-keywords">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta-keywords" style="display:none">
            <h3>Sign in to view keywords</h3>
            <p>Information is pulled from your HireMate profile</p>
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
            <p>Information is pulled from your HireMate profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-profile-authenticated" id="ja-profile-authenticated">
          <div class="ja-profile-cards">
            <div class="ja-profile-card"><h4>Job Matches</h4><p>Fill out my preferences →</p></div>
            <div class="ja-profile-card"><h4>Job Tracker</h4><p>Add your first job! →</p></div>
          </div>
          <div class="ja-copy-tip">Click any block of text below to copy it! Reference your profile to fill out your application.</div>
          <div class="ja-profile-main" id="ja-profile-main">
            <div class="ja-profile-header">
              <span class="ja-profile-name" id="ja-profile-name">—</span>
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
    <button class="ja-mini" id="ja-open">S</button>
  `;
  document.documentElement.appendChild(root);

  updateWidgetAuthUI(root);

  // Render autofill accordions (Resume, Cover Letter, Unique Questions, Common Questions)
  const accordionsContainer = root.querySelector("#ja-autofill-accordions");
  if (accordionsContainer) {
    renderAccordions(accordionsContainer, [
      { id: "resume", iconBg: "#e9d5ff", iconSvg: ACCORDION_ICONS.document, title: "Resume", showHelpIcon: true },
      { id: "cover-letter", iconBg: "#fed7aa", iconSvg: ACCORDION_ICONS.coverLetter, title: "Cover Letter", statusText: "No Field Found" },
      { id: "unique-questions", iconBg: "#fef08a", iconSvg: ACCORDION_ICONS.star, title: "Unique Questions", statusText: "Filled (0/6)", statusCheckmark: true },
      { id: "common-questions", iconBg: "#99f6e4", iconSvg: ACCORDION_ICONS.person, title: "Common Questions", statusText: "Filled (0/9)", statusCheckmark: true },
    ]);
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
    const isWorkday = /workday\.com|myworkdayjobs\.com/i.test(window.location.href);
    const scope = isWorkday ? "all" : "current_document";
    setStatus(stepNum > 1 ? `Step ${stepNum} — Extracting fields...` : "Extracting form fields...", "loading");
    setProgress(5);
    const { fields } = scrapeFields({ scope });
    if (!fields.length) throw new Error("No form fields found");

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

    const values = {};
    for (const [key, mapping] of Object.entries(mappings)) {
      values[key] = typeof mapping === "object" && mapping !== null ? mapping.value : mapping;
    }

    const result = await fillWithValues({
      values,
      scope,
      resumeData,
      shouldAbort: () => abortRequested,
      shouldSkip: () => {
        if (skipToNextRequested) {
          skipToNextRequested = false;
          return true;
        }
        return false;
      },
      onProgress: (p) => {
        if (p?.phase === "filling" && p?.message) {
          setStatus(p.message, "loading");
          const fillPct = 50 + Math.round((p.current / p.total) * 45);
          setProgress(fillPct);
        }
      },
    });
    return result;
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
    }
  };

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
  const urlSuggestsJob = isCareerPage();
  return (urlSuggestsJob && (hasApplicationForm || hasSubstantialContent)) || (hasApplicationForm && hasSubstantialContent);
}

function tryAutoOpenPopup() {
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
