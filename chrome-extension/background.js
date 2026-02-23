const DB_NAME = "JobAutofillDB";
const HIREMATE_ORIGINS = [
  "http://localhost:5173",
  "http://127.0.0.1:5173",
  "http://localhost:5174",
  "http://127.0.0.1:5174",
  "https://hiremate.ai",
  "https://www.hiremate.ai",
  "https://app.hiremate.ai",
  "https://hiremate.com",
  "https://www.hiremate.com",
];
const DB_VERSION = 1;
const STORE_NAME = "resume";
const LOG_PREFIX = "[JobAutofill][background]";

function logInfo(message, meta) {
  if (meta !== undefined) console.info(LOG_PREFIX, message, meta);
  else console.info(LOG_PREFIX, message);
}

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => resolve(req.result);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
  });
}

async function saveResume(buffer, name) {
  logInfo("Saving resume in IndexedDB", {
    fileName: name || "resume.pdf",
    bytes: Array.isArray(buffer) ? buffer.length : 0,
  });
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    store.put({ id: "current", buffer, name, updatedAt: Date.now() });
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => reject(tx.error);
  });
}

async function getResume() {
  logInfo("Fetching resume from IndexedDB");
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const req = tx.objectStore(STORE_NAME).get("current");
    req.onsuccess = () => {
      db.close();
      resolve(req.result || null);
    };
    req.onerror = () => reject(req.error);
  });
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "SAVE_RESUME") {
    const { buffer, name } = msg.payload || {};
    if (!buffer || !name) {
      sendResponse({ ok: false, error: "Missing buffer or name" });
      return true;
    }
    saveResume(buffer, name)
      .then(() => {
        logInfo("Resume saved successfully", { fileName: name });
        sendResponse({ ok: true });
      })
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (msg.type === "OPEN_LOGIN_TAB") {
    const url = msg.url || "http://localhost:5173/login";
    chrome.tabs.create({ url }).then(() => sendResponse({ ok: true })).catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (msg.type === "SYNC_TOKEN_TO_HIREMATE_TAB") {
    const { token } = msg;
    if (!token) return false;
    (async () => {
      try {
        const { loginPageUrl } = (await chrome.storage.local.get(["loginPageUrl"])) || {};
        const allowedOrigins = [...HIREMATE_ORIGINS];
        if (loginPageUrl) {
          try {
            const customOrigin = new URL(loginPageUrl).origin;
            if (!allowedOrigins.includes(customOrigin)) allowedOrigins.push(customOrigin);
          } catch {}
        }
        const tabs = await chrome.tabs.query({});
        const hiremateTab = tabs.find((t) => {
          if (!t.url) return false;
          try {
            return allowedOrigins.includes(new URL(t.url).origin);
          } catch {
            return false;
          }
        });
        if (hiremateTab?.id) {
          await chrome.scripting.executeScript({
            target: { tabId: hiremateTab.id },
            func: (t) => {
              try {
                localStorage.setItem("token", t);
                localStorage.setItem("access_token", t);
              } catch {}
            },
            args: [token],
          });
          logInfo("Token synced to HireMate tab localStorage");
        }
      } catch (_) {}
    })();
    return false; // Fire-and-forget, don't block sender
  }

  if (msg.type === "FETCH_TOKEN_FROM_OPEN_TAB") {
    (async () => {
      try {
        const { loginPageUrl } = (await chrome.storage.local.get(["loginPageUrl"])) || {};
        const allowedOrigins = [...HIREMATE_ORIGINS];
        if (loginPageUrl) {
          try {
            const customOrigin = new URL(loginPageUrl).origin;
            if (!allowedOrigins.includes(customOrigin)) allowedOrigins.push(customOrigin);
          } catch {}
        }
        const tabs = await chrome.tabs.query({});
        const hiremateTab = tabs.find((t) => {
          if (!t.url) return false;
          try {
            const origin = new URL(t.url).origin;
            return allowedOrigins.includes(origin);
          } catch {
            return false;
          }
        });
        if (!hiremateTab?.id) {
          sendResponse({ ok: true, token: null });
          return;
        }
        const results = await chrome.scripting.executeScript({
          target: { tabId: hiremateTab.id },
          func: () => {
            try {
              return localStorage.getItem("token") || localStorage.getItem("access_token") || null;
            } catch {
              return null;
            }
          },
        });
        const token = results?.[0]?.result || null;
        if (token) {
          await chrome.storage.local.set({ accessToken: token });
          logInfo("Token synced from open HireMate tab");
        }
        sendResponse({ ok: true, token });
      } catch (err) {
        logInfo("FETCH_TOKEN_FROM_OPEN_TAB error", err);
        sendResponse({ ok: false, token: null });
      }
    })();
    return true;
  }

  if (msg.type === "GET_ALL_FRAMES_HTML") {
    (async () => {
      try {
        const tabId = sender.tab?.id;
        if (!tabId) {
          sendResponse({ ok: false, html: null, error: "No tab" });
          return;
        }
        const results = await chrome.scripting.executeScript({
          target: { tabId, allFrames: true },
          func: () => {
            try {
              const el = document.documentElement || document.body;
              return el ? (el.outerHTML || el.innerHTML || "").slice(0, 1500000) : "";
            } catch {
              return "";
            }
          },
        });
        const htmls = (results || [])
          .map((r) => (r.result && typeof r.result === "string" ? r.result : ""))
          .filter((h) => h && h.length > 200);
        const combined = htmls.length ? htmls.join("\n<!--FRAME_SEP-->\n") : null;
        sendResponse({ ok: true, html: combined });
      } catch (err) {
        sendResponse({ ok: false, html: null, error: String(err) });
      }
    })();
    return true;
  }

  if (msg.type === "SCRAPE_ALL_FRAMES") {
    (async () => {
      try {
        const tabId = msg.tabId ?? sender.tab?.id;
        if (!tabId) {
          sendResponse({ ok: false, fields: [], error: "No tab" });
          return;
        }
        const scope = msg.scope || "all";
        let frameIds = [0];
        try {
          const frames = await chrome.webNavigation.getAllFrames({ tabId });
          frameIds = (frames || []).map((f) => f.frameId).filter((id) => id != null);
          if (!frameIds.length) frameIds = [0];
          frameIds = [...new Set(frameIds)];
        } catch (_) {}

        const results = [];
        for (const frameId of frameIds) {
          try {
            let res = await chrome.tabs.sendMessage(tabId, { type: "SCRAPE_FIELDS", payload: { scope } }, { frameId });
            results.push({ frameId, ok: true, res });
          } catch (e) {
            if (e?.message?.includes("Receiving end does not exist")) {
              try {
                await chrome.scripting.executeScript({ target: { tabId, frameIds: [frameId] }, files: ["content.js"] });
                const res = await chrome.tabs.sendMessage(tabId, { type: "SCRAPE_FIELDS", payload: { scope } }, { frameId });
                results.push({ frameId, ok: true, res });
              } catch (e2) {
                results.push({ frameId, ok: false, err: String(e2) });
              }
            } else {
              results.push({ frameId, ok: false, err: String(e) });
            }
          }
        }

        const mergedFields = [];
        let idx = 0;
        for (const r of results) {
          if (!r.ok || !r.res?.fields?.length) continue;
          for (const f of r.res.fields) {
            mergedFields.push({ ...f, index: idx, frameId: r.frameId, frameLocalIndex: f.index, domId: f.id || null });
            idx += 1;
          }
        }
        sendResponse({ ok: true, fields: mergedFields });
      } catch (err) {
        logInfo("SCRAPE_ALL_FRAMES error", err);
        sendResponse({ ok: false, fields: [], error: String(err) });
      }
    })();
    return true;
  }

  if (msg.type === "FILL_ALL_FRAMES") {
    (async () => {
      try {
        const { tabId: msgTabId, valuesByFrame, resumeData } = msg.payload || {};
        const tabId = msgTabId ?? sender?.tab?.id;
        if (!tabId || !valuesByFrame) {
          sendResponse({ ok: false, totalFilled: 0, totalResumes: 0, error: "Missing tabId or valuesByFrame" });
          return;
        }
        let frameIds = Object.keys(valuesByFrame);
        if (!frameIds.length) {
          try {
            const frames = await chrome.webNavigation.getAllFrames({ tabId });
            frameIds = (frames || []).map((f) => String(f.frameId)).filter(Boolean);
            if (!frameIds.length) frameIds = ["0"];
          } catch (_) {
            frameIds = ["0"];
          }
        }
        let totalFilled = 0;
        let totalResumes = 0;
        for (const fid of frameIds) {
          try {
            const vals = valuesByFrame[fid] || {};
            let res = await chrome.tabs.sendMessage(tabId, {
              type: "FILL_WITH_VALUES",
              payload: { values: vals, resumeData, scope: "current_document" }
            }, { frameId: parseInt(fid, 10) || 0 });
            if (res?.ok) {
              totalFilled += res.filledCount || 0;
              totalResumes += res.resumeUploadCount || 0;
            }
          } catch (e) {
            if (e?.message?.includes("Receiving end does not exist")) {
              try {
                await chrome.scripting.executeScript({ target: { tabId, frameIds: [parseInt(fid, 10) || 0] }, files: ["content.js"] });
                const res = await chrome.tabs.sendMessage(tabId, {
                  type: "FILL_WITH_VALUES",
                  payload: { values: valuesByFrame[fid] || {}, resumeData, scope: "current_document" }
                }, { frameId: parseInt(fid, 10) || 0 });
                if (res?.ok) {
                  totalFilled += res.filledCount || 0;
                  totalResumes += res.resumeUploadCount || 0;
                }
              } catch (_) {}
            }
          }
        }
        sendResponse({ ok: true, totalFilled, totalResumes });
      } catch (err) {
        sendResponse({ ok: false, totalFilled: 0, totalResumes: 0, error: String(err) });
      }
    })();
    return true;
  }

  if (msg.type === "GET_RESUME") {
    getResume()
      .then((row) => {
        if (!row) {
          logInfo("No resume found in storage");
          sendResponse({ ok: true, data: null });
          return;
        }
        logInfo("Resume loaded from storage", { fileName: row.name || "resume.pdf" });
        sendResponse({
          ok: true,
          data: {
            buffer: row.buffer,
            name: row.name || "resume.pdf",
          },
        });
      })
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  return false;
});

chrome.runtime.onInstalled.addListener(() => {
  // Optional: set default profile keys so popup can show placeholders
});

// Handle extension icon click (when popup is not used)
chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id) return;
  
  try {
    // Try to send message to content script
    await chrome.tabs.sendMessage(tab.id, { type: "SHOW_WIDGET" });
  } catch (error) {
    // Content script not injected, inject it first
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["content.js"]
      });
      // Retry after injection
      await chrome.tabs.sendMessage(tab.id, { type: "SHOW_WIDGET" });
    } catch (err) {
      console.error("[Background] Failed to show widget:", err);
    }
  }
});
