/**
 * Selector Resolver - Multi-strategy element resolution for form filling
 * Fallback chain: id -> data-testid -> data-automation-id -> name -> xpath -> fingerprint
 */
class SelectorResolver {
  constructor() {
    this.strategies = [
      this.byId,
      this.byDataTestId,
      this.byDataAutomationId,
      this.byAriaLabel,
      this.byName,
      this.byXPath,
      this.byFingerprint,
      this.bySiblingText,
    ];
  }

  resolve(fieldMeta, doc = document) {
    for (const strategy of this.strategies) {
      try {
        const el = strategy.call(this, fieldMeta, doc);
        if (el && this.isValidTarget(el)) {
          if (window.__CONFIG__?.log) window.__CONFIG__.log("[Resolver] Found via", strategy.name);
          return el;
        }
      } catch (_) {}
    }
    return null;
  }

  byId(fieldMeta, doc) {
    if (!fieldMeta.domId) return null;
    return doc.getElementById(fieldMeta.domId);
  }

  byDataTestId(fieldMeta, doc) {
    const testId = fieldMeta.domId || fieldMeta.name;
    if (!testId) return null;
    return doc.querySelector(`[data-testid="${testId}"]`);
  }

  byDataAutomationId(fieldMeta, doc) {
    if (!fieldMeta.name) return null;
    return doc.querySelector(`[data-automation-id*="${fieldMeta.name}"]`);
  }

  byAriaLabel(fieldMeta, doc) {
    if (!fieldMeta.label) return null;
    return doc.querySelector(`[aria-label="${fieldMeta.label}"]`);
  }

  byName(fieldMeta, doc) {
    if (!fieldMeta.name) return null;
    return doc.querySelector(
      `input[name="${fieldMeta.name}"], textarea[name="${fieldMeta.name}"], select[name="${fieldMeta.name}"]`
    );
  }

  byXPath(fieldMeta, doc) {
    if (!fieldMeta.xpath) return null;
    const result = doc.evaluate(fieldMeta.xpath, doc, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
    return result.singleNodeValue;
  }

  byFingerprint(fieldMeta, doc) {
    if (!fieldMeta.type || !fieldMeta.label) return null;
    const candidates = doc.querySelectorAll(`input[type="${fieldMeta.type}"], textarea, select`);
    for (const el of candidates) {
      const label = this.getElementLabel(el, doc);
      if (this.labelsMatch(label, fieldMeta.label)) return el;
    }
    return null;
  }

  bySiblingText(fieldMeta, doc) {
    if (!fieldMeta.label) return null;
    const body = doc.body;
    if (!body) return null;
    const walker = doc.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) {
      if (n.textContent?.trim()) nodes.push(n);
    }
    for (const node of nodes) {
      if (node.textContent.trim().toLowerCase().includes(fieldMeta.label.toLowerCase())) {
        const input = this.findNearestInput(node, doc);
        if (input) return input;
      }
    }
    return null;
  }

  isValidTarget(el) {
    if (!el) return false;
    if (el.offsetParent === null) return false;
    if (el.disabled) return false;
    return true;
  }

  getElementLabel(el, doc) {
    if (el.id) {
      const label = doc.querySelector(`label[for="${el.id}"]`);
      if (label) return label.textContent?.trim() || "";
    }
    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
    if (el.getAttribute("placeholder")) return el.getAttribute("placeholder");
    return "";
  }

  labelsMatch(a, b) {
    const n = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    return n(a) === n(b);
  }

  findNearestInput(node, doc) {
    let current = node.parentElement;
    let depth = 0;
    while (current && depth < 5) {
      const input = current.querySelector("input, textarea, select");
      if (input) return input;
      current = current.parentElement;
      depth++;
    }
    return null;
  }
}

if (typeof window !== "undefined") {
  window.__SELECTOR_RESOLVER__ = new SelectorResolver();
}
