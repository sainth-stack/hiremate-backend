/**
 * Error Handler - Global error capture and optional backend reporting
 */
class ErrorHandler {
  constructor() {
    this.errors = [];
    this.maxErrors = 100;
    this._reportThrottle = null;
    this._lastReport = 0;
    this.setupGlobalHandlers();
  }

  setupGlobalHandlers() {
    window.addEventListener("unhandledrejection", (event) => {
      this.captureError({
        type: "unhandledRejection",
        message: event.reason?.message || String(event.reason),
        stack: event.reason?.stack,
        timestamp: Date.now(),
      });
      event.preventDefault();
    });

    window.addEventListener("error", (event) => {
      this.captureError({
        type: "globalError",
        message: event.message,
        source: event.filename,
        line: event.lineno,
        column: event.colno,
        stack: event.error?.stack,
        timestamp: Date.now(),
      });
    });
  }

  captureError(error) {
    console.error("[ErrorHandler]", error);
    this.errors.push(error);
    if (this.errors.length > this.maxErrors) this.errors.shift();
    this.sendErrorToBackend(error);
  }

  async sendErrorToBackend(error) {
    try {
      const config = window.__CONFIG__;
      if (!config?.get("enableAnalytics")) return;
      if (Date.now() - this._lastReport < 5000) return;
      this._lastReport = Date.now();

      const apiBase = await config.getApiBase();
      let token = null;
      try {
        if (window.__SECURITY_MANAGER__) token = await window.__SECURITY_MANAGER__.getToken();
        else {
          const d = await chrome.storage.local.get(["accessToken"]);
          token = d.accessToken;
        }
      } catch (_) {}

      await fetch(`${apiBase}/chrome-extension/errors`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({
          ...error,
          extensionVersion: chrome?.runtime?.getManifest?.()?.version || "1.0.0",
          userAgent: navigator.userAgent,
          url: window.location?.href || "",
          environment: config.env,
        }),
      });
    } catch (_) {}
  }

  wrapAsync(fn, context = "unknown") {
    return async (...args) => {
      try {
        return await fn(...args);
      } catch (err) {
        this.captureError({
          type: "asyncError",
          context,
          message: err?.message || String(err),
          stack: err?.stack,
          timestamp: Date.now(),
        });
        throw err;
      }
    };
  }
}

if (typeof window !== "undefined") {
  window.__ERROR_HANDLER__ = new ErrorHandler();
}
