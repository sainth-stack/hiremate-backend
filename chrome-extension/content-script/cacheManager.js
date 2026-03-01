/**
 * Cache Manager - IndexedDB persistent cache for keyword analysis, form mappings
 * v2: Adds fieldMappings (fp->mapping, 7d TTL), pendingSubmits, profileVersion
 */
const STORES = {
  keywordAnalysis: { keyPath: "url", ttl: 45 * 60 * 1000 },
  fieldMappings: { keyPath: "fp", ttl: 7 * 86400 * 1000 },
  formStructures: { keyPath: "domain", ttl: 7 * 86400 * 1000 },
  pendingSubmits: { keyPath: "id", ttl: 24 * 3600 * 1000 },
  profileVersion: { keyPath: "key", ttl: Infinity },
};

class CacheManager {
  constructor() {
    this.dbName = "OpsBrainCache";
    this.version = 3;
    this.db = null;
  }

  async init() {
    if (this.db) return;
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        if (window.__CONFIG__?.log) window.__CONFIG__.log("[CacheManager] Initialized v2");
        resolve();
      };
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains("keywordAnalysis")) {
          const store = db.createObjectStore("keywordAnalysis", { keyPath: "url" });
          store.createIndex("timestamp", "timestamp", { unique: false });
        }
        if (!db.objectStoreNames.contains("formMappings")) {
          const store = db.createObjectStore("formMappings", { keyPath: "hash" });
          store.createIndex("timestamp", "timestamp", { unique: false });
        }
        if (!db.objectStoreNames.contains("autofillContext")) {
          const store = db.createObjectStore("autofillContext", { keyPath: "id" });
          store.createIndex("timestamp", "timestamp", { unique: false });
        }
        if (!db.objectStoreNames.contains("fieldMappings")) {
          db.createObjectStore("fieldMappings", { keyPath: "fp" });
        }
        if (!db.objectStoreNames.contains("pendingSubmits")) {
          db.createObjectStore("pendingSubmits", { keyPath: "id" });
        }
        if (!db.objectStoreNames.contains("profileVersion")) {
          db.createObjectStore("profileVersion", { keyPath: "key" });
        }
        if (!db.objectStoreNames.contains("formStructures")) {
          db.createObjectStore("formStructures", { keyPath: "domain" });
        }
      };
    });
  }

  async get(storeName, key) {
    if (!this.db) await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([storeName], "readonly");
      const store = tx.objectStore(storeName);
      const req = store.get(key);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async set(storeName, data) {
    if (!this.db) await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([storeName], "readwrite");
      const store = tx.objectStore(storeName);
      const req = store.put({ ...data, timestamp: Date.now() });
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  }

  async getCachedMappings(fps) {
    if (!this.db) await this.init();
    const out = {};
    const ttl = STORES.fieldMappings?.ttl ?? 7 * 86400 * 1000;
    const now = Date.now();
    for (const fp of fps || []) {
      try {
        const rec = await this.get("fieldMappings", fp);
        if (rec && rec.cached_at && (now - rec.cached_at) < ttl) {
          out[fp] = rec.mapping;
        }
      } catch (_) {}
    }
    return out;
  }

  async setCachedMappings(mappingsByFp) {
    if (!this.db) await this.init();
    const now = Date.now();
    for (const [fp, mapping] of Object.entries(mappingsByFp || {})) {
      try {
        await new Promise((resolve, reject) => {
          const tx = this.db.transaction(["fieldMappings"], "readwrite");
          tx.objectStore("fieldMappings").put({ fp, mapping, cached_at: now });
          tx.oncomplete = () => resolve();
          tx.onerror = () => reject(tx.error);
        });
      } catch (_) {}
    }
  }

  async getPendingSubmission() {
    if (!this.db) await this.init();
    try {
      return await this.get("pendingSubmits", "current") || null;
    } catch (_) {
      return null;
    }
  }

  async setPendingSubmission(data) {
    if (!this.db) await this.init();
    try {
      await this.set("pendingSubmits", { id: "current", ...data, timestamp: Date.now() });
    } catch (_) {}
  }

  async clearPendingSubmission() {
    if (!this.db) await this.init();
    try {
      const tx = this.db.transaction(["pendingSubmits"], "readwrite");
      tx.objectStore("pendingSubmits").delete("current");
      await new Promise((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    } catch (_) {}
  }

  async getCachedFormStructure(domain) {
    if (!this.db) await this.init();
    try {
      const rec = await this.get("formStructures", domain);
      if (window.__CONFIG__?.log) window.__CONFIG__.log("[CacheManager] getCachedFormStructure", domain, rec ? "hit" : "miss");
      if (!rec) return null;
      const ttl = STORES.formStructures?.ttl ?? 7 * 86400 * 1000;
      if (rec.cached_at && Date.now() - rec.cached_at > ttl) return null;
      return rec.data;
    } catch (_) {
      return null;
    }
  }

  async setCachedFormStructure(domain, data) {
    if (!this.db) await this.init();
    try {
      const tx = this.db.transaction(["formStructures"], "readwrite");
      tx.objectStore("formStructures").put({ domain, data, cached_at: Date.now() });
      await new Promise((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    } catch (e) {
      if (window.__CONFIG__?.log) window.__CONFIG__.log("[CacheManager] setCachedFormStructure failed", e);
    }
  }

  async onProfileUpdated(newProfileHash) {
    if (!this.db) await this.init();
    try {
      const stored = await this.get("profileVersion", "hash");
      if (stored?.value !== newProfileHash) {
        const tx = this.db.transaction(["fieldMappings"], "readwrite");
        tx.objectStore("fieldMappings").clear();
        await new Promise((resolve, reject) => {
          tx.oncomplete = () => resolve();
          tx.onerror = () => reject(tx.error);
        });
        await this.set("profileVersion", { key: "hash", value: newProfileHash, timestamp: Date.now() });
      }
    } catch (_) {}
  }

  async cleanup(storeName, maxAge = 7 * 24 * 60 * 60 * 1000) {
    if (!this.db) await this.init();
    const cutoff = Date.now() - maxAge;
    const tx = this.db.transaction([storeName], "readwrite");
    const store = tx.objectStore(storeName);
    const index = store.index("timestamp");
    const range = IDBKeyRange.upperBound(cutoff);
    return new Promise((resolve) => {
      const req = index.openCursor(range);
      let deletedCount = 0;
      req.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor) {
          cursor.delete();
          deletedCount++;
          cursor.continue();
        } else {
          if (window.__CONFIG__?.log) window.__CONFIG__.log("[CacheManager] Cleaned", deletedCount, "from", storeName);
          resolve(deletedCount);
        }
      };
      req.onerror = () => resolve(0);
    });
  }
}

if (typeof window !== "undefined") {
  window.__CACHE_MANAGER__ = new CacheManager();
}
