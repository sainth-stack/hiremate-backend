/**
 * OpsBrain Extension - Environment Configuration
 * Centralized config for dev vs production, API URLs, cache TTLs, debug flags.
 */
class ConfigManager {
  constructor() {
    this.env = this.detectEnvironment();
    this.config = this.loadConfig();
  }

  detectEnvironment() {
    try {
      const extensionId = chrome?.runtime?.id || "";
      const devIds = ["development", "localhost"];
      if (extensionId && devIds.some((d) => extensionId.includes(d))) return "development";
      const apiBase = typeof window !== "undefined" && window.__STORED_API_BASE__;
      if (apiBase && apiBase.includes("localhost")) return "development";
      return "production";
    } catch (_) {
      return "development";
    }
  }

  loadConfig() {
    const configs = {
      development: {
        apiBase: "http://localhost:8000/api",
        loginPageUrl: "http://localhost:5173/login",
        appUrl: "http://localhost:5173",
        enableDebugLogs: true,
        enableAnalytics: false,
        cacheTTL: {
          autofillContext: 10 * 60 * 1000,
          keywordAnalysis: 30 * 60 * 1000,
          formMappings: 5 * 60 * 1000,
        },
      },
      production: {
        apiBase: "http://localhost:8000/api",
        loginPageUrl: "http://localhost:5173/login",
        appUrl: "http://localhost:5173",
        enableDebugLogs: false,
        enableAnalytics: true,
        cacheTTL: {
          autofillContext: 30 * 60 * 1000,
          keywordAnalysis: 60 * 60 * 1000,
          formMappings: 15 * 60 * 1000,
        },
      },
    };
    return configs[this.env] || configs.development;
  }

  get(key) {
    return this.config[key];
  }

  async getApiBase() {
    try {
      const stored = await chrome.storage.local.get(["apiBase"]);
      return stored.apiBase || this.config.apiBase;
    } catch (_) {
      return this.config.apiBase;
    }
  }

  log(...args) {
    if (this.config.enableDebugLogs) {
      console.log("[OpsBrain]", ...args);
    }
  }

  error(...args) {
    console.error("[OpsBrain][ERROR]", ...args);
  }
}

if (typeof window !== "undefined") {
  window.__CONFIG__ = new ConfigManager();
}
