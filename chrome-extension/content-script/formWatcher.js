/**
 * Form Watcher - SPA form change detection via MutationObserver
 * Invalidates caches when form structure changes (React/Vue dynamic forms)
 */
class FormWatcher {
  constructor() {
    this.lastFormHash = null;
    this.observer = null;
    this.debounceTimer = null;
  }

  start() {
    if (typeof document === "undefined" || !document.body) return;
    if (this.observer) return;

    this.observer = new MutationObserver(() => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => this.checkForFormChanges(), 500);
    });

    this.observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    if (window.__CONFIG__?.log) window.__CONFIG__.log("[FormWatcher] Started");
  }

  stop() {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
  }

  checkForFormChanges() {
    const currentHash = this.computeFormHash();
    if (currentHash !== this.lastFormHash) {
      if (window.__CONFIG__?.log) window.__CONFIG__.log("[FormWatcher] Form changed");
      this.lastFormHash = currentHash;
      this.onFormChanged();
    }
  }

  computeFormHash() {
    try {
      const forms = document.querySelectorAll("form");
      const inputs = document.querySelectorAll("input, textarea, select");
      const types = Array.from(inputs).map((i) => i.type || i.tagName).join(",");
      return `forms:${forms.length}|inputs:${inputs.length}|types:${types}`;
    } catch (_) {
      return "";
    }
  }

  onFormChanged() {
    document.dispatchEvent(
      new CustomEvent("opsbrain-form-changed", { detail: { timestamp: Date.now() } })
    );
  }
}

if (typeof window !== "undefined") {
  window.__FORM_WATCHER__ = new FormWatcher();
}
