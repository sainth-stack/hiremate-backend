// ─── Field Scraping Orchestration ─────────────────────────────────────────
// Depends on: logInfo, logWarn (utils.js)
//             isInsideExtensionWidget, getFillableFields, getFieldMeta (dom-utils.js)
//             enrichFieldsWithLearnedSelectors, scrapeWithLearning (services/form-learning.js)

async function scrapeFields(options = {}) {
  const t0 = Date.now();
  const includeNestedDocuments = options.scope !== "current_document";
  const expandSelectOptions = options.expandSelectOptions !== false;
  const preExpandEmployment = Math.max(0, options.preExpandEmployment || 0);
  const preExpandEducation = Math.max(0, options.preExpandEducation || 0);
  logInfo("scrapeFields: start", { scope: options.scope, expandSelectOptions, preExpandEmployment, preExpandEducation });

  const scraper = typeof window !== "undefined" && window.__HIREMATE_FIELD_SCRAPER__;
  logInfo("scrapeFields: scraper check", { hasScraper: !!scraper });

  const atsPlatform = window.__OPSBRAIN_ATS__ || (scraper?.detectPlatform?.(document) || "unknown");
  if (scraper?.detectPlatform && !window.__OPSBRAIN_ATS__) {
    window.__OPSBRAIN_ATS__ = atsPlatform;
  }

  const doc = document;
  const maxEducationBlocks = Math.max(1, options.maxEducationBlocks ?? 999);
  const maxEmploymentBlocks = Math.max(1, options.maxEmploymentBlocks ?? 999);

  function findRemoveBtn(container) {
    if (!container) return null;
    const text = (n) => (n?.textContent || n?.getAttribute?.("aria-label") || n?.getAttribute?.("title") || "").toLowerCase();
    for (const el of container.querySelectorAll("button, a[href='#'], [role='button']")) {
      if (/\b(remove|delete|clear)\b/.test(text(el))) return el;
      const svg = el.querySelector("svg");
      if (svg) return el;
    }
    return null;
  }

  for (let round = 0; round < 2; round++) {
    const maxBlocks = round === 0 ? maxEmploymentBlocks : maxEducationBlocks;
    const ids = round === 0 ? ["company", "job_title", "employer"] : ["school", "degree"];
    const anchors = doc.querySelectorAll(ids.map((p) => `[id^="${p}--"]`).join(", "));
    const indices = [...new Set(Array.from(anchors).map((el) => {
      const m = (el.id || "").match(/(\d+)$/);
      return m ? parseInt(m[1], 10) : -1;
    }).filter((n) => n >= 0))].sort((a, b) => b - a);
    for (const idx of indices) {
      if (idx >= maxBlocks) {
        const anchor = ids.reduce((a, p) => a || doc.getElementById(`${p}--${idx}`), null);
        if (anchor) {
          const block = anchor.closest("[class*='field'],[class*='block'],[class*='question'],fieldset") || anchor.parentElement?.parentElement;
          const btn = block && findRemoveBtn(block);
          if (btn) {
            btn.click();
            await new Promise((r) => setTimeout(r, 500));
            logInfo("Removed extra block", { round: round ? "education" : "employment", index: idx });
          }
        }
      }
    }
  }

  // Expand "Add another" (employment/education) at start of initial scrape
  if (scraper?.findAddAnotherLinks) {
    for (let round = 0; round < 2; round++) {
      const hint = round === 0 ? "employment" : "education";
      const count = round === 0 ? preExpandEmployment : preExpandEducation;
      for (let i = 0; i < count; i++) {
        const links = scraper.findAddAnotherLinks(doc, hint);
        if (links.length === 0) break;
        try {
          const el = links[0];
          el.scrollIntoView({ block: "center", behavior: "auto" });
          await new Promise((r) => setTimeout(r, 200));
          const rect = el.getBoundingClientRect();
          const x = rect.left + rect.width / 2;
          const y = rect.top + rect.height / 2;
          for (const name of ["mousedown", "mouseup", "click"]) {
            el.dispatchEvent(new MouseEvent(name, { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y }));
          }
          await new Promise((r) => setTimeout(r, 800));
        } catch (_) { }
      }
    }
  }

  logInfo("scrapeFields: calling scrapeWithLearning", { ms: Date.now() - t0 });
  const fastResult = await scrapeWithLearning(options);
  logInfo("scrapeFields: scrapeWithLearning returned", { fastPath: !!fastResult?.length, count: fastResult?.length || 0, ms: Date.now() - t0 });
  if (fastResult && fastResult.length > 0) {
    const fields = fastResult.map((f, index) => ({
      index,
      label: f.label || null,
      name: f.name || null,
      id: f.id || null,
      placeholder: f.placeholder || null,
      required: f.required || false,
      type: f.type || null,
      tag: f.tag || f.type || null,
      role: null,
      options: f.options || null,
      selector: f.selector,
      selectors: f.selectors,
      atsFieldType: f.atsFieldType || null,
      isStandardField: f.isStandardField || false,
      fingerprint: f.fingerprint,
    }));
    logInfo("Scrape: fast path completed", { totalFields: fields.length });
    return { fields };
  }

  if (scraper) {
    logInfo("scrapeFields: full DOM scrape via scraper", { ms: Date.now() - t0 });
    try {
      const scrapeOpts = {
        scope: includeNestedDocuments ? "all" : "current_document",
        includeHidden: true,
        excludePredicate: isInsideExtensionWidget,
        expandSelectOptions,
      };
      let result = expandSelectOptions && scraper.getScrapedFieldsWithExpandedOptions
        ? await scraper.getScrapedFieldsWithExpandedOptions(scrapeOpts)
        : scraper.getScrapedFields(scrapeOpts);
      if (scraper.attachShaFingerprints && result.fields?.length > 0) {
        await scraper.attachShaFingerprints(result.fields);
      }
      if (result.fields.length === 0) {
        result = scraper.getScrapedFields({
          scope: includeNestedDocuments ? "all" : "current_document",
          includeHidden: false,
          excludePredicate: isInsideExtensionWidget,
          expandSelectOptions: false,
        });
        if (scraper.attachShaFingerprints && result.fields?.length > 0) {
          await scraper.attachShaFingerprints(result.fields);
        }
      }
      if (result.fields.length > 0) {
        result.fields = await enrichFieldsWithLearnedSelectors(result.fields, atsPlatform);
        const fields = result.fields.map((f, index) => ({
          index,
          label: f.label || null,
          name: f.name || null,
          id: f.id || null,
          placeholder: f.placeholder || null,
          required: f.required,
          type: f.type || null,
          tag: f.tagName || f.tag || null,
          role: f.element?.getAttribute?.("role") || null,
          options: f.options || null,
          selector: f.selector,
          selectors: f.selectors,
          atsFieldType: f.atsFieldType,
          isStandardField: f.isStandardField,
          fingerprint: f.fingerprint,
        }));
        const preview = fields.slice(0, 15).map((f) => ({ index: f.index, type: f.type, label: f.label, id: f.id, name: f.name, required: f.required }));
        logInfo("Scrape: completed", { totalFields: fields.length, requiredFields: fields.filter((f) => f.required).length, fields: preview });
        return { fields };
      }
    } catch (e) {
      logWarn("Enhanced field scraper failed, falling back", { error: String(e) });
    }
  } else {
    logInfo("scrapeFields: no scraper, using legacy getFillableFields", { ms: Date.now() - t0 });
  }

  let fillable = getFillableFields(includeNestedDocuments || true, true);
  if (fillable.length === 0) fillable = getFillableFields(true, false);
  if (fillable.length === 0) fillable = getFillableFields(true, true);

  const fields = fillable.map((el, index) => {
    const meta = getFieldMeta(el);
    const opts = meta.tag === "select"
      ? Array.from(el.options || []).map((o) => (o.text || "").trim()).filter(Boolean)
      : null;
    const id = meta.id || null;
    const selector = id ? `#${CSS.escape(id)}` : null;
    return {
      index,
      label: meta.label || null,
      name: meta.name || null,
      id,
      selector,
      placeholder: meta.placeholder || null,
      required: meta.required,
      type: meta.type || null,
      tag: meta.tag || null,
      role: meta.role || null,
      options: opts,
    };
  });
  const preview = fields.slice(0, 15).map((f) => ({ index: f.index, type: f.type, label: f.label, id: f.id, name: f.name, required: f.required }));
  logInfo("Scrape: completed (legacy)", { totalFields: fields.length, requiredFields: fields.filter((f) => f.required).length, fields: preview });
  return { fields };
}
