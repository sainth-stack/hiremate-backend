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
const LOGIN_PAGE_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"];
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

async function fillFileInput(field, resumeData) {
  if (!resumeData?.buffer) return false;
  const blob = new Blob([new Uint8Array(resumeData.buffer)], { type: "application/pdf" });
  const file = new File([blob], resumeData.name || "resume.pdf", { type: "application/pdf" });
  const dt = new DataTransfer();
  dt.items.add(file);
  field.files = dt.files;
  dispatchFrameworkEvents(field);
  return true;
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
        label: meta.label || meta.name || `Field ${i + 1}`,
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
        }
      } else if (shouldUploadResume) {
        failedCount += 1;
        highlightFailedField(field);
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
    }
    await delay(fillDelay);
  }
  logInfo("Mapped fill completed", {
    totalFillable: fillable.length,
    textFieldsFilled: filledCount,
    resumeUploads: resumeUploadCount,
    failedCount,
  });
  return { filledCount, resumeUploadCount, failedCount };
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
    url.includes("jobvite.com")
  );
}

const KEYWORD_MATCH_ROOT_ID = "ja-keyword-match-root";
const STOP_WORDS = new Set(
  "a,an,the,and,or,but,in,on,at,to,for,of,with,by,from,as,is,was,are,were,been,be,have,has,had,do,does,did,will,would,could,should,may,might,must,shall,can,need,dare,ought,used".split(",")
);

function extractJobDescription() {
  const selectors = [
    "[data-automation-id='jobDescription']",
    "[data-automation-id='job-description']",
    ".job-description",
    ".job-description-content",
    ".job-details",
    ".job-body",
    "[class*='job-description']",
    "[class*='description']",
    ".description",
    "article",
    "[role='main']",
  ];
  for (const sel of selectors) {
    try {
      const el = document.querySelector(sel);
      if (el) {
        const text = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
        if (text.length > 100) return text;
      }
    } catch (_) {}
  }
  const body = document.body?.innerText || document.body?.textContent || "";
  return body.length > 200 ? body.slice(0, 8000) : "";
}

function extractKeywords(text) {
  const normalized = text
    .toLowerCase()
    .replace(/[^a-z0-9\s\-+#./]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const words = normalized.split(/\s+/).filter((w) => w.length >= 2);
  const seen = new Set();
  const keywords = [];
  for (const w of words) {
    const clean = w.replace(/^[.#\-]+|[.#\-]+$/g, "");
    if (clean.length >= 2 && !STOP_WORDS.has(clean) && !/^\d+$/.test(clean) && !seen.has(clean)) {
      seen.add(clean);
      keywords.push(clean);
    }
  }
  return keywords.slice(0, 50);
}

function computeKeywordMatch(jobDesc, resumeText) {
  const jobKeywords = extractKeywords(jobDesc);
  const resumeLower = (resumeText || "").toLowerCase();
  const matched = jobKeywords.filter((kw) => resumeLower.includes(kw));
  const total = jobKeywords.length;
  const percent = total > 0 ? Math.round((matched.length / total) * 100) : 0;
  return { matched, total, percent, allKeywords: jobKeywords };
}

function mountKeywordMatchWidget() {
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
        background: conic-gradient(#0ea5e9 0deg, #e5e7eb 0deg);
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
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-tag { display: inline-block; margin-top: 8px; font-size: 10px; color: #0ea5e9; font-weight: 600; text-decoration: underline; }
    </style>
    <div class="ja-kw-card">
      <div class="ja-kw-circle" id="ja-kw-circle"><div class="ja-kw-circle-inner" id="ja-kw-percent">0%</div></div>
      <div class="ja-kw-title">Resume Match</div>
      <div class="ja-kw-desc" id="ja-kw-desc">Loading...</div>
      <span class="ja-kw-tag">HireMate</span>
    </div>
  `;
  document.documentElement.appendChild(root);

  (async () => {
    try {
      const jobDesc = extractJobDescription();
      const context = await getAutofillContextFromApi();
      const resumeText = context.resumeText || "";

      const circleEl = root.querySelector("#ja-kw-circle");
      const percentEl = root.querySelector("#ja-kw-percent");
      const descEl = root.querySelector("#ja-kw-desc");

      if (!jobDesc || jobDesc.length < 50) {
        descEl.textContent = "No job description found";
        return;
      }
      if (!resumeText) {
        descEl.textContent = "Add resume in profile";
        return;
      }

      const { matched, total, percent } = computeKeywordMatch(jobDesc, resumeText);
      percentEl.textContent = `${percent}%`;
      descEl.textContent = `${matched.length} of ${total} keywords are present in your resume.`;
      circleEl.style.background = `conic-gradient(#0ea5e9 ${percent * 3.6}deg, #e5e7eb ${percent * 3.6}deg)`;
    } catch (_) {
      root.querySelector("#ja-kw-desc").textContent = "Unable to analyze";
    }
  })();

  const card = root.querySelector(".ja-kw-card");
  card?.addEventListener("click", () => {
    mountInPageUI();
    const widget = document.getElementById(INPAGE_ROOT_ID);
    if (widget) {
      const cardEl = widget.querySelector(".ja-card");
      if (cardEl) cardEl.classList.remove("collapsed");
      const keywordsTab = widget.querySelector('[data-tab="keywords"]');
      if (keywordsTab) keywordsTab.click();
    }
  });
}

async function getApiBase() {
  try {
    const data = await chrome.storage.local.get(["apiBase"]);
    return data.apiBase || "http://localhost:8001/api";
  } catch (_) {
    return "http://localhost:8001/api";
  }
}

async function loadProfileIntoPanel(root) {
  const personalEl = root?.querySelector("#ja-profile-personal .ja-value");
  const educationEl = root?.querySelector("#ja-profile-education .ja-value");
  const experienceEl = root?.querySelector("#ja-profile-experience .ja-value");
  const skillsEl = root?.querySelector("#ja-profile-skills .ja-value");
  const setText = (el, text) => {
    if (el) el.textContent = text || "—";
  };
  try {
    const ctx = await getAutofillContextFromApi();
    const p = ctx.profile || {};
    setText(personalEl, [p.firstName, p.lastName, p.email, p.phone, p.city, p.country].filter(Boolean).join(" • ") || "Add your profile in settings");
    setText(educationEl, p.education || "No education provided.");
    setText(experienceEl, (p.experience || p.professionalSummary || "No experience provided.").slice(0, 500) + (p.experience && p.experience.length > 500 ? "…" : ""));
    setText(skillsEl, p.skills || "No skills provided.");
  } catch (_) {
    setText(personalEl, "Sign in to load profile");
    setText(educationEl, "—");
    setText(experienceEl, "—");
    setText(skillsEl, "—");
  }
}

async function getAutofillContextFromApi() {
  const apiBase = await getApiBase();
  const data = await chrome.storage.local.get(["accessToken"]);
  const token = data.accessToken || null;
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${apiBase}/chrome-extension/autofill/data`, { headers });
  if (!res.ok) {
    throw new Error(`Profile load failed (${res.status})`);
  }
  const json = await res.json();
  return {
    profile: json.profile || {},
    customAnswers: json.custom_answers || {},
    resumeText: json.resume_text || "",
    resumeFileName: json.resume_file_name || null,
  };
}

async function getStaticResume() {
  return null;
}

async function fetchMappingsFromApi(fields, context) {
  const apiBase = await getApiBase();
  const data = await chrome.storage.local.get(["accessToken"]);
  const token = data.accessToken || null;
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const mapRes = await fetch(`${apiBase}/chrome-extension/form-fields/map`, {
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
  const data = await chrome.storage.local.get(["accessToken", "loginPageUrl"]);
  const hasToken = !!data.accessToken;
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
        overflow: hidden;
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
        padding: 14px;
        overflow-y: auto;
        flex: 1;
      }
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
      #${INPAGE_ROOT_ID} .ja-progress {
        width: 100%;
        height: 4px;
        background: rgba(255,255,255,0.3);
        border-radius: 2px;
        margin-bottom: 10px;
        overflow: hidden;
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
      #${INPAGE_ROOT_ID} .ja-profile-cards {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin-bottom: 12px;
      }
      #${INPAGE_ROOT_ID} .ja-profile-card {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 12px;
        cursor: pointer;
      }
      #${INPAGE_ROOT_ID} .ja-profile-card:hover { background: #f3f4f6; }
      #${INPAGE_ROOT_ID} .ja-profile-card h4 { margin: 0 0 4px 0; font-size: 13px; color: #111; }
      #${INPAGE_ROOT_ID} .ja-profile-card p { margin: 0; font-size: 11px; color: #6b7280; }
      #${INPAGE_ROOT_ID} .ja-copy-tip {
        background: #e0f2fe;
        color: #0369a1;
        padding: 10px 12px;
        border-radius: 8px;
        font-size: 12px;
        margin-bottom: 12px;
      }
      #${INPAGE_ROOT_ID} .ja-profile-section {
        padding: 10px 0;
        border-bottom: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-profile-section:last-child { border-bottom: none; }
      #${INPAGE_ROOT_ID} .ja-profile-section h4 { margin: 0 0 6px 0; font-size: 12px; font-weight: 600; color: #374151; }
      #${INPAGE_ROOT_ID} .ja-profile-section .ja-value { font-size: 13px; color: #111; }
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
              <p class="ja-status" id="ja-status">Ready to autofill</p>
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
          </div>
        </div>
        <div class="ja-panel" id="ja-panel-keywords">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta-keywords" style="display:none">
            <h3>Sign in to view keywords</h3>
            <p>Information is pulled from your HireMate profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-keywords-authenticated" id="ja-keywords-authenticated">
          <div class="ja-keywords-section">
            <label>Resume</label>
            <div class="ja-resume-row">
              <span>Default resume</span>
              <button type="button" title="Change">›</button>
              <button type="button" title="Preview">Preview</button>
            </div>
            <p style="font-size:11px;color:#9ca3af;margin:0 0 8px 0;">Bold % indicates keyword coverage.</p>
            <button type="button" class="ja-tailor-btn">Tailor Resume</button>
          </div>
          <div class="ja-keyword-card">
            <h4>Keyword Match – Needs Work</h4>
            <p class="ja-score-text">Your resume has <strong>9 out of 24 (38%)</strong> keywords that appear in the job description.</p>
            <p style="font-size:11px;background:#fef9c3;padding:6px 8px;border-radius:6px;margin:0 0 12px 0;">Try to get your score above <strong>70%</strong> to increase your chances!</p>
            <div class="ja-kw-priority-section">
              <div class="ja-kw-priority-header">
                <span class="ja-kw-priority-title">High Priority Keywords ?</span>
                <span class="ja-kw-priority-count">8/20</span>
              </div>
              <div class="ja-kw-grid">
                <div class="ja-kw-item"><span class="ja-kw-check ja-matched">✓</span><span class="ja-kw-matched">Angular</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-matched">✓</span><span class="ja-kw-matched">MongoDB</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-matched">✓</span><span class="ja-kw-matched">JSON</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-matched">✓</span><span class="ja-kw-matched">JavaScript</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-matched">✓</span><span class="ja-kw-matched">Bootstrap</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-matched">✓</span><span class="ja-kw-matched">ReactJS</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-matched">✓</span><span class="ja-kw-matched">Python</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-matched">✓</span><span class="ja-kw-matched">XML</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">Apigee</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">Cassandra</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">HBase</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">NoSQL</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">C#</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">HTML</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">Spring</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">DOM</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">jQuery</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">ZeroMQ</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">Java</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">Ruby</span></div>
              </div>
            </div>
            <div class="ja-kw-priority-section">
              <div class="ja-kw-priority-header">
                <span class="ja-kw-priority-title">Low Priority Keywords ?</span>
                <span class="ja-kw-priority-count">1/4</span>
              </div>
              <div class="ja-kw-grid">
                <div class="ja-kw-item"><span class="ja-kw-check ja-matched">✓</span><span class="ja-kw-matched">API</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">user interface</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">machine learning</span></div>
                <div class="ja-kw-item"><span class="ja-kw-check ja-unmatched">✓</span><span class="ja-kw-unmatched">customer engagement</span></div>
              </div>
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
          <div class="ja-copy-tip">Click any block of text below to copy it! Profile data loaded from your account.</div>
          <div class="ja-profile-section" id="ja-profile-personal">
            <h4>Personal Information</h4>
            <p class="ja-value">Loading...</p>
          </div>
          <div class="ja-profile-section" id="ja-profile-education">
            <h4>Education</h4>
            <p class="ja-value">Loading...</p>
          </div>
          <div class="ja-profile-section" id="ja-profile-experience">
            <h4>Experience</h4>
            <p class="ja-value">Loading...</p>
          </div>
          <div class="ja-profile-section" id="ja-profile-skills">
            <h4>Skills</h4>
            <p class="ja-value">Loading...</p>
          </div>
          </div>
        </div>
      </div>
    </div>
    <button class="ja-mini" id="ja-open">S</button>
  `;
  document.documentElement.appendChild(root);

  updateWidgetAuthUI(root);

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes.accessToken) {
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
    });
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
    const [context, resumeData] = await Promise.all([
      getAutofillContextFromApi(),
      getResumeFromBackground().then((r) => r || getStaticResume()),
    ]);

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

        setProgress(100);
        const bullets = [];
        if (totalFilled > 0) bullets.push(`✓ Filled ${totalFilled} field${totalFilled === 1 ? "" : "s"}`);
        if (totalResumes > 0) bullets.push(`✓ Uploaded resume`);
        if (totalFailed > 0) bullets.push(`⚠ ${totalFailed} field${totalFailed === 1 ? "" : "s"} need attention`);
        const statusHtml = bullets.length > 0 ? `<ul>${bullets.map((b) => `<li>${b}</li>`).join("")}</ul>` : "Done";
        setStatus(statusHtml, "success", true);

        if (!autoAdvance || !isWorkday || step >= maxSteps) break;

        const hasUnfilledFields = result.failedCount > 0;

        if (hasUnfilledFields) {
          bullets.push('<span class="ja-note">Fix the highlighted fields, then click Continue filling</span>');
          setStatus(`<ul>${bullets.map((b) => `<li>${b}</li>`).join("")}</ul>`, "success", true);
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

// Sync token from website when user logs in on HireMate frontend
function syncTokenFromWebsite() {
  if (!LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o)) return;
  const script = document.createElement("script");
  script.textContent = `
    (function() {
      try {
        const token = localStorage.getItem('token');
        if (token) {
          window.postMessage({ type: 'HIREMATE_TOKEN_SYNC', token: token }, '*');
        }
      } catch (e) {}
    })();
  `;
  (document.head || document.documentElement).appendChild(script);
  script.remove();
}
window.addEventListener("message", (e) => {
  if (e.source !== window || e.data?.type !== "HIREMATE_TOKEN_SYNC" || !e.data?.token) return;
  chrome.storage.local.set({ accessToken: e.data.token });
  logInfo("Token synced from website");
});
if (LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o)) {
  syncTokenFromWebsite();
  setTimeout(syncTokenFromWebsite, 2000);
  setTimeout(syncTokenFromWebsite, 5000);
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  logInfo("Received message", { type: msg?.type || "unknown" });
  
  if (msg.type === "SHOW_WIDGET") {
    mountInPageUI();
    if (isCareerPage()) mountKeywordMatchWidget();
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
  if (!isCareerPage()) return false;
  const hasApplicationForm = looksLikeJobApplicationForm();
  const jobDesc = extractJobDescription();
  const hasJobDesc = !!(jobDesc && jobDesc.length >= 100);
  return hasApplicationForm || hasJobDesc;
}

function tryAutoOpenPopup() {
  if (!isJobFormPage()) return;
  mountInPageUI();
  const widget = document.getElementById(INPAGE_ROOT_ID);
  if (widget) {
    const card = widget.querySelector(".ja-card");
    if (card) card.classList.remove("collapsed");
  }
  mountKeywordMatchWidget();
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
