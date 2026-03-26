// ─── Logging ───────────────────────────────────────────────────────────────
// Depends on: LOG_PREFIX (consts.js)

function logInfo(message, meta) {
  if (meta !== undefined) console.info(LOG_PREFIX, message, meta);
  else console.info(LOG_PREFIX, message);
}

function logWarn(message, meta) {
  if (meta !== undefined) console.warn(LOG_PREFIX, message, meta);
  else console.warn(LOG_PREFIX, message);
}

// ─── Text Helpers ──────────────────────────────────────────────────────────

function normalizeKey(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function getText(el) {
  if (!el) return "";
  return (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
}

function escapeHtml(s) {
  if (!s) return "";
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

// ─── Async Helpers ─────────────────────────────────────────────────────────

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ─── Date Formatting ───────────────────────────────────────────────────────

function formatDateForInput(value) {
  if (!value) return value;
  const str = String(value).trim();
  if (!str) return value;
  const isoMatch = str.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) return `${isoMatch[1]}-${isoMatch[2]}-${isoMatch[3]}`;
  const dmyMatch = str.match(/(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/);
  if (dmyMatch) {
    const [, a, b, y] = dmyMatch;
    return `${y}-${b.padStart(2, "0")}-${a.padStart(2, "0")}`;
  }
  return value;
}

// ─── File Helpers ──────────────────────────────────────────────────────────

function getMimeTypeForResume(fileName) {
  const ext = (fileName || "").toLowerCase().split(".").pop();
  const mimeMap = {
    pdf: "application/pdf",
    doc: "application/msword",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    txt: "text/plain",
    rtf: "application/rtf",
  };
  return mimeMap[ext] || "application/pdf";
}

// ─── Time Formatting ───────────────────────────────────────────────────────

// ─── DOM Interaction Helpers ───────────────────────────────────────────────

function makeCopyable(el, text) {
  if (!el || !text) return;
  el.classList.add("ja-copyable");
  el.addEventListener("click", () => {
    navigator.clipboard.writeText(text).catch(() => { });
  });
}

// ─── Time Formatting ───────────────────────────────────────────────────────

/** Format ISO `last_fill_time` from GET /chrome-extension/summary. */
function formatRelativeTimeFromIso(iso) {
  if (!iso || typeof iso !== "string") return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const sec = Math.round((Date.now() - d.getTime()) / 1000);
  if (sec < 45) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hr${hr === 1 ? "" : "s"} ago`;
  const day = Math.floor(hr / 24);
  if (day < 14) return `${day} day${day === 1 ? "" : "s"} ago`;
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: d.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined,
  });
}
