const DB_NAME = "JobAutofillDB";
// Full content script list — must match manifest so frames have scraper/filler when injected on retry
const CONTENT_SCRIPT_FILES = [
  "config.js",
  "security-manager.js",
  "content-script/requestManager.js",
  "content-script/cacheManager.js",
  "content-script/error-handler.js",
  "content-script/pageDetector.js",
  "content-script/formWatcher.js",
  "content-script/selectorResolver.js",
  "content-script/professionalWidget.js",
  "content-script/fieldScraper.js",
  "content-script/humanFiller.js",
  "content-script/workday-step-manager.js",
  "content-script/consts.js",
  "content-script/icons.js",
  "content-script/utils.js",
  "content-script/dom-utils.js",
  "content-script/features/keyword-match.js",
  "content-script/features/autofill-stats.js",
  "content-script/features/accordion.js",
  "content-script/services/form-learning.js",
  "content-script/services/api-service.js",
  "content-script/services/autofill-context.js",
  "content-script/features/page-detection.js",
  "content-script/features/scrape-fields.js",
  "content-script/features/fill-engine.js",
  "content-script/features/keyword-analysis.js",
  "content-script/features/profile-panel.js",
  "content-script/features/job-form.js",
  "content-script/features/activity-tracking.js",
  "content-script/features/widget-auth.js",
  "content-script/ui/widget-styles-base.js",
  "content-script/ui/widget-styles-components.js",
  "content-script/ui/widget-html.js",
  "content-script/features/submit-feedback.js",
  "content.js",
];
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
const DB_VERSION = 2;
const STORE_NAME = "resume";
const LOG_PREFIX = "[Autofill][background]";

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
      const oldVersion = e.oldVersion;

      if (oldVersion < 1) {
        // Fresh install: create the object store
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
      if (oldVersion < 2) {
        // v1 → v2 migration: store already exists, nothing structural to change.
        // Tab-specific keys use the same object store with different id values.
        // No schema change needed — just version bump to track the migration.
      }
    };
  });
}

function resumeKey(tabId) {
  return tabId ? `resume_tab_${tabId}` : "current";
}

async function saveResume(buffer, name, tabId, hash = null) {
  const key = resumeKey(tabId);
  logInfo("Saving resume in IndexedDB", {
    key,
    fileName: name || "resume.pdf",
    bytes: Array.isArray(buffer) ? buffer.length : 0,
  });
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    store.put({ id: key, buffer, name, hash, updatedAt: Date.now() });
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => reject(tx.error);
  });
}

async function getResume(tabId) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const tabKey = resumeKey(tabId);
    const tryCurrent = () => {
      const r = store.get("current");
      r.onsuccess = () => {
        db.close();
        resolve(r.result || null);
      };
      r.onerror = () => reject(r.error);
    };
    if (tabKey !== "current") {
      const r = store.get(tabKey);
      r.onsuccess = () => {
        if (r.result) {
          db.close();
          resolve(r.result);
        } else {
          tryCurrent();
        }
      };
      r.onerror = () => reject(r.error);
    } else {
      tryCurrent();
    }
  });
}

// Clean up tab-specific resume storage when a tab is closed
chrome.tabs.onRemoved.addListener(async (tabId) => {
  const idbKey = resumeKey(tabId);
  try {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).delete(idbKey);
    tx.oncomplete = () => db.close();
  } catch (_) {}
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "SAVE_RESUME") {
    const { buffer, name, tabId, hash } = msg.payload || {};
    if (!buffer || !name) {
      sendResponse({ ok: false, error: "Missing buffer or name" });
      return true;
    }
    const effectiveTabId = tabId ?? sender?.tab?.id;
    saveResume(buffer, name, effectiveTabId, hash)
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

  if (msg.type === "OPEN_RESUME_TAILOR") {
    (async () => {
      try {
        const { loginPageUrl } = await chrome.storage.local.get(["loginPageUrl"]);
        const base = loginPageUrl ? new URL(loginPageUrl).origin : "http://localhost:5173";
        const tailorUrl = new URL(`${base}/resume-generator/build`);
        tailorUrl.searchParams.set("tailor", "1");
        tailorUrl.searchParams.set("source", "extension");
        if (msg.jobId) tailorUrl.searchParams.set("job_id", String(msg.jobId));
        await chrome.tabs.create({ url: tailorUrl.toString() });
        sendResponse({ ok: true });
      } catch (err) {
        sendResponse({ ok: false, error: String(err) });
      }
    })();
    return true;
  }

  if (msg.type === "RESUME_SAVED_FROM_TAILOR") {
    const { resumeId } = msg;
    if (resumeId != null) {
      chrome.storage.local.set({ hm_selected_resume_id: resumeId }).catch(() => {});
      const tabId = sender?.tab?.id;
      if (tabId) chrome.tabs.remove(tabId).catch(() => {});
    }
    return false;
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
      const t0 = Date.now();
      logInfo("SCRAPE_ALL_FRAMES received");
      try {
        const tabId = msg.tabId ?? sender.tab?.id;
        if (!tabId) {
          logInfo("SCRAPE_ALL_FRAMES: no tabId");
          sendResponse({ ok: false, fields: [], error: "No tab" });
          return;
        }
        logInfo("SCRAPE_ALL_FRAMES: tabId", { tabId, ms: Date.now() - t0 });
        const scope = msg.scope || "all";
        const preExpandEmployment = Math.max(0, msg.preExpandEmployment ?? 0);
        const preExpandEducation = Math.max(0, msg.preExpandEducation ?? 0);
        const maxEducationBlocks = Math.max(1, msg.maxEducationBlocks ?? 999);
        const maxEmploymentBlocks = Math.max(1, msg.maxEmploymentBlocks ?? 999);
        const payload = { scope, preExpandEmployment, preExpandEducation, maxEducationBlocks, maxEmploymentBlocks };
        let frameIds = [0];
        try {
          const frames = await chrome.webNavigation.getAllFrames({ tabId });
          frameIds = (frames || []).map((f) => f.frameId).filter((id) => id != null);
          if (!frameIds.length) frameIds = [0];
          frameIds = [...new Set(frameIds)];
        } catch (_) {}

        const results = [];
        logInfo("SCRAPE_ALL_FRAMES: sending to frames", { frameCount: frameIds.length, frameIds });
        for (const frameId of frameIds) {
          try {
            let res = await chrome.tabs.sendMessage(tabId, { type: "SCRAPE_FIELDS", payload }, { frameId });
            logInfo("SCRAPE_ALL_FRAMES: frame response", { frameId, fieldCount: res?.fields?.length ?? 0 });
            results.push({ frameId, ok: true, res });
          } catch (e) {
            if (e?.message?.includes("Receiving end does not exist")) {
              try {
                await chrome.scripting.executeScript({ target: { tabId, frameIds: [frameId] }, files: CONTENT_SCRIPT_FILES });
                const res = await chrome.tabs.sendMessage(tabId, { type: "SCRAPE_FIELDS", payload }, { frameId });
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
        logInfo("SCRAPE_ALL_FRAMES: done", { totalFields: mergedFields.length, ms: Date.now() - t0 });
        sendResponse({ ok: true, fields: mergedFields });
      } catch (err) {
        logInfo("SCRAPE_ALL_FRAMES error", { error: String(err), ms: Date.now() - t0 });
        sendResponse({ ok: false, fields: [], error: String(err) });
      }
    })();
    return true;
  }

  if (msg.type === "INVALIDATE_MAPPING_CACHE") {
    (async () => {
      try {
        const all = await chrome.storage.local.get(null);
        const keysToRemove = Object.keys(all || {}).filter((k) => k.startsWith("hm_fm_"));
        if (keysToRemove.length > 0) {
          await chrome.storage.local.remove(keysToRemove);
          logInfo("Mapping cache invalidated", { keysRemoved: keysToRemove.length });
        }
        // Legacy: also remove old flat key if present
        await chrome.storage.local.remove("hm_field_mappings");
      } catch (e) {
        logInfo("Could not invalidate mapping cache", { error: String(e) });
      }
      sendResponse({ ok: true });
    })();
    return true;
  }

  if (msg.type === "START_WORKDAY_AUTOFILL") {
    (async () => {
      try {
        const { profileData } = msg.payload || {};
        const tabId = msg.tabId ?? sender?.tab?.id;
        if (!tabId || !profileData) {
          sendResponse({ ok: false, error: "Missing tabId or profileData" });
          return;
        }
        let frameIds = [0];
        try {
          const frames = await chrome.webNavigation.getAllFrames({ tabId });
          frameIds = (frames || []).map((f) => f.frameId).filter((id) => id != null);
          if (!frameIds.length) frameIds = [0];
          frameIds = [...new Set(frameIds)];
        } catch (_) {}
        logInfo("START_WORKDAY_AUTOFILL: broadcasting to frames", { frameCount: frameIds.length, frameIds });
        for (const frameId of frameIds) {
          try {
            await chrome.tabs.sendMessage(tabId, { type: "START_WORKDAY_AUTOFILL", payload: { profileData } }, { frameId });
          } catch (e) {
            if (e?.message?.includes("Receiving end does not exist")) {
              try {
                await chrome.scripting.executeScript({ target: { tabId, frameIds: [frameId] }, files: CONTENT_SCRIPT_FILES });
                await chrome.tabs.sendMessage(tabId, { type: "START_WORKDAY_AUTOFILL", payload: { profileData } }, { frameId });
              } catch (_) {}
            }
          }
        }
        sendResponse({ ok: true });
      } catch (err) {
        logInfo("START_WORKDAY_AUTOFILL error", { error: String(err) });
        sendResponse({ ok: false, error: String(err) });
      }
    })();
    return true;
  }

  if (msg.type === "STOP_WORKDAY_AUTOFILL") {
    (async () => {
      try {
        const tabId = msg.tabId ?? sender?.tab?.id;
        if (!tabId) {
          sendResponse({ ok: true });
          return;
        }
        let frameIds = [0];
        try {
          const frames = await chrome.webNavigation.getAllFrames({ tabId });
          frameIds = (frames || []).map((f) => f.frameId).filter((id) => id != null);
          if (!frameIds.length) frameIds = [0];
        } catch (_) {}
        for (const frameId of frameIds) {
          try {
            await chrome.tabs.sendMessage(tabId, { type: "STOP_WORKDAY_AUTOFILL" }, { frameId });
          } catch (_) {}
        }
        sendResponse({ ok: true });
      } catch (_) {
        sendResponse({ ok: true });
      }
    })();
    return true;
  }

  if (msg.type === "FILL_ALL_FRAMES") {
    (async () => {
      try {
        const { tabId: msgTabId, valuesByFrame, fieldsByFrame, resumeData, lastFill } = msg.payload || {};
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
            const fieldsForFrame = (fieldsByFrame && fieldsByFrame[fid]) || [];
            let res = await chrome.tabs.sendMessage(tabId, {
              type: "FILL_WITH_VALUES",
              payload: { values: vals, fieldsForFrame, resumeData, lastFill, scope: "current_document" }
            }, { frameId: parseInt(fid, 10) || 0 });
            if (res?.ok) {
              totalFilled += res.filledCount || 0;
              totalResumes += res.resumeUploadCount || 0;
            }
          } catch (e) {
            if (e?.message?.includes("Receiving end does not exist")) {
              try {
                await chrome.scripting.executeScript({ target: { tabId, frameIds: [parseInt(fid, 10) || 0] }, files: CONTENT_SCRIPT_FILES });
                const fieldsForFrame = (fieldsByFrame && fieldsByFrame[fid]) || [];
                const res = await chrome.tabs.sendMessage(tabId, {
                  type: "FILL_WITH_VALUES",
                  payload: { values: valuesByFrame[fid] || {}, fieldsForFrame, resumeData, lastFill, scope: "current_document" }
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

  if (msg.type === "GET_CACHED_MAPPINGS_BY_FP") {
    const { fps, domain } = msg.payload || {};
    if (!fps?.length) {
      sendResponse({ ok: true, data: {} });
      return true;
    }
    (async () => {
      try {
        const key = `hm_fm_${(domain || "").replace(/\./g, "_")}`;
        const stored = await chrome.storage.local.get([key]);
        const all = stored[key] || {};
        const now = Date.now();
        const TTL = 7 * 86400 * 1000;
        const out = {};
        for (const fp of fps) {
          const rec = all[fp];
          if (rec && rec.cached_at && (now - rec.cached_at) < TTL) {
            out[fp] = rec.mapping;
          }
        }
        sendResponse({ ok: true, data: out });
      } catch (e) {
        sendResponse({ ok: false, data: {} });
      }
    })();
    return true;
  }

  if (msg.type === "SET_CACHED_MAPPINGS_BY_FP") {
    const { mappingsByFp, domain } = msg.payload || {};
    if (!mappingsByFp || Object.keys(mappingsByFp).length === 0) {
      sendResponse({ ok: true });
      return true;
    }
    (async () => {
      try {
        const key = `hm_fm_${(domain || "").replace(/\./g, "_")}`;
        const stored = await chrome.storage.local.get([key]);
        const all = stored[key] || {};
        const now = Date.now();
        for (const [fp, mapping] of Object.entries(mappingsByFp)) {
          if (mapping && mapping.value !== undefined) {
            all[fp] = { mapping, cached_at: now };
          }
        }
        const keys = Object.keys(all);
        if (keys.length > 500) {
          const sorted = keys.map((k) => ({ k, t: all[k].cached_at })).sort((a, b) => a.t - b.t);
          for (let i = 0; i < sorted.length - 400; i++) {
            delete all[sorted[i].k];
          }
        }
        await chrome.storage.local.set({ [key]: all });
        sendResponse({ ok: true });
      } catch (e) {
        sendResponse({ ok: false });
      }
    })();
    return true;
  }

  if (msg.type === "GET_RESUME") {
    const tabId = msg.tabId ?? sender?.tab?.id;
    getResume(tabId)
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
            hash: row.hash || null,
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
    // Content script not injected, inject it first (full chain; Preact build may include content-ui.js last).
    try {
      const withPreact = [...CONTENT_SCRIPT_FILES, "content-ui.js"];
      try {
        await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: withPreact });
      } catch (_) {
        await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: CONTENT_SCRIPT_FILES });
      }
      await chrome.tabs.sendMessage(tab.id, { type: "SHOW_WIDGET" });
    } catch (err) {
      console.error("[Background] Failed to show widget:", err);
    }
  }
});
