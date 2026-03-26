// ─── DOM Utilities — Field Detection & Filling ────────────────────────────
// Depends on: FIELD_SELECTOR, IGNORE_INPUT_TYPES, INPAGE_ROOT_ID,
//             AUTOFILL_FAILED_CLASS, SCROLL_DURATION_MS, SCROLL_WAIT_AFTER_MS (consts.js)
//             logInfo, logWarn, normalizeKey, formatDateForInput, getMimeTypeForResume,
//             delay (utils.js)

// ─── Visibility ────────────────────────────────────────────────────────────

function isVisible(el) {
  if (!el || !el.ownerDocument || !el.isConnected) return false;
  if (el.getAttribute("aria-hidden") === "true" || el.hidden) return false;
  const style = el.ownerDocument.defaultView?.getComputedStyle(el);
  if (!style) return false;
  if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
  if (el.getClientRects().length === 0) return false;
  return true;
}

// ─── Document / Shadow DOM Traversal ──────────────────────────────────────

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
    } catch (_) { }
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

// ─── Field Fillability ─────────────────────────────────────────────────────

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

// ─── Label Detection ───────────────────────────────────────────────────────

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

// ─── Extension Widget Guard ────────────────────────────────────────────────

function isInsideExtensionWidget(el) {
  if (!el?.ownerDocument) return false;
  const doc = el.ownerDocument;
  if (doc !== document) return false;
  const widget = document.getElementById(INPAGE_ROOT_ID);
  return !!(widget && widget.contains(el));
}

// ─── Get Fillable Fields ───────────────────────────────────────────────────

function getFillableFields(includeNestedDocuments = true, includeHidden = false) {
  const scraper = typeof window !== "undefined" && window.__HIREMATE_FIELD_SCRAPER__;
  if (scraper) {
    try {
      const result = scraper.getScrapedFields({
        scope: includeNestedDocuments ? "all" : "current_document",
        includeHidden,
        excludePredicate: isInsideExtensionWidget,
      });
      const elements = result.elements || (result.fields || []).map((f) => f.element).filter(Boolean);
      if (elements.length > 0) return elements;
    } catch (e) {
      logWarn("Enhanced field scraper failed, falling back", { error: String(e) });
    }
  }
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
      } catch (_) { }
    }
  }
  if (totalCandidates > 0 && out.length === 0) {
    logWarn("Found form candidates but all filtered out", { totalCandidates, includeHidden, docCount: docs.length });
  }
  return out;
}

// ─── Framework Event Dispatch ──────────────────────────────────────────────

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

// ─── Native Value Setter ───────────────────────────────────────────────────

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
      logWarn("Select dropdown has no valid options", { field: field.name || field.id || field.placeholder });
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
        availableOptions: options.map(opt => ({ text: opt.text, value: opt.value })).slice(0, 10),
      });
      return false;
    }

    // Step 1: Focus and simulate opening the dropdown
    focusWithoutScroll(field);
    field.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
    field.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
    field.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));

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
    try {
      const tracker = field._valueTracker;
      if (tracker) {
        tracker.setValue(field.value === match.value ? "" : field.value);
      }
    } catch (_) { }

    // Step 4: Simulate clicking the matching <option> element
    try {
      match.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
      match.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
      match.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
    } catch (_) { }

    // Step 5: Fire change + blur so all framework listeners fire
    field.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    field.dispatchEvent(new Event("blur", { bubbles: true }));

    logInfo("Select dropdown filled", { field: field.name || field.id, matchedOption: { text: match.text, value: match.value } });
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
      try { if (field._valueTracker) field._valueTracker.setValue(""); } catch (_) { }
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
    try { if (field._valueTracker) field._valueTracker.setValue(""); } catch (_) { }
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
    try { if (field._valueTracker) field._valueTracker.setValue(""); } catch (_) { }
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

// ─── Field Display Value ───────────────────────────────────────────────────

/** Get displayed value for any field type — used to detect if dropdown/combobox is filled */
function getFieldDisplayValue(field) {
  const tag = (field.tagName || "").toLowerCase();
  if (tag === "select") return (field.value || "").toString().trim();
  if (tag === "input" || tag === "textarea") return (field.value || "").toString().trim();
  if (tag === "div" || tag === "span") {
    const input = field.querySelector?.('input[type="text"],input[type="search"],input:not([type])');
    if (input) return (input.value || "").toString().trim();
    const singleValue = field.querySelector?.('[class*="singleValue"],[class*="single-value"],[data-value]');
    if (singleValue) return (singleValue.textContent || singleValue.getAttribute("data-value") || "").toString().trim();
    const text = (field.textContent || "").trim();
    if (text && !/select\.\.\.|choose|search/i.test(text) && text.length < 200) return text;
  }
  return (field.value ?? field.textContent ?? "").toString().trim();
}

// ─── Dropdown Interaction ──────────────────────────────────────────────────

function openDropdownForSelection(field) {
  try {
    if (field.disabled || field.getAttribute("aria-disabled") === "true") return;
    const tag = (field.tagName || "").toLowerCase();
    const role = (field.getAttribute("role") || "").toLowerCase();
    const isCombobox = role === "combobox" || field.closest?.("[class*='select']");
    if (tag === "select" || role === "combobox" || isCombobox) {
      field.focus();
      const rect = field.getBoundingClientRect();
      const opts = {
        bubbles: true,
        cancelable: true,
        view: field.ownerDocument?.defaultView || window,
        clientX: rect.left + rect.width / 2,
        clientY: rect.top + rect.height / 2,
      };
      field.dispatchEvent(new MouseEvent("mousedown", opts));
      field.dispatchEvent(new MouseEvent("mouseup", opts));
      field.dispatchEvent(new MouseEvent("click", opts));
    }
  } catch (_) { }
}

// ─── Scroll ────────────────────────────────────────────────────────────────

async function scrollFieldIntoView(field) {
  const rect = field.getBoundingClientRect();
  const vh = window.innerHeight;
  if (rect.top >= 0 && rect.bottom <= vh) return;
  try {
    field.scrollIntoView({ behavior: "auto", block: "center", inline: "nearest" });
  } catch (_) {
    field.scrollIntoView({ block: "center" });
  }
  await delay(SCROLL_DURATION_MS + SCROLL_WAIT_AFTER_MS);
}

// ─── Continue Button ───────────────────────────────────────────────────────

function findContinueButton(doc = document) {
  // Workday-first: data-automation-id is most reliable
  const workdaySelectors = [
    '[data-automation-id="continueButton"]',
    '[data-automation-id="continue"]',
    '[data-automation-id="nextButton"]',
    '[data-automation-id*="continue"]',
    '[data-automation-id*="next"]',
    '[data-automation-id="submitButton"]',
  ];
  for (const sel of workdaySelectors) {
    try {
      const el = doc.querySelector(sel);
      if (el && el.getBoundingClientRect?.().width > 0) return el;
    } catch (_) { }
  }
  const sel = 'button, [role="button"], input[type="submit"]';
  for (const el of doc.querySelectorAll(sel)) {
    const text = (el.textContent || el.innerText || el.value || "").trim().toLowerCase();
    if (text.includes("continue") || text === "next" || text === "submit") return el;
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

// ─── File Input ────────────────────────────────────────────────────────────

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

// ─── Failed Field Highlighting ─────────────────────────────────────────────

function ensureFailHighlightStyle(doc = document) {
  const id = "ja-autofill-fail-style";
  if (doc.getElementById(id)) return;
  const style = doc.createElement("style");
  style.id = id;
  style.textContent = `.${AUTOFILL_FAILED_CLASS} { outline: 2px solid #dc2626 !important; box-shadow: 0 0 0 2px #dc2626 !important; }`;
  (doc.head || doc.documentElement).appendChild(style);
}

function highlightFailedField(field) {
  const doc = field.ownerDocument || document;
  ensureFailHighlightStyle(doc);
  field.classList.add(AUTOFILL_FAILED_CLASS);
  openDropdownForSelection(field);
}

function highlightUnfilledRequiredFields(includeNestedDocuments = true) {
  const fillable = getFillableFields(includeNestedDocuments, true);
  if (fillable.length === 0) return;
  let highlighted = 0;
  for (const field of fillable) {
    const meta = getFieldMeta(field);
    if (!meta.required) continue;
    const displayVal = getFieldDisplayValue(field);
    const isEmpty = !displayVal || displayVal === "" || /^select\.\.\.|^choose\s|^search\s/i.test(displayVal);
    if (isEmpty && field.isConnected && !field.disabled) {
      highlightFailedField(field);
      highlighted++;
    }
  }
  if (highlighted > 0) logInfo("Highlighted unfilled required fields", { count: highlighted });
}
