/**
 * Security Manager - Encrypted token storage (AES-256-GCM)
 * Works in content scripts, popup, and service worker (background)
 */
(function () {
  "use strict";

  const ctx = typeof window !== "undefined" ? window : typeof self !== "undefined" ? self : globalThis;

  class SecurityManager {
    constructor() {
      this.encryptionKey = null;
    }

    async init() {
      let { encryptionKey } = await chrome.storage.local.get("encryptionKey");
      if (!encryptionKey) {
        const key = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
        const exported = await crypto.subtle.exportKey("jwk", key);
        encryptionKey = JSON.stringify(exported);
        await chrome.storage.local.set({ encryptionKey });
      }
      const keyData = JSON.parse(encryptionKey);
      this.encryptionKey = await crypto.subtle.importKey("jwk", keyData, { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
    }

    async encryptToken(token) {
      if (!this.encryptionKey) await this.init();
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const encoded = new TextEncoder().encode(token);
      const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, this.encryptionKey, encoded);
      const combined = new Uint8Array(iv.length + encrypted.byteLength);
      combined.set(iv);
      combined.set(new Uint8Array(encrypted), iv.length);
      return btoa(String.fromCharCode(...combined));
    }

    async decryptToken(encryptedToken) {
      if (!this.encryptionKey) await this.init();
      const combined = Uint8Array.from(atob(encryptedToken), (c) => c.charCodeAt(0));
      const iv = combined.slice(0, 12);
      const ciphertext = combined.slice(12);
      const decrypted = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, this.encryptionKey, ciphertext);
      return new TextDecoder().decode(decrypted);
    }

    async storeToken(token) {
      try {
        const encrypted = await this.encryptToken(token);
        await chrome.storage.local.set({ accessToken: encrypted });
      } catch (e) {
        await chrome.storage.local.set({ accessToken: token });
      }
    }

    async getToken() {
      const { accessToken } = await chrome.storage.local.get("accessToken");
      if (!accessToken) return null;
      try {
        return await this.decryptToken(accessToken);
      } catch (e) {
        return accessToken;
      }
    }
  }

  ctx.__SECURITY_MANAGER__ = new SecurityManager();
})();
