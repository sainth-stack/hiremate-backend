/**
 * Request Manager - Deduplication and in-flight tracking for API calls
 * Prevents duplicate keyword analysis / autofill context requests
 */
class RequestManager {
  constructor() {
    this.inFlightRequests = new Map();
    this.requestCache = new Map();
    this.CACHE_TTL = 30 * 60 * 1000;
  }

  async dedupedRequest(cacheKey, requestFn, ttl = this.CACHE_TTL) {
    const cached = this.requestCache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < ttl) {
      if (window.__CONFIG__?.log) window.__CONFIG__.log("[RequestManager] Cache hit:", cacheKey);
      return cached.data;
    }

    if (this.inFlightRequests.has(cacheKey)) {
      if (window.__CONFIG__?.log) window.__CONFIG__.log("[RequestManager] Deduping:", cacheKey);
      return this.inFlightRequests.get(cacheKey);
    }

    const promise = requestFn()
      .then((data) => {
        this.requestCache.set(cacheKey, { data, timestamp: Date.now() });
        this.inFlightRequests.delete(cacheKey);
        return data;
      })
      .catch((err) => {
        this.inFlightRequests.delete(cacheKey);
        throw err;
      });

    this.inFlightRequests.set(cacheKey, promise);
    return promise;
  }

  clearCache(cacheKey) {
    this.requestCache.delete(cacheKey);
  }

  clearAll() {
    this.requestCache.clear();
    this.inFlightRequests.clear();
  }
}

if (typeof window !== "undefined") {
  window.__REQUEST_MANAGER__ = new RequestManager();
}
