// ─── Form Structure Learning & Fast Scrape ────────────────────────────────
// Depends on: ENRICH_TIMEOUT_MS, FORM_STRUCTURE_FETCH_TIMEOUT_MS (consts.js)
//             logInfo, logWarn (utils.js)
//             getApiBase, getAuthHeaders (content.js)

/**
 * Fetch server's best-known selectors for fingerprints; prepend to each field's selector bundle.
 */
async function enrichFieldsWithLearnedSelectors(fields, atsPlatform) {
  const t0 = Date.now();
  if (!fields?.length) return fields;
  const fps = fields.map((f) => f.fingerprint).filter(Boolean);
  if (!fps.length) return fields;
  logInfo("enrichFieldsWithLearnedSelectors: calling best-batch", { fieldCount: fields.length });
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ENRICH_TIMEOUT_MS);
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    if (!headers?.Authorization) return fields;
    const res = await fetch(`${apiBase}/chrome-extension/selectors/best-batch`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ fps, ats_platform: atsPlatform || "unknown" }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) return fields;
    const { selectors } = await res.json();
    logInfo("enrichFieldsWithLearnedSelectors: done", { learnedCount: Object.keys(selectors || {}).length, ms: Date.now() - t0 });
    return fields.map((f) => {
      const learned = (selectors[f.fingerprint] || []).map((s) => ({
        ...s,
        priority: 0,
        source: "learned",
      }));
      return {
        ...f,
        selectors: [...learned, ...(f.selectors || [])],
        selector: learned[0]?.selector || f.selector,
      };
    });
  } catch (e) {
    logWarn("enrichFieldsWithLearnedSelectors failed", { error: String(e) });
    return fields;
  }
}

/**
 * Check IndexedDB formStructures cache first, then server. Timeout only on network fetch.
 * Skips cache read/write when hm_cache_enabled is false in storage.
 */
async function getKnownFormStructure(domain, url) {
  const t0 = Date.now();
  let useCache = true;
  try {
    const stored = await chrome.storage.local.get(["hm_cache_enabled"]);
    useCache = stored.hm_cache_enabled !== false;
  } catch (_) { }
  const cacheManager = window.__CACHE_MANAGER__;
  logInfo("getKnownFormStructure: entry", { domain, hasCacheManager: !!cacheManager, useCache });
  if (useCache) {
    try {
      if (cacheManager?.getCachedFormStructure) {
        logInfo("getKnownFormStructure: checking IndexedDB cache");
        const cached = await cacheManager.getCachedFormStructure(domain);
        if (cached) {
          logInfo("getKnownFormStructure: cache hit", { domain, ms: Date.now() - t0 });
          return cached;
        }
      }
    } catch (_) { }
  }
  try {
    logInfo("getKnownFormStructure: fetching from server", { domain });
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FORM_STRUCTURE_FETCH_TIMEOUT_MS);
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const res = await fetch(
      `${apiBase}/chrome-extension/form-structure/check?domain=${encodeURIComponent(domain)}&url=${encodeURIComponent(url || "")}`,
      { headers, signal: controller.signal }
    );
    clearTimeout(timer);
    if (!res.ok) return null;
    const data = await res.json();
    logInfo("getKnownFormStructure: server response", { found: data?.found, ms: Date.now() - t0 });
    if (!data.found) return null;
    if (useCache && cacheManager?.setCachedFormStructure) {
      await cacheManager.setCachedFormStructure(domain, data);
    }
    return data;
  } catch (e) {
    logWarn("getKnownFormStructure: failed", { error: String(e) });
    return null;
  }
}

/**
 * Fast scrape using known field fingerprints + best selectors. Returns null if <50% found.
 */
async function fastScrapeWithKnownStructure(knownStructure) {
  const expectedFps = knownStructure.field_fps || [];
  const bestSelectors = knownStructure.best_selectors || {};
  const results = [];
  for (const fp of expectedFps) {
    const best = bestSelectors[fp];
    if (!best?.selector) continue;
    const el = document.querySelector(best.selector);
    if (!el) continue;
    const label =
      el.getAttribute("aria-label") ||
      (el.labels?.[0]?.textContent?.trim()) ||
      el.getAttribute("placeholder") ||
      el.getAttribute("name") ||
      "";
    results.push({
      fingerprint: fp,
      label,
      type: (el.type || el.tagName || "").toLowerCase(),
      selector: best.selector,
      selectors: [{ selector: best.selector, type: best.type || "css", priority: 0, source: "learned" }],
      options: el.tagName === "SELECT" ? Array.from(el.options || []).map((o) => (o.text || "").trim()).filter(Boolean) : [],
      source: "fast_scrape",
    });
  }
  if (results.length < expectedFps.length * 0.5) {
    logInfo("Fast scrape found only", results.length, "/", expectedFps.length, "— falling back");
    return null;
  }
  logInfo("Fast scrape — known structure, confidence:", knownStructure.confidence);
  return results;
}

/**
 * Smart scrape: fast path if known form, full DOM scan otherwise.
 */
async function scrapeWithLearning(options) {
  const t0 = Date.now();
  const domain = location.hostname;
  const url = location.href;
  logInfo("scrapeWithLearning: start", { domain });

  let knownStructure = null;
  try {
    knownStructure = await getKnownFormStructure(domain, url);
  } catch (e) {
    logWarn("scrapeWithLearning: getKnownFormStructure failed", { error: String(e), ms: Date.now() - t0 });
  }

  if (knownStructure && knownStructure.confidence > 0.85) {
    const fastResult = await fastScrapeWithKnownStructure(knownStructure);
    if (fastResult && fastResult.length > 0) {
      const ats = window.__OPSBRAIN_ATS__ || (window.__HIREMATE_FIELD_SCRAPER__?.detectPlatform?.(document) || "unknown");
      return await enrichFieldsWithLearnedSelectors(fastResult, ats);
    }
  }
  logInfo("scrapeWithLearning: full DOM path (no fast path)", { ms: Date.now() - t0 });
  return null;
}
