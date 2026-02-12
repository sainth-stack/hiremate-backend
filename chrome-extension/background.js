const DB_NAME = "JobAutofillDB";
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
