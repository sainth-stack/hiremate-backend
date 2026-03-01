/**
 * OpsBrain Field Scraper v3 — Intelligent 100% field detection
 *
 * CORE ARCHITECTURE CHANGES:
 * 1. TWO-PHASE: collect raw candidates → resolve canonical interactive element
 *    Fixes wrapper/inner double-detection for React-Select, MUI, Ant Design, Workday
 * 2. MULTI-SELECTOR BUNDLE: 5+ fallback selectors per field (id, automation-id, testid, form+name, dom-path)
 * 3. FIELD FINGERPRINT: label+type+atsType hash survives SPA re-renders for fill-time rematch
 * 4. CANONICAL RESOLVER: resolves any matched element (wrapper or native) to true interactive target
 * 5. PROPER SHADOW DOM: uses shadowRoot's OWN TreeWalker, not document's
 * 6. SMART DEDUP: by canonical element reference (not selector string)
 * 7. CONTEXT-AWARE LABEL: checks wrapper AND canonical inner element for label associations
 * 8. PLATFORM BOOSTS: Workday/Greenhouse/Lever get extra targeted queries
 * 9. AUXILIARY FILTER: skips dropdown options, phone country pickers, extension UI, search boxes
 * 10. SERIALIZE/RESOLVE API: strip element refs for message passing; resolve back at fill time
 */
(function () {
  "use strict";

  const LOG = "[OpsBrain][scraper]";
  const log = (lvl, msg, meta) => {
    const fn = lvl === "warn" ? console.warn : lvl === "error" ? console.error : console.info;
    meta !== undefined ? fn(LOG, msg, meta) : fn(LOG, msg);
  };

  // ─── CONSTANTS ────────────────────────────────────────────────
  const IGNORE_INPUT_TYPES = new Set(["submit","button","image","reset","range","color"]);
  const STANDARD_ATS = new Set(["first_name","last_name","email","phone","resume","cover_letter","linkedin"]);

  // ─── PLATFORM DETECTION ───────────────────────────────────────
  let _plat = null;
  function detectPlatform(doc) {
    if (_plat) return _plat;
    const url = (doc.defaultView?.location?.href || "").toLowerCase();
    const snip = (doc.documentElement?.innerHTML || "").slice(0, 10000).toLowerCase();
    const is = (u, h) => url.includes(u) || snip.includes(h || u);
    if (is("greenhouse.io") || is("boards.greenhouse") || snip.includes('"greenhouse"')) _plat = "greenhouse";
    else if (is("workday.com") || is("myworkdayjobs") || snip.includes("wd3.myworkday")) _plat = "workday";
    else if (is("lever.co") || snip.includes("lever-job-listing")) _plat = "lever";
    else if (is("smartrecruiters.com") || snip.includes("smartrecruiters")) _plat = "smartrecruiters";
    else if (is("ashbyhq.com") || snip.includes("ashby")) _plat = "ashby";
    else if (is("taleo.net") || snip.includes("taleo")) _plat = "taleo";
    else if (is("jobvite.com") || snip.includes("jobvite")) _plat = "jobvite";
    else if (is("icims.com") || snip.includes("icims")) _plat = "icims";
    else if (is("successfactors") || snip.includes("sap-successfactors")) _plat = "successfactors";
    else _plat = "generic";
    return _plat;
  }

  // ─── SELECTOR GROUPS ──────────────────────────────────────────
  const SEL = {
    text: [
      'input[type="text"]','input[type="email"]','input[type="tel"]','input[type="url"]',
      'input[type="search"]','input[type="number"]','input[type="password"]','input:not([type])',
      'textarea','input[formcontrolname]','input[ng-model]','input[v-model]',
      'mat-input-element','input[matInput]',
    ].join(","),
    richText: [
      '[contenteditable="true"]:not([class*="ql-toolbar"])',
      '[contenteditable=""]',
      '.ql-editor','.DraftEditor-root [contenteditable]','.ProseMirror',
      '.ck-editor__editable[contenteditable]','.jodit-wysiwyg',
    ].join(","),
    selectWrappers: [
      '[class*="react-select__control"]','[class*="Select__control"]',
      '.ant-select:not(.ant-select-disabled)','.MuiSelect-root','.MuiAutocomplete-root',
      '.select2-container','.chosen-container',
    ].join(","),
    ariaSelect: [
      '[role="combobox"]:not([aria-disabled="true"])',
      '[aria-haspopup="listbox"]:not([aria-disabled="true"])',
    ].join(","),
    nativeSelect: 'select',
    date: [
      'input[type="date"]','input[type="datetime-local"]','input[type="month"]','input[type="time"]',
      '.react-datepicker__input-container > input','.react-datepicker-wrapper input',
      '.MuiDatePicker-root input','.ant-picker-input > input','.flatpickr-input:not([readonly])',
      '[placeholder*="MM/DD/YYYY" i]','[placeholder*="DD/MM/YYYY" i]',
      '[data-automation-id*="dateSectionDay"]','[data-automation-id*="dateSectionMonth"]',
      '[data-automation-id*="dateSectionYear"]',
    ].join(","),
    file: [
      'input[type="file"]','.filepond--root input[type="file"]',
      '[data-automation-id*="file"]','[data-automation-id*="attachment"]','[data-automation-id*="resume"]',
      '[data-automation-id="file-upload-input"]','.attachment-input','[data-field="resume"]',
    ].join(","),
    checkboxRadio: [
      'input[type="checkbox"]','input[type="radio"]',
      '[role="checkbox"]:not([aria-disabled="true"])',
      '[role="radio"]:not([aria-disabled="true"])',
      '[role="switch"]:not([aria-disabled="true"])',
    ].join(","),
    workday: [
      '[data-automation-id*="textInput"]','[data-automation-id*="textArea"]',
      '[data-automation-id*="dropdown"]','[data-automation-id*="selectWidget"]',
      '[data-automation-id*="formSelect"]','[data-automation-id*="checkbox"]',
      '[data-automation-id*="radioButton"]','[data-automation-id*="numericInput"]',
    ].join(","),
  };

  // ─── CANONICAL ELEMENT RESOLVER ───────────────────────────────
  // Given any matched element (wrapper or native), return the TRUE fillable element.
  function resolveCanonical(el) {
    if (!el) return null;
    const tag = el.tagName.toLowerCase();
    const type = (el.type || "").toLowerCase();
    // Already native interactive
    if ((tag === "input" && !IGNORE_INPUT_TYPES.has(type)) || tag === "select" || tag === "textarea") return el;
    // Rich text editor surfaces
    if (el.isContentEditable) return el;
    const cls = String(el.className || "");
    if (/ql-editor|ProseMirror|DraftEditor-content|ck-content|jodit-wysiwyg/i.test(cls)) return el;
    // Wrapper: find best child
    const inner = el.querySelector(
      'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([disabled]),' +
      'select:not([disabled]),textarea:not([disabled])'
    );
    if (inner) return inner;
    const innerEdit = el.querySelector('[contenteditable="true"],.ql-editor,.ProseMirror');
    if (innerEdit) return innerEdit;
    // ARIA-only element (Workday, Headless UI)
    const role = (el.getAttribute("role") || "").toLowerCase();
    if (["combobox","listbox","checkbox","radio","switch","textbox"].includes(role)) return el;
    return el;
  }

  // ─── VISIBILITY ───────────────────────────────────────────────
  function isVisible(el, doc) {
    if (!el?.isConnected) return false;
    if ((el.type || "") === "hidden") return false;
    const win = (doc || document).defaultView || window;
    let cur = el;
    while (cur && cur.nodeType === 1) {
      try {
        const s = win.getComputedStyle(cur);
        if (s.display === "none" || s.visibility === "hidden") return false;
        if (cur.getAttribute?.("aria-hidden") === "true") return false;
        if (cur === (doc || document).documentElement) break;
      } catch (_) { break; }
      cur = cur.parentElement;
    }
    try {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) {
        const pos = win.getComputedStyle(el).position;
        if (!["absolute","fixed","sticky"].includes(pos)) return false;
      }
    } catch (_) {}
    return true;
  }

  // ─── LABEL DETECTION ──────────────────────────────────────────
  function cleanLabel(t) {
    return String(t||"").replace(/\u00a0/g," ").trim().replace(/\s+/g," ")
      .replace(/[*:]+$/,"").replace(/\(required\)/gi,"").replace(/\brequired\b/gi,"")
      .replace(/\(optional\)/gi,"").trim();
  }
  function humanize(n) {
    return String(n||"").replace(/[-_.[\]]/g," ")
      .replace(/([a-z])([A-Z])/g,"$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g,"$1 $2")
      .replace(/\b\w/g,c=>c.toUpperCase()).trim();
  }

  function getSmartLabel(canonical, wrapper, doc) {
    const targets = wrapper && wrapper !== canonical ? [canonical, wrapper] : [canonical];

    // 1. aria-labelledby (highest authority)
    for (const t of targets) {
      const ids = (t.getAttribute("aria-labelledby")||"").split(/\s+/).filter(Boolean);
      for (const id of ids) {
        try { const le = doc.getElementById(id); if (le?.textContent?.trim()) return cleanLabel(le.textContent); } catch(_) {}
      }
    }
    // 2. explicit label[for]
    for (const t of targets) {
      if (!t.id) continue;
      try { const lbl = doc.querySelector(`label[for="${CSS.escape(t.id)}"]`); if (lbl?.textContent?.trim()) return cleanLabel(lbl.textContent); } catch(_) {}
    }
    // 3. aria-label
    for (const t of targets) {
      const al = t.getAttribute("aria-label"); if (al?.trim()) return cleanLabel(al);
    }
    // 4. wrapping <label>
    const wl = canonical.closest("label");
    if (wl) {
      const clone = wl.cloneNode(true);
      clone.querySelectorAll("input,select,textarea,button,svg").forEach(n=>n.remove());
      const t = clone.textContent?.trim(); if (t) return cleanLabel(t);
    }
    // 5. Workday automation-id → sibling label
    for (const t of targets) {
      const aid = t.getAttribute("data-automation-id"); if (!aid) continue;
      const parent = t.closest("[data-automation-id]")?.parentElement || t.parentElement;
      if (parent) {
        const lbl = parent.querySelector("label,[data-automation-id*='label'],[class*='label']");
        if (lbl?.textContent?.trim()) return cleanLabel(lbl.textContent);
      }
      return humanize(aid.replace(/^(input|select|textbox|widget|form|field)[-_]?/,""));
    }
    // 6. Question wrapper (Greenhouse/Lever/Ashby)
    const qw = canonical.closest(
      ".application-question,.form-group,.question,.field-wrapper," +
      "[class*='field-group'],[class*='fieldGroup'],[class*='form-field']," +
      "[class*='application-field'],[class*='custom-question']"
    );
    if (qw) {
      const ql = qw.querySelector(".question-text,.application-label,.field-label,label,.label,legend,[class*='label'],[class*='Label']");
      if (ql?.textContent?.trim()) return cleanLabel(ql.textContent);
    }
    // 7. placeholder
    for (const t of targets) {
      const ph = t.getAttribute("placeholder"); if (ph && ph.length > 1) return cleanLabel(ph);
    }
    // 8. name / formcontrolname
    for (const t of targets) {
      const n = t.getAttribute("name")||t.getAttribute("formcontrolname")||t.getAttribute("v-model")||t.getAttribute("ng-model");
      if (n) return humanize(n);
    }
    // 9. data-* label attrs
    for (const t of targets) {
      const dl = t.getAttribute("data-label")||t.getAttribute("data-field-name")||t.getAttribute("data-field")||t.getAttribute("data-testid");
      if (dl) return cleanLabel(dl);
    }
    // 10. preceding sibling text
    const par = canonical.parentElement;
    if (par) {
      let text = "";
      for (const c of par.childNodes) {
        if (c === canonical || c === wrapper) break;
        if (c.nodeType === 3) text += c.textContent;
        else if (c.nodeType === 1 && !["INPUT","SELECT","TEXTAREA","BUTTON","SCRIPT","STYLE","SVG"].includes(c.tagName)) text += c.textContent||"";
      }
      const t = text.trim(); if (t && t.length < 120) return cleanLabel(t);
    }
    // 11. fieldset legend
    const leg = canonical.closest("fieldset")?.querySelector("legend");
    if (leg?.textContent?.trim()) return cleanLabel(leg.textContent);
    // 12. section heading
    const sec = canonical.closest('section,[role="group"],fieldset,.form-section,[class*="section"]');
    const hd = sec?.querySelector("h1,h2,h3,h4,h5,h6");
    if (hd?.textContent?.trim()) return cleanLabel(hd.textContent);
    // 13. title
    for (const t of targets) {
      const ti = t.getAttribute("title"); if (ti?.trim()) return cleanLabel(ti);
    }
    // 14. id humanized
    for (const t of targets) {
      if (t.id && t.id.length > 1 && t.id.length < 60) return humanize(t.id);
    }
    return "Unnamed Field";
  }

  // ─── FIELD TYPE ───────────────────────────────────────────────
  function normalizeType(canonical, wrapper) {
    const tag = canonical.tagName.toLowerCase();
    const type = (canonical.type||"").toLowerCase();
    const role = (canonical.getAttribute("role")||"").toLowerCase();
    const cls = String(canonical.className||"")+String(wrapper?.className||"");
    const aid = (canonical.getAttribute("data-automation-id")||wrapper?.getAttribute("data-automation-id")||"").toLowerCase();
    if (canonical.isContentEditable || /ql-editor|ProseMirror|DraftEditor-content|ck-content|jodit/i.test(cls)) return "richtext";
    if (type === "file" || /file|attachment|resume/i.test(aid)) return "file";
    if (/dateSection/i.test(aid)) return "date";
    if (["date","datetime-local","month","time","week"].includes(type)) return "date";
    if (/date/i.test(aid) || /datepicker|date-picker|date-input/i.test(cls)) return "date";
    if (type === "checkbox" || role === "checkbox" || role === "switch") return "checkbox";
    if (type === "radio" || role === "radio") return "radio";
    if (tag === "select") return canonical.multiple ? "multiselect" : "select";
    if (role === "combobox" || role === "listbox" ||
      canonical.getAttribute("aria-haspopup") === "listbox" ||
      /react-select|Select__|ant-select|MuiSelect/i.test(cls) ||
      /dropdown|select/i.test(aid)) return "select";
    if (tag === "textarea") return "textarea";
    if (tag === "input") {
      if (!type || ["text","email","tel","url","search"].includes(type)) return "text";
      if (type === "number") return "number";
    }
    return type || "text";
  }

  // ─── ATS FIELD TYPE ───────────────────────────────────────────
  function detectATSType(canonical, wrapper, label) {
    const parts = [
      canonical.name||"", canonical.id||"", label||"",
      canonical.getAttribute("placeholder")||"",
      canonical.getAttribute("data-automation-id")||"",
      canonical.getAttribute("aria-label")||"",
      canonical.getAttribute("data-field")||"",
      canonical.getAttribute("autocomplete")||"",
      wrapper?.getAttribute("data-automation-id")||"", wrapper?.id||"",
    ].join(" ").toLowerCase().replace(/[\[\]()]/g," ");
    const m = r => r.test(parts);
    if (m(/resume|curriculum.vitae|\bcv\b/) && !m(/iti-\d+__item/)) return "resume";
    if (m(/cover.?letter|motivation.?letter/)) return "cover_letter";
    if (m(/first.?name|fname|forename|given.?name|firstname/)) return "first_name";
    if (m(/last.?name|surname|lname|family.?name|lastname/)) return "last_name";
    if (m(/full.?name|your.?name|applicant.?name/)) return "full_name";
    if (m(/\bemail\b|e.mail|emailaddress/)) return "email";
    if (m(/phone|mobile|telephone|\bcell\b/)) return "phone";
    if (m(/\blinkedin\b/)) return "linkedin";
    if (m(/portfolio|personal.?web|github|gitlab/)) return "portfolio";
    if (m(/\bcity\b|\btown\b|\blocality\b/)) return "city";
    if (m(/\bstate\b|\bprovince\b|\bregion\b/)) return "state";
    if (m(/\bcountry\b|\bnation\b/)) return "country";
    if (m(/zip|postal|postcode/)) return "postal_code";
    if (m(/\bstreet\b|\baddress\b/)) return "address";
    if (m(/university|college|school|institution/)) return "school";
    if (m(/\bdegree\b|qualification/)) return "degree";
    if (m(/\bmajor\b|field.?of.?study/)) return "major";
    if (m(/graduation|grad.?year/)) return "graduation_year";
    if (m(/notice.?period|availability/)) return "notice_period";
    if (m(/\bcompany\b|\bemployer\b|\borganization\b/)) return "company";
    if (m(/job.?title|position|designation/)) return "job_title";
    if (m(/start.?date/)) return "start_date";
    if (m(/end.?date/)) return "end_date";
    if (m(/salary|compensation|\bpay\b|\bctc\b/)) return "salary";
    if (m(/authorization|visa|work.?permit|eligible.?to.?work/)) return "work_authorization";
    if (m(/\bsponsor/)) return "sponsorship";
    if (m(/\bgender\b/)) return "gender";
    if (m(/\bveteran\b/)) return "veteran_status";
    if (m(/\bdisability\b/)) return "disability_status";
    if (m(/\brace\b|\bethnicity\b/)) return "ethnicity";
    if (m(/referr|how.?did.?you.?hear/)) return "referral_source";
    if (m(/years?.of.exp|experience/)) return "years_experience";
    if (m(/\bskill/)) return "skills";
    if (m(/\blanguage/)) return "languages";
    if (m(/certif/)) return "certification";
    return "custom";
  }

  // ─── MULTI-SELECTOR BUNDLE ────────────────────────────────────
  function buildSelectorBundle(canonical, wrapper, doc) {
    const bundle = [];
    const try_ = (type, sel, priority) => {
      try { if (doc.querySelectorAll(sel).length === 1) bundle.push({ type, selector: sel, priority }); } catch(_) {}
    };
    if (canonical.id) try_("id", `#${CSS.escape(canonical.id)}`, 10);
    const aid = canonical.getAttribute("data-automation-id") || wrapper?.getAttribute("data-automation-id");
    if (aid) try_("automation-id", `[data-automation-id="${CSS.escape(aid)}"]`, 9);
    const tid = canonical.getAttribute("data-testid") || wrapper?.getAttribute("data-testid");
    if (tid) try_("testid", `[data-testid="${CSS.escape(tid)}"]`, 8);
    const form = canonical.closest("form");
    const name = canonical.getAttribute("name");
    if (form && name) {
      try {
        const tag = canonical.tagName.toLowerCase();
        const ns = `${tag}[name="${CSS.escape(name)}"]`;
        if (form.querySelectorAll(ns).length === 1) {
          const fi = Array.from(doc.querySelectorAll("form")).indexOf(form);
          bundle.push({ type:"form-name", selector: fi>=0 ? `form:nth-of-type(${fi+1}) ${ns}` : `form ${ns}`, priority:7 });
        }
      } catch(_) {}
    }
    const al = canonical.getAttribute("aria-label");
    if (al) try_("aria-label", `${canonical.tagName.toLowerCase()}[aria-label="${CSS.escape(al)}"]`, 6);
    if (wrapper && wrapper !== canonical && wrapper.id) {
      try_("wrapper-id", `#${CSS.escape(wrapper.id)} ${canonical.tagName.toLowerCase()}`, 5);
    }
    const path = buildStablePath(canonical, doc);
    if (path) bundle.push({ type:"dom-path", selector:path, priority:1 });
    bundle.sort((a,b) => b.priority - a.priority);
    return bundle;
  }

  function buildStablePath(el, doc) {
    try {
      const path = []; let cur = el; let depth = 0;
      while (cur && cur !== doc.body && depth < 8) {
        let seg = cur.tagName.toLowerCase();
        if (cur.id) { path.unshift(`#${CSS.escape(cur.id)}`); break; }
        const stableAttrs = ["data-automation-id","data-testid","data-field","name"];
        let anchored = false;
        for (const attr of stableAttrs) {
          const v = cur.getAttribute(attr);
          if (v) {
            const asel = `${seg}[${attr}="${CSS.escape(v)}"]`;
            try { if ((cur.closest("form")||doc).querySelectorAll(asel).length <= 3) { seg = asel; anchored = true; break; } } catch(_) {}
          }
        }
        if (!anchored) {
          const par = cur.parentElement;
          if (par) { const sibs = Array.from(par.children).filter(c=>c.tagName===cur.tagName); if (sibs.length>1) seg+=`:nth-of-type(${sibs.indexOf(cur)+1})`; }
        }
        path.unshift(seg); cur = cur.parentElement; depth++;
      }
      return path.join(" > ");
    } catch(_) { return ""; }
  }

  // ─── FIELD FINGERPRINT ────────────────────────────────────────
  // Legacy: for SPA rematch (atsType|fieldType|label)
  function makeFingerprint(label, atsType, fieldType, formIdx, fieldIdx) {
    return `${atsType}|${fieldType}|${label.slice(0,30).toLowerCase().replace(/\s+/g,"_")}|f${formIdx}|i${fieldIdx}`;
  }

  // Production: SHA-256 fingerprint - MUST match Python's compute_field_fingerprint (alphabetical key order)
  function normalizeLabelForFp(text) {
    return (text || "").toLowerCase().trim()
      .replace(/[^a-z0-9 ]/g, " ")
      .replace(/\s+/g, " ").trim();
  }

  async function computeFieldFingerprint(field) {
    const label = normalizeLabelForFp(field.label || field.placeholder || field.name || "");
    const ftype = (field.type || "").toLowerCase().trim();
    const options = (field.options || []).map(normalizeLabelForFp).sort();
    // CRITICAL: key order alphabetical to match Python sort_keys=True -> {label, options, type}
    const payload = JSON.stringify({ label, options, type: ftype });
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(payload));
    return Array.from(new Uint8Array(buf))
      .map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 32);
  }

  // ─── AUXILIARY FILTER ─────────────────────────────────────────
  function isAuxiliary(el, label, doc) {
    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute("role")||"").toLowerCase();
    const id = el.getAttribute("id")||"";
    const cls = String(el.className||"");
    const ll = (label||"").toLowerCase();
    if (el.closest?.("#ja-keyword-match-root,#job-autofill-inpage-root,#opsbrain-widget")) return true;
    if ((tag==="li"||tag==="option"||tag==="div") && role==="option") return true;
    if (tag==="ul" && role==="listbox") return true;
    if (/^iti-\d+__(search-input|country-listbox|item-)/.test(id)) return true;
    if (el.closest?.(".iti__flag-container,.iti__selected-flag")) return true;
    if (el.getAttribute?.("aria-hidden")==="true") return true;
    if (tag==="input" && el.getAttribute("type")==="search") {
      if (el.closest("header,nav,[role='navigation'],[role='banner']")) return true;
    }
    return false;
  }

  // ─── SHADOW DOM TRAVERSAL ─────────────────────────────────────
  function traverseShadow(root, callback, seen) {
    if (!seen) seen = new WeakSet();
    if (!root || seen.has(root)) return;
    seen.add(root);
    const ownerDoc = root.ownerDocument || (root.nodeType===11 ? null : root);
    if (!ownerDoc) return;
    try {
      const walker = ownerDoc.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
      let node = walker.nextNode();
      while (node) {
        if (!seen.has(node)) {
          seen.add(node);
          if (node.shadowRoot && !seen.has(node.shadowRoot)) {
            callback(node.shadowRoot);
            traverseShadow(node.shadowRoot, callback, seen);
          }
          if (typeof chrome!=="undefined" && chrome.dom?.openOrClosedShadowRoot) {
            try {
              const closed = chrome.dom.openOrClosedShadowRoot(node);
              if (closed && closed !== node.shadowRoot && !seen.has(closed)) { callback(closed); traverseShadow(closed, callback, seen); }
            } catch(_) {}
          }
          if (node.tagName==="SLOT") {
            try { for (const a of node.assignedElements({flatten:true})) { if (!seen.has(a)) callback(a); } } catch(_) {}
          }
        }
        node = walker.nextNode();
      }
    } catch(_) {}
  }

  // ─── OPTIONS EXTRACTION ───────────────────────────────────────
  function extractOptions(canonical, doc) {
    if (canonical.tagName === "SELECT") {
      return Array.from(canonical.options||[]).map(o=>(o.text?.trim()||String(o.value||"")).trim()).filter(Boolean);
    }
    const cid = canonical.getAttribute("aria-controls")||canonical.getAttribute("aria-owns");
    if (cid) {
      try {
        const lb = doc.getElementById(cid);
        if (lb) return Array.from(lb.querySelectorAll('[role="option"]')).map(o=>o.textContent?.trim()||"").filter(Boolean).slice(0,100);
      } catch(_) {}
    }
    return [];
  }

  function extractValidation(el) {
    return {
      pattern: el.pattern||"", minLength: el.minLength>0?el.minLength:null,
      maxLength: el.maxLength>0&&el.maxLength<524288?el.maxLength:null,
      min: el.min||null, max: el.max||null, accept: el.accept||"", multiple: !!el.multiple,
    };
  }
  function getVal(el) {
    const type = (el.type||"").toLowerCase();
    if (type==="checkbox"||type==="radio") return el.checked?"true":"false";
    if (el.tagName==="SELECT") return el.value||"";
    if (el.isContentEditable) return (el.innerText||el.textContent||"").trim();
    return el.value||"";
  }

  // ─── IFRAME DISCOVERY ─────────────────────────────────────────
  function getFrames(doc) {
    const out = [];
    try {
      const iframes = doc.querySelectorAll("iframe,frame");
      for (let i=0; i<iframes.length; i++) {
        try {
          const d = iframes[i].contentDocument || iframes[i].contentWindow?.document;
          if (d && d.readyState!=="uninitialized" && d.body) out.push({ id:i+1, document:d });
        } catch(_) {}
      }
    } catch(_) {}
    return out;
  }

  // ─── SINGLE ROOT SCRAPER ──────────────────────────────────────
  function scrapeRoot(root, doc, frameId, isShadow, seenGlobal, includeHidden, platform) {
    const results = [];
    const seenCanonicals = new WeakSet();
    const rawCandidates = new Set();

    const queryAll = (sel) => { try { root.querySelectorAll(sel).forEach(el=>rawCandidates.add(el)); } catch(_) {} };
    queryAll(SEL.text); queryAll(SEL.richText); queryAll(SEL.selectWrappers); queryAll(SEL.ariaSelect);
    queryAll(SEL.nativeSelect); queryAll(SEL.date); queryAll(SEL.file); queryAll(SEL.checkboxRadio);
    if (platform==="workday") queryAll(SEL.workday);
    if (platform==="greenhouse") { queryAll('[data-provides="select"],[data-provides="typeahead"]'); queryAll('.attachment-input,[data-field="resume"]'); }
    if (platform==="lever") queryAll('.application-field input,.application-field select,.application-field textarea');

    const allForms = Array.from(doc.querySelectorAll("form"));

    for (const el of rawCandidates) {
      try {
        if (seenGlobal.has(el)) continue;
        const tag = el.tagName.toLowerCase();
        const type = (el.type||"").toLowerCase();
        if (tag==="input" && IGNORE_INPUT_TYPES.has(type)) continue;
        if (el.disabled || el.getAttribute("aria-disabled")==="true") continue;
        if (!includeHidden && !isVisible(el, doc)) continue;

        const canonical = resolveCanonical(el);
        if (!canonical) continue;
        if (seenCanonicals.has(canonical) || seenGlobal.has(canonical)) continue;
        seenCanonicals.add(canonical);
        seenGlobal.add(el);
        seenGlobal.add(canonical);

        const wrapper = el !== canonical ? el : null;
        const label = getSmartLabel(canonical, wrapper || canonical, doc);
        if (isAuxiliary(canonical, label, doc)) continue;
        if (wrapper && isAuxiliary(wrapper, label, doc)) continue;

        const fieldType = normalizeType(canonical, wrapper);
        const atsType = detectATSType(canonical, wrapper, label);
        const selectorBundle = buildSelectorBundle(canonical, wrapper, doc);

        const form = canonical.closest("form");
        const formIndex = form ? allForms.indexOf(form) : -1;
        const fieldsInForm = form ? Array.from(form.querySelectorAll("input:not([disabled]),select:not([disabled]),textarea:not([disabled])")) : [];
        const fieldIndexInForm = fieldsInForm.indexOf(canonical);

        results.push({
          _canonical: canonical,
          _wrapper: wrapper,
          index: results.length,
          frameId, frameLocalIndex: results.length,
          label,
          name: canonical.getAttribute("name")||wrapper?.getAttribute("name")||"",
          id: canonical.getAttribute("id")||wrapper?.getAttribute("id")||"",
          type: fieldType, inputType: type, tagName: tag, tag: canonical.tagName.toLowerCase(),
          required: !!(canonical.required || canonical.getAttribute("aria-required")==="true" || wrapper?.getAttribute("aria-required")==="true"),
          placeholder: canonical.getAttribute("placeholder")||"",
          value: getVal(canonical),
          options: extractOptions(canonical, doc),
          validation: extractValidation(canonical),
          atsFieldType: atsType,
          isStandardField: STANDARD_ATS.has(atsType),
          isInShadowDOM: isShadow, isInIframe: frameId>0,
          formId: form?.id||form?.getAttribute("data-automation-id")||"",
          sectionLabel: (canonical.closest("fieldset")?.querySelector("legend")?.textContent||"").trim(),
          ariaDescribedBy: canonical.getAttribute("aria-describedby")||"",
          autocomplete: canonical.getAttribute("autocomplete")||"",
          dataAutomationId: canonical.getAttribute("data-automation-id")||wrapper?.getAttribute("data-automation-id")||"",
          scrapedAt: Date.now(), platform,
          selectors: selectorBundle,
          selector: selectorBundle[0]?.selector||"",
          alternativeSelectors: selectorBundle.slice(1).map(s=>s.selector),
          _selectorHint: makeFingerprint(label, atsType, fieldType, formIndex, fieldIndexInForm),
        });
      } catch(err) { log("warn","Error processing element",{error:String(err)}); }
    }
    return results;
  }

  // ─── EXPAND DROPDOWN OPTIONS ──────────────────────────────────
  function isPhoneCountryEl(el) { return !!el?.closest?.(".iti__country-list,.iti__country,[class*='iti-'],[class*='intl-tel']"); }
  function looksLikePhoneList(opts) { return opts.length >= 15 && opts.filter(o=>/\+\d{1,4}/.test(o)).length >= opts.length*0.6; }

  function collectVisibleOptions(triggerEl, doc, isCountry) {
    const limit = isCountry ? 250 : 100;
    const optSel = '[role="option"],.select__option,[class*="option"][role],li[data-value]';
    const cid = triggerEl.getAttribute("aria-controls")||triggerEl.getAttribute("aria-owns");
    if (cid) {
      try {
        const lb = doc.getElementById(cid);
        if (lb) { const o = Array.from(lb.querySelectorAll(optSel)).filter(x=>!isPhoneCountryEl(x)).map(x=>x.textContent?.trim()||"").filter(Boolean); if (o.length) return o.slice(0,limit); }
      } catch(_) {}
    }
    const openLB = doc.querySelector('[role="listbox"][aria-expanded="true"],[role="listbox"][data-state="open"],[role="listbox"]:not([hidden]):not([style*="display: none"])');
    if (openLB && !isPhoneCountryEl(openLB)) {
      const o = Array.from(openLB.querySelectorAll(optSel)).filter(x=>!isPhoneCountryEl(x)).map(x=>x.textContent?.trim()||"").filter(Boolean);
      if (o.length) return o.slice(0,limit);
    }
    const allOpts = Array.from(doc.querySelectorAll(optSel)).filter(o=>{
      if (isPhoneCountryEl(o)) return false;
      const r = o.getBoundingClientRect(); return r.width>0 && r.height>0;
    }).map(o=>o.textContent?.trim()||"").filter(Boolean);
    const radixOpts = Array.from(doc.querySelectorAll('[data-radix-collection-item],[data-headlessui-state]')).filter(o=>{
      const r = o.getBoundingClientRect(); return r.width>0 && r.height>0;
    }).map(o=>o.textContent?.trim()||"").filter(Boolean);
    return [...new Set([...allOpts,...radixOpts])].slice(0,limit);
  }

  async function expandDropdownForOptions(el, doc) {
    if (!el?.isConnected) return [];
    const role = (el.getAttribute("role")||"").toLowerCase();
    const tag = el.tagName.toLowerCase();
    const isSelectLike = tag==="select" || role==="combobox" ||
      el.getAttribute("aria-haspopup")==="listbox" ||
      /react-select|Select__|ant-select|MuiSelect|Dropdown/i.test(el.className||"");
    if (!isSelectLike) return [];

    const win = doc.defaultView || window;
    const lText = (el.getAttribute("aria-label")||"").toLowerCase();
    const isCountry = /country|nation/.test(lText+(el.id||"").toLowerCase());

    // Close any open dropdown
    try { win.document.body.dispatchEvent(new MouseEvent("mousedown",{bubbles:true,cancelable:true})); await new Promise(r=>setTimeout(r,50)); } catch(_) {}

    try { el.scrollIntoView({block:"nearest",behavior:"auto"}); } catch(_) {}
    await new Promise(r=>setTimeout(r,30));

    try {
      const rect = el.getBoundingClientRect();
      if (rect.width>0 && rect.height>0) {
        const cx = rect.left+rect.width/2, cy = rect.top+rect.height/2;
        const opts = {bubbles:true,cancelable:true,clientX:cx,clientY:cy,view:win};
        el.focus?.({preventScroll:true});
        el.dispatchEvent(new MouseEvent("mousedown",opts));
        el.dispatchEvent(new MouseEvent("mouseup",opts));
        el.dispatchEvent(new MouseEvent("click",opts));
      }
    } catch(_) {}

    for (let attempt=0; attempt<8; attempt++) {
      await new Promise(r=>setTimeout(r, attempt<3 ? 80 : 150));
      const options = collectVisibleOptions(el, doc, isCountry);
      if (options.length > 0) {
        if (!isCountry && looksLikePhoneList(options)) {
          try { el.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",keyCode:27,bubbles:true})); } catch(_) {}
          return [];
        }
        try { el.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",keyCode:27,bubbles:true})); } catch(_) {}
        await new Promise(r=>setTimeout(r,50));
        return options;
      }
    }
    try { el.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",keyCode:27,bubbles:true})); } catch(_) {}
    return [];
  }

  // ─── ADD ANOTHER LINKS ────────────────────────────────────────
  function findAddAnotherLinks(doc, sectionHint) {
    const addRx = /add another|add more|add previous|add experience|add education|add employment|add\s+entry|add\s+position|\+\s*add/i;
    const seen = new Set(); const out = [];
    try {
      const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_ELEMENT);
      let node = walker.nextNode();
      while (node) {
        const tag = node.tagName.toLowerCase();
        const role = (node.getAttribute?.("role")||"").toLowerCase();
        if (tag==="a"||tag==="button"||role==="button"||role==="link"||node.onclick) {
          const text = (node.textContent||"").replace(/\s+/g," ").trim();
          if (addRx.test(text) && text.length<=120) {
            if (sectionHint==="employment" && /education|degree|school/i.test(text)) { node=walker.nextNode(); continue; }
            if (sectionHint==="education" && /experience|employment|job/i.test(text) && !/education/i.test(text)) { node=walker.nextNode(); continue; }
            let el = node.parentElement;
            let linkSection = null;
            while (el && el !== doc.body) {
              const hasEdu = el.querySelector && el.querySelector("[id^='school--'], [id^='degree--']");
              const hasEmp = el.querySelector && el.querySelector("[id^='company--'], [id^='job_title--'], [id^='employer--']");
              if (hasEdu && !hasEmp) { linkSection = "education"; break; }
              if (hasEmp && !hasEdu) { linkSection = "employment"; break; }
              el = el.parentElement;
            }
            if (sectionHint==="employment" && linkSection==="education") { node=walker.nextNode(); continue; }
            if (sectionHint==="education" && linkSection==="employment") { node=walker.nextNode(); continue; }
            if (!seen.has(node)) { seen.add(node); out.push(node); }
          }
        }
        node = walker.nextNode();
      }
    } catch(_) {}
    return out;
  }

  // ─── MAIN ENTRY ───────────────────────────────────────────────
  function getScrapedFields(options = {}) {
    const t0 = performance.now();
    const scope = options.scope||"all";
    const includeHidden = options.includeHidden !== false;
    const rootDoc = options.document || document;
    const platform = detectPlatform(rootDoc);
    const seenGlobal = new WeakSet();
    const allFields = [];
    const absorb = fields => { for (const f of fields) allFields.push(f); };

    log("info","Scrape start",{platform,scope,url:rootDoc.defaultView?.location?.href?.slice(0,80)});

    absorb(scrapeRoot(rootDoc, rootDoc, 0, false, seenGlobal, includeHidden, platform));

    if (scope !== "current_document") {
      traverseShadow(rootDoc.body||rootDoc.documentElement, shadowRoot => {
        absorb(scrapeRoot(shadowRoot, rootDoc, 0, true, seenGlobal, includeHidden, platform));
      });
      for (const frame of getFrames(rootDoc)) {
        try { absorb(scrapeRoot(frame.document, frame.document, frame.id, false, seenGlobal, includeHidden, platform)); } catch(_) {}
      }
    }

    allFields.forEach((f,i) => { f.index=i; f.frameLocalIndex=i; });
    const elapsed = Math.round(performance.now()-t0);
    log("info","Scrape done",{count:allFields.length,ms:elapsed,platform,preview:allFields.slice(0,8).map(f=>({i:f.index,label:f.label?.slice(0,35),type:f.type,ats:f.atsFieldType}))});
    return { fields: allFields, elements: allFields.map(f=>f._canonical).filter(Boolean), stats:{count:allFields.length,ms:elapsed,platform} };
  }

  async function getScrapedFieldsWithExpandedOptions(options = {}) {
    const result = getScrapedFields(options);
    if (options.expandSelectOptions === false) {
      await attachShaFingerprints(result.fields);
      return result;
    }
    const selectFields = result.fields.filter(f=>(f.type==="select")&&(!f.options||!f.options.length)&&f._canonical);
    if (!selectFields.length) return result;
    selectFields.sort((a,b)=>{
      const aC=/country|nation/i.test(a.label+a.id), bC=/country|nation/i.test(b.label+b.id);
      return (aC?1:0)-(bC?1:0);
    });
    log("info","Expanding dropdowns",{count:selectFields.length});
    for (const f of selectFields) {
      try {
        const doc = f._canonical.ownerDocument||document;
        const opts = await expandDropdownForOptions(f._canonical, doc);
        if (opts.length>0) { f.options=opts; log("info","Expanded",{label:f.label?.slice(0,30),count:opts.length}); }
        await new Promise(r=>setTimeout(r,80));
      } catch(_) {}
    }
    await attachShaFingerprints(result.fields);
    return result;
  }

  async function attachShaFingerprints(fields) {
    for (const f of fields || []) {
      try {
        f.fingerprint = await computeFieldFingerprint(f);
      } catch (_) {}
    }
  }

  // ─── SERIALIZE / RESOLVE ─────────────────────────────────────
  function serializeFields(fields) {
    return fields.map(f => {
      const out = {...f}; delete out._canonical; delete out._wrapper; return out;
    });
  }

  function resolveElementFromField(field, doc) {
    for (const {selector} of (field.selectors||[])) {
      try { const el=doc.querySelector(selector); if (el?.isConnected) return el; } catch(_) {}
    }
    if (field.selector) { try { const el=doc.querySelector(field.selector); if (el?.isConnected) return el; } catch(_) {} }
    if (field.id) { const el=doc.getElementById(field.id); if (el?.isConnected) return el; }
    // Fingerprint-based scan as last resort
    const hint = field._selectorHint || field.fingerprint;
    if (hint && hint.includes("|")) {
      const [atsType,,labelSlug] = hint.split("|");
      try {
        const cands = doc.querySelectorAll('input,select,textarea,[contenteditable="true"],[role="combobox"]');
        for (const el of cands) {
          if (el.disabled || !isVisible(el,doc)) continue;
          const canonical = resolveCanonical(el);
          const lbl = getSmartLabel(canonical, el!==canonical?el:canonical, doc);
          const slug = lbl.slice(0,30).toLowerCase().replace(/\s+/g,"_");
          if (slug===labelSlug) return canonical;
        }
      } catch(_) {}
    }
    return null;
  }

  // ─── EXPORTS ──────────────────────────────────────────────────
  window.__OPSBRAIN_SCRAPER__ = {
    getScrapedFields, getScrapedFieldsWithExpandedOptions, attachShaFingerprints,
    serializeFields, resolveElementFromField,
    findAddAnotherLinks, expandDropdownForOptions,
    detectPlatform, getSmartLabel, isVisible, resolveCanonical,
    normalizeType, detectATSType, buildSelectorBundle, extractOptions,
  };
  window.__HIREMATE_FIELD_SCRAPER__ = window.__OPSBRAIN_SCRAPER__;
})();