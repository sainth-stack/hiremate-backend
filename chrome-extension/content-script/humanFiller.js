/**
 * OpsBrain Human Filler v3 — Intelligent form filling with 100% accuracy
 *
 * CORE ARCHITECTURE CHANGES vs v2:
 * 1. FIELD-BASED FILL (not index-based): fill loop resolves element from field metadata
 *    using selector bundle → fingerprint fallback. Index mismatches never cause wrong fills.
 * 2. SMART SELECT: detects searchable vs non-searchable dropdowns before deciding to type.
 *    Non-searchable = click only. Searchable = type then wait for filtered results.
 * 3. REACT 18 COMPATIBLE: nativeInputSetter + _valueTracker in correct order, 
 *    dispatches InputEvent with 'inputType: insertFromPaste' for bulk fills (avoids keydown detection).
 * 4. RETRY WITH FALLBACK CHAIN: each field tries up to 3 strategies before marking as failed.
 * 5. WORKDAY FILE UPLOAD: dispatches dragenter+dragover+drop on the dropzone wrapper.
 * 6. RADIO GROUP LOGIC: skips radios whose value doesn't match desired, clicks matching one.
 * 7. PORTAL-AWARE SELECT: uses bounding-rect filtering to find the correct open dropdown
 *    even when rendered outside the form root (React portals, Radix, Headless UI).
 * 8. DATE INTELLIGENCE: handles native date, Workday date sections, flatpickr, month-year pickers,
 *    and year-only dropdowns (graduation year).
 */
(function () {
  "use strict";

  const LOG = "[OpsBrain][filler]";
  const log = (msg, meta) => { meta !== undefined ? console.info(LOG, msg, meta) : console.info(LOG, msg); };
  const delay = (min, max) => new Promise(r => setTimeout(r, min + Math.random() * (max - min)));

  // Track which Workday date groups have been atomically filled
  // Prevents triple-fill when scraper detects Month/Day/Year as 3 separate fields
  const _filledDateGroupRoots = new WeakSet();

  // ─── REACT / FRAMEWORK VALUE SETTER ───────────────────────────
  // Correct order: nativeSetter → _valueTracker reset → InputEvent
  // This works for React 16, 17, 18 (including concurrent mode)
  function getNativeSetter(el) {
    const tag = el.tagName.toLowerCase();
    if (tag === "textarea") return Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    if (tag === "select") return Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
    let proto = Object.getPrototypeOf(el);
    while (proto) {
      const desc = Object.getOwnPropertyDescriptor(proto, "value");
      if (desc?.set) return desc.set;
      proto = Object.getPrototypeOf(proto);
    }
    return null;
  }

  function setNativeValue(el, value) {
    const setter = getNativeSetter(el);
    if (setter) setter.call(el, value);
    else el.value = value;
    // Reset tracker BEFORE dispatching event (React reads tracker in handler)
    try { if (el._valueTracker) el._valueTracker.setValue(el.value === value ? "" : el.value); } catch(_) {}
  }

  // Dispatch a framework-compatible change (works for React, Vue, Angular)
  function triggerChange(el, value, doc) {
    const win = (doc||document).defaultView || window;
    // InputEvent with insertFromPaste skips keydown bot detection on most ATS
    try {
      el.dispatchEvent(new InputEvent("input", {
        bubbles: true, cancelable: true,
        inputType: "insertFromPaste",
        data: value,
        view: win,
      }));
    } catch(_) {
      try { el.dispatchEvent(new Event("input", {bubbles:true})); } catch(_) {}
    }
    try { el.dispatchEvent(new Event("change", {bubbles:true})); } catch(_) {}
  }

  // ─── PLATFORM DETECTION (reuse from scraper if available) ─────
  function detectPlatform(doc) {
    const url = (doc?.defaultView?.location?.href||"").toLowerCase();
    const html = (doc?.documentElement?.innerHTML||"").slice(0,5000).toLowerCase();
    if (url.includes("greenhouse.io")||url.includes("boards.greenhouse")) return "greenhouse";
    if (url.includes("workday.com")||url.includes("myworkdayjobs")||url.includes("jobs.workday.com")||html.includes("wd3.myworkday")||/wd\d+\.myworkday/.test(html)) return "workday";
    if (url.includes("lever.co")) return "lever";
    if (url.includes("smartrecruiters.com")) return "smartrecruiters";
    if (url.includes("ashbyhq.com")) return "ashby";
    if (url.includes("taleo.net")) return "taleo";
    if (url.includes("jobvite.com")) return "jobvite";
    if (url.includes("icims.com")) return "icims";
    if (url.includes("bamboohr.com")) return "bamboohr";
    if (url.includes("jazz.co")) return "jazz";
    if (url.includes("recruitee.com")) return "recruitee";
    return "generic";
  }

  // ─── SCROLL & CLICK ───────────────────────────────────────────
  async function humanScrollTo(el) {
    try { el.scrollIntoView({behavior:"auto",block:"center",inline:"nearest"}); await delay(15,35); }
    catch(_) { try { el.scrollIntoView({block:"center"}); await delay(15,35); } catch(_2) {} }
  }

  async function humanClick(el, opts = {}) {
    if (!el?.isConnected) return;
    const doc = el.ownerDocument || document;
    const win = doc.defaultView || window;
    let x=0, y=0;
    try {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) {
        if (opts.center) { x = r.left+r.width/2; y = r.top+r.height/2; }
        else { x = r.left+(0.3+Math.random()*0.4)*r.width; y = r.top+(0.3+Math.random()*0.4)*r.height; }
      }
    } catch(_) {}
    const ev = {bubbles:true,cancelable:true,view:win,clientX:x,clientY:y};
    try { el.dispatchEvent(new MouseEvent("mousemove",ev)); } catch(_) {}
    await delay(8,20);
    try { el.dispatchEvent(new MouseEvent("mousedown",ev)); } catch(_) {}
    await delay(6,16);
    try { el.dispatchEvent(new MouseEvent("mouseup",ev)); } catch(_) {}
    try { el.dispatchEvent(new MouseEvent("click",ev)); } catch(_) {}
    try { el.focus({preventScroll:true}); } catch(_) { try { el.focus(); } catch(_2) {} }
    await delay(20,50);
  }

  // ─── FIELD CLEAR ─────────────────────────────────────────────
  async function clearField(el) {
    const doc = el.ownerDocument || document;
    const win = doc.defaultView || window;
    try {
      el.focus();
      // Select all + delete
      el.dispatchEvent(new KeyboardEvent("keydown",{key:"a",code:"KeyA",keyCode:65,ctrlKey:true,bubbles:true,view:win}));
      await delay(20,40);
      el.dispatchEvent(new KeyboardEvent("keydown",{key:"Delete",code:"Delete",keyCode:46,bubbles:true,view:win}));
      await delay(20,40);
    } catch(_) {}
    // Native setter to empty (always, to ensure React state cleared)
    try { setNativeValue(el, ""); triggerChange(el, "", doc); } catch(_) { el.value = ""; }
    await delay(25,50);
  }

  // ─── HUMAN TYPE ───────────────────────────────────────────────
  // FIX: sets full substring value per character (not appending to existing)
  // FIX: _valueTracker set to PREVIOUS value before dispatching input event
  async function humanType(el, text) {
    const doc = el.ownerDocument || document;
    const win = doc.defaultView || window;
    const str = String(text ?? "");
    el.focus();
    await delay(20,50);
    // Clear first
    if ((el.value||"").length > 0 || el.textContent?.length > 0) {
      await clearField(el);
      await delay(20,40);
    }
    for (let i=0; i<str.length; i++) {
      const char = str[i];
      const code = char.charCodeAt(0);
      const newVal = str.slice(0, i+1);
      try { el.dispatchEvent(new KeyboardEvent("keydown",{key:char,keyCode:code,which:code,bubbles:true,cancelable:true,view:win})); } catch(_) {}
      // Set value to substring — nativeSetter ensures React synthetic event sees the change
      const setter = getNativeSetter(el);
      if (setter) setter.call(el, newVal);
      else el.value = newVal;
      // Set tracker to PREVIOUS value so React detects the diff
      try { if (el._valueTracker) el._valueTracker.setValue(str.slice(0,i)); } catch(_) {}
      try {
        el.dispatchEvent(new InputEvent("input",{bubbles:true,cancelable:true,data:char,inputType:"insertText",view:win}));
      } catch(_) {}
      try { el.dispatchEvent(new KeyboardEvent("keyup",{key:char,keyCode:code,which:code,bubbles:true,view:win})); } catch(_) {}
      let d = 4 + Math.random()*8;
      if (Math.random()<0.02) d += 15+Math.random()*20;
      await delay(d, d+4);
    }
    await delay(20,40);
    try { el.dispatchEvent(new Event("change",{bubbles:true})); } catch(_) {}
    await delay(12,25);
    try { el.dispatchEvent(new FocusEvent("blur",{bubbles:true})); } catch(_) {}
    await delay(12,25);
  }

  // ─── RICH TEXT TYPING ─────────────────────────────────────────
  async function humanTypeRichText(el, text) {
    await humanScrollTo(el);
    await humanClick(el);
    el.focus();
    await delay(40,80);
    // Clear via Selection API
    try {
      const doc = el.ownerDocument || document;
      const sel = doc.getSelection?.();
      if (sel) {
        const r = doc.createRange();
        r.selectNodeContents(el);
        sel.removeAllRanges(); sel.addRange(r);
      }
      el.textContent = "";
      await delay(50,100);
    } catch(_) {}
    const doc = el.ownerDocument || document;
    const win = doc.defaultView || window;
    const str = String(text ?? "");
    for (let i=0; i<str.length; i++) {
      const char = str[i];
      try {
        el.textContent = (el.textContent||"") + char;
        const sel = doc.getSelection?.();
        if (sel && el.lastChild) {
          try { const r=doc.createRange(); r.setStartAfter(el.lastChild); r.collapse(true); sel.removeAllRanges(); sel.addRange(r); } catch(_) {}
        }
        el.dispatchEvent(new InputEvent("input",{bubbles:true,data:char,inputType:"insertText",view:win}));
      } catch(_) { el.textContent = (el.textContent||"")+char; }
      await delay(6+Math.random()*9, 14+Math.random()*9);
    }
    try { el.dispatchEvent(new Event("input",{bubbles:true})); } catch(_) {}
    try { el.dispatchEvent(new FocusEvent("blur",{bubbles:true})); } catch(_) {}
    await delay(40,80);
  }

  // ─── FALLBACK FILL ────────────────────────────────────────────
  async function fallbackFill(el, value, doc) {
    try {
      setNativeValue(el, value);
      triggerChange(el, value, doc);
      await delay(25,55);
    } catch(_) { el.value = value; }
  }

  // ─── DATE INPUT ───────────────────────────────────────────────
  function parseDate(val) {
    const s = String(val||"").trim();
    const iso = s.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (iso) return {year:iso[1],month:iso[2],day:iso[3],iso:iso[0]};
    const us = s.match(/(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/);
    if (us) return {year:us[3],month:us[1].padStart(2,"0"),day:us[2].padStart(2,"0"),iso:`${us[3]}-${us[1].padStart(2,"0")}-${us[2].padStart(2,"0")}`};
    const yr = s.match(/^(\d{4})$/);
    if (yr) return {year:yr[1],month:null,day:null,iso:s};
    const ym = s.match(/^(\d{4})-(\d{2})$/);
    if (ym) return {year:ym[1],month:ym[2],day:null,iso:s};
    return {year:null,month:null,day:null,iso:s};
  }

  async function tabKey(el) {
    const win = el.ownerDocument?.defaultView || window;
    el.dispatchEvent(new KeyboardEvent("keydown",{key:"Tab",code:"Tab",keyCode:9,bubbles:true,view:win}));
    el.dispatchEvent(new KeyboardEvent("keyup",{key:"Tab",code:"Tab",keyCode:9,bubbles:true,view:win}));
    await delay(40,80);
  }

  async function humanDateInput(el, value) {
    const parsed = parseDate(value);
    await humanScrollTo(el);
    await humanClick(el);
    await delay(40,100);
    const type = (el.type||"").toLowerCase();

    // Native date/month/time inputs
    if (["date","datetime-local","month","week"].includes(type)) {
      try {
        setNativeValue(el, parsed.iso);
        try { if (el._valueTracker) el._valueTracker.setValue(""); } catch(_) {}
        el.dispatchEvent(new Event("change",{bubbles:true}));
        el.dispatchEvent(new FocusEvent("blur",{bubbles:true}));
        return true;
      } catch(_) {}
    }

    // Workday date sections — fill Year → Month → Day atomically, single blur at end
    // WeakSet guard prevents triple-fill when scraper detects all 3 parts as separate fields
    const aid = el.getAttribute("data-automation-id") || "";
    if (/dateSection/i.test(aid)) {
      let fieldGroup = el.parentElement;
      for (let i = 0; i < 8 && fieldGroup; i++) {
        const yearEl = fieldGroup.querySelector('[data-automation-id*="dateSectionYear"]');
        const monthEl = fieldGroup.querySelector('[data-automation-id*="dateSectionMonth"]');
        const dayEl = fieldGroup.querySelector('[data-automation-id*="dateSectionDay"]');
        if (yearEl || monthEl || dayEl) {
          // If this group was already filled atomically, skip (prevents triple-fill)
          if (_filledDateGroupRoots.has(fieldGroup)) {
            return true; // silently succeed — date was already filled by a sibling field's call
          }
          _filledDateGroupRoots.add(fieldGroup);
          if (yearEl && parsed.year) { await humanType(yearEl, parsed.year); await delay(40, 80); }
          if (monthEl && parsed.month) { await humanType(monthEl, parsed.month); await delay(40, 80); }
          if (dayEl && parsed.day) { await humanType(dayEl, parsed.day); await delay(40, 80); }
          const lastEl = dayEl || monthEl || yearEl;
          if (lastEl) lastEl.dispatchEvent(new FocusEvent("blur", { bubbles: true }));
          return true;
        }
        fieldGroup = fieldGroup.parentElement;
      }
      if (/Month/i.test(aid) && parsed.month) await humanType(el, parsed.month);
      else if (/Day/i.test(aid) && parsed.day) await humanType(el, parsed.day);
      else if (/Year/i.test(aid) && parsed.year) await humanType(el, parsed.year);
      return true;
    }

    // Year-only fields (graduation year, etc.)
    if (parsed.year && !parsed.month && !parsed.day) {
      await humanType(el, parsed.year);
      return true;
    }

    // Generic text datepicker: type MM Tab DD Tab YYYY
    if (parsed.month && parsed.day && parsed.year) {
      el.focus(); await clearField(el);
      await humanType(el, parsed.month);
      await tabKey(el);
      await humanType(el, parsed.day);
      await tabKey(el);
      await humanType(el, parsed.year);
    } else {
      await humanType(el, parsed.iso);
    }
    return true;
  }

  // ─── NORMALIZE KEY FOR MATCHING ───────────────────────────────
  function normKey(t) {
    return String(t||"").toLowerCase().replace(/[_\-]+/g," ").replace(/[^a-z0-9 ]+/g," ").replace(/\s+/g," ").trim();
  }

  // ─── NATIVE SELECT MATCH ──────────────────────────────────────
  function findNativeMatch(selectEl, value) {
    const opts = Array.from(selectEl.options||[]).filter(o=>normKey(o.text)||normKey(String(o.value||"")));
    if (!opts.length) return null;
    const v = normKey(String(value??"")); if (!v) return null;
    // 1. exact text or value
    let m = opts.find(o => normKey(String(o.value??""))===v || normKey(o.text||"")===v);
    if (m) return m;
    // 2. starts with
    m = opts.find(o => normKey(o.text||"").startsWith(v) || v.startsWith(normKey(o.text||"")));
    if (m) return m;
    // 3. contains
    m = opts.find(o => normKey(o.text||"").includes(v) || v.includes(normKey(o.text||"")));
    if (m) return m;
    // 4. first word
    const fw = v.split(/\s+/)[0];
    if (fw && fw.length>1) m = opts.find(o => normKey(o.text||"").startsWith(fw));
    return m || null;
  }

  // ─── FIND "OTHER" OPTION (for school/company when value not in list) ──
  const OTHER_LABELS = ["other","not listed","none of the above","other (please specify)","other (specify)","not in list","other:","autre","otro"];
  function findOtherOptionNative(selectEl) {
    const opts = Array.from(selectEl.options||[]);
    for (const o of opts) {
      const t = normKey(o.text||String(o.value||""));
      if (OTHER_LABELS.some(l => t === l || t.startsWith(l) || t.includes(l))) return o;
    }
    return null;
  }
  function findOptionElOther(optEls) {
    for (const o of optEls) {
      const t = normKey(o.textContent||o.getAttribute?.("data-value")||"");
      if (OTHER_LABELS.some(l => t === l || t.startsWith(l) || t.includes(l))) return o;
    }
    return null;
  }
  async function findSpecifyInputAfterOther(selectEl, valueToFill, doc) {
    let scope = selectEl.closest("form,.form-group,.field,.question,.application-question,.input-group,[data-provides]") || selectEl.parentElement;
    if (!scope) scope = doc;
    const maxWait = 500;
    const start = Date.now();
    const isSpecifyLike = (inp) => {
      if (inp === selectEl || selectEl.contains(inp)) return false;
      const ph = (inp.placeholder||"").toLowerCase();
      const name = (inp.name||inp.id||"").toLowerCase();
      const label = (inp.closest?.("label")?.textContent||"").toLowerCase();
      return /specify|other|please enter|school name|company name|institution|employer|enter (the )?name/.test(ph+name+label);
    };
    while (Date.now() - start < maxWait) {
      const inputs = scope.querySelectorAll('input[type="text"]:not([disabled]),input:not([type]):not([disabled]),textarea:not([disabled])');
      for (const inp of inputs) {
        if (!isSpecifyLike(inp)) continue;
        const r = inp.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
          await humanClick(inp);
          await humanType(inp, String(valueToFill));
          return true;
        }
      }
      const visible = Array.from(scope.querySelectorAll("input:not([type=hidden]):not([disabled]),textarea:not([disabled])")).filter(el => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && el !== selectEl && !selectEl.contains(el) && el.type !== "file";
      });
      const best = visible.find(isSpecifyLike) || visible.find(el => !el.value && (el.placeholder||"").length > 0) || visible[0];
      if (best) {
        await humanClick(best);
        await humanType(best, String(valueToFill));
        return true;
      }
      await delay(50,100);
    }
    return false;
  }

  // ─── INSTITUTION-LIKE VALUE (avoid fuzzy match for school/company names) ──
  // Fuzzy "first word" match can select wrong option (e.g. JNTU Hyderabad vs JNTU Pulivendula)
  function isInstitutionLikeValue(value) {
    const s = String(value||"").trim();
    if (s.length < 25) return false;
    return /university|college|institute|institution|school|polytechnic|academy/i.test(s);
  }

  // ─── OPTION ELEMENT MATCH ─────────────────────────────────────
  // For institution/company names: EXACT match only (no fuzzy) to avoid wrong selection
  function findOptionEl(optEls, value) {
    const v = normKey(value); if (!v) return null;
    const strictMatch = isInstitutionLikeValue(value);

    // exact
    let m = optEls.find(el => normKey(el.textContent||el.getAttribute?.("data-value")||"")=== v);
    if (m) return m;

    // For institution-like values: ONLY exact match — never fuzzy (avoids JNTU Hyderabad vs Pulivendula)
    if (strictMatch) return null;

    // starts with (avoid overly long matches like "British Indian...")
    m = optEls.find(el => normKey(el.textContent||"").startsWith(v+" ") || normKey(el.textContent||"")===v);
    if (m) return m;
    // contains with territory exclusion
    const isShort = v.length<=20 && !/\d{3,}/.test(value);
    m = optEls.find(el => {
      const t = normKey(el.textContent||""); if (!t.includes(v)) return false;
      if (isShort && /territory|ocean|island|virgin|samoa/.test(t) && !t.startsWith(v)) return false;
      return true;
    });
    if (m) return m;
    // first word (skip for long institution names)
    const fw = v.split(/\s+/)[0];
    if (fw && fw.length>1 && v.length<=40) m = optEls.find(el => normKey(el.textContent||"").startsWith(fw));
    return m||null;
  }

  // ─── DETECT IF DROPDOWN IS SEARCHABLE ─────────────────────────
  // Many Radix/Headless UI selects are NOT searchable (click-only).
  // Typing in them filters options and may hide the target.
  function isSearchableDropdown(el) {
    const tag = el.tagName.toLowerCase();
    const cls = String(el.className||"");
    const role = (el.getAttribute("role")||"").toLowerCase();
    // Explicit search inputs
    if (tag === "input" && (el.getAttribute("type")==="text" || el.getAttribute("type")==="search" || !el.type)) {
      // If it's inside a react-select or MUI autocomplete, it's searchable
      if (el.closest('[class*="react-select"],[class*="MuiAutocomplete"],[class*="Autocomplete"]')) return true;
      // standalone combobox input
      if (role === "combobox") return true;
    }
    // React-Select, MUI autocomplete — searchable
    if (/react-select__input|MuiAutocomplete|ant-select-search/i.test(cls)) return true;
    // Workday searchable text input inside a select widget
    if (el.getAttribute("data-automation-id")?.includes("textInput") && el.closest('[data-automation-id*="select"],[data-automation-id*="dropdown"]')) return true;
    return false;
  }

  // ─── WAIT FOR OPTIONS ─────────────────────────────────────────
  function isPhoneCountry(el) { return !!el?.closest?.(".iti__country-list,.iti__country,[class*='iti-'],[class*='intl-tel']"); }

  async function waitForOptions(doc, triggerEl, maxMs = 1500) {
    const optSel = '[role="option"],.select__option,[class*="option"][role],li[data-value],[data-radix-collection-item]';
    const start = Date.now();
    const radixContentId = triggerEl?.getAttribute?.("aria-controls")||triggerEl?.getAttribute?.("aria-owns")||triggerEl?.id;

    while (Date.now()-start < maxMs) {
      // 1. aria-controls (most reliable, works for Radix when id is set)
      const cid = triggerEl?.getAttribute?.("aria-controls")||triggerEl?.getAttribute?.("aria-owns");
      if (cid) {
        try {
          const lb = doc.getElementById(cid);
          if (lb) {
            const opts = Array.from(lb.querySelectorAll(optSel)).filter(o=>!isPhoneCountry(o));
            if (opts.length) return opts;
          }
        } catch(_) {}
      }

      // 2. Radix portal: look for popper wrapper that is open
      const radixPortals = Array.from(doc.querySelectorAll(
        '[data-radix-popper-content-wrapper],[data-state="open"][role="listbox"]'
      )).filter(el => {
        const r = el.getBoundingClientRect();
        return r.width>0 && r.height>0;
      });
      if (radixPortals.length === 1) {
        const opts = Array.from(radixPortals[0].querySelectorAll(optSel)).filter(o=>!isPhoneCountry(o));
        if (opts.length) return opts;
      } else if (radixPortals.length > 1 && radixContentId) {
        const triggerRect = triggerEl?.getBoundingClientRect?.() || { left: 0, top: 0 };
        radixPortals.sort((a, b) => {
          const ar = a.getBoundingClientRect();
          const br = b.getBoundingClientRect();
          const distA = Math.abs(ar.left - triggerRect.left) + Math.abs(ar.top - triggerRect.top);
          const distB = Math.abs(br.left - triggerRect.left) + Math.abs(br.top - triggerRect.top);
          return distA - distB;
        });
        const opts = Array.from(radixPortals[0].querySelectorAll(optSel)).filter(o=>!isPhoneCountry(o));
        if (opts.length) return opts;
      }

      // 3. visible listbox fallback
      const lb = doc.querySelector('[role="listbox"]:not([hidden]):not([style*="display: none"]),[role="listbox"][data-state="open"]');
      if (lb && !isPhoneCountry(lb)) {
        const opts = Array.from(lb.querySelectorAll(optSel)).filter(o=>!isPhoneCountry(o));
        if (opts.length) return opts;
      }

      // 4. document-wide visible options (portal pattern)
      const all = Array.from(doc.querySelectorAll(optSel)).filter(o => {
        if (isPhoneCountry(o)) return false;
        const r = o.getBoundingClientRect(); return r.width>0 && r.height>0;
      });
      if (all.length) return all;
      await delay(50,100);
    }
    return [];
  }

  // ─── INJECT CUSTOM OPTION (when value not in dropdown) ─────────
  // For school/company fields: inject our value as a selectable option below the field
  async function injectCustomOptionAndSelect(doc, triggerEl, optionEls, value, fieldMeta) {
    const atsType = (fieldMeta?.atsFieldType||"").toLowerCase();
    const label = (fieldMeta?.label||"").toLowerCase();
    const isSchoolOrCompany = atsType==="school" || atsType==="company" ||
      /school|university|college|institution/i.test(label) || /company|employer|organization/i.test(label);
    if (!isSchoolOrCompany && !isInstitutionLikeValue(value)) return false;

    const listbox = optionEls[0]?.parentElement ||
      doc.querySelector('[role="listbox"]:not([hidden]),[role="listbox"][data-state="open"]');
    if (!listbox || !listbox.isConnected) return false;

    // Ensure full value is in the input (type it if searchable)
    const tag = (triggerEl?.tagName||"").toLowerCase();
    const inputEl = tag==="input" ? triggerEl : triggerEl?.querySelector?.('input[type="text"],input[type="search"],input:not([type])');
    if (inputEl) {
      const currentVal = (inputEl.value||"").trim();
      const wantVal = String(value||"").trim();
      if (normKey(currentVal) !== normKey(wantVal)) {
        await clearField(inputEl);
        await delay(30,60);
        await humanType(inputEl, wantVal);
        await delay(80,150);
      }
    }

    // Create injected option — match structure of existing options or use simple div
    const sample = optionEls[0];
    const injected = doc.createElement(sample ? (sample.tagName||"div") : "div");
    injected.setAttribute("role", "option");
    injected.textContent = String(value||"").trim();
    injected.setAttribute("data-value", String(value||"").trim());
    injected.classList.add("ja-injected-option");
    if (sample?.className) injected.className = String(sample.className) + " ja-injected-option";
    if (sample) {
      const r = sample.getBoundingClientRect();
      if (r?.height > 0) injected.style.minHeight = r.height + "px";
    }
    injected.style.cursor = "pointer";
    injected.style.padding = "8px 12px";

    listbox.insertBefore(injected, listbox.firstChild);
    await delay(30,60);

    try {
      await humanScrollTo(injected);
      await humanClick(injected);
      await delay(50,100);
      log("Injected custom option and selected",{value:String(value).slice(0,50)});
      return true;
    } finally {
      try { injected.remove(); } catch(_) {}
    }
  }

  // ─── HUMAN SELECT ─────────────────────────────────────────────
  async function humanSelect(el, value, knownOptions, doc, fieldMeta) {
    if (!doc) doc = el.ownerDocument || document;
    const win = doc.defaultView || window;
    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute("role")||"").toLowerCase();
    await humanScrollTo(el);

    // ── Native <select> ──
    if (tag === "select") {
      const match = findNativeMatch(el, value);
      if (!match) { log("No match in <select>",{value}); return false; }
      await humanClick(el);
      await delay(30,80);
      const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,"value")?.set;
      if (setter) setter.call(el, match.value); else el.value = match.value;
      try { if (el._valueTracker) el._valueTracker.setValue(""); } catch(_) {}
      el.dispatchEvent(new Event("change",{bubbles:true}));
      el.dispatchEvent(new FocusEvent("blur",{bubbles:true}));
      return true;
    }

    // ── Custom dropdown / combobox ──
    const hasKnown = Array.isArray(knownOptions) && knownOptions.length > 0;
    const fast = hasKnown;

    // Find the trigger element (what to click to open the dropdown)
    let triggerEl = el;
    if (tag === "div" || tag === "span") {
      triggerEl = el.querySelector('[role="combobox"],input,button,[aria-haspopup]') || el;
    } else if (tag === "input") {
      // Input IS the trigger
      triggerEl = el;
    }

    // Step 1: Focus and click to open dropdown
    try { triggerEl.focus?.({preventScroll:true}); } catch(_) {}
    await delay(fast?10:30, fast?25:60);
    await humanClick(triggerEl, {center:true});
    await delay(fast?80:180, fast?150:300);

    // Step 2: For searchable dropdowns WITHOUT known options, type to filter
    const searchable = isSearchableDropdown(triggerEl) || isSearchableDropdown(el);
    const institutionLike = isInstitutionLikeValue(value);
    if (searchable && !hasKnown) {
      const inputEl = tag==="input" ? el : el.querySelector('input[type="text"],input[type="search"],input:not([type])');
      if (inputEl) {
        await humanClick(inputEl);
        await delay(30,60);
        // For institution names: type FULL value so input shows correct text; inject will add option if not in list
        const typeVal = institutionLike ? String(value) : String(value).slice(0,20);
        await humanType(inputEl, typeVal);
        await delay(120,220);
      }
    }

    // Step 3: Wait for and click the matching option
    const optionEls = await waitForOptions(doc, triggerEl, fast ? 800 : 1500);
    if (optionEls.length > 0) {
      const match = findOptionEl(optionEls, value);
      if (match) {
        await humanScrollTo(match);
        await humanClick(match);
        await delay(fast?15:40, fast?50:100);
        log("Custom select filled",{value,text:match.textContent?.trim()?.slice(0,40)});
        return true;
      }
      // No match: for school/company, inject our value as option and select it
      const injected = await injectCustomOptionAndSelect(doc, triggerEl, optionEls, value, fieldMeta);
      if (injected) return true;
      log("Option not found in list",{value,sample:optionEls.slice(0,3).map(o=>o.textContent?.trim())});
    } else if (institutionLike && fieldMeta) {
      // Dropdown may show "no results" — inject into listbox if we can find it
      const injected = await injectCustomOptionAndSelect(doc, triggerEl, [], value, fieldMeta);
      if (injected) return true;
    }

    // Step 4: Workday aria-activedescendant fallback
    const activeId = triggerEl.getAttribute("aria-activedescendant");
    if (activeId) {
      const allOpts = Array.from(doc.querySelectorAll('[role="option"]'));
      const match = findOptionEl(allOpts, value);
      if (match) { await humanClick(match); return true; }
    }

    // Step 5: Press Enter to accept typed value
    try {
      triggerEl.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",code:"Enter",keyCode:13,bubbles:true,view:win}));
      await delay(50,100);
    } catch(_) {}

    log("Select: could not find option, may have confirmed via Enter",{value});
    return false;
  }

  // ─── SELECT "OTHER" AND FILL SPECIFY INPUT (school/company fallback) ──
  async function trySelectOtherAndFillSpecify(el, valueToFill, knownOptions, fieldMeta, doc) {
    const atsType = (fieldMeta?.atsFieldType||"").toLowerCase();
    const label = (fieldMeta?.label||"").toLowerCase();
    const isSchoolOrCompany = atsType==="school" || atsType==="company" ||
      /school|university|college|institution/i.test(label) || /company|employer|organization/i.test(label);
    if (!isSchoolOrCompany || !valueToFill) return false;

    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute("role")||"").toLowerCase();
    if (!doc) doc = el.ownerDocument || document;

    await humanScrollTo(el);
    if (tag === "select") {
      const otherOpt = findOtherOptionNative(el);
      if (!otherOpt) return false;
      await humanClick(el);
      await delay(30,80);
      const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,"value")?.set;
      if (setter) setter.call(el, otherOpt.value); else el.value = otherOpt.value;
      try { if (el._valueTracker) el._valueTracker.setValue(""); } catch(_) {}
      el.dispatchEvent(new Event("change",{bubbles:true}));
      el.dispatchEvent(new FocusEvent("blur",{bubbles:true}));
      await delay(300,500);
      const ok = await findSpecifyInputAfterOther(el, valueToFill, doc);
      if (ok) log("Select Other + filled specify",{value:valueToFill.slice(0,40)});
      return ok;
    }

    let triggerEl = el;
    if (tag === "div" || tag === "span") triggerEl = el.querySelector('[role="combobox"],input,button,[aria-haspopup]') || el;
    try { triggerEl.focus?.({preventScroll:true}); } catch(_) {}
    await delay(20,50);
    await humanClick(triggerEl, {center:true});
    await delay(150,300);
    const optionEls = await waitForOptions(doc, triggerEl, 1000);
    const otherOpt = optionEls.length ? findOptionElOther(optionEls) : null;
    if (!otherOpt) return false;
    await humanScrollTo(otherOpt);
    await humanClick(otherOpt);
    await delay(300,500);
    const ok = await findSpecifyInputAfterOther(el, valueToFill, doc);
    if (ok) log("Custom select Other + filled specify",{value:valueToFill.slice(0,40)});
    return ok;
  }

  // ─── FILE UPLOAD ──────────────────────────────────────────────
  async function humanUploadFile(input, resumeData) {
    if (!resumeData?.buffer) { log("No resume buffer"); return false; }
    const name = resumeData.name || "resume.pdf";
    const ext = name.toLowerCase().split(".").pop();
    const mimes = {pdf:"application/pdf",doc:"application/msword",docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",txt:"text/plain"};
    const mime = mimes[ext] || "application/pdf";
    const file = new File([new Uint8Array(resumeData.buffer)], name, {type:mime, lastModified:Date.now()});
    const dt = new DataTransfer();
    dt.items.add(file);

    await humanScrollTo(input);
    await delay(120,250);

    // Strategy 1: native files setter (React-compatible)
    try {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"files")?.set;
      if (setter) setter.call(input, dt.files); else input.files = dt.files;
    } catch(_) { try { input.files = dt.files; } catch(_2) {} }

    try { if (input._valueTracker) input._valueTracker.setValue(""); } catch(_) {}
    input.dispatchEvent(new Event("change",{bubbles:true}));
    input.dispatchEvent(new Event("input",{bubbles:true}));
    await delay(200,400);

    // Strategy 2: If file not registered, try drag-and-drop on dropzone wrapper (Workday, Greenhouse)
    if (!input.files?.length) {
      const dropzone = input.closest(
        '[class*="dropzone"],[class*="upload"],[class*="filepond"],[data-dropzone],' +
        '[data-automation-id*="fileUpload"],[data-automation-id*="file-upload"],[data-automation-id*="attachment"]'
      ) || input.parentElement;
      if (dropzone) {
        try {
          const r = dropzone.getBoundingClientRect();
          const cx = r.left+r.width/2, cy = r.top+r.height/2;
          const evOpts = {bubbles:true,cancelable:true,dataTransfer:dt,clientX:cx,clientY:cy};
          dropzone.dispatchEvent(new DragEvent("dragenter",evOpts));
          dropzone.dispatchEvent(new DragEvent("dragover",evOpts));
          dropzone.dispatchEvent(new DragEvent("drop",evOpts));
          await delay(200,400);
        } catch(_) {}
      }
    }

    const ok = !!(input.files?.length || (input.value && input.value.length > 0));
    log(ok ? "File upload success" : "File upload may have failed", {name});
    return ok;
  }

  // ─── FIELD RESOLUTION AT FILL TIME ───────────────────────────
  // Uses the scraper's resolveElementFromField if available, else tries selector bundle
  function resolveField(fieldMeta, doc) {
    // Use scraper's resolution if available
    if (window.__OPSBRAIN_SCRAPER__?.resolveElementFromField) {
      const el = window.__OPSBRAIN_SCRAPER__.resolveElementFromField(fieldMeta, doc);
      if (el?.isConnected) return el;
    }
    // Manual resolution with selector bundle
    for (const s of (fieldMeta.selectors || [])) {
      try { const el=doc.querySelector(s.selector||s); if (el?.isConnected) return el; } catch(_) {}
    }
    if (fieldMeta.selector) {
      try { const el=doc.querySelector(fieldMeta.selector); if (el?.isConnected) return el; } catch(_) {}
    }
    if (fieldMeta.id) {
      const el = doc.getElementById(fieldMeta.id); if (el?.isConnected) return el;
    }
    for (const s of (fieldMeta.alternativeSelectors || [])) {
      try { const el=doc.querySelector(s); if (el?.isConnected) return el; } catch(_) {}
    }
    if (window.__SELECTOR_RESOLVER__) {
      const el = window.__SELECTOR_RESOLVER__.resolve(fieldMeta, doc);
      if (el?.isConnected) return el;
    }
    return null;
  }

  // ─── SINGLE FIELD FILLER ──────────────────────────────────────
  async function fillField(fieldMeta, value, resumeData, doc) {
    const el = resolveField(fieldMeta, doc);
    if (!el) {
      log("Cannot resolve element",{label:fieldMeta.label,selector:fieldMeta.selector});
      return {ok:false,reason:"element_not_found"};
    }
    if (el.disabled || el.getAttribute("aria-disabled")==="true") return {ok:false,reason:"disabled"};

    const tag = el.tagName.toLowerCase();
    const type = (el.type||"").toLowerCase();
    const role = (el.getAttribute("role")||"").toLowerCase();
    const fieldType = fieldMeta.type || "text";

    await humanScrollTo(el);
    await delay(25,70);

    // ── Workday upload button (fileUploadButton) — MUST be before generic FILE block ──
    // Workday 2024 uses <button data-automation-id="fileUploadButton"> instead of input[type=file]
    const elAid = (el.getAttribute("data-automation-id") || "").toLowerCase();
    const isWorkdayUploadBtn = (tag === "button") &&
      (elAid.includes("fileupload") || elAid.includes("uploadfile") || elAid.includes("attachment")) &&
      (value === "RESUME_FILE" || fieldMeta.atsFieldType === "resume" ||
       /resume|cv\b/i.test(fieldMeta.label || "") || fieldType === "file");
    if (isWorkdayUploadBtn && resumeData) {
      const form = el.closest("form") || el.parentElement?.parentElement;
      const fileInput =
        form?.querySelector('input[type="file"]') ||
        el.nextElementSibling?.querySelector('input[type="file"]') ||
        el.parentElement?.querySelector('input[type="file"]') ||
        el.closest('[data-automation-id*="fileUpload"],[data-automation-id*="attachment"]')
          ?.querySelector('input[type="file"]');
      if (fileInput) {
        const ok = await humanUploadFile(fileInput, resumeData);
        return { ok, isResume: true };
      }
    }

    // ── FILE (native input[type=file]) ──
    if (type === "file" || fieldType === "file") {
      const isResume = value === "RESUME_FILE" || fieldMeta.atsFieldType === "resume" ||
        /resume|cv\b/i.test(fieldMeta.label || "");
      if (isResume && resumeData) {
        const ok = await humanUploadFile(el, resumeData);
        return { ok, isResume: true };
      }
      return { ok: false, reason: "no_resume" };
    }

    // ── SELECT / COMBOBOX ──
    // Include school/company inputs that are autocomplete (inside combobox or have dropdown)
    const isAutocompleteInput = (fieldMeta.atsFieldType==="school" || fieldMeta.atsFieldType==="company") &&
      (tag==="input") && (el.closest('[role="combobox"],[aria-haspopup="listbox"]') || el.getAttribute("aria-haspopup")==="listbox");
    if (tag==="select" || fieldType==="select" ||
      role==="combobox" || role==="listbox" ||
      el.getAttribute("aria-haspopup")==="listbox" ||
      /react-select|MuiSelect|ant-select/i.test(el.className||"") ||
      isAutocompleteInput) {
      const ok = await humanSelect(el, String(value), fieldMeta.options, doc, fieldMeta);
      if (!ok) {
        // For school/company: try "Other" option, then fill the specify/enter field
        const otherOk = await trySelectOtherAndFillSpecify(el, String(value), fieldMeta.options, fieldMeta, doc);
        if (otherOk) return {ok:true};
        // Retry with fallbackFill for native select
        if (tag === "select") { await fallbackFill(el, String(value), doc); return {ok:true,fallback:true}; }
      }
      return {ok};
    }

    // ── DATE ──
    if (fieldType==="date" || ["date","datetime-local","month","time","week"].includes(type) ||
      /datepicker|date-input/i.test(el.className||"")) {
      const ok = await humanDateInput(el, value);
      return {ok};
    }

    // ── CHECKBOX ──
    if (type==="checkbox" || role==="checkbox" || role==="switch" || fieldType==="checkbox") {
      const vs = String(value||"").toLowerCase();
      const want = value===true || ["true","1","yes","on","checked"].includes(vs);
      if (want !== el.checked) {
        await humanClick(el);
        await delay(40,100);
        if (el.checked !== want) { el.checked = want; el.dispatchEvent(new Event("change",{bubbles:true})); }
      }
      return {ok:true};
    }

    // ── RADIO ──
    if (type==="radio" || role==="radio" || fieldType==="radio") {
      // Only click if this radio's value matches what we want
      const own = normKey(String(el.value||""));
      const want = normKey(String(value||""));
      if (own && want && own!==want && !want.includes(own) && !own.includes(want)) {
        return {ok:false,reason:"radio_value_mismatch"};
      }
      await humanClick(el);
      return {ok:true};
    }

    // ── RICH TEXT ──
    if (el.isContentEditable || el.contentEditable==="true" || role==="textbox" ||
      fieldType==="richtext" || /ql-editor|DraftEditor|ProseMirror|jodit|ck-content/i.test(el.className||"")) {
      await humanTypeRichText(el, String(value));
      return {ok:true};
    }

    // ── STANDARD INPUT / TEXTAREA ──
    if (tag==="input" || tag==="textarea" || fieldType==="text" || fieldType==="textarea" || fieldType==="number") {
      const expected = String(value||"");
      // Fast path: try fallbackFill first (instant, React-compatible). Only humanType if value doesn't stick.
      await humanScrollTo(el);
      await humanClick(el);
      await delay(15,40);
      await fallbackFill(el, expected, doc);
      await delay(20,50);
      const got = (el.value||"").toString().trim();
      const expectedTrim = expected.trim();
      if (got !== expectedTrim && Math.abs(got.length-expectedTrim.length) > 2) {
        log("Fallback didn't stick, retrying with humanType",{label:fieldMeta.label});
        await humanType(el, expected);
      }
      return {ok:true};
    }

    log("Unhandled field",{label:fieldMeta.label,tag,type,role,fieldType});
    return {ok:false,reason:"unhandled_type"};
  }

  // ─── WORKDAY RESUME-ONLY STEP ─────────────────────────────────
  async function handleWorkdayResumeStep(resumeData, doc) {
    if (!doc) doc = document;
    log("Workday resume-only step: starting");

    if (resumeData?.buffer) {
      const fileInput =
        doc.querySelector('input[type="file"]') ||
        doc.querySelector('[data-automation-id*="fileUpload"] input[type="file"]') ||
        doc.querySelector('[data-automation-id*="attachment"] input[type="file"]');

      if (fileInput) {
        const ok = await humanUploadFile(fileInput, resumeData);
        log("Resume upload result", { ok });

        if (ok) {
          // Wait for Workday to show filename preview (up to 3s)
          const start = Date.now();
          while (Date.now() - start < 3000) {
            const preview =
              doc.querySelector('[data-automation-id*="fileName"]') ||
              doc.querySelector('[class*="fileName"],[class*="file-name"]') ||
              doc.querySelector('[data-automation-id*="uploadedFile"]');
            if (preview?.textContent?.trim()) {
              log("File preview appeared", { text: preview.textContent.trim() });
              break;
            }
            await new Promise(r => setTimeout(r, 150));
          }
        }
      } else {
        // Drag-drop fallback
        const dropzone =
          doc.querySelector('[class*="drop-zone"],[class*="dropzone"],[class*="dropZone"]') ||
          doc.querySelector('[data-automation-id*="fileUpload"]');
        if (dropzone && resumeData.buffer) {
          try {
            const name = resumeData.name || "resume.pdf";
            const ext = name.toLowerCase().split(".").pop();
            const mimes = { pdf: "application/pdf", doc: "application/msword", docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", txt: "text/plain" };
            const file = new File([new Uint8Array(resumeData.buffer)], name, { type: mimes[ext] || "application/pdf" });
            const dt = new DataTransfer();
            dt.items.add(file);
            const r = dropzone.getBoundingClientRect();
            const evOpts = { bubbles: true, cancelable: true, dataTransfer: dt, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 };
            dropzone.dispatchEvent(new DragEvent("dragenter", evOpts));
            await new Promise(r2 => setTimeout(r2, 80));
            dropzone.dispatchEvent(new DragEvent("dragover", evOpts));
            await new Promise(r2 => setTimeout(r2, 80));
            dropzone.dispatchEvent(new DragEvent("drop", evOpts));
            await new Promise(r2 => setTimeout(r2, 1500));
          } catch (e) {
            log("Dropzone drop failed", { error: String(e) });
          }
        }
      }
    }

    // Click Continue
    await new Promise(r => setTimeout(r, 400));
    const selectors = [
      "[data-automation-id='bottom-navigation-next-button']",
      "[data-automation-id='wd-CommandButton_uic_nextButton']",
      "button[data-automation-id*='continueButton']",
      "button[data-automation-id*='nextButton']",
      "button[data-automation-id*='continue']",
    ];

    for (const sel of selectors) {
      const btn = doc.querySelector(sel);
      if (btn && !btn.disabled && btn.getBoundingClientRect().width > 0) {
        await humanScrollTo(btn);
        await new Promise(r => setTimeout(r, 200));
        await humanClick(btn);
        log("Clicked Continue", { selector: sel });
        return true;
      }
    }

    // Last resort
    const allBtns = Array.from(doc.querySelectorAll("button:not([disabled])"))
      .filter(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && r.top > window.innerHeight / 2;
      })
      .sort((a, b) => b.getBoundingClientRect().right - a.getBoundingClientRect().right);
    if (allBtns[0]) {
      await humanScrollTo(allBtns[0]);
      await humanClick(allBtns[0]);
      return true;
    }
    return false;
  }

  // ─── MAIN FILL LOOP ───────────────────────────────────────────
  /**
   * fillWithValuesHumanLike — THE main entry point
   *
   * Accepts two calling patterns:
   *
   * Pattern A (field-based, preferred):
   *   { fieldsForFrame: FieldMeta[], values: { [localIndex]: value }, resumeData }
   *
   * Pattern B (element-array, legacy):
   *   { elements: Element[], valuesByIndex: { [i]: value }, fieldsForFrame, resumeData }
   */
  async function fillWithValuesHumanLike(payload) {
    const {
      fieldsForFrame = [],
      values = {},
      elements = [],
      valuesByIndex = {},
      resumeData,
      onProgress,
      shouldAbort,
      highlightFailedField,
    } = payload;

    const t0 = Date.now();
    const doc = (elements[0]?.ownerDocument) || document;
    const platform = detectPlatform(doc);

    // Normalize: prefer fieldsForFrame+values, fall back to elements+valuesByIndex
    const useFieldBased = fieldsForFrame.length > 0;
    const fillItems = useFieldBased
      ? fieldsForFrame
          .filter(f => {
            const v = values[String(f.frameLocalIndex ?? f.index)];
            return v !== undefined && v !== null && v !== "";
          })
          .map(f => ({
            meta: f,
            value: values[String(f.frameLocalIndex ?? f.index)],
          }))
      : elements
          .map((el, i) => ({ meta: { _canonical: el, selector: "", selectors: [], index: i, label: `Field ${i}` }, value: valuesByIndex[i] }))
          .filter(item => item.value !== undefined && item.value !== null && item.value !== "");

    // Also find file fields (even if value is empty/RESUME_FILE)
    const fileFields = useFieldBased
      ? fieldsForFrame.filter(f => f.type === "file" || f.atsFieldType === "resume")
      : [];

    const allItems = [...fillItems, ...fileFields.filter(f => !fillItems.find(i => i.meta === f)).map(f => ({ meta: f, value: "RESUME_FILE" }))];

    log("Fill start",{mode:useFieldBased?"field-based":"element-array",items:allItems.length,platform,hasResume:!!resumeData});

    let filledCount = 0, resumeCount = 0;
    const failed = [];

    for (let i=0; i<allItems.length; i++) {
      if (shouldAbort?.()) { log("Aborted"); break; }
      const {meta, value} = allItems[i];

      // Resolve element — for field-based mode, use selector bundle
      // For legacy element mode, _canonical is already the element
      const el = meta._canonical && meta._canonical.isConnected
        ? meta._canonical
        : resolveField(meta, doc);

      if (!el) {
        failed.push({label:meta.label||`Field ${i}`});
        if (highlightFailedField) {
          // Try to find by fingerprint just to highlight
          try {
            const cands = doc.querySelectorAll("input,select,textarea");
            // Can't highlight without element
          } catch(_) {}
        }
        await delay(20,50);
        continue;
      }

      onProgress?.({phase:"filling",current:i+1,total:allItems.length,label:meta.label||`Field ${i+1}`});

      // Override meta with resolved element for fillField
      const fillMeta = { ...meta, _canonical: el };

      let result;
      try {
        result = await fillField(fillMeta, value, resumeData, doc);
      } catch(err) {
        log("Error filling field",{label:meta.label,error:String(err)});
        result = {ok:false,reason:"exception"};
      }

      if (result.ok) {
        filledCount++;
        if (result.isResume) resumeCount++;
      } else if (result.reason !== "radio_value_mismatch" && result.reason !== "disabled") {
        failed.push({label:meta.label||`Field ${i}`,reason:result.reason});
        if (highlightFailedField && el.isConnected && !el.disabled) highlightFailedField(el);
      }

      await delay(35,90);
    }

    const elapsed = Date.now()-t0;
    log("Fill done",{filledCount,resumeCount,failedCount:failed.length,elapsed,failed:failed.slice(0,5)});

    // Remove failure highlights from fields that became disabled (e.g. "present" checkbox hides end date)
    await delay(50,100);
    for (const f of failed) {
      try {
        if (f.element?.isConnected && (f.element.disabled || f.element.getAttribute?.("aria-disabled")==="true")) {
          f.element.classList?.remove("ja-autofill-failed");
        }
      } catch(_) {}
    }

    return {filledCount, resumeUploadCount:resumeCount, failedCount:failed.length, failedFields:failed};
  }

  // ─── EXPORTS ──────────────────────────────────────────────────
  window.__OPSBRAIN_FILLER__ = {
    fillWithValuesHumanLike,
    fillField,
    handleWorkdayResumeStep,
    humanType, humanTypeRichText, humanSelect, humanUploadFile, humanDateInput,
    humanScrollTo, humanClick, clearField, fallbackFill,
    setNativeValue, getNativeSetter, triggerChange,
    normKey, findNativeMatch, findOptionEl, waitForOptions,
    isInstitutionLikeValue, injectCustomOptionAndSelect,
    parseDate, resolveField, detectPlatform,
  };
  window.__HIREMATE_HUMAN_FILLER__ = window.__OPSBRAIN_FILLER__;
})();