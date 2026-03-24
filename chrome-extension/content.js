const FIELD_MAP = {
  name: ["name", "full name", "first name", "last name", "candidate name", "legal name"],
  email: ["email", "e-mail", "email address"],
  phone: ["phone", "mobile", "telephone", "cell", "contact number"],
  linkedin: ["linkedin", "linkedin url", "linkedin profile"],
  github: ["github", "github url", "github profile"],
  portfolio: ["portfolio", "portfolio url", "website", "personal website"],
  location: ["location", "current location", "city", "address"],
  skills: ["skills", "skill", "technical skills", "key skills", "technologies"],
  experience: ["experience", "work experience", "employment", "summary", "about you"],
  education: ["education", "degree", "university", "college", "school"],
  company: ["current company", "company"],
  title: ["title", "job title", "current title", "position"],
  resume: ["resume", "cv", "upload", "attach", "cover letter", "paste your resume"],
};

const TEXTLIKE_INPUT_TYPES = new Set([
  "",
  "text",
  "email",
  "tel",
  "url",
  "search",
  "number",
  "date",
  "datetime-local",
  "month",
  "week",
  "time",
  "password",
]);

const IGNORE_INPUT_TYPES = new Set(["submit", "button", "hidden", "image", "reset", "range", "color"]);
const FIELD_SELECTOR = [
  "input",
  "textarea",
  "select",
  '[contenteditable="true"]',
  '[contenteditable=""]',
  '[contenteditable]',
  '[role="textbox"]',
  '[role="combobox"]',
  '[role="searchbox"]',
  '[role="spinbutton"]',
  ".ql-editor",
].join(",");

const LOG_PREFIX = "[Autofill][content]";
const INPAGE_ROOT_ID = "job-autofill-inpage-root";
const AUTOFILL_TIME_SAVED_KEY = "hm_autofill_total_fields";
const AVG_SECONDS_PER_FIELD = 10; // ~10 sec manual typing per field on average
const _visitedUrls = new Set();
const LOGIN_PAGE_ORIGINS = [
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
const DEFAULT_LOGIN_PAGE_URL = "http://localhost:5173/login";

function logInfo(message, meta) {
  if (meta !== undefined) console.info(LOG_PREFIX, message, meta);
  else console.info(LOG_PREFIX, message);
}
function logWarn(message, meta) {
  if (meta !== undefined) console.warn(LOG_PREFIX, message, meta);
  else console.warn(LOG_PREFIX, message);
}

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

const ACCORDION_ICONS = {
  document: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>',
  coverLetter: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>',
  person: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>',
};

/** Inline SVGs for question UIs (Lucide-style, matches Tailwind/shadcn references). */
const QUESTION_UI_ICONS = {
  helpCircle: '<svg class="ja-q-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>',
  sparkles: '<svg class="ja-q-svg ja-q-svg-tiny" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>',
  wand: '<svg class="ja-q-svg ja-q-svg-tiny" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M15 4V2"/><path d="M15 16v-2"/><path d="M8 9h2"/><path d="M20 9h2"/><path d="M17.8 11.8 19 13"/><path d="M5 20l14-14"/></svg>',
  edit: '<svg class="ja-q-svg ja-q-svg-tiny" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
  checkCircle: '<svg class="ja-q-svg ja-cq-state" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>',
  alertCircle: '<svg class="ja-q-svg ja-cq-warn" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>',
  clock: '<svg class="ja-q-svg ja-q-meta" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
  layers: '<svg class="ja-q-svg ja-q-meta" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.05 4.32a2 2 0 0 1-1.9 0L2 17.65"/><path d="m22 12.65-9.05 4.32a2 2 0 0 1-1.9 0L2 12.65"/></svg>',
  download: '<svg class="ja-footer-link-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M5 21h14"/></svg>',
  users: '<svg class="ja-footer-link-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 11c1.66 0 3-1.79 3-4s-1.34-4-3-4-3 1.79-3 4 1.34 4 3 4z"/><path d="M8 11c1.66 0 3-1.79 3-4S9.66 3 8 3 5 4.79 5 7s1.34 4 3 4z"/><path d="M2 21v-2c0-2.5 3.5-4 6-4"/><path d="M22 21v-2c0-2.5-3.5-4-6-4"/></svg>',
};

/** Keywords tab — Lucide-style icons (Tailor, gauge tip, suggestions, refresh). */
const KEYWORD_TAB_ICONS = {
  target: '<svg class="ja-kw-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2"/></svg>',
  lightbulb: '<svg class="ja-kw-ico ja-kw-ico-tip" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>',
  trendingUp: '<svg class="ja-kw-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 7l-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/></svg>',
  refreshCw: '<svg class="ja-kw-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/></svg>',
  chipCheck: '<svg class="ja-kw-chip-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
};

/** Profile tab — Lucide-style icons (contact rows, sections, actions). */
const PROFILE_TAB_ICONS = {
  mapPin: '<svg class="ja-prof-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>',
  mail: '<svg class="ja-prof-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>',
  phone: '<svg class="ja-prof-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
  linkedin: '<svg class="ja-prof-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/></svg>',
  github: '<svg class="ja-prof-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg>',
  globe: '<svg class="ja-prof-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>',
  graduationCap: '<svg class="ja-prof-svg ja-prof-svg-sec" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 10v6M6 12v4c0 1.1.9 2 2 2h2"/><path d="M18 22v-4"/><path d="M4 10 12 6l8 4-8 4-8-4Z"/><path d="M6 12v7a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-7"/></svg>',
  briefcase: '<svg class="ja-prof-svg ja-prof-svg-sec" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect width="20" height="14" x="2" y="7" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
  award: '<svg class="ja-prof-svg ja-prof-svg-sec" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/></svg>',
  awardSm: '<svg class="ja-prof-award-sm" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2" aria-hidden="true"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/></svg>',
  upload: '<svg class="ja-prof-svg ja-prof-svg-sec" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>',
  fileText: '<svg class="ja-prof-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>',
  code: '<svg class="ja-prof-svg ja-prof-svg-sec" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
  messageSquare: '<svg class="ja-prof-svg ja-prof-svg-sec" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  copy: '<svg class="ja-prof-copy-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>',
  check: '<svg class="ja-prof-copy-ico ja-prof-copy-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
  refreshCwSm: '<svg class="ja-prof-btn-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/></svg>',
  editSm: '<svg class="ja-prof-btn-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
  eyeSm: '<svg class="ja-prof-btn-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>',
  downloadSm: '<svg class="ja-prof-btn-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>',
  eyeFile: '<svg class="ja-prof-file-act" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>',
  downloadFile: '<svg class="ja-prof-file-act" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>',
};

/** Autofill tab hero — Zap, Sparkles, Check (button states). */
const AUTOFILL_TAB_ICONS = {
  zap: '<svg class="ja-hero-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
  sparkles: '<svg class="ja-hero-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3Z"/></svg>',
  check: '<svg class="ja-hero-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
};

function keywordGaugeDashArray(percent) {
  const c = 213.628;
  const p = Math.max(0, Math.min(100, Number(percent) || 0));
  return `${(p / 100) * c} ${c}`;
}

/** @returns {{ label: string, color: string, badgeBg: string, stroke: string }} */
function keywordMatchTheme(matchPercent, totalKeywords) {
  if (!totalKeywords) {
    return { label: "No skills found", color: "#6b7280", badgeBg: "rgba(243, 244, 246, 0.9)", stroke: "#e5e7eb" };
  }
  const p = Number(matchPercent) || 0;
  if (p >= 70) return { label: "Strong Match", color: "#16a34a", badgeBg: "rgba(34, 197, 94, 0.12)", stroke: "#22c55e" };
  if (p >= 40) return { label: "Needs Improvement", color: "#d97706", badgeBg: "rgba(245, 158, 11, 0.12)", stroke: "#f59e0b" };
  return { label: "Weak Match", color: "#dc2626", badgeBg: "rgba(239, 68, 68, 0.1)", stroke: "#ef4444" };
}

function renderKeywordMatchChip(item) {
  const freq = item.frequency != null ? Number(item.frequency) : 1;
  const m = item.matched;
  return `<div class="ja-kw-chip ${m ? "ja-kw-chip--on" : "ja-kw-chip--off"}">
    <span class="ja-kw-chip-box">${m ? KEYWORD_TAB_ICONS.chipCheck : ""}</span>
    <span class="ja-kw-chip-name">${escapeHtml(item.keyword)}</span>
    <span class="ja-kw-chip-freq">×${Number.isFinite(freq) ? freq : 1}</span>
  </div>`;
}

/** Reusable accordion component. opts: { id, iconBg, iconColor, iconSvg, title, showHelpIcon, statusText, statusCheckmark } */
function createAccordionItem(opts) {
  const id = escapeHtml(opts.id || "accordion");
  const iconBg = escapeHtml(opts.iconBg || "#e0e7ff");
  const iconColor = opts.iconColor != null ? escapeHtml(String(opts.iconColor)) : "";
  const iconSvg = opts.iconSvg || ACCORDION_ICONS.document;
  const title = escapeHtml(opts.title || "");
  const showHelpIcon = !!opts.showHelpIcon;
  const statusText = escapeHtml(opts.statusText || "");
  const statusCheckmark = !!opts.statusCheckmark;
  const checkImgUrl = chrome.runtime.getURL("icons/circle-check-big.svg");
  const checkMarkHtml = statusCheckmark
    ? `<span class="ja-accordion-check" aria-hidden="true"><img src="${checkImgUrl}" alt="" width="14" height="14" class="ja-resume-check-img" /></span>`
    : "";
  const iconStyle = iconColor ? `background:${iconBg};color:${iconColor}` : `background:${iconBg}`;
  return `
    <div class="ja-accordion-item" data-accordion-id="${id}">
      <button type="button" class="ja-accordion-header" aria-expanded="false" aria-controls="ja-accordion-body-${id}" id="ja-accordion-trigger-${id}">
        <span class="ja-accordion-icon" style="${iconStyle}">${iconSvg}</span>
        <span class="ja-accordion-title-wrap">
          <span class="ja-accordion-title">${title}</span>
          ${showHelpIcon ? '<span class="ja-accordion-help" title="Help">?</span>' : ""}
        </span>
        ${statusText || statusCheckmark ? `<span class="ja-accordion-status">${statusText ? `<span class="ja-accordion-status-text">${statusText}</span>` : ""}${checkMarkHtml}</span>` : ""}
        <span class="ja-accordion-chevron" aria-hidden="true">▼</span>
      </button>
      <div class="ja-accordion-body" id="ja-accordion-body-${id}" role="region" aria-labelledby="ja-accordion-trigger-${id}" hidden>
        <div class="ja-accordion-content"></div>
      </div>
    </div>
  `;
}

function renderAccordions(containerEl, items, rootEl) {
  if (!containerEl) return;
  containerEl.innerHTML = items.map((item) => createAccordionItem(item)).join("");
  containerEl.querySelectorAll(".ja-accordion-header").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = btn.closest(".ja-accordion-item");
      const body = item?.querySelector(".ja-accordion-body");
      const isExpanded = btn.getAttribute("aria-expanded") === "true";
      const expanding = !isExpanded;
      btn.setAttribute("aria-expanded", expanding);
      if (body) body.hidden = !expanding;
      item?.classList.toggle("expanded", expanding);
      if (expanding && rootEl) {
        const id = item?.dataset?.accordionId || item?.querySelector("[data-accordion-id]")?.dataset?.accordionId;
        const contentEl = item?.querySelector(".ja-accordion-content");
        if (id && contentEl) loadAccordionContent(id, contentEl, rootEl);
      }
    });
  });
}

/** Same profile fields as Profile tab — from `GET .../autofill/context` → `profile`. */
function buildResumeAccordionFieldRows(flat) {
  const f = flat || {};
  const location = [f.city, f.country].filter(Boolean).join(", ") || "—";
  const fullName = [f.firstName, f.lastName].filter(Boolean).join(" ") || f.name || "—";
  return [
    ["Full name", fullName],
    ["Location", location],
    ["Email", f.email || "—"],
    ["Phone", f.phone || "—"],
    ["LinkedIn", f.linkedin || "—"],
    ["GitHub", f.github || "—"],
    ["Portfolio", f.portfolio || "—"],
  ];
}

/** Inline SVG (icons/circle-check-big.svg) — no chrome-extension:// img fetch. */
const RESUME_FIELD_CHECK_SVG =
  '<svg class="ja-resume-check-svg" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.801 10A10 10 0 1 1 17 3.335"/><path d="m9 11 3 3L22 4"/></svg>';

async function loadAccordionContent(id, contentEl, rootEl) {
  if (id === "resume") {
    await loadResumeAccordionContent(contentEl, rootEl);
  } else if (id === "cover-letter") {
    await loadCoverLetterAccordionContent(contentEl, rootEl);
  } else if (id === "unique-questions" || id === "common-questions") {
    await loadQuestionsAccordionContent(id, contentEl, rootEl);
  }
}

async function loadResumeAccordionContent(contentEl, rootEl) {
  contentEl.innerHTML = "<p class=\"ja-score-text\">Loading...</p>";

  try {
    const resumes = await fetchResumesFromApi();

    if (resumes.length === 0) {
      contentEl.innerHTML = `
        <p class="ja-score-text">No resumes yet. Upload in your OpsBrain profile.</p>
        <button type="button" class="ja-action" style="margin-top:8px;">Open Profile</button>
      `;
      contentEl.querySelector(".ja-action")?.addEventListener("click", openResumeGeneratorUrl);
      return;
    }

    const { hm_selected_resume_id } = await chrome.storage.local.get(["hm_selected_resume_id"]);
    const storedId = hm_selected_resume_id ? parseInt(hm_selected_resume_id, 10) : null;

    const defaultResume = resumes.find((r) => r.is_default) || resumes[0];
    const selectedId =
      storedId && resumes.some((r) => r.id === storedId)
        ? storedId
        : defaultResume?.id;

    const selectId = "ja-accordion-resume-select";

    let flat = {};
    try {
      const ctx = await getAutofillContextFromApi();
      flat = ctx.profile || {};
    } catch (_) { }

    const resumeFieldRows = buildResumeAccordionFieldRows(flat);

    contentEl.innerHTML = `
      <div class="ja-resume-accordion-row">
        <select class="ja-resume-select" id="${selectId}">
          ${resumes.map((r) => `
            <option value="${r.id}" ${r.id === selectedId ? "selected" : ""}>
              ${escapeHtml(r.resume_name || `Resume ${r.id}`)}
            </option>
          `).join("")}
        </select>

        <button type="button" class="ja-action ja-upload-preview">Preview</button>
      </div>

      <p class="ja-resume-preview-hint">
        Default selected resume shown above. Click Preview to open PDF.
      </p>

      <div class="ja-resume-card">

        ${resumeFieldRows
          .map(
            ([label, value]) => `
          <div class="ja-resume-row">
            <span class="ja-resume-label">${escapeHtml(label)}</span>
            <div class="ja-resume-value-wrap">
              <span class="ja-resume-value">${escapeHtml(value)}</span>
              <span class="ja-check-icon">${RESUME_FIELD_CHECK_SVG}</span>
            </div>
          </div>
        `
          )
          .join("")}

      </div>
    `;

    contentEl.querySelector(".ja-upload-preview")?.addEventListener("click", async () => {
      const sel = contentEl.querySelector(`#${selectId}`);
      const id = sel ? parseInt(sel.value, 10) : selectedId;

      if (!id) return;

      try {
        const apiBase = await getApiBase();
        const headers = await getAuthHeaders();
        const res = await fetchWithAuthRetry(`${apiBase}/resume/${id}/file`, { headers });

        if (res.ok) {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          window.open(url, "_blank");
        }
      } catch (_) {}
    });

  } catch (err) {
    contentEl.innerHTML = "<p class=\"ja-score-text\">Failed to load resumes.</p>";
  }
}

async function loadCoverLetterAccordionContent(contentEl, rootEl, forceRegenerate = false) {
  contentEl.innerHTML = "<p class=\"ja-score-text\">Loading...</p>";
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const currentJobUrl = forceRegenerate ? `${window.location.href}#regenerate=${Date.now()}` : window.location.href;
    const pageHtml = await getPageHtmlForKeywordsApi?.().catch(() => "") || "";
    const jobTitle = document.title?.split(/[|\-–—]/)[0]?.trim() || "";
    const _clRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/cover-letter/upsert`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ job_url: currentJobUrl, page_html: pageHtml, job_title: jobTitle }),
    });
    const coverLetterData = await _clRes.json();
    const letter = coverLetterData?.content || "";
    const displayTitle = coverLetterData?.job_title || jobTitle;
    if (letter) {
      contentEl.innerHTML = `
      <div class="ja-cover-letter-preview ja-cover-box">
  ${displayTitle ? `<p class="ja-cover-letter-job">${escapeHtml(displayTitle)}</p>` : ""}
  
  <div class="ja-cover-letter-text">
    ${escapeHtml(letter).replace(/\n/g, "<br>")}
  </div>
</div>
        <div class="ja-btn-row">
  <button type="button" class="ja-btn"  id="ja-generate-cover-letter">
    <!-- Wand Icon -->
    <svg class="ja-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path d="M15 4V2"></path>
      <path d="M15 10V8"></path>
      <path d="M19 6h2"></path>
      <path d="M13 6h-2"></path>
      <path d="M5 20l14-14"></path>
    </svg>
    Regenerate
  </button>

  <button class="ja-btn">
    <!-- Edit Icon -->
    <svg class="ja-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path d="M12 20h9"></path>
      <path d="M16.5 3.5a2.1 2.1 0 113 3L7 19l-4 1 1-4 12.5-12.5z"></path>
    </svg>
    Edit
  </button>

  <button class="ja-btn-icon">
    <!-- Copy Icon -->
    <svg class="ja-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <rect x="9" y="9" width="13" height="13" rx="2"></rect>
      <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"></path>
    </svg>
  </button>
</div>
      
      `;
    } else {
      contentEl.innerHTML = `
        <p class="ja-score-text">No cover letter yet. Generate one based on your profile and this job.</p>
        <button type="button" class="ja-action" id="ja-generate-cover-letter">Generate Cover Letter</button>
      `;
    }
    contentEl.querySelector("#ja-generate-cover-letter")?.addEventListener("click", async () => {
      const btn = contentEl.querySelector("#ja-generate-cover-letter");
      if (btn) btn.disabled = true;
      contentEl.querySelector(".ja-cover-letter-preview")?.remove();
      const statusP = contentEl.querySelector(".ja-score-text") || contentEl.appendChild(document.createElement("p"));
      statusP.className = "ja-score-text";
      statusP.textContent = "Generating...";
      try {
        await loadCoverLetterAccordionContent(contentEl, rootEl, true);
      } catch (_) {
        statusP.textContent = "Generation failed.";
      }
      if (btn) btn.disabled = false;
    });
  } catch (_) {
    contentEl.innerHTML = "<p class=\"ja-score-text\">No cover letter. Click Generate to create one.</p><button type=\"button\" class=\"ja-action\" id=\"ja-generate-cover-letter\">Generate</button>";
    contentEl.querySelector("#ja-generate-cover-letter")?.addEventListener("click", () => loadCoverLetterAccordionContent(contentEl, rootEl));
  }
}

async function loadQuestionsAccordionContent(id, contentEl, rootEl) {
  contentEl.innerHTML = "<p class=\"ja-score-text\">Scanning page for form fields...</p>";
  try {
    let fields = [];
    if (window.self === window.top) {
      const scrapeRes = await chrome.runtime.sendMessage({ type: "SCRAPE_ALL_FRAMES", scope: "all" });
      fields = scrapeRes?.ok ? (scrapeRes.fields || []) : [];
    } else {
      const scraped = await scrapeFields({ scope: "all" });
      fields = scraped?.fields || [];
    }
    if (!fields || fields.length === 0) {
      contentEl.innerHTML = "<p class=\"ja-score-text\">No application form detected. Click &quot;Apply&quot; or navigate to the application form to see questions.</p>";
      return;
    }
    const ctx = await getAutofillContextFromApi();
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const mapRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/form-fields/map`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        fields: fields.slice(0, 50).map((f) => ({ ...f, id: null })),
        profile: ctx?.profile || {},
        custom_answers: ctx?.customAnswers || {},
        resume_text: ctx?.resumeText || "",
        sync_llm: true,
      }),
    });
    if (!mapRes.ok) {
      let errMsg = "Failed to load mappings";
      try {
        const errBody = await mapRes.json();
        const d = errBody?.detail;
        errMsg = typeof d === "string" ? d : Array.isArray(d) ? (d[0]?.msg || String(d[0] || d)) : errMsg;
      } catch (_) { }
      contentEl.innerHTML = `<p class="ja-score-text">${escapeHtml(String(errMsg))} (${mapRes.status})</p>`;
      return;
    }
    const mapData = await mapRes.json();
    const mappings = mapData?.mappings || {};
    const commonKeys = ["firstname", "lastname", "email", "phone", "address", "linkedin", "github", "portfolio", "resume", "coverletter", "country", "city"];
    const isCommon = (f) => {
      const keys = getFieldKeys({ label: f.label, name: f.name, id: f.id, placeholder: f.placeholder });
      return commonKeys.some((k) => keys.some((fk) => fk.includes(k) || k.includes(fk)));
    };
    const common = fields.filter(isCommon);
    const unique = fields.filter((f) => !isCommon(f));
    const list = id === "common-questions" ? common : unique;
    const filled = list.filter((f) => {
      const m = mappings[f.index];
      return m?.value != null && String(m.value).trim() !== "";
    }).length;
    const total = list.length;
    const slice = list.slice(0, 15);

    if (id === "unique-questions") {
      const cards = slice.map((f) => {
        const m = mappings[f.index] || {};
        const val = m.value != null ? String(m.value).trim() : "";
        const label = f.label || f.name || f.placeholder || `Field ${f.index + 1}`;
        const hasAnswer = val.length > 0;
        const qRow = `
          <div class="ja-uq-qrow">
            <span class="ja-uq-help">${QUESTION_UI_ICONS.helpCircle}</span>
            <p class="ja-uq-question">${escapeHtml(label)}</p>
          </div>`;
        let body = "";
        if (hasAnswer) {
          body = `
          <div class="ja-uq-body">
            <p class="ja-uq-answer">${escapeHtml(val)}</p>
            <div class="ja-uq-foot">
              <span class="ja-badge ja-badge-ai">${QUESTION_UI_ICONS.sparkles}<span>AI Generated</span></span>
              <button type="button" class="ja-uq-textbtn">Edit</button>
            </div>
          </div>`;
        } else {
          body = `
          <div class="ja-uq-body ja-uq-body-empty">
            <span class="ja-badge ja-badge-need">Needs Answer</span>
            <button type="button" class="ja-uq-textbtn ja-uq-textbtn-wand">${QUESTION_UI_ICONS.wand}<span>Generate</span></button>
          </div>`;
        }
        return `<div class="ja-uq-card">${qRow}${body}</div>`;
      }).join("");
      contentEl.innerHTML = slice.length
        ? `<div class="ja-uq-stack">${cards}</div>`
        : "<p class=\"ja-score-text\">No questions in this category.</p>";
    } else {
      const rows = slice.map((f, i) => {
        const m = mappings[f.index] || {};
        const val = m.value != null ? String(m.value).trim() : "";
        const label = f.label || f.name || f.placeholder || `Field ${f.index + 1}`;
        const hasAnswer = val.length > 0;
        const isLast = i === slice.length - 1;
        const icon = hasAnswer ? QUESTION_UI_ICONS.checkCircle : QUESTION_UI_ICONS.alertCircle;
        return `
          <div class="ja-cq-row${isLast ? "" : " ja-cq-row-b"}">
            <span class="ja-cq-q">${escapeHtml(label)}</span>
            <div class="ja-cq-ans">
              <span class="ja-cq-val">${hasAnswer ? escapeHtml(val) : "—"}</span>
              <span class="ja-cq-ico">${icon}</span>
            </div>
          </div>`;
      }).join("");
      contentEl.innerHTML = slice.length
        ? `<div class="ja-cq-shell">
            <div class="ja-cq-list">${rows}</div>
            <div class="ja-cq-editbar">
              <button type="button" class="ja-cq-editall">${QUESTION_UI_ICONS.edit}<span>Edit all answers in settings</span></button>
            </div>
          </div>
          <div class="ja-cq-meta">
            <span class="ja-cq-meta-item">${QUESTION_UI_ICONS.clock}<span>Last fill: —</span></span>
            <span class="ja-cq-meta-item">${QUESTION_UI_ICONS.layers}<span>— applications filled</span></span>
          </div>`
        : "<p class=\"ja-score-text\">No questions in this category.</p>";
    }

    const statusWrap = rootEl?.querySelector(`[data-accordion-id="${id}"]`)?.querySelector(".ja-accordion-status-text");
    if (statusWrap) statusWrap.textContent = `${filled}/${total}`;
  } catch (err) {
    contentEl.innerHTML = "<p class=\"ja-score-text\">Failed to load questions.</p>";
  }
}

function isVisible(el) {
  if (!el || !el.ownerDocument || !el.isConnected) return false;
  if (el.getAttribute("aria-hidden") === "true" || el.hidden) return false;

  const style = el.ownerDocument.defaultView?.getComputedStyle(el);
  if (!style) return false;
  if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
  if (el.getClientRects().length === 0) return false;
  return true;
}

function getAllRoots(doc) {
  const roots = [];
  const seen = new Set();
  function addRoot(root) {
    if (!root || seen.has(root)) return;
    seen.add(root);
    roots.push(root);
    try {
      const all = root.querySelectorAll ? root.querySelectorAll("*") : [];
      for (const el of all) {
        if (el.shadowRoot) addRoot(el.shadowRoot);
      }
    } catch (_) { }
  }
  addRoot(doc);
  return roots;
}

function getDocuments(includeNestedDocuments = true) {
  const docs = [];
  const queue = [document];
  const seen = new Set();
  if (!includeNestedDocuments) return [document];
  while (queue.length > 0) {
    const doc = queue.shift();
    if (!doc || seen.has(doc)) continue;
    seen.add(doc);
    docs.push(doc);

    const iframes = Array.from(doc.querySelectorAll("iframe, frame"));
    for (const frame of iframes) {
      try {
        if (frame.contentDocument) queue.push(frame.contentDocument);
      } catch (_) {
        // Ignore cross-origin frames.
      }
    }
  }
  return docs;
}

function isFillable(field, includeHidden = false) {
  if (!field || !field.ownerDocument || !field.isConnected) return false;
  const tag = (field.tagName || "").toLowerCase();
  const type = (field.type || "").toLowerCase();

  if (tag === "input" && type === "file") {
    if (field.disabled || field.getAttribute("aria-disabled") === "true") return false;
    return true;
  }

  if (!includeHidden && !isVisible(field)) return false;
  if (field.disabled || field.readOnly) return false;
  if (field.getAttribute("aria-disabled") === "true") return false;

  const role = (field.getAttribute("role") || "").toLowerCase();

  if (tag === "input") {
    if (IGNORE_INPUT_TYPES.has(type)) return false;
    return true;
  }

  if (tag === "textarea" || tag === "select") return true;
  if (field.isContentEditable) return true;
  if (role === "textbox" || role === "combobox" || role === "searchbox" || role === "spinbutton") return true;
  if (tag === "div" || tag === "span") {
    const ce = field.getAttribute("contenteditable");
    if (ce === "true" || ce === "") return true;
  }

  return false;
}

function getClosestQuestionText(field) {
  const container = field.closest(
    ".field,.form-group,.formField,.question,.application-question,.input-wrapper,.input-group,li,section,div"
  );
  if (!container) return "";
  const candidates = container.querySelectorAll("label,legend,h1,h2,h3,h4,strong,p,span");
  for (const candidate of candidates) {
    if (candidate.contains(field)) continue;
    const txt = getText(candidate);
    if (txt && txt.length <= 180) return txt;
  }
  return "";
}

function getLabelText(field) {
  const doc = field.ownerDocument || document;

  if (field.id) {
    try {
      const label = doc.querySelector(`label[for="${CSS.escape(field.id)}"]`);
      if (label) {
        const txt = getText(label);
        if (txt) return txt;
      }
    } catch (_) {
      // Ignore invalid selectors.
    }
  }

  const parentLabel = field.closest("label");
  if (parentLabel) {
    const clone = parentLabel.cloneNode(true);
    const controls = clone.querySelectorAll(FIELD_SELECTOR);
    controls.forEach((el) => el.remove());
    const txt = getText(clone);
    if (txt) return txt;
  }

  const ariaLabel = field.getAttribute("aria-label");
  if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim();

  const labelledBy = field.getAttribute("aria-labelledby");
  if (labelledBy) {
    const ids = labelledBy.split(/\s+/).filter(Boolean);
    const txt = ids
      .map((id) => {
        const el = doc.getElementById(id);
        return el ? getText(el) : "";
      })
      .filter(Boolean)
      .join(" ");
    if (txt) return txt;
  }

  const placeholder = field.getAttribute("placeholder");
  if (placeholder && placeholder.trim()) return placeholder.trim();

  const questionText = getClosestQuestionText(field);
  if (questionText) return questionText;

  const name = field.getAttribute("name");
  if (name && name.trim()) return name.trim();
  const id = field.getAttribute("id");
  if (id && id.trim()) return id.trim();
  return "";
}

function getFieldMeta(field) {
  const tag = (field.tagName || "").toLowerCase();
  const role = (field.getAttribute("role") || "").toLowerCase();
  let type = (field.type || "").toLowerCase();

  if (tag === "select") type = "select";
  if (tag === "textarea") type = "textarea";
  if (!type && field.isContentEditable) type = "contenteditable";
  if (!type && role) type = role;

  return {
    tag,
    role,
    type,
    label: getLabelText(field),
    name: field.getAttribute("name") || "",
    id: field.getAttribute("id") || "",
    placeholder: field.getAttribute("placeholder") || "",
    required: !!field.required || field.getAttribute("aria-required") === "true",
  };
}

function isInsideExtensionWidget(el) {
  if (!el?.ownerDocument) return false;
  const doc = el.ownerDocument;
  if (doc !== document) return false;
  const widget = document.getElementById(INPAGE_ROOT_ID);
  return !!(widget && widget.contains(el));
}

function getFillableFields(includeNestedDocuments = true, includeHidden = false) {
  const scraper = typeof window !== "undefined" && window.__HIREMATE_FIELD_SCRAPER__;
  if (scraper) {
    try {
      const result = scraper.getScrapedFields({
        scope: includeNestedDocuments ? "all" : "current_document",
        includeHidden,
        excludePredicate: isInsideExtensionWidget,
      });
      const elements = result.elements || (result.fields || []).map((f) => f.element).filter(Boolean);
      if (elements.length > 0) return elements;
    } catch (e) {
      logWarn("Enhanced field scraper failed, falling back", { error: String(e) });
    }
  }
  const out = [];
  const seen = new Set();
  let totalCandidates = 0;
  const docs = getDocuments(includeNestedDocuments);

  for (const doc of docs) {
    const roots = getAllRoots(doc);
    for (const root of roots) {
      try {
        const candidates = Array.from(root.querySelectorAll(FIELD_SELECTOR));
        for (const el of candidates) {
          if (seen.has(el)) continue;
          if (isInsideExtensionWidget(el)) continue;
          seen.add(el);
          totalCandidates += 1;
          if (isFillable(el, includeHidden)) out.push(el);
        }
      } catch (_) { }
    }
  }
  if (totalCandidates > 0 && out.length === 0) {
    logWarn("Found form candidates but all filtered out", { totalCandidates, includeHidden, docCount: docs.length });
  }
  return out;
}

function dispatchFrameworkEvents(field) {
  const tag = (field.tagName || "").toLowerCase();
  // Selects handle their own events in setNativeValue to avoid double-firing
  if (tag === "select") return;
  field.dispatchEvent(new Event("focus", { bubbles: true }));
  try {
    field.dispatchEvent(new InputEvent("input", { bubbles: true, composed: true, inputType: "insertText" }));
  } catch (_) {
    field.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
  }
  field.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
  field.dispatchEvent(new Event("blur", { bubbles: true }));
}

function focusWithoutScroll(field) {
  try {
    field.focus({ preventScroll: true });
    return;
  } catch (_) {
    // Fallback for older browsers.
  }
  const doc = field.ownerDocument || document;
  const view = doc.defaultView || window;
  const x = view.scrollX;
  const y = view.scrollY;
  field.focus();
  view.scrollTo(x, y);
}

function setNativeValue(field, nextValue) {
  const value = String(nextValue ?? "");
  const tag = (field.tagName || "").toLowerCase();

  if (field.isContentEditable || tag === "div" || tag === "span") {
    focusWithoutScroll(field);
    field.textContent = value;
    dispatchFrameworkEvents(field);
    return true;
  }

  if (tag === "select") {
    const valStr = normalizeKey(value);
    const options = Array.from(field.options || []).filter(opt => {
      // Skip placeholder options like "Select...", "Choose...", empty options
      const optText = normalizeKey(opt.text);
      const optValue = normalizeKey(opt.value);
      return optValue !== "" &&
        !optText.startsWith("select") &&
        !optText.startsWith("choose") &&
        !optText.startsWith("pick");
    });

    if (options.length === 0) {
      logWarn("Select dropdown has no valid options", {
        field: field.name || field.id || field.placeholder
      });
      return false;
    }

    // Try exact match first (case-insensitive)
    let match = options.find((opt) =>
      String(opt.value).toLowerCase() === value.toLowerCase() ||
      opt.text.toLowerCase() === value.toLowerCase()
    );

    // Special handling for Yes/No questions
    if (!match && (valStr === "yes" || valStr === "no" || valStr === "none")) {
      match = options.find((opt) => {
        const optText = normalizeKey(opt.text);
        const optValue = normalizeKey(opt.value);
        return optText === valStr || optValue === valStr;
      });
    }

    // Try normalized text/value match
    if (!match) {
      match = options.find((opt) => normalizeKey(opt.text) === valStr || normalizeKey(opt.value) === valStr);
    }

    // Try partial contains match (both ways)
    if (!match) {
      match = options.find((opt) => {
        const optText = normalizeKey(opt.text);
        const optValue = normalizeKey(opt.value);
        return optText.includes(valStr) || valStr.includes(optText) ||
          optValue.includes(valStr) || valStr.includes(optValue);
      });
    }

    // Try first word match (for cases like "Male" matching "Male / पुरुष")
    if (!match && valStr) {
      const firstWord = valStr.split(/\s+/)[0];
      match = options.find((opt) => {
        const optText = normalizeKey(opt.text).split(/\s+/)[0];
        return optText === firstWord || optText.includes(firstWord) || firstWord.includes(optText);
      });
    }

    if (!match) {
      logWarn("Select dropdown match failed", {
        field: field.name || field.id || field.placeholder,
        value,
        availableOptions: options.map(opt => ({ text: opt.text, value: opt.value })).slice(0, 10)
      });
      return false;
    }

    // Step 1: Focus and simulate opening the dropdown
    focusWithoutScroll(field);
    field.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
    field.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
    field.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));

    // Step 2: Set value using the native prototype setter so React/Vue get the real DOM change
    const nativeSetter = Object.getOwnPropertyDescriptor(
      Object.getPrototypeOf(field), "value"
    )?.set || Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
    if (nativeSetter) {
      nativeSetter.call(field, match.value);
    } else {
      field.value = match.value;
    }

    // Step 3: Fool React's _valueTracker so it detects the value as changed
    // (React skips onChange if tracker thinks value didn't change)
    try {
      const tracker = field._valueTracker;
      if (tracker) {
        tracker.setValue(field.value === match.value ? "" : field.value);
      }
    } catch (_) { }

    // Step 4: Simulate clicking the matching <option> element
    try {
      match.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
      match.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
      match.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: field.ownerDocument?.defaultView }));
    } catch (_) { }

    // Step 5: Fire change + blur so all framework listeners fire
    field.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    field.dispatchEvent(new Event("blur", { bubbles: true }));

    logInfo("Select dropdown filled", {
      field: field.name || field.id,
      matchedOption: { text: match.text, value: match.value }
    });
    return true;
  }

  if (tag === "input") {
    const inputType = (field.type || "").toLowerCase();
    if (inputType === "checkbox") {
      const shouldCheck = value === "true" || value === "1" || value === "yes" || value === "on";
      field.checked = shouldCheck;
      dispatchFrameworkEvents(field);
      return true;
    }
    if (inputType === "radio") {
      const own = normalizeKey(field.value);
      const wanted = normalizeKey(value);
      if (own && wanted && own !== wanted) return false;
      field.checked = true;
      dispatchFrameworkEvents(field);
      return true;
    }
    if (inputType === "date" || inputType === "datetime-local" || inputType === "month") {
      const formattedDate = formatDateForInput(value);
      focusWithoutScroll(field);
      field.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      const proto = Object.getPrototypeOf(field);
      const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
      if (descriptor?.set) descriptor.set.call(field, formattedDate);
      else field.value = formattedDate;
      try { if (field._valueTracker) field._valueTracker.setValue(""); } catch (_) { }
      dispatchFrameworkEvents(field);
      return true;
    }

    // Regular text/email/tel/number input — simulate click then type
    focusWithoutScroll(field);
    field.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    const nativeSetter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(field), "value")?.set
      || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    if (nativeSetter) nativeSetter.call(field, value);
    else field.value = value;
    try { if (field._valueTracker) field._valueTracker.setValue(""); } catch (_) { }
    dispatchFrameworkEvents(field);
    return true;
  }

  if (tag === "textarea") {
    focusWithoutScroll(field);
    field.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    const nativeSetter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(field), "value")?.set
      || Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    if (nativeSetter) nativeSetter.call(field, value);
    else field.value = value;
    try { if (field._valueTracker) field._valueTracker.setValue(""); } catch (_) { }
    dispatchFrameworkEvents(field);
    return true;
  }

  const role = (field.getAttribute("role") || "").toLowerCase();
  if (role === "textbox" || role === "combobox") {
    focusWithoutScroll(field);
    field.textContent = value;
    dispatchFrameworkEvents(field);
    return true;
  }

  return false;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Record autofill usage for dynamic time-saved display (~10 sec per field) */
async function recordAutofillFieldsFilled(count) {
  if (!count || count < 1) return;
  try {
    const stored = await chrome.storage.local.get([AUTOFILL_TIME_SAVED_KEY]);
    const prev = stored[AUTOFILL_TIME_SAVED_KEY] || 0;
    await chrome.storage.local.set({ [AUTOFILL_TIME_SAVED_KEY]: prev + count });
  } catch (_) { }
}

/** Get saved time text for display */
async function getSavedTimeDisplayText() {
  try {
    const stored = await chrome.storage.local.get([AUTOFILL_TIME_SAVED_KEY]);
    const total = stored[AUTOFILL_TIME_SAVED_KEY] || 0;
    const mins = Math.round((total * AVG_SECONDS_PER_FIELD) / 60);
    if (mins <= 0) return "One-click fill for this job application";
    return `You have saved ${mins} minute${mins === 1 ? "" : "s"} by autofilling so far 🔥`;
  } catch (_) {
    return "One-click fill for this job application";
  }
}

/** Update the saved-time status in the widget (call on mount / when idle) */
async function updateSavedTimeDisplay(root) {
  const statusEl = root?.querySelector?.("#ja-status");
  if (!statusEl) return;
  const text = await getSavedTimeDisplayText();
  if (!statusAreaHasFillResults(statusEl)) {
    statusEl.textContent = text;
    statusEl.className = "ja-status ja-autofill-hero-sub";
  }
}

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

/** Footer stats (Last fill / applications filled): GET /api/chrome-extension/summary when signed in; else chrome.storage fallback. */
async function updateAutofillFooterStats(root) {
  const lastEl = root?.querySelector?.("#ja-autofill-last-fill");
  const appsEl = root?.querySelector?.("#ja-autofill-apps-filled");
  if (!lastEl && !appsEl) return;

  let hasToken = false;
  try {
    const t = await chrome.storage.local.get(["accessToken"]);
    hasToken = !!t.accessToken;
  } catch (_) { }
  if (!hasToken) {
    try {
      const res = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
      if (res?.ok && res?.token) hasToken = true;
    } catch (_) { }
  }

  if (hasToken) {
    try {
      const apiBase = await getApiBase();
      const headers = await getAuthHeaders();
      if (headers.Authorization) {
        const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/summary`, { headers });
        if (res.ok) {
          const data = await res.json().catch(() => ({}));
          const apps = data.applications_filled;
          const lastIso = data.last_fill_time;
          if (lastEl) {
            const rel = formatRelativeTimeFromIso(lastIso);
            lastEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.clock}</span> Last fill: ${rel}`;
          }
          if (appsEl && typeof apps === "number" && Number.isFinite(apps)) {
            appsEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.layers}</span> ${apps} application${apps === 1 ? "" : "s"} filled`;
          }
          return;
        }
      }
    } catch (_) { }
  }

  try {
    const s = await chrome.storage.local.get(["hm_autofill_last_fill_label", "hm_autofill_apps_count"]);
    if (lastEl) {
      if (s.hm_autofill_last_fill_label) {
        lastEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.clock}</span> ${String(s.hm_autofill_last_fill_label)}`;
      } else {
        lastEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.clock}</span> Last fill: —`;
      }
    }
    if (appsEl) {
      if (typeof s.hm_autofill_apps_count === "number" && Number.isFinite(s.hm_autofill_apps_count)) {
        const n = s.hm_autofill_apps_count;
        appsEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.layers}</span> ${n} application${n === 1 ? "" : "s"} filled`;
      } else {
        appsEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.layers}</span> — applications filled`;
      }
    }
  } catch (_) {
    if (lastEl) {
      lastEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.clock}</span> Last fill: —`;
    }
    if (appsEl) {
      appsEl.innerHTML = `<span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.layers}</span> — applications filled`;
    }
  }
}

function statusAreaHasFillResults(statusEl) {
  if (!statusEl) return false;
  const html = statusEl.innerHTML || "";
  const text = (statusEl.textContent || "").trim();
  return html.includes("ja-status-bullets") || /✓\s*Filled\s+\d+/.test(text) || /Fields need attention/.test(text);
}

const AUTOFILL_FAILED_CLASS = "ja-autofill-failed";
function ensureFailHighlightStyle(doc = document) {
  const id = "ja-autofill-fail-style";
  if (doc.getElementById(id)) return;
  const style = doc.createElement("style");
  style.id = id;
  style.textContent = `.${AUTOFILL_FAILED_CLASS} { outline: 2px solid #dc2626 !important; box-shadow: 0 0 0 2px #dc2626 !important; }`;
  (doc.head || doc.documentElement).appendChild(style);
}

/** Get displayed value for any field type — used to detect if dropdown/combobox is filled */
function getFieldDisplayValue(field) {
  const tag = (field.tagName || "").toLowerCase();
  const role = (field.getAttribute("role") || "").toLowerCase();
  if (tag === "select") return (field.value || "").toString().trim();
  if (tag === "input" || tag === "textarea") return (field.value || "").toString().trim();
  if (tag === "div" || tag === "span") {
    const input = field.querySelector?.('input[type="text"],input[type="search"],input:not([type])');
    if (input) return (input.value || "").toString().trim();
    const placeholder = (field.getAttribute("placeholder") || "").toLowerCase();
    const singleValue = field.querySelector?.('[class*="singleValue"],[class*="single-value"],[data-value]');
    if (singleValue) return (singleValue.textContent || singleValue.getAttribute("data-value") || "").toString().trim();
    const text = (field.textContent || "").trim();
    if (text && !/select\.\.\.|choose|search/i.test(text) && text.length < 200) return text;
  }
  return (field.value ?? field.textContent ?? "").toString().trim();
}

function openDropdownForSelection(field) {
  try {
    if (field.disabled || field.getAttribute("aria-disabled") === "true") return;
    const tag = (field.tagName || "").toLowerCase();
    const role = (field.getAttribute("role") || "").toLowerCase();
    const isCombobox = role === "combobox" || field.closest?.("[class*='select']");
    if (tag === "select" || role === "combobox" || isCombobox) {
      field.focus();
      const rect = field.getBoundingClientRect();
      const opts = {
        bubbles: true,
        cancelable: true,
        view: field.ownerDocument?.defaultView || window,
        clientX: rect.left + rect.width / 2,
        clientY: rect.top + rect.height / 2,
      };
      field.dispatchEvent(new MouseEvent("mousedown", opts));
      field.dispatchEvent(new MouseEvent("mouseup", opts));
      field.dispatchEvent(new MouseEvent("click", opts));
    }
  } catch (_) { }
}

function highlightFailedField(field) {
  const doc = field.ownerDocument || document;
  ensureFailHighlightStyle(doc);
  field.classList.add(AUTOFILL_FAILED_CLASS);
  openDropdownForSelection(field);
}

function highlightUnfilledRequiredFields(includeNestedDocuments = true) {
  const fillable = getFillableFields(includeNestedDocuments, true);
  if (fillable.length === 0) return;
  let highlighted = 0;
  for (const field of fillable) {
    const meta = getFieldMeta(field);
    if (!meta.required) continue;
    const displayVal = getFieldDisplayValue(field);
    const isEmpty = !displayVal || displayVal === "" || /^select\.\.\.|^choose\s|^search\s/i.test(displayVal);
    if (isEmpty && field.isConnected && !field.disabled) {
      highlightFailedField(field);
      highlighted++;
    }
  }
  if (highlighted > 0) logInfo("Highlighted unfilled required fields", { count: highlighted });
}

const SCROLL_DURATION_MS = 80;
const SCROLL_WAIT_AFTER_MS = 30;

async function scrollFieldIntoView(field) {
  const rect = field.getBoundingClientRect();
  const vh = window.innerHeight;
  if (rect.top >= 0 && rect.bottom <= vh) return;
  try {
    field.scrollIntoView({ behavior: "auto", block: "center", inline: "nearest" });
  } catch (_) {
    field.scrollIntoView({ block: "center" });
  }
  await delay(SCROLL_DURATION_MS + SCROLL_WAIT_AFTER_MS);
}

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

async function fillFileInput(field, resumeData) {
  if (!resumeData?.buffer) return false;
  const fileName = resumeData.name || "resume.pdf";
  const mimeType = getMimeTypeForResume(fileName);
  const blob = new Blob([new Uint8Array(resumeData.buffer)], { type: mimeType });
  const file = new File([blob], fileName, { type: mimeType });
  const dt = new DataTransfer();
  dt.items.add(file);
  try {
    field.files = dt.files;
    dispatchFrameworkEvents(field);
    return field.files?.length > 0;
  } catch (e) {
    logWarn("fillFileInput failed (some sites block programmatic file assignment)", { error: String(e) });
    return false;
  }
}

function findContinueButton(doc = document) {
  // Workday-first: data-automation-id is most reliable
  const workdaySelectors = [
    '[data-automation-id="continueButton"]',
    '[data-automation-id="continue"]',
    '[data-automation-id="nextButton"]',
    '[data-automation-id*="continue"]',
    '[data-automation-id*="next"]',
    '[data-automation-id="submitButton"]',
  ];
  for (const sel of workdaySelectors) {
    try {
      const el = doc.querySelector(sel);
      if (el && el.getBoundingClientRect?.().width > 0) return el;
    } catch (_) { }
  }
  const sel = 'button, [role="button"], input[type="submit"]';
  for (const el of doc.querySelectorAll(sel)) {
    const text = (el.textContent || el.innerText || el.value || "").trim().toLowerCase();
    if (text.includes("continue") || text === "next" || text === "submit") return el;
  }
  for (const el of doc.querySelectorAll("*")) {
    if (!el.shadowRoot) continue;
    for (const sh of el.shadowRoot.querySelectorAll(sel)) {
      const text = (sh.textContent || sh.innerText || sh.value || "").trim().toLowerCase();
      if (text.includes("continue") || text === "next") return sh;
    }
  }
  return null;
}

const ENRICH_TIMEOUT_MS = 2000; // Never block scrape for more than 2s

/**
 * Fetch server's best-known selectors for fingerprints; prepend to each field's selector bundle.
 */
async function enrichFieldsWithLearnedSelectors(fields, atsPlatform) {
  const t0 = Date.now();
  if (!fields?.length) return fields;
  const fps = fields.map((f) => f.fingerprint).filter(Boolean);
  if (!fps.length) return fields;
  logInfo("enrichFieldsWithLearnedSelectors: calling best-batch", { fieldCount: fields.length });
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ENRICH_TIMEOUT_MS);
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    if (!headers?.Authorization) return fields;
    const res = await fetch(`${apiBase}/chrome-extension/selectors/best-batch`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ fps, ats_platform: atsPlatform || "unknown" }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) return fields;
    const { selectors } = await res.json();
    logInfo("enrichFieldsWithLearnedSelectors: done", { learnedCount: Object.keys(selectors || {}).length, ms: Date.now() - t0 });
    return fields.map((f) => {
      const learned = (selectors[f.fingerprint] || []).map((s) => ({
        ...s,
        priority: 0,
        source: "learned",
      }));
      return {
        ...f,
        selectors: [...learned, ...(f.selectors || [])],
        selector: learned[0]?.selector || f.selector,
      };
    });
  } catch (e) {
    logWarn("enrichFieldsWithLearnedSelectors failed", { error: String(e) });
    return fields;
  }
}

const FORM_STRUCTURE_FETCH_TIMEOUT_MS = 1500;

/**
 * Check IndexedDB formStructures cache first, then server. Timeout only on network fetch.
 * Skips cache read/write when hm_cache_enabled is false in storage.
 */
async function getKnownFormStructure(domain, url) {
  const t0 = Date.now();
  let useCache = true;
  try {
    const stored = await chrome.storage.local.get(["hm_cache_enabled"]);
    useCache = stored.hm_cache_enabled !== false;
  } catch (_) { }
  const cacheManager = window.__CACHE_MANAGER__;
  logInfo("getKnownFormStructure: entry", { domain, hasCacheManager: !!cacheManager, useCache });
  if (useCache) {
    try {
      if (cacheManager?.getCachedFormStructure) {
        logInfo("getKnownFormStructure: checking IndexedDB cache");
        const cached = await cacheManager.getCachedFormStructure(domain);
        if (cached) {
          logInfo("getKnownFormStructure: cache hit", { domain, ms: Date.now() - t0 });
          return cached;
        }
      }
    } catch (_) { }
  }
  try {
    logInfo("getKnownFormStructure: fetching from server", { domain });
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FORM_STRUCTURE_FETCH_TIMEOUT_MS);
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const res = await fetch(
      `${apiBase}/chrome-extension/form-structure/check?domain=${encodeURIComponent(domain)}&url=${encodeURIComponent(url || "")}`,
      { headers, signal: controller.signal }
    );
    clearTimeout(timer);
    if (!res.ok) return null;
    const data = await res.json();
    logInfo("getKnownFormStructure: server response", { found: data?.found, ms: Date.now() - t0 });
    if (!data.found) return null;
    if (useCache && cacheManager?.setCachedFormStructure) {
      await cacheManager.setCachedFormStructure(domain, data);
    }
    return data;
  } catch (e) {
    logWarn("getKnownFormStructure: failed", { error: String(e) });
    return null;
  }
}

/**
 * Fast scrape using known field fingerprints + best selectors. Returns null if <50% found.
 */
async function fastScrapeWithKnownStructure(knownStructure) {
  const expectedFps = knownStructure.field_fps || [];
  const bestSelectors = knownStructure.best_selectors || {};
  const results = [];
  for (const fp of expectedFps) {
    const best = bestSelectors[fp];
    if (!best?.selector) continue;
    const el = document.querySelector(best.selector);
    if (!el) continue;
    const label =
      el.getAttribute("aria-label") ||
      (el.labels?.[0]?.textContent?.trim()) ||
      el.getAttribute("placeholder") ||
      el.getAttribute("name") ||
      "";
    results.push({
      fingerprint: fp,
      label,
      type: (el.type || el.tagName || "").toLowerCase(),
      selector: best.selector,
      selectors: [{ selector: best.selector, type: best.type || "css", priority: 0, source: "learned" }],
      options: el.tagName === "SELECT" ? Array.from(el.options || []).map((o) => (o.text || "").trim()).filter(Boolean) : [],
      source: "fast_scrape",
    });
  }
  if (results.length < expectedFps.length * 0.5) {
    logInfo("Fast scrape found only", results.length, "/", expectedFps.length, "— falling back");
    return null;
  }
  logInfo("Fast scrape — known structure, confidence:", knownStructure.confidence);
  return results;
}

/**
 * Smart scrape: fast path if known form, full DOM scan otherwise.
 */
async function scrapeWithLearning(options) {
  const t0 = Date.now();
  const domain = location.hostname;
  const url = location.href;
  logInfo("scrapeWithLearning: start", { domain });

  let knownStructure = null;
  try {
    knownStructure = await getKnownFormStructure(domain, url);
  } catch (e) {
    logWarn("scrapeWithLearning: getKnownFormStructure failed", { error: String(e), ms: Date.now() - t0 });
  }

  if (knownStructure && knownStructure.confidence > 0.85) {
    const fastResult = await fastScrapeWithKnownStructure(knownStructure);
    if (fastResult && fastResult.length > 0) {
      const ats = window.__OPSBRAIN_ATS__ || (window.__HIREMATE_FIELD_SCRAPER__?.detectPlatform?.(document) || "unknown");
      return await enrichFieldsWithLearnedSelectors(fastResult, ats);
    }
  }
  logInfo("scrapeWithLearning: full DOM path (no fast path)", { ms: Date.now() - t0 });
  return null;
}

async function scrapeFields(options = {}) {
  const t0 = Date.now();
  const includeNestedDocuments = options.scope !== "current_document";
  const expandSelectOptions = options.expandSelectOptions !== false;
  const preExpandEmployment = Math.max(0, options.preExpandEmployment || 0);
  const preExpandEducation = Math.max(0, options.preExpandEducation || 0);
  logInfo("scrapeFields: start", { scope: options.scope, expandSelectOptions, preExpandEmployment, preExpandEducation });

  const scraper = typeof window !== "undefined" && window.__HIREMATE_FIELD_SCRAPER__;
  logInfo("scrapeFields: scraper check", { hasScraper: !!scraper });

  const atsPlatform = window.__OPSBRAIN_ATS__ || (scraper?.detectPlatform?.(document) || "unknown");
  if (scraper?.detectPlatform && !window.__OPSBRAIN_ATS__) {
    window.__OPSBRAIN_ATS__ = atsPlatform;
  }

  const doc = document;
  const maxEducationBlocks = Math.max(1, options.maxEducationBlocks ?? 999);
  const maxEmploymentBlocks = Math.max(1, options.maxEmploymentBlocks ?? 999);
  function findRemoveBtn(container) {
    if (!container) return null;
    const text = (n) => (n?.textContent || n?.getAttribute?.("aria-label") || n?.getAttribute?.("title") || "").toLowerCase();
    for (const el of container.querySelectorAll("button, a[href='#'], [role='button']")) {
      if (/\b(remove|delete|clear)\b/.test(text(el))) return el;
      const svg = el.querySelector("svg");
      if (svg) return el;
    }
    return null;
  }
  for (let round = 0; round < 2; round++) {
    const maxBlocks = round === 0 ? maxEmploymentBlocks : maxEducationBlocks;
    const ids = round === 0 ? ["company", "job_title", "employer"] : ["school", "degree"];
    const anchors = doc.querySelectorAll(ids.map((p) => `[id^="${p}--"]`).join(", "));
    const indices = [...new Set(Array.from(anchors).map((el) => {
      const m = (el.id || "").match(/(\d+)$/);
      return m ? parseInt(m[1], 10) : -1;
    }).filter((n) => n >= 0))].sort((a, b) => b - a);
    for (const idx of indices) {
      if (idx >= maxBlocks) {
        const anchor = ids.reduce((a, p) => a || doc.getElementById(`${p}--${idx}`), null);
        if (anchor) {
          const block = anchor.closest("[class*='field'],[class*='block'],[class*='question'],fieldset") || anchor.parentElement?.parentElement;
          const btn = block && findRemoveBtn(block);
          if (btn) {
            btn.click();
            await new Promise((r) => setTimeout(r, 500));
            logInfo("Removed extra block", { round: round ? "education" : "employment", index: idx });
          }
        }
      }
    }
  }

  // Expand "Add another" (employment/education) at start of initial scrape so both fast path and full scrape see extended form
  if (scraper?.findAddAnotherLinks) {
    for (let round = 0; round < 2; round++) {
      const hint = round === 0 ? "employment" : "education";
      const count = round === 0 ? preExpandEmployment : preExpandEducation;
      for (let i = 0; i < count; i++) {
        const links = scraper.findAddAnotherLinks(doc, hint);
        if (links.length === 0) break;
        try {
          const el = links[0];
          el.scrollIntoView({ block: "center", behavior: "auto" });
          await new Promise((r) => setTimeout(r, 200));
          const rect = el.getBoundingClientRect();
          const x = rect.left + rect.width / 2;
          const y = rect.top + rect.height / 2;
          for (const name of ["mousedown", "mouseup", "click"]) {
            el.dispatchEvent(new MouseEvent(name, { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y }));
          }
          await new Promise((r) => setTimeout(r, 800));
        } catch (_) { }
      }
    }
  }

  logInfo("scrapeFields: calling scrapeWithLearning", { ms: Date.now() - t0 });
  const fastResult = await scrapeWithLearning(options);
  logInfo("scrapeFields: scrapeWithLearning returned", { fastPath: !!fastResult?.length, count: fastResult?.length || 0, ms: Date.now() - t0 });
  if (fastResult && fastResult.length > 0) {
    const fields = fastResult.map((f, index) => ({
      index,
      label: f.label || null,
      name: f.name || null,
      id: f.id || null,
      placeholder: f.placeholder || null,
      required: f.required || false,
      type: f.type || null,
      tag: f.tag || f.type || null,
      role: null,
      options: f.options || null,
      selector: f.selector,
      selectors: f.selectors,
      atsFieldType: f.atsFieldType || null,
      isStandardField: f.isStandardField || false,
      fingerprint: f.fingerprint,
    }));
    logInfo("Scrape: fast path completed", { totalFields: fields.length });
    return { fields };
  }

  if (scraper) {
    logInfo("scrapeFields: full DOM scrape via scraper", { ms: Date.now() - t0 });
    try {
      const scrapeOpts = {
        scope: includeNestedDocuments ? "all" : "current_document",
        includeHidden: true,
        excludePredicate: isInsideExtensionWidget,
        expandSelectOptions,
      };
      let result = expandSelectOptions && scraper.getScrapedFieldsWithExpandedOptions
        ? await scraper.getScrapedFieldsWithExpandedOptions(scrapeOpts)
        : scraper.getScrapedFields(scrapeOpts);
      if (scraper.attachShaFingerprints && result.fields?.length > 0) {
        await scraper.attachShaFingerprints(result.fields);
      }
      if (result.fields.length === 0) {
        result = scraper.getScrapedFields({
          scope: includeNestedDocuments ? "all" : "current_document",
          includeHidden: false,
          excludePredicate: isInsideExtensionWidget,
          expandSelectOptions: false,
        });
        if (scraper.attachShaFingerprints && result.fields?.length > 0) {
          await scraper.attachShaFingerprints(result.fields);
        }
      }
      if (result.fields.length > 0) {
        result.fields = await enrichFieldsWithLearnedSelectors(result.fields, atsPlatform);
        const fields = result.fields.map((f, index) => ({
          index,
          label: f.label || null,
          name: f.name || null,
          id: f.id || null,
          placeholder: f.placeholder || null,
          required: f.required,
          type: f.type || null,
          tag: f.tagName || f.tag || null,
          role: f.element?.getAttribute?.("role") || null,
          options: f.options || null,
          selector: f.selector,
          selectors: f.selectors,
          atsFieldType: f.atsFieldType,
          isStandardField: f.isStandardField,
          fingerprint: f.fingerprint,
        }));
        const preview = fields.slice(0, 15).map((f) => ({
          index: f.index,
          type: f.type,
          label: f.label,
          id: f.id,
          name: f.name,
          required: f.required,
        }));
        logInfo("Scrape: completed", {
          totalFields: fields.length,
          requiredFields: fields.filter((f) => f.required).length,
          fields: preview,
        });
        return { fields };
      }
    } catch (e) {
      logWarn("Enhanced field scraper failed, falling back", { error: String(e) });
    }
  } else {
    logInfo("scrapeFields: no scraper, using legacy getFillableFields", { ms: Date.now() - t0 });
  }
  let fillable = getFillableFields(includeNestedDocuments || true, true);
  if (fillable.length === 0) {
    fillable = getFillableFields(true, false);
  }
  if (fillable.length === 0) {
    fillable = getFillableFields(true, true);
  }
  const fields = fillable.map((el, index) => {
    const meta = getFieldMeta(el);
    const opts =
      meta.tag === "select"
        ? Array.from(el.options || [])
          .map((o) => (o.text || "").trim())
          .filter(Boolean)
        : null;
    const id = meta.id || null;
    const selector = id ? `#${CSS.escape(id)}` : null;

    return {
      index,
      label: meta.label || null,
      name: meta.name || null,
      id,
      selector,
      placeholder: meta.placeholder || null,
      required: meta.required,
      type: meta.type || null,
      tag: meta.tag || null,
      role: meta.role || null,
      options: opts,
    };
  });
  const preview = fields.slice(0, 15).map((f) => ({
    index: f.index,
    type: f.type,
    label: f.label,
    id: f.id,
    name: f.name,
    required: f.required,
  }));
  logInfo("Scrape: completed (legacy)", {
    totalFields: fields.length,
    requiredFields: fields.filter((f) => f.required).length,
    fields: preview,
  });
  return { fields };
}

function isEmptyField(field) {
  const tag = (field.tagName || "").toLowerCase();
  if (field.isContentEditable) return !normalizeKey(getText(field));
  if (tag === "input") {
    const type = (field.type || "").toLowerCase();
    if (type === "checkbox" || type === "radio") return !field.checked;
    return !String(field.value || "").trim();
  }
  if (tag === "textarea") return !String(field.value || "").trim();
  if (tag === "select") return !String(field.value || "").trim();
  return !normalizeKey(getText(field));
}

function getFieldKeys(meta) {
  const sources = [
    meta.label,
    meta.name,
    meta.id,
    meta.placeholder,
    meta.type,
    meta.role,
    meta.tag,
  ].filter(Boolean);
  return sources.map((s) => normalizeKey(s)).filter(Boolean);
}

function pickRuleBasedValue(meta, profile, customAnswers) {
  const keys = getFieldKeys(meta);
  const allText = keys.join(" ");

  const customEntries = Object.entries(customAnswers || {});
  for (const [question, answer] of customEntries) {
    const normQ = normalizeKey(question);
    if (!normQ || !answer) continue;
    if (keys.includes(normQ) || allText.includes(normQ) || normQ.includes(allText)) return answer;
  }

  for (const [profileKey, aliases] of Object.entries(FIELD_MAP)) {
    if (!profile?.[profileKey]) continue;
    const match = aliases.some((alias) => {
      const normAlias = normalizeKey(alias);
      return keys.includes(normAlias) || allText.includes(normAlias);
    });
    if (match) return profile[profileKey];
  }

  if (meta.tag === "input" && TEXTLIKE_INPUT_TYPES.has(meta.type)) {
    if (meta.type === "email" && profile?.email) return profile.email;
    if (meta.type === "tel" && profile?.phone) return profile.phone;
    if (meta.type === "url") {
      if (allText.includes("linkedin") && profile?.linkedin) return profile.linkedin;
      if (allText.includes("github") && profile?.github) return profile.github;
      if (profile?.portfolio) return profile.portfolio;
    }
  }

  if (meta.tag === "textarea" && profile?.experience) {
    if (allText.includes("experience") || allText.includes("summary") || allText.includes("about")) {
      return profile.experience;
    }
  }

  return null;
}

async function getResumeFromBackground() {
  try {
    const res = await chrome.runtime.sendMessage({ type: "GET_RESUME" });
    if (res?.ok) return res.data || null;
  } catch (_) {
    // Ignore resume retrieval errors for non-file fields.
  }
  return null;
}

async function fillWithValues(payload) {
  const humanFiller = typeof window !== "undefined" && window.__HIREMATE_HUMAN_FILLER__;
  if (humanFiller) {
    try {
      const includeNestedDocuments = payload.scope !== "current_document";
      const { values = {}, fieldsForFrame = [], resumeData, onProgress, shouldAbort } = payload;
      logInfo("Fill: starting (human-like)", {
        providedValues: Object.keys(values).length,
        fieldsWithSelectors: fieldsForFrame.length,
        scope: payload.scope,
      });
      // Use includeHidden: true to match scrape order (avoids index mismatch)
      let fillable = getFillableFields(includeNestedDocuments, true);
      if (fillable.length === 0) fillable = getFillableFields(true, false);
      const resumeWithTimeout = () =>
        Promise.race([
          getResumeFromBackground(),
          new Promise((_, rej) => setTimeout(() => rej(new Error("Resume timeout")), 8000)),
        ]).catch(() => null);
      const effectiveResumeData = resumeData || (await resumeWithTimeout()) || (await getStaticResume());

      const result = await humanFiller.fillWithValuesHumanLike({
        elements: fillable,
        values,
        valuesByIndex: values,
        fieldsForFrame,
        resumeData: effectiveResumeData,
        getFieldMeta,
        getFieldKeys,
        dispatchFrameworkEvents,
        onProgress,
        shouldAbort,
        formatDateForInput,
        highlightFailedField,
      });

      logInfo("Fill: completed (human-like)", {
        totalFillable: fillable.length,
        filled: result.filledCount,
        resumes: result.resumeUploadCount,
        failed: result.failedCount,
      });
      highlightUnfilledRequiredFields(includeNestedDocuments);
      return result;
    } catch (e) {
      logWarn("Human filler failed, falling back to legacy", { error: String(e) });
    }
  }

  const includeNestedDocuments = payload.scope !== "current_document";
  const { values = {}, resumeData, onProgress, shouldAbort, shouldSkip } = payload;
  logInfo("Fill: starting (legacy)", {
    providedValues: Object.keys(values).length,
    scope: payload.scope,
  });
  let fillable = getFillableFields(includeNestedDocuments, false);
  if (fillable.length === 0) fillable = getFillableFields(true, true);
  const resumeWithTimeout = () =>
    Promise.race([
      getResumeFromBackground(),
      new Promise((_, rej) => setTimeout(() => rej(new Error("Resume timeout")), 8000)),
    ]).catch(() => null);
  const effectiveResumeData = resumeData || (await resumeWithTimeout()) || (await getStaticResume());
  const fillDelay = 60 + Math.floor(Math.random() * 60);
  let filledCount = 0;
  let resumeUploadCount = 0;
  let failedCount = 0;
  const failedFields = [];

  const indexed = fillable.map((el, i) => ({ element: el, originalIndex: i }));

  const totalToFill = indexed.length;
  for (let idx = 0; idx < indexed.length; idx++) {
    if (shouldAbort?.()) break;
    if (shouldSkip?.()) continue;
    const { element: field, originalIndex: i } = indexed[idx];
    const id = field.getAttribute("id");
    let val;

    await scrollFieldIntoView(field);

    const meta = getFieldMeta(field);
    const fieldLabel = meta.label || meta.name || meta.placeholder || getClosestQuestionText(field) || `Field ${i + 1}`;
    const isResumeField =
      (field.type || "").toLowerCase() === "file" &&
      (getFieldKeys(meta).join(" ").includes("resume") || getFieldKeys(meta).join(" ").includes("cv"));
    const progressMessage = isResumeField
      ? "Filling resume..."
      : `Filling field ${idx + 1} of ${totalToFill}`;
    if (onProgress) {
      onProgress({
        phase: "filling",
        current: idx + 1,
        total: totalToFill,
        message: progressMessage,
        label: fieldLabel,
      });
    }

    if (id && values[id] !== undefined) {
      val = typeof values[id] === "object" && values[id] !== null ? values[id].value : values[id];
    } else if (values[i] !== undefined) {
      val = typeof values[i] === "object" && values[i] !== null ? values[i].value : values[i];
    }

    if ((field.type || "").toLowerCase() === "file") {
      const fieldKeysText = getFieldKeys(meta).join(" ");
      const looksLikeResumeField = fieldKeysText.includes("resume") || fieldKeysText.includes("cv");
      const shouldUploadResume = val === "RESUME_FILE" || looksLikeResumeField;
      if (shouldUploadResume && effectiveResumeData) {
        const ok = await fillFileInput(field, effectiveResumeData);
        if (ok) {
          resumeUploadCount += 1;
          logInfo("Filled resume field", { index: i, label: meta.label });
        } else {
          failedCount += 1;
          highlightFailedField(field);
          failedFields.push({ element: field, label: fieldLabel });
        }
      } else if (shouldUploadResume) {
        failedCount += 1;
        highlightFailedField(field);
        failedFields.push({ element: field, label: fieldLabel });
        logWarn("Resume field found but no resume data available", {
          index: i,
          id: id || null,
          label: meta.label || null,
        });
      }
      await delay(fillDelay);
      continue;
    }

    if (val === undefined || val === null || val === "") {
      if (meta.required) {
        failedCount += 1;
        highlightFailedField(field);
        failedFields.push({ element: field, label: fieldLabel });
      }
      await delay(fillDelay);
      continue;
    }

    const success = setNativeValue(field, val);
    if (success) {
      filledCount += 1;
      logInfo("Filled field", { index: i, label: meta.label, value: String(val).substring(0, 50) });
    } else {
      failedCount += 1;
      highlightFailedField(field);
      failedFields.push({ element: field, label: fieldLabel });
    }
    await delay(fillDelay);
  }
  logInfo("Fill: completed (legacy)", {
    totalFillable: fillable.length,
    filled: filledCount,
    resumes: resumeUploadCount,
    failed: failedCount,
  });
  highlightUnfilledRequiredFields(includeNestedDocuments);
  return { filledCount, resumeUploadCount, failedCount, failedFields };
}

async function fillFormRuleBased(payload = {}) {
  const includeNestedDocuments = payload.scope !== "current_document";
  logInfo("Starting rule-based fill");
  const [{ profile = {}, customAnswers = {} }, resumeData] = await Promise.all([
    chrome.storage.local.get(["profile", "customAnswers"]),
    getResumeFromBackground(),
  ]);

  const fillable = getFillableFields(includeNestedDocuments);
  const fillDelay = 60 + Math.floor(Math.random() * 60);
  let filledCount = 0;
  let resumeUploadCount = 0;

  for (const field of fillable) {
    if (!isEmptyField(field)) continue;

    const meta = getFieldMeta(field);
    if (meta.type === "file") {
      const shouldUseResume = getFieldKeys(meta).join(" ").includes("resume");
      if (shouldUseResume && resumeData) {
        const ok = await fillFileInput(field, resumeData);
        if (ok) {
          filledCount += 1;
          resumeUploadCount += 1;
        }
      }
      await delay(fillDelay);
      continue;
    }

    const val = pickRuleBasedValue(meta, profile, customAnswers);
    if (!val) continue;

    const ok = setNativeValue(field, val);
    if (ok) {
      filledCount += 1;
      await delay(fillDelay);
    }
  }

  logInfo("Rule-based fill completed", {
    totalFillable: fillable.length,
    totalFilled: filledCount,
    resumeUploads: resumeUploadCount,
  });
  return { filledCount };
}

function isCareerPage(urlStr = window.location.href) {
  const url = String(urlStr || "").toLowerCase();
  return (
    url.includes("/careers") ||
    url.includes("careers.") ||
    url.includes("jobs.") ||
    url.includes("/jobs") ||
    url.includes("/apply") ||
    url.includes("/job/") ||
    url.includes("greenhouse.io") ||
    url.includes("lever.co") ||
    url.includes("myworkdayjobs.com") ||
    url.includes("workday.com") ||
    url.includes("smartrecruiters.com") ||
    url.includes("icims.com") ||
    url.includes("ashbyhq.com") ||
    url.includes("bamboohr.com") ||
    url.includes("jobvite.com") ||
    url.includes("recruit") ||
    url.includes("talent")
  );
}

/** Content hint: page shows multiple job listings (cards/links). */
function hasListingPageContent() {
  const body = document.body;
  if (!body) return false;
  const sel = [
    "a[href*='job']",
    "a[href*='career']",
    "a[href*='position']",
    "[data-job-id]",
    "[data-testid*='job-card']",
    "[class*='job-card']",
    "[class*='job-listing']",
    "[class*='position-card']",
  ].join(",");
  const matches = body.querySelectorAll(sel);
  const jobLikeCount = Array.from(matches).filter((el) => {
    const text = (el.textContent || "").trim();
    const href = (el.getAttribute("href") || "").toLowerCase();
    return text.length >= 10 && text.length < 120 && (href.includes("job") || href.includes("detail") || href.includes("position"));
  }).length;
  const headings = body.querySelectorAll("h2, h3, h4");
  const multiTitle = headings.length >= 4 && Array.from(headings).filter((h) => (h.textContent || "").trim().length >= 5 && (h.textContent || "").trim().length < 100).length >= 3;
  return jobLikeCount >= 5 || multiTitle;
}

/** Content hint: page has single JD (Apply button + JD keywords). */
function hasJobDetailContent() {
  const body = document.body;
  if (!body) return false;
  const text = (body.innerText || body.textContent || "").toLowerCase();
  if (text.length < 400) return false;
  const jdKeywords = ["responsibilities", "requirements", "qualifications", "experience", "about the role", "what you will"];
  const jdScore = jdKeywords.filter((k) => text.includes(k)).length;
  const hasApply =
    /apply|submit application|apply now/i.test(text) ||
    !!body.querySelector('a[href*="apply"]') ||
    !!body.querySelector("[class*='apply']") ||
    Array.from(body.querySelectorAll("a, button")).some((el) => /^\s*apply\s*$/i.test((el.textContent || "").trim()));
  return jdScore >= 2 && hasApply;
}

/** True when page is a job LISTING (many jobs). No popup. Works across all career sites. */
function isJobListingPage(urlStr = window.location.href) {
  try {
    const path = new URL(urlStr || "").pathname.toLowerCase().replace(/\/+$/, "") || "/";
    const listingPaths = [
      "/jobs",
      "/careers",
      "/positions",
      "/opportunities",
      "/vacancies",
      "/openings",
      "/open-positions",
      "/current-openings",
      "/jobs/all",
      "/jobs/search",
      "/careers/all",
      "/careers/search",
      "/positions/all",
      "/opportunities/all",
      "/join",
      "/join-us",
      "/work-with-us",
    ];
    if (listingPaths.some((p) => path === p)) return true;
    if (/\/jobs\/?$|\/careers\/?$|\/positions\/?$/.test(path)) return true;
    if (path === "/" && /jobs\.|careers\.|greenhouse\.|lever\.|workday\.|ashbyhq\.|bamboohr\.|icims\.|smartrecruiters\./i.test(urlStr || "")) return true;
    if (hasListingPageContent() && !isJobDetailPage(urlStr)) return true;
    return false;
  } catch (_) {
    return false;
  }
}

/** True when page is a single JD. Popup allowed. Works across all career sites. */
function isJobDetailPage(urlStr = window.location.href) {
  const url = (urlStr || "").toLowerCase();
  try {
    const path = new URL(urlStr || "").pathname.toLowerCase();
    const search = new URL(urlStr || "").search.toLowerCase();

    if (path === "/jobs" || path === "/jobs/" || path === "/careers" || path === "/careers/") return false;

    const hasJdInPath = /\/(detail|job|position|opportunity|vacancy|posting|role|opening)\/?([^/]|$)/.test(path);
    const hasJdInQuery = /[?&](gh_jid|jid|job_id|jobid|position_id|opportunity_id|posting_id|req_id|reqid|id)=/.test(search);
    const hasNestedJobPath =
      /\/jobs\/[^/]+\/detail/.test(path) ||
      (/\/careers\/[^/]+/.test(path) && !/\/careers\/(all|search)\/?$/.test(path)) ||
      /\/job\/[^/]+|\/position\/[^/]+|\/opportunity\/[^/]+|\/posting\/[^/]+|\/role\/[^/]+|\/vacancy\/[^/]+/.test(path);
    const atsJdPattern = /(greenhouse|lever|workday|ashbyhq|bamboohr|icims|smartrecruiters|jobvite)[^/]*\/[^/]+\/[^/\s]+/.test(url);

    if (hasJdInPath || hasJdInQuery || hasNestedJobPath || atsJdPattern) return true;

    if (isCareerPage(urlStr) && hasJobDetailContent()) return true;
    return false;
  } catch (_) {
    return false;
  }
}

async function isJobPageViaLLM(url, title, snippet) {
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/job-page-detect`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ url: url || "", title: title || "", snippet: (snippet || "").slice(0, 800) }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.is_job_page === true;
  } catch (_) {
    return null;
  }
}

const KEYWORD_MATCH_ROOT_ID = "ja-keyword-match-root";

/** Get page HTML from all frames (main + iframes) - works for Greenhouse embeds, Lever, etc. */
async function getPageHtmlForKeywordsApi() {
  try {
    const res = await chrome.runtime.sendMessage({ type: "GET_ALL_FRAMES_HTML" });
    if (res?.ok && res.html) return res.html;
  } catch (_) { }
  try {
    const el = document.documentElement || document.body;
    if (!el) return null;
    const html = (el.outerHTML || el.innerHTML || "").slice(0, 1500000);
    return html && html.length > 100 ? html : null;
  } catch (_) {
    return null;
  }
}

/** Fetch job description via keywords/analyze (sends client-scraped page_html from all frames). */
async function fetchJobDescriptionFromKeywordsApi(url) {
  if (!url || !url.startsWith("http")) return null;
  try {
    const pageHtml = await getPageHtmlForKeywordsApi();
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const body = { url, page_html: pageHtml || undefined };
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/keywords/analyze`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.job_description && data.job_description.length >= 50 ? data.job_description : null;
  } catch (e) {
    logWarn("fetchJobDescriptionFromKeywordsApi failed", { url: url?.slice(0, 80), error: String(e) });
    return null;
  }
}

async function runKeywordAnalysisAndMaybeShowWidget() {
  if (window.self !== window.top) return;
  if (document.getElementById(KEYWORD_MATCH_ROOT_ID) || document.getElementById("opsbrain-match-widget")) return;
  if (/workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(window.location.href)) return;

  const url = window.location.href;
  const urlSuggestsJob = isCareerPage(url);
  if (!urlSuggestsJob) {
    if (window.__PAGE_DETECTOR__ && !window.__PAGE_DETECTOR__.shouldShowWidget()) return;
    const snippet = (document.body?.innerText || document.body?.textContent || "").replace(/\s+/g, " ").slice(0, 800);
    const llmSaysJob = await isJobPageViaLLM(url, document.title, snippet);
    if (llmSaysJob !== true) return;
  }

  setTimeout(async () => {
    const cacheKey = `keyword_analysis:${url}`;
    const requestManager = window.__REQUEST_MANAGER__;
    const cacheManager = window.__CACHE_MANAGER__;

    const fetchAndShow = async () => {
      const pageHtml = await getPageHtmlForKeywordsApi();
      const apiBase = await getApiBase();
      const headers = await getAuthHeaders();
      const body = { url, page_html: (pageHtml || "").slice(0, 50000) };
      const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/keywords/analyze`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) return null;
      const data = await res.json();
      if ((data.total_keywords || 0) === 0) return null;
      if (cacheManager) {
        try { await cacheManager.set("keywordAnalysis", { url, result: data }); } catch (_) { }
      }
      return data;
    };

    try {
      let data = null;
      if (cacheManager) {
        try {
          const cached = await cacheManager.get("keywordAnalysis", url);
          const CACHE_TTL = (window.__CONFIG__?.get?.("cacheTTL")?.keywordAnalysis) || 30 * 60 * 1000;
          if (cached?.result && cached?.timestamp && Date.now() - cached.timestamp < CACHE_TTL) {
            if (window.__CONFIG__?.log) window.__CONFIG__.log("[Keyword] Cache hit");
            data = cached.result;
          }
        } catch (_) { }
      }
      if (!data) {
        data = requestManager?.dedupedRequest
          ? await requestManager.dedupedRequest(cacheKey, fetchAndShow, 30 * 60 * 1000)
          : await fetchAndShow();
      }
      if (!data || (data.percent || 0) < 60) return;
      if (window.__PROFESSIONAL_WIDGET__) {
        const Widget = window.__PROFESSIONAL_WIDGET__;
        const widget = new Widget();
        widget.create(data);
      } else {
        mountKeywordMatchWidgetWithData({ matched: data.matched_count, total: data.total_keywords, percent: data.percent });
      }
    } catch (_) { }
  }, 2000);
}

function mountKeywordMatchWidgetWithData({ matched, total, percent }) {
  if (document.getElementById(KEYWORD_MATCH_ROOT_ID)) return;

  const root = document.createElement("div");
  root.id = KEYWORD_MATCH_ROOT_ID;
  root.innerHTML = `
    <style>
      #${KEYWORD_MATCH_ROOT_ID} {
        all: initial;
        position: fixed;
        right: 20px;
        top: 50%;
        transform: translateY(-50%);
        z-index: 2147483646;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 14px;
      }
      #${KEYWORD_MATCH_ROOT_ID} * { box-sizing: border-box; }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-card {
        width: 180px;
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        padding: 16px;
        text-align: center;
        margin: 0 auto;
        cursor: pointer;
        transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-card:hover {
        box-shadow: 0 8px 28px rgba(14,165,233,0.2);
        border-color: #0ea5e9;
        transform: translateY(-2px);
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-circle {
        width: 64px;
        height: 64px;
        margin: 0 auto 12px;
        border-radius: 50%;
        background: conic-gradient(#0ea5e9 ${percent * 3.6}deg, #e5e7eb ${percent * 3.6}deg);
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-circle-inner {
        width: 52px;
        height: 52px;
        border-radius: 50%;
        background: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 700;
        color: #0ea5e9;
      }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-title { font-size: 13px; font-weight: 600; color: #111; margin-bottom: 4px; }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-desc { font-size: 11px; color: #6b7280; }
      #${KEYWORD_MATCH_ROOT_ID} .ja-kw-tag { display: inline-block; margin-top: 8px; font-size: 10px; color: #0ea5e9; font-weight: 600; text-decoration: underline; cursor: pointer; }
    </style>
    <div class="ja-kw-card">
      <div class="ja-kw-circle" id="ja-kw-circle"><div class="ja-kw-circle-inner" id="ja-kw-percent">${percent}%</div></div>
      <div class="ja-kw-title">Resume Match</div>
      <div class="ja-kw-desc" id="ja-kw-desc">${percent}% – ${matched} of ${total} keywords in your resume.</div>
      <span class="ja-kw-tag">OpsBrain</span>
    </div>
  `;
  document.documentElement.appendChild(root);

  const card = root.querySelector(".ja-kw-card");
  const hiremateLink = root.querySelector(".ja-kw-tag");
  card?.addEventListener("click", (e) => {
    if (e.target === hiremateLink || hiremateLink?.contains(e.target)) return;
    mountInPageUI();
    const widget = document.getElementById(INPAGE_ROOT_ID);
    if (widget) {
      const cardEl = widget.querySelector(".ja-card");
      if (cardEl) cardEl.classList.remove("collapsed");
      const keywordsTab = widget.querySelector('[data-tab="keywords"]');
      if (keywordsTab) keywordsTab.click();
    }
  });
  hiremateLink?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    openResumeGeneratorUrl();
  });
}

async function getApiBase() {
  if (window.__CONFIG__?.getApiBase) return window.__CONFIG__.getApiBase();
  try {
    const data = await chrome.storage.local.get(["apiBase"]);
    return data.apiBase || "http://localhost:8000/api";
  } catch (_) {
    return "http://localhost:8000/api";
  }
}

function normalizeUrlForTailor(u) {
  if (!u || typeof u !== "string") return "";
  const s = u.trim();
  if (!s) return "";
  const withoutHash = s.split("#")[0] || s;
  return withoutHash.replace(/\/+$/, "") || withoutHash;
}

async function openResumeGeneratorUrl() {
  const data = await chrome.storage.local.get(["loginPageUrl"]);
  const base = data.loginPageUrl ? new URL(data.loginPageUrl).origin : "http://localhost:5173";
  let url = `${base}/resume-generator/build?tailor=1`;
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const widget = document.getElementById(INPAGE_ROOT_ID);
    const lastJobId = widget?.dataset?.lastJobId;
    const lastJobUrl = widget?.dataset?.lastJobUrl;
    const currentUrl = normalizeUrlForTailor(window.location.href);
    const useJobId = lastJobId && lastJobUrl && currentUrl === normalizeUrlForTailor(lastJobUrl);

    if (useJobId && headers?.Authorization) {
      const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/tailor-context`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: parseInt(lastJobId, 10) }),
      });
      if (res.ok) {
        url = `${base}/resume-generator/build?tailor=1&job_id=${lastJobId}`;
        chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url });
        return;
      }
    }
    const pageHtml = await getPageHtmlForKeywordsApi();
    if (pageHtml && pageHtml.length > 100 && headers?.Authorization) {
      const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/tailor-context`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          page_html: pageHtml,
          url: window.location.href,
          job_title: document.querySelector("h1, [data-automation-id='jobTitle'], .job-title, [class*='job-title']")?.textContent?.trim?.()?.slice(0, 100) || "",
        }),
      });
      if (res.ok) {
        const json = await res.json().catch(() => ({}));
        const jobId = json?.job_id;
        url = jobId ? `${base}/resume-generator/build?tailor=1&job_id=${jobId}` : `${base}/resume-generator/build?tailor=1`;
      }
    }
  } catch (err) {
    logWarn("Tailor context save failed", { error: String(err) });
  }
  chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url });
}

/** Build auth refresh URL - handles apiBase with or without /api suffix. */
function getRefreshUrl(apiBase) {
  const base = String(apiBase || "").replace(/\/+$/, "");
  if (base.endsWith("/api")) return `${base}/auth/refresh`;
  return `${base}${base ? "/" : ""}api/auth/refresh`;
}

/** Mutex: only one refresh in flight; others wait and reuse the result. */
let _refreshInFlight = null;

/** Refresh token via API (only on 401). Returns new token or null. Tries multiple URL patterns (404 can mean wrong path/port). */
async function refreshTokenViaApi() {
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = (async () => {
    try {
      const data = await chrome.storage.local.get(["accessToken", "apiBase"]);
      const oldToken = data.accessToken;
      if (!oldToken) {
        logWarn("refreshTokenViaApi: No token in storage, cannot refresh");
        return null;
      }
      const apiBase = data.apiBase || "http://localhost:8000/api";
      const baseNoApi = apiBase.replace(/\/api\/?$/, "");
      const urlsToTry = [
        getRefreshUrl(apiBase),
        `${apiBase}/auth/refresh`,
        `${baseNoApi}/api/auth/refresh`,
        baseNoApi.replace(/:\d+/, ":8001") + "/api/auth/refresh",
        baseNoApi.replace(/:\d+/, ":8000") + "/api/auth/refresh",
      ];
      for (const refreshUrl of [...new Set(urlsToTry)]) {
        try {
          logInfo("Attempting token refresh", { url: refreshUrl });
          const res = await fetch(refreshUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${oldToken}` },
          });
          if (res.ok) {
            const json = await res.json();
            const newToken = json.access_token || json.accessToken;
            if (newToken) {
              await chrome.storage.local.set({ accessToken: newToken });
              try {
                await chrome.runtime.sendMessage({ type: "SYNC_TOKEN_TO_HIREMATE_TAB", token: newToken });
              } catch (_) { }
              if (LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o)) {
                try {
                  localStorage.setItem("token", newToken);
                  localStorage.setItem("access_token", newToken);
                } catch (_) { }
              }
              logInfo("Token refreshed via API and synced to chrome.storage + localStorage");
              return newToken;
            }
            logWarn("Refresh returned 200 but no access_token in response", { keys: Object.keys(json || {}) });
          } else {
            const errBody = await res.text().catch(() => "");
            logWarn("Refresh failed", { url: refreshUrl, status: res.status, body: errBody?.slice(0, 200) });
          }
        } catch (err) {
          logWarn("Refresh request error", { url: refreshUrl, error: String(err) });
          continue;
        }
      }
      logWarn("All refresh attempts failed");
      return null;
    } finally {
      _refreshInFlight = null;
    }
  })();
  return _refreshInFlight;
}

/** Get auth headers. Sync token from open HireMate tab only. Refresh happens only on 401 (in fetchWithAuthRetry). */
async function getAuthHeaders() {
  try {
    const syncRes = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
    if (syncRes?.ok && syncRes?.token) {
      await chrome.storage.local.set({ accessToken: syncRes.token });
    }
  } catch (_) { }
  let token = null;
  if (window.__SECURITY_MANAGER__?.getToken) {
    try { token = await window.__SECURITY_MANAGER__.getToken(); } catch (_) { }
  }
  if (!token) {
    const data = await chrome.storage.local.get(["accessToken"]);
    token = data.accessToken || null;
  }
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

/** Normalize headers to plain object (handles Headers instance). */
function toPlainHeaders(headers) {
  if (!headers) return {};
  if (headers instanceof Headers) return Object.fromEntries(headers.entries());
  return typeof headers === "object" ? { ...headers } : {};
}

/** Fetch interceptor: on 401 → refresh token, persist to chrome.storage + HireMate localStorage, retry once with new token. */
async function fetchWithAuthRetry(url, options = {}) {
  const t0 = Date.now();
  let res = await fetch(url, options);
  logInfo("fetchWithAuthRetry: first attempt", { path: url?.split("/").slice(-2).join("/"), status: res.status, ms: Date.now() - t0 });
  if (res.status === 401) {
    logInfo("401 received, attempting token refresh", { url: url?.slice(-50) });
    let newToken = null;
    newToken = await refreshTokenViaApi();
    if (!newToken) {
      try {
        const syncRes = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
        if (syncRes?.ok && syncRes?.token) {
          newToken = syncRes.token;
          await chrome.storage.local.set({ accessToken: newToken });
        }
      } catch (_) { }
    }
    if (!newToken) {
      await chrome.storage.local.remove([AUTOFILL_CTX_KEY]);
    }
    if (newToken) {
      const base = toPlainHeaders(options.headers);
      const retryOptions = { ...options, headers: { ...base, Authorization: `Bearer ${newToken}` } };
      res = await fetch(url, retryOptions);
      logInfo("fetchWithAuthRetry: retry result", { status: res.status, ms: Date.now() - t0 });
      if (res.status === 401) {
        logWarn("Retry still returned 401 after refresh");
      }
    }
  }
  return res;
}

function makeCopyable(el, text) {
  if (!el || !text) return;
  el.classList.add("ja-copyable");
  el.addEventListener("click", () => {
    navigator.clipboard.writeText(text).catch(() => { });
  });
}


async function fetchProfileResumeBlob(ctx) {
  const resumeUrl = ctx?.resumeUrl || ctx?.resume_url;
  const resumeFilename = resumeUrl ? (resumeUrl.split("/").pop() || "").split("?")[0] : null;
  if (!resumeFilename) return null;
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const res = await fetchWithAuthRetry(
    `${apiBase}/chrome-extension/autofill/resume/${encodeURIComponent(resumeFilename)}`,
    { headers }
  );
  if (!res.ok) return null;
  return { blob: await res.blob(), filename: resumeFilename };
}

async function loadProfileIntoPanel(root) {
  const nameEl = root?.querySelector("#ja-profile-name");
  const contactEl = root?.querySelector("#ja-profile-contact");
  const educationEl = root?.querySelector("#ja-profile-education");
  const experienceEl = root?.querySelector("#ja-profile-experience");
  const uploadsEl = root?.querySelector("#ja-profile-uploads");
  const certificationsEl = root?.querySelector("#ja-profile-certifications");
  const techSkillsEl = root?.querySelector("#ja-profile-tech-skills");
  const softSkillsEl = root?.querySelector("#ja-profile-soft-skills");
  const languagesEl = root?.querySelector("#ja-profile-languages");
  const avatarEl = root?.querySelector("#ja-profile-avatar");
  const titleEl = root?.querySelector("#ja-profile-title");
  const statApps = root?.querySelector("#ja-profile-stat-apps");
  const statInt = root?.querySelector("#ja-profile-stat-interviews");
  const statFill = root?.querySelector("#ja-profile-stat-fill");
  const techCountEl = root?.querySelector("#ja-profile-tech-count");

  const setHtml = (el, html) => {
    if (el) el.innerHTML = html || "—";
  };
  const setText = (el, text) => {
    if (el) el.textContent = text || "—";
  };

  const clearStats = () => {
    if (statApps) statApps.textContent = "—";
    if (statInt) statInt.textContent = "—";
    if (statFill) statFill.textContent = "—";
  };

  try {
    const ctx = await getAutofillContextFromApi();
    root._profileCtx = ctx;
    const flat = ctx.profile || {};
    const detail = ctx.profileDetail;

    try {
      const st = await chrome.storage.local.get(["hm_stat_applications", "hm_stat_interviews", "hm_stat_fill_rate"]);
      if (statApps) statApps.textContent = st.hm_stat_applications != null ? String(st.hm_stat_applications) : "—";
      if (statInt) statInt.textContent = st.hm_stat_interviews != null ? String(st.hm_stat_interviews) : "—";
      if (statFill) statFill.textContent = st.hm_stat_fill_rate != null ? String(st.hm_stat_fill_rate) : "—";
    } catch (_) {
      clearStats();
    }

    const fullName = [flat.firstName, flat.lastName].filter(Boolean).join(" ") || flat.name || "—";
    setText(nameEl, fullName);
    setText(titleEl, flat.title || flat.professionalHeadline || "");
    try {
      if (avatarEl) {
        const initials = (fullName || "")
          .split(" ")
          .filter(Boolean)
          .slice(0, 2)
          .map((s) => s[0]?.toUpperCase() || "")
          .join("");
        avatarEl.textContent = initials || (flat.name || flat.firstName || "—").charAt(0).toUpperCase();
      }
    } catch (_) { }

    const location = [flat.city, flat.country].filter(Boolean).join(", ") || "—";
    const contactRows = [
      { icon: PROFILE_TAB_ICONS.mapPin, key: "Location", copy: location === "—" ? "" : location, display: location },
      { icon: PROFILE_TAB_ICONS.mail, key: "Email", copy: flat.email || "", display: flat.email || "—" },
      { icon: PROFILE_TAB_ICONS.phone, key: "Phone", copy: flat.phone || "", display: flat.phone || "—" },
      { icon: PROFILE_TAB_ICONS.linkedin, key: "LinkedIn", copy: flat.linkedin || "", display: flat.linkedin || "—" },
      { icon: PROFILE_TAB_ICONS.github, key: "GitHub", copy: flat.github || "", display: flat.github || "—" },
      { icon: PROFILE_TAB_ICONS.globe, key: "Portfolio", copy: flat.portfolio || "", display: flat.portfolio || "—" },
    ];
    setHtml(
      contactEl,
      `<div class="ja-prof-contact-grid">${contactRows
        .map(
          (r) => `
      <div class="ja-prof-contact-row">
        <span class="ja-prof-contact-ico">${r.icon}</span>
        <span class="ja-prof-contact-val" title="${escapeHtml(r.display)}">${escapeHtml(r.display)}</span>
        <button type="button" class="ja-prof-copy" data-copy="${escapeHtml(r.copy)}" aria-label="Copy ${escapeHtml(r.key)}">${PROFILE_TAB_ICONS.copy}</button>
      </div>`
        )
        .join("")}</div>`
    );

    const educations = detail?.educations ?? flat.educations ?? [];
    if (educations.length) {
      const eduHtml = educations
        .map((e) => {
          const dates = [e.startYear, e.endYear].filter(Boolean).join(" — ");
          const degreeLine = [e.degree, e.fieldOfStudy].filter(Boolean).join(" · ");
          const gpa = e.grade ? `<span class="ja-prof-badge ja-prof-badge-muted">GPA: ${escapeHtml(e.grade)}</span>` : "";
          return `
        <div class="ja-prof-edu-card">
          <p class="ja-prof-edu-school">${escapeHtml(e.institution || "—")}</p>
          <p class="ja-prof-edu-degree">${escapeHtml(degreeLine || "—")}</p>
          <div class="ja-prof-edu-meta">
            <span class="ja-prof-edu-dates">${escapeHtml(dates || "—")}</span>
            ${gpa}
          </div>
        </div>`;
        })
        .join("");
      setHtml(educationEl, eduHtml);
    } else {
      setHtml(educationEl, `<p class="ja-prof-empty">${escapeHtml(flat.education || "—")}</p>`);
    }

    const experiences = detail?.experiences ?? flat.experiences ?? [];
    if (experiences.length) {
      const expHtml = experiences
        .map((e) => {
          const locDate = [e.location, [e.startDate, e.endDate].filter(Boolean).join(" — ")].filter(Boolean).join(" · ");
          const bullets = (e.description || "")
            .split(/\n|•/)
            .map((s) => s.trim())
            .filter(Boolean)
            .map((b) => `<li class="ja-prof-exp-li"><span class="ja-prof-exp-dot"></span><span>${escapeHtml(b)}</span></li>`)
            .join("");
          const typeBadge = escapeHtml(e.employmentType || "Full-time");
          return `
          <div class="ja-prof-exp-card">
            <div class="ja-prof-exp-top">
              <p class="ja-prof-exp-title">${escapeHtml(e.jobTitle || "—")}</p>
              <span class="ja-prof-badge ja-prof-badge-muted">${typeBadge}</span>
            </div>
            <p class="ja-prof-exp-company">${escapeHtml(e.companyName || "")}</p>
            <p class="ja-prof-exp-meta">${escapeHtml(locDate || "—")}</p>
            ${bullets ? `<ul class="ja-prof-exp-bullets">${bullets}</ul>` : ""}
          </div>`;
        })
        .join("");
      setHtml(experienceEl, expHtml);
    } else {
      setHtml(experienceEl, `<p class="ja-prof-empty">${escapeHtml((flat.experience || flat.professionalSummary || "—").slice(0, 800))}</p>`);
    }

    const certs = flat.certifications || flat.certifications_list || [];
    const certList = Array.isArray(certs) ? certs.map((c) => (typeof c === "string" ? c : c.name || c.title || "")).filter(Boolean) : [];
    const certBlock = root?.querySelector("#ja-profile-cert-block");
    if (certList.length && certificationsEl) {
      if (certBlock) certBlock.style.display = "";
      setHtml(
        certificationsEl,
        `<div class="ja-prof-cert-wrap">${certList.map((c) => `<span class="ja-prof-cert-pill">${PROFILE_TAB_ICONS.awardSm}<span>${escapeHtml(c)}</span></span>`).join("")}</div>`
      );
    } else {
      if (certBlock) certBlock.style.display = "none";
      if (certificationsEl) setHtml(certificationsEl, "");
    }

    const resumeName = ctx.resumeName || ctx.resumeFileName || (ctx.resumeUrl || "").split("/").pop() || "Resume";
    const resumeDate = detail?.resumeLastUpdated ? new Date(detail.resumeLastUpdated).toLocaleString() : "";
    const hasResume = !!(ctx.resumeUrl || ctx.resumeFileName);
    const uploadsHtml = hasResume
      ? `
      <div class="ja-prof-upload-card">
        <div class="ja-prof-upload-left">
          <div class="ja-prof-upload-icon">${PROFILE_TAB_ICONS.fileText}</div>
          <div>
            <p class="ja-prof-upload-name">${escapeHtml(resumeName)}</p>
            <p class="ja-prof-upload-meta">${resumeDate ? `${escapeHtml(resumeDate)}` : "Resume on file"}</p>
          </div>
        </div>
        <div class="ja-prof-upload-actions">
          <button type="button" class="ja-prof-file-btn" id="ja-profile-upload-preview" title="Preview">${PROFILE_TAB_ICONS.eyeFile}</button>
          <button type="button" class="ja-prof-file-btn" id="ja-profile-upload-download" title="Download">${PROFILE_TAB_ICONS.downloadFile}</button>
        </div>
      </div>`
      : `<p class="ja-prof-empty">No uploads</p>`;
    setHtml(uploadsEl, uploadsHtml);
    if (hasResume) {
      const runResume = async (mode) => {
        try {
          const got = await fetchProfileResumeBlob(ctx);
          if (!got) return;
          const url = URL.createObjectURL(got.blob);
          if (mode === "open") window.open(url, "_blank");
          else {
            const a = document.createElement("a");
            a.href = url;
            a.download = got.filename || "resume.pdf";
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 2000);
          }
        } catch (_) { }
      };
      const pPrev = uploadsEl.querySelector("#ja-profile-upload-preview");
      const pDown = uploadsEl.querySelector("#ja-profile-upload-download");
      if (pPrev) pPrev.onclick = () => runResume("open");
      if (pDown) pDown.onclick = () => runResume("download");
    }

    let techSkills = Array.isArray(flat.tech_skills_list) ? [...flat.tech_skills_list] : [];
    let softSkills = Array.isArray(flat.soft_skills_list) ? [...flat.soft_skills_list] : [];
    if (!techSkills.length && !softSkills.length && Array.isArray(flat.skills_list) && flat.skills_list.length) {
      techSkills = [...flat.skills_list];
    } else if (!techSkills.length && !softSkills.length && flat.skills) {
      techSkills = String(flat.skills).split(",").map((s) => s.trim()).filter(Boolean);
    }

    if (techSkills.length) {
      setHtml(
        techSkillsEl,
        `<div class="ja-prof-skill-wrap">${techSkills.map((s) => `<button type="button" class="ja-prof-chip ja-prof-chip-tech ja-prof-skill-copy" data-copy="${escapeHtml(s)}">${escapeHtml(s)}</button>`).join("")}</div>`
      );
      techSkillsEl?.querySelectorAll(".ja-prof-skill-copy").forEach((node) => {
        node.addEventListener("click", () => navigator.clipboard.writeText(node.getAttribute("data-copy") || node.textContent || "").catch(() => { }));
      });
    } else {
      setHtml(techSkillsEl, `<p class="ja-prof-empty">—</p>`);
    }
    if (techCountEl) techCountEl.textContent = `${techSkills.length} skills`;

    if (softSkills.length) {
      setHtml(
        softSkillsEl,
        `<div class="ja-prof-skill-wrap">${softSkills.map((s) => `<span class="ja-prof-chip ja-prof-chip-soft">${escapeHtml(s)}</span>`).join("")}</div>`
      );
    } else {
      setHtml(softSkillsEl, `<p class="ja-prof-empty">—</p>`);
    }

    const langs = Array.isArray(flat.languages_list) ? flat.languages_list : detail?.willingToWorkIn || [];
    if (langs.length) {
      setHtml(
        languagesEl,
        `<div class="ja-prof-skill-wrap">${langs.map((l) => `<span class="ja-prof-chip ja-prof-chip-lang">${escapeHtml(l)}</span>`).join("")}</div>`
      );
    } else {
      setHtml(languagesEl, `<p class="ja-prof-empty">—</p>`);
    }
  } catch (_) {
    clearStats();
    setText(nameEl, "Sign in to load profile");
    setHtml(contactEl, "");
    setHtml(educationEl, "—");
    setHtml(experienceEl, "—");
    setHtml(uploadsEl, "—");
    setHtml(root?.querySelector("#ja-profile-certifications"), "");
    setHtml(techSkillsEl, "—");
    setHtml(softSkillsEl, "—");
    setHtml(languagesEl, "—");
  }
}

function extractCompanyAndPosition() {
  const title = document.title || "";
  const url = window.location.href || "";
  let company = "";
  let position = "";
  let location = "";

  // 1. Extract company from URL (Greenhouse, Lever, Workday, etc.)
  try {
    const u = new URL(url);
    const path = (u.pathname || "").replace(/^\/+|\/+$/g, "");
    const segments = path.split("/").filter(Boolean);
    if (u.hostname.includes("greenhouse.io") && segments.length >= 1) {
      company = segments[0];
    } else if (u.hostname.includes("lever.co") && segments.length >= 1) {
      company = segments[0];
    } else if (u.hostname.includes("jobs.workday.com") && segments.length >= 2) {
      company = segments[0];
    } else if (u.hostname.includes("ashbyhq.com") && segments.length >= 1) {
      company = segments[0];
    } else if (u.hostname.includes("bamboohr.com") && segments.length >= 1) {
      company = segments[0];
    }
    if (company) {
      company = company.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    }
  } catch (_) { }

  // 2. Try JSON-LD JobPosting on page
  if (!company || !position) {
    document.querySelectorAll('script[type="application/ld+json"]').forEach((script) => {
      try {
        const data = JSON.parse(script.textContent || "{}");
        const item = Array.isArray(data) ? data.find((i) => i["@type"] === "JobPosting") : data["@type"] === "JobPosting" ? data : null;
        if (item) {
          if (!company && item.hiringOrganization?.name) company = item.hiringOrganization.name;
          if (!position && item.title) position = item.title;
          if (!location && item.jobLocation) {
            const loc = item.jobLocation;
            location = typeof loc === "string" ? loc : loc.address?.addressLocality && loc.address?.addressCountry
              ? `${loc.address.addressLocality}, ${loc.address.addressCountry}`
              : loc.name || "";
          }
        }
      } catch (_) { }
    });
  }

  // 3. og:title — "Job Title | Company" or "Tagline | Company" (job titles usually 2+ words)
  const ogTitle = document.querySelector('meta[property="og:title"]')?.content;
  const isTagline = (t) => !t || /^(best|payment|gateway|online|financial|leading|top|number one)/i.test(t) || t.length > 55;
  const looksLikeJobTitle = (t) => t && t.length >= 5 && t.length < 80 && !isTagline(t) && t.split(/\s+/).length >= 2;
  if (ogTitle) {
    const parts = ogTitle.split(/[|\-–—]/).map((p) => p.trim()).filter(Boolean);
    if (parts.length >= 2) {
      const a = parts[0], b = parts[1];
      if (!company) company = (b.length <= 30 && b.split(/\s+/).length <= 3) ? b : (a.length <= 30 ? a : "");
      if (!position && looksLikeJobTitle(a)) position = a;
      else if (!position && looksLikeJobTitle(b)) position = b;
    } else if (!position && looksLikeJobTitle(ogTitle.trim())) {
      position = ogTitle.trim();
    }
  }

  // 4. Page content: h1 first (most reliable on job detail pages)
  const h1 = document.querySelector("h1");
  if (!position && h1) position = getText(h1);

  // 5. "Back to jobs JOB_TITLE Location Apply" pattern (Greenhouse / common ATS)
  const bodyText = document.body?.innerText?.slice(0, 1500) || "";
  if (!position && /Back to jobs\s+(.+?)\s+(?:Apply|Remote|Hybrid|Malaysia|India|Singapore|Bangalore|Kuala Lumpur)/i.test(bodyText)) {
    const m = bodyText.match(/Back to jobs\s+(.+?)\s+(?:Apply|Remote|Hybrid|Malaysia|India|Singapore|Bangalore|Kuala Lumpur|,\s*[A-Za-z]+)/i);
    if (m) {
      const candidate = m[1].trim();
      if (candidate.length >= 5 && candidate.length < 80 && !/^(payment|best|gateway|online|financial|leading|india)/i.test(candidate)) {
        position = candidate;
      }
    }
  }
  if (!position && /Back to jobs\s+(.+?)\s+Apply/i.test(bodyText)) {
    const m = bodyText.match(/Back to jobs\s+(.+?)\s+Apply/i);
    if (m && !position) {
      const candidate = m[1].trim();
      if (candidate.length >= 5 && candidate.length < 80) position = candidate;
    }
  }

  if (!company || !location) {
    if (!company && /About\s+([A-Za-z0-9&\s]+):/i.test(bodyText)) {
      const m = bodyText.match(/About\s+([A-Za-z0-9&\s]+):/i);
      if (m) company = m[1].trim();
    }
    if (!location && /([A-Za-z\s]+,\s*[A-Za-z\s]+)\s*(?:Apply|Remote|Hybrid)/i.test(bodyText)) {
      const m = bodyText.match(/([A-Za-z\s]+,\s*[A-Za-z\s]+)\s*(?:Apply|Remote|Hybrid)/i);
      if (m) location = m[1].trim();
    }
    if (!location && /([A-Za-z\s]+,\s+[A-Za-z]{2,})\s*$/.test(bodyText.slice(0, 800))) {
      const m = bodyText.slice(0, 800).match(/([A-Za-z][A-Za-z\s]+,\s*[A-Za-z]{2,})/);
      if (m && m[1].length < 50) location = m[1].trim();
    }
  }

  if (!position && ogTitle) {
    const parts = ogTitle.split(/[|\-–—]/).map((p) => p.trim()).filter(Boolean);
    for (const p of parts) {
      if (p.length >= 5 && p.length < 80 && !/^(payment|best|gateway|online|financial|leading|india|razorpay)/i.test(p)) {
        position = p;
        break;
      }
    }
  }
  if (!position && title) {
    const t = title.trim();
    if (t.length >= 5 && t.length < 80 && !/^(payment|best|gateway|online|financial)/i.test(t)) position = t;
  }
  return { company: company || "", position: position || "", location: location || "" };
}

async function prefillJobForm(root) {
  const { company, position, location } = extractCompanyAndPosition();
  const urlInput = root?.querySelector("#ja-job-url");
  const descInput = root?.querySelector("#ja-job-description");
  const companyInput = root?.querySelector("#ja-job-company");
  const positionInput = root?.querySelector("#ja-job-position");
  const locationInput = root?.querySelector("#ja-job-location");
  if (urlInput) urlInput.value = window.location.href || "";
  if (companyInput) companyInput.value = company || "";
  if (positionInput) positionInput.value = position || "";
  if (locationInput) locationInput.value = location || "";

  if (descInput) {
    descInput.placeholder = "Scraping job description...";
    descInput.value = "";
    const jobDesc = await fetchJobDescriptionFromKeywordsApi(window.location.href);
    descInput.value = jobDesc || "";
    descInput.placeholder = "Auto-detected description available.";
  }
}

async function saveJobFromForm(root) {
  const btn = root?.querySelector("#ja-job-save");
  const origText = btn?.textContent || "Save Job";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Saving...";
  }
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const payload = {
      company: root.querySelector("#ja-job-company")?.value || "",
      position_title: root.querySelector("#ja-job-position")?.value || "",
      location: root.querySelector("#ja-job-location")?.value || "",
      min_salary: root.querySelector("#ja-job-min-salary")?.value || null,
      max_salary: root.querySelector("#ja-job-max-salary")?.value || null,
      currency: root.querySelector("#ja-job-currency")?.value || "USD",
      period: root.querySelector("#ja-job-period")?.value || "Yearly",
      job_type: root.querySelector("#ja-job-type")?.value || "Full-Time",
      job_description: root.querySelector("#ja-job-description")?.value || null,
      notes: root.querySelector("#ja-job-notes")?.value || null,
      application_status: root.querySelector("#ja-job-status")?.value || "I have not yet applied",
      job_posting_url: root.querySelector("#ja-job-url")?.value || null,
    };
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const view = root.querySelector("#ja-keywords-view");
      const formPanel = root.querySelector("#ja-job-form-panel");
      if (view && formPanel) {
        formPanel.style.display = "none";
        view.style.display = "block";
      }
    }
  } catch (err) {
    logWarn("Save job failed", { error: String(err) });
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origText;
    }
  }
}

async function fetchResumesFromApi() {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const res = await fetchWithAuthRetry(`${apiBase}/resume/workspace`, { headers });
  if (!res.ok) return [];
  const data = await res.json();
  console.log(data);
  return data.resumes || [];
}

async function loadKeywordsIntoPanel(root) {
  const container = root?.querySelector("#ja-keyword-analysis");
  const card = root?.querySelector("#ja-keyword-card");
  const selectEl = root?.querySelector("#ja-resume-select");
  if (!container) return;

  container.innerHTML = "<p class=\"ja-score-text\">Loading profile...</p>";
  if (card) card.classList.add("ja-loading");
  const keywordsListEl = root?.querySelector("#ja-keyword-keywords-list");
  if (keywordsListEl) keywordsListEl.innerHTML = "";

  try {
    const resumes = await fetchResumesFromApi();
    if (resumes.length === 0) {
      container.innerHTML = `
        <p class="ja-score-text">Please upload resume in profile to analyze keywords.</p>
        <button type="button" class="ja-action ja-upload-resume-btn" style="margin-top:8px;">Upload Resume</button>
      `;
      container.querySelector(".ja-upload-resume-btn")?.addEventListener("click", () => openResumeGeneratorUrl());
      if (card) card.classList.remove("ja-loading");
      return;
    }

    if (selectEl) {
      const prevSelection = selectEl.value ? parseInt(selectEl.value, 10) : null;
      const validIds = new Set(resumes.map((r) => r.id));
      selectEl.innerHTML = "";
      let defaultId = null;
      resumes.forEach((r, idx) => {
        const opt = document.createElement("option");
        opt.value = r.id;
        opt.textContent = r.resume_name || `Resume ${idx + 1}`;
        if (r.is_default) {
          opt.textContent += " (default)";
          defaultId = r.id;
        }
        selectEl.appendChild(opt);
      });
      const { hm_selected_resume_id } = await chrome.storage.local.get(["hm_selected_resume_id"]);
      const storedId = hm_selected_resume_id != null ? parseInt(hm_selected_resume_id, 10) : null;
      if (storedId && validIds.has(storedId)) {
        selectEl.value = String(storedId);
      } else if (prevSelection && validIds.has(prevSelection)) {
        selectEl.value = String(prevSelection);
      } else if (defaultId !== null) {
        selectEl.value = String(defaultId);
      } else if (resumes.length) {
        selectEl.value = String(resumes[0].id);
      }
    }

    const selectedId = selectEl?.value ? parseInt(selectEl.value, 10) : null;
    const resumeId = selectedId && selectedId > 0 ? selectedId : null;

    container.innerHTML = "<p class=\"ja-score-text\">Analyzing keywords...</p>";
    if (keywordsListEl) keywordsListEl.innerHTML = "";
    const pageHtml = await getPageHtmlForKeywordsApi();
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const body = { url: window.location.href, page_html: pageHtml || undefined };
    if (resumeId) body.resume_id = resumeId;

    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/keywords/analyze`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let errMsg = "Unable to analyze keywords.";
      try {
        const errData = await res.json();
        errMsg = errData.detail || errMsg;
        if (typeof errMsg === "object" && errMsg.msg) errMsg = errMsg.msg;
      } catch (_) { }
      container.innerHTML = `<p class="ja-score-text">${escapeHtml(String(errMsg))}</p>`;
      if (keywordsListEl) keywordsListEl.innerHTML = "";
      if (card) card.classList.remove("ja-loading");
      return;
    }
    const data = await res.json();
    const high = data.high_priority || [];
    const low = data.low_priority || [];
    const total = data.total_keywords || 0;
    const matched = data.matched_count || 0;
    const percent = data.percent || 0;
    const highMatched = high.filter((i) => i.matched).length;
    const lowMatched = low.filter((i) => i.matched).length;
    const apiMessage = data.message || "";
    const theme = keywordMatchTheme(percent, total);
    const dashArr = keywordGaugeDashArray(percent);
    const pctRounded = Math.round(percent);
    const highHtml = high.map(renderKeywordMatchChip).join("");
    const lowHtml = low.map(renderKeywordMatchChip).join("");
    const quickFromApi = Array.isArray(data.quick_suggestions) ? data.quick_suggestions.filter(Boolean) : [];
    const quickPills =
      quickFromApi.length > 0
        ? quickFromApi.slice(0, 8)
        : high.filter((k) => !k.matched).slice(0, 4).map((k) => k.keyword);
    const suggestionsHtml = quickPills
      .map((kw) => `<button type="button" class="ja-kw-suggest-pill">+ ${escapeHtml(typeof kw === "string" ? kw : kw.keyword || String(kw))}</button>`)
      .join("");

    container.innerHTML =
      total === 0
        ? `<div class="ja-kw-score-card-inner ja-kw-score-empty">
            <p class="ja-score-text">${escapeHtml(apiMessage || "No technical skills found in the job description. Scroll down for the full requirements section.")}</p>
          </div>`
        : `<div class="ja-kw-score-card-inner">
            <div class="ja-kw-score-main">
              <div class="ja-kw-gauge-circle-wrap" aria-hidden="true">
                <svg class="ja-kw-gauge-circle" viewBox="0 0 80 80">
                  <circle cx="40" cy="40" r="34" fill="none" stroke="#e5e7eb" stroke-width="6" />
                  <circle
                    cx="40" cy="40" r="34" fill="none"
                    stroke="${theme.stroke}" stroke-width="6" stroke-linecap="round"
                    stroke-dasharray="${dashArr}"
                    transform="rotate(-90 40 40)"
                  />
                </svg>
                <div class="ja-kw-gauge-circle-label">
                  <span class="ja-kw-pct-num" style="color:${theme.color}">${pctRounded}%</span>
                  <span class="ja-kw-pct-sub">MATCH</span>
                </div>
              </div>
              <div class="ja-kw-score-copy">
                <div class="ja-kw-badge-row">
                  <span class="ja-kw-status-badge" style="color:${theme.color};background:${theme.badgeBg}">${theme.label}</span>
                </div>
                <p class="ja-kw-line ja-kw-line-muted">
                  <strong class="ja-kw-strong">${matched}</strong> of <strong class="ja-kw-strong">${total}</strong> keywords matched from the job description.
                </p>
                <div class="ja-kw-hilo">
                  <span class="ja-kw-hilo-item">High: <strong class="ja-kw-strong">${highMatched}/${high.length}</strong></span>
                  <span class="ja-kw-hilo-item">Low: <strong class="ja-kw-strong">${lowMatched}/${low.length}</strong></span>
                </div>
              </div>
            </div>
            <div class="ja-kw-tip-bar">
              ${KEYWORD_TAB_ICONS.lightbulb}
              <p class="ja-kw-tip-text">Aim for <strong>70%+</strong> match rate. Click &quot;Tailor&quot; to auto-optimize your resume for this role.</p>
            </div>
          </div>`;

    if (keywordsListEl) {
      if (!high.length && !low.length) {
        keywordsListEl.innerHTML = "";
      } else {
        keywordsListEl.innerHTML = `
      ${high.length ? `<div class="ja-kw-priority-block">
        <div class="ja-kw-priority-head">
          <span class="ja-kw-priority-head-left"><span class="ja-kw-dot ja-kw-dot-high"></span><span class="ja-kw-priority-name">High Priority</span></span>
          <span class="ja-kw-priority-meta">${highMatched}/${high.length} matched</span>
        </div>
        <div class="ja-kw-chip-grid">${highHtml}</div>
      </div>` : ""}
      ${low.length ? `<div class="ja-kw-priority-block">
        <div class="ja-kw-priority-head">
          <span class="ja-kw-priority-head-left"><span class="ja-kw-dot ja-kw-dot-low"></span><span class="ja-kw-priority-name">Low Priority</span></span>
          <span class="ja-kw-priority-meta">${lowMatched}/${low.length} matched</span>
        </div>
        <div class="ja-kw-chip-grid">${lowHtml}</div>
      </div>` : ""}
      ${
        suggestionsHtml
          ? `<div class="ja-kw-suggest-card">
        <div class="ja-kw-suggest-head">
          ${KEYWORD_TAB_ICONS.trendingUp}
          <span class="ja-kw-suggest-title">Quick Suggestions</span>
        </div>
        <p class="ja-kw-suggest-sub">Add these missing keywords to boost your score:</p>
        <div class="ja-kw-suggest-pills">${suggestionsHtml}</div>
      </div>`
          : ""
      }
      `;
      }
    }
    if (root && data.job_id != null) {
      root.dataset.lastJobId = String(data.job_id);
      root.dataset.lastJobUrl = window.location.href;
    }
  } catch (err) {
    logWarn("Keyword analysis failed", { error: String(err) });
    container.innerHTML = "<p class=\"ja-score-text\">Unable to analyze. Please try again.</p>";
    if (root) {
      const kwList = root.querySelector("#ja-keyword-keywords-list");
      if (kwList) kwList.innerHTML = "";
    }
  } finally {
    if (card) card.classList.remove("ja-loading");
  }
}

const AUTOFILL_CTX_KEY = "hm_autofill_ctx";
const AUTOFILL_CTX_TTL = 10 * 60 * 1000;

async function getAutofillContextFromApi() {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const _stored = await chrome.storage.local.get(AUTOFILL_CTX_KEY);
  const _cached = _stored[AUTOFILL_CTX_KEY];
  let autofillCtx;
  if (_cached && (Date.now() - _cached.ts) < AUTOFILL_CTX_TTL) {
    autofillCtx = _cached.data;
  } else {
    const _res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/autofill/context?nocache=1`, { headers });
    if (!_res.ok) throw new Error(`Profile load failed (${_res.status})`);
    autofillCtx = await _res.json();
    await chrome.storage.local.set({ [AUTOFILL_CTX_KEY]: { data: autofillCtx, ts: Date.now() } });
  }
  return {
    profile: autofillCtx.profile || {},
    profileDetail: null,
    customAnswers: autofillCtx.custom_answers || {},
    resumeText: autofillCtx.resume_text || "",
    resumeName: autofillCtx.resume_name || null,
    resumeFileName: autofillCtx.resume_url ? (autofillCtx.resume_url.split("/").pop() || "").split("?")[0] : null,
    resumeUrl: autofillCtx.resume_url || null,
  };
}

/** Sanitize resume display name to valid filename (e.g. "Sainath Reddy (default)" → "Sainath_Reddy_Resume.pdf"). */
function sanitizeResumeFilename(displayName) {
  if (!displayName || typeof displayName !== "string") return null;
  const s = displayName.replace(/\s*\(default\)\s*/gi, "").replace(/\s+/g, "_").replace(/[^\w\-_.]/g, "");
  if (!s) return null;
  return s.endsWith(".pdf") ? s : s + ".pdf";
}

/** Fetch resume from API (backend proxies S3/local file). Uses resume_url from context. */
async function fetchResumeFromContext(context) {
  const resumeUrl = context?.resumeUrl || context?.resume_url;
  const resumeFilename = resumeUrl ? (resumeUrl.split("/").pop() || "").split("?")[0] : null;
  if (!resumeFilename) return null;
  try {
    const existing = await chrome.runtime.sendMessage({ type: "GET_RESUME" }).then((r) => (r?.ok ? r.data : null)).catch(() => null);
    const existingHash = existing?.hash;

    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const resumeRes = await fetchWithAuthRetry(
      `${apiBase}/chrome-extension/autofill/resume/${encodeURIComponent(resumeFilename)}`,
      { headers }
    );
    if (!resumeRes.ok) return null;
    const resumeBuffer = await resumeRes.arrayBuffer();
    const buffer = Array.from(new Uint8Array(resumeBuffer));

    const hashInput = buffer.slice(0, 512).join(",");
    const hash = btoa(hashInput).slice(0, 32);

    if (existingHash && existingHash === hash && existing?.buffer?.length === buffer.length) {
      logInfo("Resume unchanged, using cached version", { fileName: resumeFilename });
      const displayName = context?.resumeName ? sanitizeResumeFilename(context.resumeName) : null;
      return { buffer: existing.buffer, name: displayName || resumeFilename, hash };
    }

    await chrome.runtime.sendMessage({
      type: "SAVE_RESUME",
      payload: { buffer, name: resumeFilename, hash },
    });
    const displayName = context?.resumeName ? sanitizeResumeFilename(context.resumeName) : null;
    const fillName = displayName || resumeFilename;
    logInfo("Resume fetched and saved from context", { fileName: fillName, bytes: buffer.length });
    return { buffer, name: fillName, hash };
  } catch (e) {
    logWarn("Failed to fetch resume from context", e);
    return null;
  }
}

async function getStaticResume() {
  return null;
}

function trackCareerPageView() {
  if (!_visitedUrls.has(location.href)) {
    _visitedUrls.add(location.href);
    getApiBase().then((apiBase) =>
      getAuthHeaders().then((headers) => {
        if (!headers?.Authorization) return;
        const { company } = extractCompanyAndPosition();
        fetch(`${apiBase}/activity/track`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...headers },
          body: JSON.stringify({
            event_type: "career_page_view",
            page_url: location.href,
            metadata: { company_name: company || null, job_url: location.href || null, job_title: null },
          }),
        }).catch((e) => logWarn("Failed to track career page view", { error: String(e) }));
      })
    );
  }
}

function trackAutofillUsed() {
  const currentUrl = window.location.href || "";
  getApiBase().then((apiBase) =>
    getAuthHeaders().then((headers) => {
      if (!headers?.Authorization) return;
      const { company, position } = extractCompanyAndPosition();
      fetch(`${apiBase}/activity/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({
          event_type: "autofill_used",
          page_url: currentUrl,
          metadata: { company_name: company || null, job_url: currentUrl || null, job_title: position || null },
        }),
      }).catch((e) => logWarn("Failed to track autofill", { error: String(e) }));
    })
  );
}

const EDUCATION_ATS = new Set(["school", "degree", "major", "graduation_year"]);
const EMPLOYMENT_ATS = new Set(["company", "job_title", "start_date", "end_date"]);

/** Build flat profileValues for Workday step manager from context. Keys match atsFieldType (first_name, email, etc.). */
function buildProfileValuesForWorkday(context) {
  const p = context?.profile || {};
  const custom = context?.customAnswers || {};
  const exp0 = p.experiences?.[0] || {};
  const edu0 = p.educations?.[0] || {};
  const values = {
    first_name: p.firstName || "",
    last_name: p.lastName || "",
    full_name: (p.firstName && p.lastName ? `${p.firstName} ${p.lastName}` : p.name || "").trim(),
    email: p.email || "",
    phone: p.phone || "",
    linkedin: p.linkedin || "",
    portfolio: p.portfolio || "",
    github: p.github || "",
    address: p.location || p.address || "",
    city: p.city || "",
    state: p.state || "",
    country: p.country || "",
    postal_code: p.postalCode || p.zip || "",
    work_authorization: p.workAuthorization || p.work_authorization || "Yes",
    sponsorship: p.sponsorship || "No",
    school: edu0.institution || p.school || "",
    degree: edu0.degree || p.degree || "",
    major: edu0.fieldOfStudy || p.major || p.fieldOfStudy || "",
    graduation_year: String(edu0.endYear || edu0.graduationYear || p.graduationYear || ""),
    company: exp0.companyName || p.company || "",
    job_title: exp0.jobTitle || p.title || p.jobTitle || "",
    years_experience: p.yearsExperience || p.experience || "",
    salary: p.expectedSalary || p.salary || "",
    notice_period: p.noticePeriod || p.availability || "",
    referral_source: p.referralSource || "LinkedIn",
    gender: p.gender || "",
    ethnicity: p.ethnicity || p.race || "",
    veteran_status: p.veteranStatus || "I am not a protected veteran",
    disability_status: p.disabilityStatus || "I don't wish to answer",
  };
  // Merge custom answers (normalized keys)
  for (const [k, v] of Object.entries(custom)) {
    if (v != null && String(v).trim() !== "") {
      const norm = String(k).toLowerCase().trim().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
      if (norm) values[norm] = String(v).trim();
    }
  }
  return values;
}

function buildValuesByFrameWithLimits(fields, mappings, maxEducationBlocks, maxEmploymentBlocks) {
  const occurrenceByFp = {};
  const valuesByFrame = {};
  for (const field of fields) {
    const mapData = mappings[String(field.index)] || mappings[field.index] || mappings[field.fingerprint];
    let val = mapData?.value;
    if ((field.type || "").toLowerCase() === "file" && !val) val = "RESUME_FILE";
    if (val === undefined || val === null || val === "") continue;
    const ats = (field.atsFieldType || "").toLowerCase();
    const fp = field.fingerprint;
    // Use real fingerprint when available; for null-fp, build synthetic key from atsFieldType + label
    // so the same logical block still gets capped correctly (per flow doc §3.4).
    if (EDUCATION_ATS.has(ats) || EMPLOYMENT_ATS.has(ats)) {
      const capKey =
        fp ||
        `__synthetic__${ats}_${(field.label || "").slice(0, 20).toLowerCase().replace(/\s+/g, "_")}`;
      const seen = occurrenceByFp[capKey] ?? 0;
      occurrenceByFp[capKey] = seen + 1;
      const maxBlocks = EDUCATION_ATS.has(ats) ? maxEducationBlocks : maxEmploymentBlocks;
      if (seen >= maxBlocks) continue;
    }
    const fid = String(field.frameId ?? 0);
    const localKey = String(field.frameLocalIndex ?? field.index);
    if (!valuesByFrame[fid]) valuesByFrame[fid] = {};
    valuesByFrame[fid][localKey] = val;
  }
  return valuesByFrame;
}

/** Build field metadata per frame for selector-based element resolution during fill */
function buildFieldsByFrame(fields) {
  const fieldsByFrame = {};
  for (const field of fields) {
    const frameId = String(field.frameId ?? 0);
    if (!fieldsByFrame[frameId]) fieldsByFrame[frameId] = [];
    const localKey = String(field.frameLocalIndex ?? field.index);
    fieldsByFrame[frameId].push({
      index: localKey,
      frameLocalIndex: field.frameLocalIndex ?? field.index,
      selector: field.selector || null,
      id: field.domId || field.id || null,
      domId: field.domId || field.id || null,
      label: field.label || null,
      type: field.type || null,
      tag: field.tag || null,
      atsFieldType: field.atsFieldType || null,
      options: field.options || [],
    });
  }
  return fieldsByFrame;
}

async function fetchMappingsFromApi(fields, context) {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const mapRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/form-fields/map`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({
      fields: fields.map((field) => ({ ...field, id: null })),
      profile: context.profile,
      custom_answers: context.customAnswers,
      resume_text: context.resumeText,
      sync_llm: true, // Run LLM synchronously so dropdowns get values on first fill
    }),
  });
  if (!mapRes.ok) {
    throw new Error(`AI mapping failed (${mapRes.status})`);
  }
  const mapData = await mapRes.json();
  return mapData.mappings || {};
}
if (typeof window !== "undefined") window.__FETCH_MAPPINGS_FROM_API__ = fetchMappingsFromApi;

async function updateWidgetAuthUI(root) {
  let data = {};
  let hasToken = false;
  let loginUrl = DEFAULT_LOGIN_PAGE_URL;

  try {
    data = await chrome.storage.local.get(["accessToken", "loginPageUrl"]);
    hasToken = !!data.accessToken;
    if (data.loginPageUrl) loginUrl = data.loginPageUrl;
  } catch (e) {
    if (e?.message?.includes("Extension context invalidated")) return;
    throw e;
  }

  let isHireMateOrigin = LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o);
  if (!isHireMateOrigin && data.loginPageUrl) {
    try {
      isHireMateOrigin = new URL(data.loginPageUrl).origin === window.location.origin;
    } catch (_) { }
  }

  // 1) If no token in chrome.storage, try localStorage (when on HireMate frontend - same origin)
  if (!hasToken && isHireMateOrigin) {
    try {
      const localToken = localStorage.getItem("token") || localStorage.getItem("access_token");
      if (localToken) {
        hasToken = true;
        await chrome.storage.local.set({ accessToken: localToken });
        logInfo("Token synced from localStorage to extension storage");
      }
    } catch (e) {
      if (e?.message?.includes("Extension context invalidated")) return;
    }
  }

  // 2) If still no token, try fetching from any open HireMate tab (works when on job sites)
  if (!hasToken) {
    try {
      const res = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
      if (res?.ok && res?.token) hasToken = true;
    } catch (e) {
      if (e?.message?.includes("Extension context invalidated")) return;
    }
  }

  const signinCta = root?.querySelector("#ja-signin-cta");
  const autofillAuth = root?.querySelector("#ja-autofill-authenticated");
  if (signinCta) signinCta.style.display = hasToken ? "none" : "block";
  if (autofillAuth) autofillAuth.style.display = hasToken ? "block" : "none";

  const signinCtaKeywords = root?.querySelector("#ja-signin-cta-keywords");
  const keywordsAuth = root?.querySelector("#ja-keywords-authenticated");
  if (signinCtaKeywords) signinCtaKeywords.style.display = hasToken ? "none" : "block";
  if (keywordsAuth) keywordsAuth.style.display = hasToken ? "block" : "none";

  const signinCtaProfile = root?.querySelector("#ja-signin-cta-profile");
  const profileAuth = root?.querySelector("#ja-profile-authenticated");
  if (signinCtaProfile) signinCtaProfile.style.display = hasToken ? "none" : "block";
  if (profileAuth) profileAuth.style.display = hasToken ? "block" : "none";

  const signinBtns = root?.querySelectorAll(".ja-signin-to-autofill");
  signinBtns?.forEach((btn) => {
    btn.onclick = (e) => {
      e.preventDefault();
      try {
        chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url: loginUrl });
      } catch (err) {
        if (!err?.message?.includes("Extension context invalidated")) logWarn("Sign-in click failed", err);
      }
    };
  });

  void updateAutofillFooterStats(root);
}

function mountInPageUI() {
  if (window.self !== window.top) return;
  const existing = document.getElementById(INPAGE_ROOT_ID);
  if (existing) {
    existing.classList.remove("collapsed");
    updateWidgetAuthUI(existing);
    if (isCareerPage()) trackCareerPageView();
    updateSavedTimeDisplay(existing);
    return;
  }

  const root = document.createElement("div");
  root.id = INPAGE_ROOT_ID;
  root.innerHTML = `
    <style>
      #${INPAGE_ROOT_ID} {
        all: initial;
        position: fixed;
        right: 20px;
        top: 80px;
        width: 380px;
        max-width: min(380px, 100vw - 40px);
        max-height: calc(100vh - 100px);
        z-index: 2147483647;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: #1a1a1a;
        box-sizing: border-box;
      }
      #${INPAGE_ROOT_ID} * { box-sizing: border-box; }
      #${INPAGE_ROOT_ID} .ja-card {
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.12);
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        max-height: calc(100vh - 140px);
      }
      #${INPAGE_ROOT_ID} .ja-head {
         display: flex;
  align-items: center;
  justify-content: space-between;

  padding-left: 16px;   /* px-4 */
  padding-right: 16px;
  padding-top: 12px;    /* py-3 */
   padding-bottom: 12px;

  border-bottom: 1px solid #e5e7eb; /* border-border */
  background-color: #ffffff;        /* bg-card */
      }
  #${INPAGE_ROOT_ID} .icon-btn {
  width: 28px;
  height: 28px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 8px; /* rounded-lg */

  color: #6b7280; /* muted text */
  background: transparent;
  border: none;
  cursor: pointer;

  transition: background-color 0.2s ease, color 0.2s ease;
}
  #${INPAGE_ROOT_ID} .icon-btn:hover {
  background-color: #f3f4f6; /* muted background */
}
  #${INPAGE_ROOT_ID} .icon-btn svg {
  width: 14px;
  height: 14px;
}
      #${INPAGE_ROOT_ID} .ja-logo-wrap {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-logo-icon {
        height: 28px;
        object-fit: contain;
        flex-shrink: 0;
      }
        #${INPAGE_ROOT_ID} .ja-upload-box-up{
        margin-top:-7px;


        }
      #${INPAGE_ROOT_ID} .ja-title {
        font-size: 16px;
        font-weight: 700;
        color: #111;
        margin: 0;
      }
      #${INPAGE_ROOT_ID} .ja-head-actions {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-head-btn {
        background: none;
        border: none;
        color: #6b7280;
        font-size: 12px;
        padding: 4px 8px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-head-btn:hover { color: #111; }
     #${INPAGE_ROOT_ID} .ja-close {
  width: 28px;
  height: 28px;

  padding: 0;              /* IMPORTANT: remove extra padding */
  border-radius: 8px;
  display: flex;
 align-items: center;
  justify-content: center;
  transition: background-color 0.2s ease, color 0.2s ease;
}
  #${INPAGE_ROOT_ID} .ja-close:hover {
  background-color: #f3f4f6;
  color: #111;
}
  #${INPAGE_ROOT_ID} .ja-close svg {
  width: 16px;
  height: 16px;
}
      #${INPAGE_ROOT_ID} .ja-tabs {
  display: flex;
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff; /* bg-card */
}
      #${INPAGE_ROOT_ID} .ja-tab {
  flex: 1; /* equal width like flex-1 */

  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;

  padding: 10px 0; /* py-2.5 */
  font-size: 12px; /* text-xs */
  font-weight: 600;

  color: #6b7280; /* muted */
  background: none;
  border: none;

  border-bottom: 2px solid transparent;
  cursor: pointer;

  transition: all 0.2s ease;
  position: relative;
}
    #${INPAGE_ROOT_ID} .ja-tab:hover {
  color: #111827; /* hover:text-foreground */
  background-color: rgba(243, 244, 246, 0.6); /* hover:bg-muted/30 */
}
  
     #${INPAGE_ROOT_ID} .ja-tab.active {
  color: #2563eb; /* primary */
  border-bottom-color: #2563eb;
}
     #${INPAGE_ROOT_ID} .ja-tab svg {
  width: 14px;
  height: 14px;
}
      #${INPAGE_ROOT_ID} .ja-body {
        padding: 6px 8px 10px;
        overflow-y: scroll;
        overflow-x: hidden;
        flex: 1;
        min-height: 0;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
        scrollbar-color: #cbd5e1 #f1f5f9;
        
      }
      #${INPAGE_ROOT_ID} .ja-body::-webkit-scrollbar { width: 6px; }
      #${INPAGE_ROOT_ID} .ja-body::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 3px; }
      #${INPAGE_ROOT_ID} .ja-body::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
      #${INPAGE_ROOT_ID} .ja-body::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
      #${INPAGE_ROOT_ID} .ja-panel { display: none; }
      #${INPAGE_ROOT_ID} .ja-panel.active { display: block; }
#${INPAGE_ROOT_ID} .ja-signin-cta.ja-autofill-box {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border-radius: 16px;
  padding: 18px;
  color: #fff;
  margin: 4px 0 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
  overflow: hidden;
}
      #${INPAGE_ROOT_ID} .ja-signin-cta.ja-autofill-box h3 {
        margin: 0 0 6px 0;
        font-size: 14px;
        font-weight: 600;
        color: #fff;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-signin-cta.ja-autofill-box::before,
      #${INPAGE_ROOT_ID} .ja-signin-cta.ja-autofill-box::after {
        content: "";
        position: absolute;
        border-radius: 50%;
        background: rgba(255,255,255,0.08);
      }
      #${INPAGE_ROOT_ID} .ja-signin-cta.ja-autofill-box::before {
        width: 120px;
        height: 120px;
        top: -40px;
        right: -40px;
      }
      #${INPAGE_ROOT_ID} .ja-signin-cta.ja-autofill-box::after {
        width: 90px;
        height: 90px;
        bottom: -30px;
        right: -20px;
      }

      #${INPAGE_ROOT_ID} .ja-autofill-hero-wrap { padding: 2px 0 0; }
      #${INPAGE_ROOT_ID} .ja-autofill-hero {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 55%, #1d4ed8 100%);
        border-radius: 12px;
        padding: 12px;
        color: #fff;
        position: relative;
        overflow: hidden;
      }
      #${INPAGE_ROOT_ID} .ja-autofill-hero-deco {
        position: absolute;
        border-radius: 50%;
        background: rgba(255,255,255,0.08);
        pointer-events: none;
      }
      #${INPAGE_ROOT_ID} .ja-autofill-hero-deco-1 { width: 96px; height: 96px; top: -24px; right: -24px; }
      #${INPAGE_ROOT_ID} .ja-autofill-hero-deco-2 { width: 64px; height: 64px; bottom: -32px; right: -8px; }
      #${INPAGE_ROOT_ID} .ja-autofill-hero-inner { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 10px; }
      #${INPAGE_ROOT_ID} .ja-autofill-hero-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-autofill-hero-title {
        margin: 0;
        font-size: 0.8125rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 6px;
        color: #fff;
        line-height: 1.25;
      }
      #${INPAGE_ROOT_ID} .ja-autofill-hero-title-ico { display: inline-flex; width: 16px; height: 16px; }
      #${INPAGE_ROOT_ID} .ja-autofill-hero-title-ico .ja-hero-ico { width: 16px; height: 16px; stroke: currentColor; }
      #${INPAGE_ROOT_ID} .ja-autofill-fields-badge {
        font-size: 10px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 999px;
        background: rgba(255,255,255,0.2);
        color: #fff;
        white-space: nowrap;
      }
      #${INPAGE_ROOT_ID} .ja-status-area { display: flex; flex-direction: column; align-items: center; gap: 4px; }
      #${INPAGE_ROOT_ID} .ja-status-loader {
        width: 36px; height: 36px; border: 3px solid rgba(255,255,255,0.3);
        border-top-color: #fff; border-radius: 50%; animation: ja-spin 0.8s linear infinite;
        margin-bottom: 4px; display: none;
      }
      #${INPAGE_ROOT_ID} .ja-status-area.loading .ja-status-loader { display: block; }
      @keyframes ja-spin { to { transform: rotate(360deg); } }
      #${INPAGE_ROOT_ID} .ja-autofill-hero .ja-status.ja-autofill-hero-sub {
        color: rgba(255,255,255,0.88);
        margin: 0;
        min-height: 18px;
        font-size: 11px;
        text-align: center;
        font-weight: 500;
        line-height: 1.45;
        width: 100%;
      }
      #${INPAGE_ROOT_ID} .ja-autofill-hero .ja-status ul { margin: 0; padding-left: 18px; text-align: left; }
      #${INPAGE_ROOT_ID} .ja-autofill-hero .ja-status li { margin: 4px 0; }
      #${INPAGE_ROOT_ID} .ja-autofill-hero .ja-status .ja-note { color: #fef08a; font-weight: 500; }
      #${INPAGE_ROOT_ID} .ja-autofill-hero .ja-status.loading { color: #fef9c3; }
      #${INPAGE_ROOT_ID} .ja-autofill-hero .ja-status.success { color: #bbf7d0; font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-autofill-hero .ja-status.error { color: #fecaca; font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-failed-field-link { background: none; border: none; padding: 0; margin: 2px 0; color: #fef08a; cursor: pointer; font-size: inherit; font-weight: 500; text-align: left; text-decoration: underline; }
      #${INPAGE_ROOT_ID} .ja-failed-field-link:hover { color: #fff; }
      #${INPAGE_ROOT_ID} .ja-failed-fields-list { margin: 4px 0 0 12px; padding-left: 0; list-style: none; }
      #${INPAGE_ROOT_ID} .ja-fields-need-attention { display: block; margin-bottom: 4px; }

      #${INPAGE_ROOT_ID} .ja-autofill-progress-block { margin-top: 2px; }
      #${INPAGE_ROOT_ID} .ja-progress-label-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 10px;
        margin-bottom: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-progress-label-row .ja-progress-label { font-weight: 600; color: rgba(255,255,255,0.72); }
      #${INPAGE_ROOT_ID} .ja-progress-label-row .ja-progress-pct { font-weight: 700; color: #fff; font-size: 10px; }
      #${INPAGE_ROOT_ID} .ja-autofill-progress-track {
        height: 6px;
        border-radius: 999px;
        background: rgba(255,255,255,0.22);
        overflow: hidden;
      }
      #${INPAGE_ROOT_ID} .ja-autofill-progress-bar {
        height: 100%;
        width: 0%;
        background: #fff;
        border-radius: 999px;
        transition: width 0.3s ease;
      }

      #${INPAGE_ROOT_ID} .ja-autofill-actions { display: flex; flex-direction: column; gap: 8px; }
      #${INPAGE_ROOT_ID} .ja-btn-hero-fill {
        width: 100%;
        height: 36px;
        border: none;
        border-radius: 10px;
        background: #fff;
        color: #2563eb;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 10px 25px rgba(0,0,0,0.12);
        transition: background 0.2s ease, opacity 0.2s ease;
      }
      #${INPAGE_ROOT_ID} .ja-btn-hero-fill:hover:not(:disabled) { background: rgba(255,255,255,0.92); }
      #${INPAGE_ROOT_ID} .ja-btn-hero-fill:disabled { opacity: 0.85; cursor: not-allowed; }
      #${INPAGE_ROOT_ID} .ja-btn-fill-inner { display: inline-flex; align-items: center; justify-content: center; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-btn-fill-icon { display: inline-flex; width: 16px; height: 16px; color: #2563eb; }
      #${INPAGE_ROOT_ID} .ja-btn-fill-icon .ja-hero-ico { width: 16px; height: 16px; stroke: currentColor; }
      #${INPAGE_ROOT_ID} .ja-hero-ico { stroke: currentColor; }

     #${INPAGE_ROOT_ID} .ja-action {
  width: 100%;
  height: 44px;

  background: #ffffff;
  color: #2563eb;

  border: none;
  border-radius: 12px;

  font-size: 14px;
  font-weight: 600;

  cursor: pointer;

  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;

  transition: all 0.2s ease;
}

#${INPAGE_ROOT_ID} .ja-action:hover {
  background: rgba(255,255,255,0.9);
}
      #${INPAGE_ROOT_ID} .ja-action-row { display: flex; gap: 8px; margin-top: 6px;}
      #${INPAGE_ROOT_ID} .ja-action { flex: 1; }
      #${INPAGE_ROOT_ID} .ja-action:hover { background: #f0fdfa; }
      #${INPAGE_ROOT_ID} .ja-action:disabled { opacity: 0.6; cursor: not-allowed; }
      #${INPAGE_ROOT_ID} .ja-fill-controls { display: none; flex-direction: column; gap: 6px; margin-top: 0; }
      #${INPAGE_ROOT_ID} .ja-fill-controls.visible { display: flex; }
      #${INPAGE_ROOT_ID} .ja-fill-controls .ja-fill-label { font-size: 12px; color: rgba(255,255,255,0.9); font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-fill-controls-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
      #${INPAGE_ROOT_ID} .ja-stop { padding: 8px 14px; background: #dc2626; color: #fff; border: none; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-stop:hover { background: #b91c1c; }
      #${INPAGE_ROOT_ID} .ja-skip-next { padding: 8px 14px; background: rgba(255,255,255,0.2); color: #fff; border: 1px solid rgba(255,255,255,0.4); border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-skip-next:hover { background: rgba(255,255,255,0.3); }
      #${INPAGE_ROOT_ID} .ja-continue-fill { width: 100%; padding: 10px 16px; background: #16a34a; color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 0; }
      #${INPAGE_ROOT_ID} .ja-continue-fill:hover { background: #15803d; }
      #${INPAGE_ROOT_ID} .ja-auto-advance { display: flex; align-items: center; gap: 8px; margin-top: 2px; font-size: 11px; color: rgba(255,255,255,0.88); cursor: pointer; }
      #${INPAGE_ROOT_ID} .ja-auto-advance input { cursor: pointer; }
    #${INPAGE_ROOT_ID} .ja-cache-enable {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(255,255,255,0.88);
  font-size: 11px;
  margin-top: 2px;
}
      #${INPAGE_ROOT_ID} .ja-cache-enable input { cursor: pointer; }

      #${INPAGE_ROOT_ID} .ja-autofill-footer-stats {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        padding: 8px 6px;
        font-size: 10px;
        color: #64748b;
        background: rgba(241, 245, 249, 0.65);
        border-top: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-autofill-footer-item { display: inline-flex; align-items: center; gap: 4px; }
      #${INPAGE_ROOT_ID} .ja-autofill-footer-ico { display: inline-flex; width: 12px; height: 12px; }
      #${INPAGE_ROOT_ID} .ja-autofill-footer-ico .ja-q-svg { width: 12px; height: 12px; stroke: #64748b; }
  #${INPAGE_ROOT_ID} .ja-footer-links {
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin-top: 0;
  border-top: 1px solid #e5e7eb;
}
  #${INPAGE_ROOT_ID} .ja-footer-link:not(:last-child) {
  border-right: 1px solid #e5e7eb;
}
     #${INPAGE_ROOT_ID} .ja-footer-link {
  min-height: 36px;
  padding: 10px 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  color: #2563eb;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background-color 0.2s ease;
}
  #${INPAGE_ROOT_ID} .ja-footer-link:hover {
  background-color: rgba(37, 99, 235, 0.08);
  text-decoration: none;
}
      #${INPAGE_ROOT_ID} .ja-footer-link-ico {
  display: inline-flex;
  width: 12px;
  height: 12px;
  align-items: center;
  justify-content: center;
}
      #${INPAGE_ROOT_ID} .ja-footer-link-ico svg {
  width: 12px;
  height: 12px;
}
#${INPAGE_ROOT_ID} .ja-accordions {
  margin: 6px 0 0;
  background: #ffffff;
  border-top: 1px solid #e5e7eb;
}
        
     #${INPAGE_ROOT_ID} .ja-accordion-item {
  border-bottom: 1px solid #e5e7eb;
}
      #${INPAGE_ROOT_ID} .ja-accordion-item:last-child { border-bottom: none; }
     #${INPAGE_ROOT_ID} .ja-accordion-header {
  width: 100%;

  display: flex;
  align-items: center;
  gap: 12px;

  padding: 10px 8px;

  background: transparent;
  border: none;

  cursor: pointer;
  text-align: left;

  transition: background-color 0.2s ease;
}
     #${INPAGE_ROOT_ID} .ja-accordion-header:hover {
  background-color: rgba(243, 244, 246, 0.6); /* muted/30 */
}
     #${INPAGE_ROOT_ID} .ja-accordion-icon {
  width: 32px;
  height: 32px;

  border-radius: 8px;

  display: flex;
  align-items: center;
  justify-content: center;

  flex-shrink: 0;
}
     #${INPAGE_ROOT_ID} .ja-accordion-icon svg {
  width: 16px;
  height: 16px;

  stroke: #374151;
  stroke-width: 2;
}
  #${INPAGE_ROOT_ID} .ja-icon-zap { 
  color:#ffffff;
}

      #${INPAGE_ROOT_ID} .ja-accordion-title-wrap {
        flex: 1;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-title { font-weight: 600; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-accordion-help {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #9ca3af;
        color: #fff;
        font-size: 11px;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-status {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        color: #9ca3af;
        font-weight: 400;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-status-text {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 500;
        color: #6b7280;
        background: #f3f4f6;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-check {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        line-height: 0;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-check .ja-resume-check-img {
        width: 14px;
        height: 14px;
        display: block;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-chevron {
        font-size: 10px;
        color: #6b7280;
        transition: transform 0.2s;
      }
/* container like Tailwind: rounded + overflow hidden */
.ja-resume-card {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
  margin-top: 12px;
}

.ja-resume-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  gap: 10px;
}

.ja-resume-row:not(:last-child) {
  border-bottom: 1px solid #e5e7eb;
}

/* left label */
.ja-resume-label {
  color: #6b7280;
  font-weight: 500;
  min-width: 130px;  /* 🔥 fixed label width */
}

/* right side */
.ja-resume-value-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: flex-end;
  flex: 1;
}

/* ✅ NO MULTILINE EVER */
.ja-resume-value {
  color: #111827;
  font-weight: 600;
  font-size: 13px;

  white-space: nowrap;   /* 🔥 SINGLE LINE */
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ✅ ICON ALWAYS VISIBLE */
.ja-check-icon {
  flex-shrink: 0;
}

.ja-check-icon img,
.ja-check-icon svg {
  width: 14px;
  height: 14px;
  display: block;
}

.ja-btn-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Shared base (IMPORTANT - avoids duplication) */
.ja-btn,
.ja-btn-icon {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s ease;

  display: flex;
  align-items: center;
  justify-content: center;
}

/* Main buttons */
.ja-btn {
  flex: 1;
  height: 30px;
  font-size: 14px;
  gap: 4px;
  color: #111827;
  font-weight: 600;
}

.ja-btn:hover {
  background: #f3f4f6; /* slightly better than fafb */
}

/* Icon only button */
.ja-btn-icon {
  width: 28px;
  height: 28px;
  font-weight: 600;
}

.ja-btn-icon:hover {
  background: #f3f4f6;
}

/* Icon */
.ja-icon {
  width: 18px;
  height: 18px;

  stroke-width: 2; /* 🔥 important for lucide look */
}


      #${INPAGE_ROOT_ID} .ja-accordion-item.expanded .ja-accordion-chevron { transform: rotate(180deg); }
      #${INPAGE_ROOT_ID} .ja-accordion-body { border-top: 1px solid #e5e7eb; }
      #${INPAGE_ROOT_ID} .ja-resume-accordion-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
      #${INPAGE_ROOT_ID} .ja-resume-accordion-row .ja-resume-select { flex: 1; padding: 6px 10px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 13px; }
      #${INPAGE_ROOT_ID} .ja-resume-preview-hint { font-size: 11px; color: #6b7280; margin: 4px 0 0 0; }
/* Container (your Tailwind equivalent) */
#${INPAGE_ROOT_ID} .ja-cover-box {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  background: #f9fafb;
  margin-bottom: 10px;
}

/* Job title */
#${INPAGE_ROOT_ID} .ja-cover-letter-job {
  font-weight: 600;
  margin: 0 0 6px 0;
  font-size: 12px;
  color: #111827;
}

/* Letter text */
#${INPAGE_ROOT_ID} .ja-cover-letter-text {
  font-size: 12px;
  line-height: 1.6;
  color: #374151;

  white-space: pre-wrap;
  word-break: break-word;
}
      /* Unique Questions — card stack (Tailwind: space-y-2, rounded-lg border p-3) */
      #${INPAGE_ROOT_ID} .ja-uq-stack {
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-height: 280px;
        overflow-y: auto;
      }
      #${INPAGE_ROOT_ID} .ja-uq-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px;
        background: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-uq-qrow {
        display: flex;
        align-items: flex-start;
        gap: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-uq-help {
        flex-shrink: 0;
        margin-top: 2px;
        color: #a855f7;
        display: flex;
      }
      #${INPAGE_ROOT_ID} .ja-uq-help .ja-q-svg { width: 14px; height: 14px; }
      #${INPAGE_ROOT_ID} .ja-uq-question {
        margin: 0;
        font-size: 12px;
        font-weight: 600;
        color: #111827;
        line-height: 1.35;
      }
      #${INPAGE_ROOT_ID} .ja-uq-body {
        margin-top: 8px;
        margin-left: 22px;
      }
      #${INPAGE_ROOT_ID} .ja-uq-body-empty {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 8px;
        margin-left: 22px;
      }
      #${INPAGE_ROOT_ID} .ja-uq-answer {
        margin: 0 0 6px 0;
        font-size: 12px;
        color: #6b7280;
        line-height: 1.5;
      }
      #${INPAGE_ROOT_ID} .ja-uq-foot {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
      }
      #${INPAGE_ROOT_ID} .ja-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 9px;
        font-weight: 600;
        line-height: 1;
        padding: 0 6px;
        height: 16px;
        border-radius: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-badge-ai {
        background: #f3f4f6;
        color: #4b5563;
        border: none;
      }
      #${INPAGE_ROOT_ID} .ja-badge-ai .ja-q-svg-tiny { width: 10px; height: 10px; stroke-width: 2; }
      #${INPAGE_ROOT_ID} .ja-badge-need {
        background: transparent;
        color: #d97706;
        border: 1px solid rgba(217, 119, 6, 0.35);
      }
      #${INPAGE_ROOT_ID} .ja-uq-textbtn {
        border: none;
        background: none;
        padding: 0;
        cursor: pointer;
        font-size: 10px;
        font-weight: 600;
        color: #2563eb;
      }
      #${INPAGE_ROOT_ID} .ja-uq-textbtn:hover { text-decoration: underline; }
      #${INPAGE_ROOT_ID} .ja-uq-textbtn-wand {
        display: inline-flex;
        align-items: center;
        gap: 2px;
      }
      #${INPAGE_ROOT_ID} .ja-uq-textbtn-wand .ja-q-svg-tiny { width: 10px; height: 10px; }

      /* Common Questions — bordered list + footer (muted/30 bar) + meta row */
      #${INPAGE_ROOT_ID} .ja-cq-shell {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        overflow: hidden;
        background: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-cq-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 10px 12px;
        font-size: 12px;
      }
      #${INPAGE_ROOT_ID} .ja-cq-row-b { border-bottom: 1px solid #e5e7eb; }
      #${INPAGE_ROOT_ID} .ja-cq-q {
        flex: 1;
        min-width: 0;
        color: #6b7280;
        line-height: 1.35;
        padding-right: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-cq-ans {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-shrink: 0;
      }
      #${INPAGE_ROOT_ID} .ja-cq-val {
        font-weight: 500;
        color: #111827;
        max-width: 140px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      #${INPAGE_ROOT_ID} .ja-cq-ico { display: flex; }
      #${INPAGE_ROOT_ID} .ja-cq-ico .ja-q-svg { width: 12px; height: 12px; }
      #${INPAGE_ROOT_ID} .ja-cq-ico .ja-cq-state { color: #22c55e; }
      #${INPAGE_ROOT_ID} .ja-cq-ico .ja-cq-warn { color: #d97706; }
      #${INPAGE_ROOT_ID} .ja-cq-editbar {
        padding: 8px 12px;
        background: rgba(243, 244, 246, 0.85);
        border-top: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-cq-editall {
        border: none;
        background: none;
        padding: 0;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 10px;
        font-weight: 600;
        color: #2563eb;
      }
      #${INPAGE_ROOT_ID} .ja-cq-editall:hover { text-decoration: underline; }
      #${INPAGE_ROOT_ID} .ja-cq-editall .ja-q-svg-tiny { width: 10px; height: 10px; }
      #${INPAGE_ROOT_ID} .ja-cq-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px solid #e5e7eb;
        font-size: 11px;
        color: #9ca3af;
      }
      #${INPAGE_ROOT_ID} .ja-cq-meta-item {
        display: inline-flex;
        align-items: center;
        gap: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-q-meta { width: 12px; height: 12px; stroke-width: 2; }
      #${INPAGE_ROOT_ID} .ja-accordion-content {
        padding: 10px 8px;
        font-size: 13px;
        color: #6b7280;
      }
      #${INPAGE_ROOT_ID} .ja-keywords-section { margin-bottom: 12px; }
      #${INPAGE_ROOT_ID} .ja-keywords-section label {
        display: block;
        font-size: 12px;
        font-weight: 600;
        color: #374151;
        margin-bottom: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-resume-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 10px;
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        
        
      }
      #${INPAGE_ROOT_ID} .ja-resume-row span { flex: 1; font-size: 13px; color: #374151; }
      #${INPAGE_ROOT_ID} .ja-resume-row button {
        background: none;
        border: none;
        color: #0ea5e9;
        cursor: pointer;
        padding: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-resume-select {
        width: 100%;
        padding: 8px 10px;
        font-size: 13px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        background: #fff;
        margin-bottom: 10px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-update-jd-btn {
        width: 100%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        padding: 8px 12px;
        margin-top: 0;
        background: #fff;
        color: #111827;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.15s, border-color 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-kw-update-jd-btn .ja-kw-ico { width: 12px; height: 12px; flex-shrink: 0; }
      #${INPAGE_ROOT_ID} .ja-kw-update-jd-btn:hover { background: #f9fafb; border-color: #d1d5db; }
      #${INPAGE_ROOT_ID} .ja-job-form input, #${INPAGE_ROOT_ID} .ja-job-form select, #${INPAGE_ROOT_ID} .ja-job-form textarea {
        width: 100%;
        padding: 8px 10px;
        font-size: 13px;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        margin-bottom: 10px;
      }
      #${INPAGE_ROOT_ID} .ja-job-form label { display: block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 4px; }
      #${INPAGE_ROOT_ID} .ja-job-form .ja-form-row { display: flex; gap: 10px; }
      #${INPAGE_ROOT_ID} .ja-job-form .ja-form-row > div { flex: 1; }
      #${INPAGE_ROOT_ID} .ja-job-form-actions { display: flex; gap: 8px; margin-top: 14px; }
      #${INPAGE_ROOT_ID} .ja-job-form-actions button { flex: 1; padding: 10px; border-radius: 8px; font-weight: 600; cursor: pointer; }
      #${INPAGE_ROOT_ID} .ja-go-back-btn { background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb; }
      #${INPAGE_ROOT_ID} .ja-save-job-btn { background: #2563eb; color: #fff; border: none; }
      /* Keywords tab — layout + score card + chip grid (Tailwind/shadcn-style) */
      #${INPAGE_ROOT_ID} .ja-kw-tab {
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-active-resume-row {
        display: flex;
        align-items: flex-end;
        gap: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-active-resume-field {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-label-upper {
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #9ca3af;
        margin: 0;
      }
      #${INPAGE_ROOT_ID} .ja-kw-resume-select {
        height: 32px;
        padding: 4px 8px;
        font-size: 12px;
        margin-bottom: 0;
      }
      #${INPAGE_ROOT_ID} .ja-kw-tailor-btn {
        flex-shrink: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
        height: 32px;
        margin-top: 18px;
        padding: 0 12px;
        background: #2563eb;
        color: #fff;
        border: none;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-kw-tailor-btn .ja-kw-ico { width: 12px; height: 12px; stroke-width: 2; }
      #${INPAGE_ROOT_ID} .ja-kw-tailor-btn:hover { background: #1d4ed8; }
      #${INPAGE_ROOT_ID} .ja-keyword-card {
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        margin-bottom: 0;
      }
      #${INPAGE_ROOT_ID} .ja-kw-score-card { padding: 0; overflow: hidden; }
      #${INPAGE_ROOT_ID} .ja-keyword-card.ja-loading { position: relative; min-height: 80px; }
      #${INPAGE_ROOT_ID} .ja-keyword-card.ja-loading::after {
        content: ""; position: absolute; top: 50%; left: 50%; margin: -12px 0 0 -12px;
        width: 24px; height: 24px; border: 2px solid #e5e7eb; border-top-color: #2563eb;
        border-radius: 50%; animation: ja-spin 0.8s linear infinite;
      }
      #${INPAGE_ROOT_ID} .ja-keyword-card .ja-score-text { font-size: 12px; color: #6b7280; margin-bottom: 0; padding: 12px 14px; }
      #${INPAGE_ROOT_ID} .ja-kw-score-empty { padding: 12px 14px; }
      #${INPAGE_ROOT_ID} .ja-kw-score-main {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 16px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-gauge-circle-wrap {
        position: relative;
        width: 80px;
        height: 80px;
        flex-shrink: 0;
      }
      #${INPAGE_ROOT_ID} .ja-kw-gauge-circle {
        width: 80px;
        height: 80px;
        display: block;
      }
      #${INPAGE_ROOT_ID} .ja-kw-gauge-circle-label {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        pointer-events: none;
      }
      #${INPAGE_ROOT_ID} .ja-kw-pct-num {
        font-size: 18px;
        font-weight: 700;
        line-height: 1;
      }
      #${INPAGE_ROOT_ID} .ja-kw-pct-sub {
        font-size: 8px;
        font-weight: 600;
        color: #9ca3af;
        margin-top: 2px;
        letter-spacing: 0.02em;
      }
      #${INPAGE_ROOT_ID} .ja-kw-score-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
      #${INPAGE_ROOT_ID} .ja-kw-badge-row { display: flex; align-items: center; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-kw-status-badge {
        display: inline-flex;
        align-items: center;
        font-size: 10px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 6px;
        border: 0;
      }
      #${INPAGE_ROOT_ID} .ja-kw-line { margin: 0; font-size: 12px; line-height: 1.45; }
      #${INPAGE_ROOT_ID} .ja-kw-line-muted { color: #6b7280; }
      #${INPAGE_ROOT_ID} .ja-kw-strong { color: #111827; font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-kw-hilo { display: flex; gap: 12px; font-size: 10px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-kw-tip-bar {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 10px 16px;
        border-top: 1px solid #e5e7eb;
        background: rgba(37, 99, 235, 0.04);
      }
      #${INPAGE_ROOT_ID} .ja-kw-tip-bar .ja-kw-ico-tip {
        width: 14px;
        height: 14px;
        flex-shrink: 0;
        margin-top: 2px;
        color: #2563eb;
      }
      #${INPAGE_ROOT_ID} .ja-kw-tip-text { margin: 0; font-size: 11px; color: #111827; line-height: 1.4; }
      #${INPAGE_ROOT_ID} .ja-keyword-keywords-list {
        margin-top: 0;
        display: flex;
        flex-direction: column;
        gap: 16px;
        max-height: 320px;
        overflow-y: auto;
      }
      #${INPAGE_ROOT_ID} .ja-kw-priority-block { display: flex; flex-direction: column; gap: 8px; }
      #${INPAGE_ROOT_ID} .ja-kw-priority-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      #${INPAGE_ROOT_ID} .ja-kw-priority-head-left {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
      #${INPAGE_ROOT_ID} .ja-kw-dot-high { background: #ef4444; }
      #${INPAGE_ROOT_ID} .ja-kw-dot-low { background: #f59e0b; }
      #${INPAGE_ROOT_ID} .ja-kw-priority-name { font-size: 12px; font-weight: 700; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-kw-priority-meta { font-size: 10px; font-weight: 600; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-kw-chip-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-chip {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 10px;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
        background: #fff;
        transition: background 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-kw-chip--on {
        border-color: rgba(34, 197, 94, 0.35);
        background: rgba(34, 197, 94, 0.06);
      }
      #${INPAGE_ROOT_ID} .ja-kw-chip--off:hover { background: rgba(243, 244, 246, 0.7); }
      #${INPAGE_ROOT_ID} .ja-kw-chip-box {
        width: 16px;
        height: 16px;
        border-radius: 4px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #${INPAGE_ROOT_ID} .ja-kw-chip--on .ja-kw-chip-box {
        background: #22c55e;
        color: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-kw-chip--off .ja-kw-chip-box {
        background: #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-kw-chip-check { width: 10px; height: 10px; stroke: currentColor; }
      #${INPAGE_ROOT_ID} .ja-kw-chip-name {
        flex: 1;
        min-width: 0;
        font-size: 11px;
        line-height: 1.25;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      #${INPAGE_ROOT_ID} .ja-kw-chip--on .ja-kw-chip-name { color: #111827; font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-kw-chip--off .ja-kw-chip-name { color: #9ca3af; font-weight: 400; }
      #${INPAGE_ROOT_ID} .ja-kw-chip-freq { font-size: 9px; font-weight: 600; color: #9ca3af; flex-shrink: 0; }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-card {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 12px;
        background: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-head {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-head .ja-kw-ico { width: 14px; height: 14px; color: #2563eb; }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-title { font-size: 12px; font-weight: 700; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-sub { margin: 0 0 8px 0; font-size: 11px; color: #6b7280; }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-pills { display: flex; flex-wrap: wrap; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-pill {
        display: inline-flex;
        align-items: center;
        padding: 4px 8px;
        font-size: 10px;
        font-weight: 500;
        color: #374151;
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 9999px;
        cursor: default;
      }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-pill:hover {
        background: rgba(37, 99, 235, 0.06);
        color: #2563eb;
        border-color: rgba(37, 99, 235, 0.25);
      }
      /* Profile tab — stats, hero, contact rows, sections (Tailwind/shadcn-style) */
      #${INPAGE_ROOT_ID} .ja-panel-profile .ja-profile-authenticated { padding: 0; }
      #${INPAGE_ROOT_ID} .ja-profile-tab {
        border-top: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-profile-stats {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        border-bottom: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-profile-stat {
        text-align: center;
        padding: 12px 8px;
        border-right: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-profile-stat:last-child { border-right: none; }
      #${INPAGE_ROOT_ID} .ja-profile-stat-val {
        margin: 0;
        font-size: 18px;
        font-weight: 700;
        color: #111827;
        line-height: 1.2;
      }
      #${INPAGE_ROOT_ID} .ja-profile-stat-success { color: #16a34a; }
      #${INPAGE_ROOT_ID} .ja-profile-stat-primary { color: #2563eb; }
      #${INPAGE_ROOT_ID} .ja-profile-stat-label {
        margin: 4px 0 0 0;
        font-size: 9px;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #9ca3af;
      }
      #${INPAGE_ROOT_ID} .ja-prof-hero-wrap {
        padding: 16px;
        border-bottom: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-prof-hero {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        margin-bottom: 12px;
      }
      #${INPAGE_ROOT_ID} .ja-avatar.ja-avatar-gradient {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #2563eb 0%, #60a5fa 100%);
        color: #fff;
        font-weight: 700;
        font-size: 14px;
        flex-shrink: 0;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
      }
      #${INPAGE_ROOT_ID} .ja-prof-hero-text { flex: 1; min-width: 0; }
      #${INPAGE_ROOT_ID} .ja-profile-name { margin: 0; font-size: 14px; font-weight: 700; color: #111827; line-height: 1.25; }
      #${INPAGE_ROOT_ID} .ja-profile-title { margin: 2px 0 0 0; font-size: 12px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-prof-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-prof-act-btn {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        height: 24px;
        padding: 0 8px;
        font-size: 10px;
        font-weight: 600;
        color: #374151;
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        cursor: pointer;
        transition: background 0.15s, border-color 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-prof-act-btn:hover { background: #f9fafb; border-color: #d1d5db; }
      #${INPAGE_ROOT_ID} .ja-prof-act-btn .ja-prof-btn-ico { width: 10px; height: 10px; flex-shrink: 0; }
      #${INPAGE_ROOT_ID} .ja-prof-contact-grid { display: flex; flex-direction: column; gap: 2px; }
      #${INPAGE_ROOT_ID} .ja-prof-contact-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        border-radius: 8px;
        transition: background 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-prof-contact-row:hover { background: rgba(243, 244, 246, 0.7); }
      #${INPAGE_ROOT_ID} .ja-prof-contact-ico {
        flex-shrink: 0;
        color: #9ca3af;
        display: flex;
      }
      #${INPAGE_ROOT_ID} .ja-prof-svg { width: 12px; height: 12px; stroke-width: 2; }
      #${INPAGE_ROOT_ID} .ja-prof-svg-sec { color: #2563eb; }
      #${INPAGE_ROOT_ID} .ja-prof-contact-val {
        flex: 1;
        min-width: 0;
        font-size: 12px;
        color: #111827;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      #${INPAGE_ROOT_ID} .ja-prof-copy {
        flex-shrink: 0;
        width: 24px;
        height: 24px;
        padding: 0;
        border: none;
        border-radius: 6px;
        background: transparent;
        color: #9ca3af;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: color 0.15s, background 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-prof-copy:hover { color: #2563eb; background: rgba(243, 244, 246, 0.9); }
      #${INPAGE_ROOT_ID} .ja-prof-copy--done { color: #16a34a; }
      #${INPAGE_ROOT_ID} .ja-prof-copy-ico { width: 12px; height: 12px; }
      #${INPAGE_ROOT_ID} .ja-prof-copy-check { stroke: #16a34a; }
      #${INPAGE_ROOT_ID} .ja-prof-block {
        padding: 16px;
        border-bottom: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-prof-block:last-child { border-bottom: none; }
      #${INPAGE_ROOT_ID} .ja-prof-sec-head {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-prof-sec-head-row {
        justify-content: space-between;
      }
      #${INPAGE_ROOT_ID} .ja-prof-sec-head-left {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-prof-sec-title {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #6b7280;
      }
      #${INPAGE_ROOT_ID} .ja-prof-sec-count { font-size: 10px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-prof-empty { margin: 0; font-size: 12px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-prof-edu-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px;
        background: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-prof-edu-school { margin: 0 0 4px 0; font-size: 12px; font-weight: 700; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-prof-edu-degree { margin: 0 0 6px 0; font-size: 11px; color: #6b7280; }
      #${INPAGE_ROOT_ID} .ja-prof-edu-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
      #${INPAGE_ROOT_ID} .ja-prof-edu-dates { font-size: 10px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-prof-badge {
        display: inline-flex;
        align-items: center;
        font-size: 9px;
        font-weight: 600;
        padding: 0 6px;
        height: 16px;
        border-radius: 9999px;
      }
      #${INPAGE_ROOT_ID} .ja-prof-badge-muted { background: #f3f4f6; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-prof-exp-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
        background: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-prof-exp-card:last-child { margin-bottom: 0; }
      #${INPAGE_ROOT_ID} .ja-prof-exp-top {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-prof-exp-title { margin: 0; font-size: 12px; font-weight: 700; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-prof-exp-company { margin: 4px 0 0 0; font-size: 11px; font-weight: 500; color: #2563eb; }
      #${INPAGE_ROOT_ID} .ja-prof-exp-meta { margin: 4px 0 0 0; font-size: 10px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-prof-exp-bullets {
        list-style: none;
        padding: 0;
        margin: 8px 0 0 0;
      }
      #${INPAGE_ROOT_ID} .ja-prof-exp-li {
        display: flex;
        gap: 8px;
        font-size: 11px;
        color: #6b7280;
        line-height: 1.45;
        margin-bottom: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-prof-exp-dot {
        width: 4px;
        height: 4px;
        border-radius: 50%;
        background: rgba(37, 99, 235, 0.45);
        flex-shrink: 0;
        margin-top: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-prof-cert-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-prof-cert-pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        font-size: 10px;
        font-weight: 500;
        color: #374151;
        border: 1px solid #e5e7eb;
        border-radius: 9999px;
        background: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-prof-award-sm { width: 10px; height: 10px; flex-shrink: 0; }
      #${INPAGE_ROOT_ID} .ja-prof-upload-card {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px;
        background: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-prof-upload-left { display: flex; align-items: center; gap: 8px; min-width: 0; }
      #${INPAGE_ROOT_ID} .ja-prof-upload-icon {
        width: 32px;
        height: 32px;
        border-radius: 8px;
        background: rgba(239, 68, 68, 0.1);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #dc2626;
        flex-shrink: 0;
      }
      #${INPAGE_ROOT_ID} .ja-prof-upload-icon .ja-prof-svg { width: 16px; height: 16px; }
      #${INPAGE_ROOT_ID} .ja-prof-upload-name { margin: 0; font-size: 12px; font-weight: 600; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-prof-upload-meta { margin: 2px 0 0 0; font-size: 10px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-prof-upload-actions { display: flex; gap: 4px; flex-shrink: 0; }
      #${INPAGE_ROOT_ID} .ja-prof-file-btn {
        width: 28px;
        height: 28px;
        padding: 0;
        border: none;
        border-radius: 6px;
        background: transparent;
        color: #6b7280;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #${INPAGE_ROOT_ID} .ja-prof-file-btn:hover { background: #f3f4f6; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-prof-file-act { width: 14px; height: 14px; }
      #${INPAGE_ROOT_ID} .ja-prof-skill-wrap { display: flex; flex-wrap: wrap; gap: 4px; }
      #${INPAGE_ROOT_ID} .ja-prof-chip {
        display: inline-flex;
        align-items: center;
        padding: 4px 8px;
        font-size: 10px;
        font-weight: 400;
        border-radius: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-prof-chip-tech {
        background: #f3f4f6;
        color: #374151;
        border: none;
        cursor: pointer;
        transition: background 0.15s, color 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-prof-chip-tech:hover { background: rgba(37, 99, 235, 0.1); color: #2563eb; }
      #${INPAGE_ROOT_ID} .ja-prof-chip-soft {
        border: 1px solid #e5e7eb;
        background: #fff;
        color: #4b5563;
      }
      #${INPAGE_ROOT_ID} .ja-prof-chip-lang {
        background: #f3f4f6;
        color: #374151;
      }
      #${INPAGE_ROOT_ID}.collapsed .ja-card { display: none; }
      #${INPAGE_ROOT_ID}.collapsed {
        width: 56px;
        height: 56px;
        min-width: 56px;
        max-height: 56px;
      }
      #${INPAGE_ROOT_ID} .ja-mini {
        display: none;
        position: absolute;
        top: 50%;
        right: 0;
        transform: translateY(-50%);
        width: 56px;
        height: 56px;
        background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
        color: white;
        border: none;
        border-radius: 50%;
        font-size: 24px;
        cursor: move;
        box-shadow: 0 8px 24px rgba(14, 165, 233, 0.4);
        align-items: center;
        justify-content: center;
        transition: transform 0.2s;
      }
      #${INPAGE_ROOT_ID} .ja-mini:hover { transform: translateY(-50%) scale(1.05); }
      #${INPAGE_ROOT_ID}.collapsed .ja-mini { display: flex; }
    </style>
    <div class="ja-card">
      <div class="ja-head" id="ja-drag-handle">
        <div class="ja-logo-wrap">
          <img class="ja-logo-icon" src="${chrome.runtime.getURL('logo.png')}" alt="OpsBrain" />
        </div>
        <div class="ja-head-actions">
        <button class="icon-btn">
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    stroke-width="2" 
    stroke-linecap="round" 
    stroke-linejoin="round"
  >
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
    <path d="M3 3v5h5"/>
  </svg>
</button>

         <button type="button" class="ja-close ja-head-btn" id="ja-close" title="Close">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
    <line x1="18" y1="6" x2="6" y2="18"></line>
    <line x1="6" y1="6" x2="18" y2="18"></line>
  </svg>
</button>
        </div>
      </div>
      <div class="ja-tabs">
        <button type="button" class="ja-tab active" data-tab="autofill" id="ja-tab-autofill">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19l7-7 3 3-7 7-3-3z M4 4l7 7 3 3"/></svg>
          Autofill
        </button>
        <button type="button" class="ja-tab" data-tab="keywords">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          Keywords Score
        </button>
        <button type="button" class="ja-tab" data-tab="profile">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
          Profile
        </button>
      </div>
      <div class="ja-body">
        <div class="ja-panel active" id="ja-panel-autofill">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta" style="display:none">
            <h3>Sign in to autofill</h3>
            <p>Information is pulled from your OpsBrain profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill" id="ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-autofill-authenticated" id="ja-autofill-authenticated">
            <div class="ja-autofill-tab">
              <div class="ja-autofill-hero-wrap">
                <div class="ja-autofill-hero">
                  <div class="ja-autofill-hero-deco ja-autofill-hero-deco-1" aria-hidden="true"></div>
                  <div class="ja-autofill-hero-deco ja-autofill-hero-deco-2" aria-hidden="true"></div>
                  <div class="ja-autofill-hero-inner">
                    <div class="ja-autofill-hero-head">
                      <p class="ja-autofill-hero-title">
                        <span class="ja-autofill-hero-title-ico" aria-hidden="true">${AUTOFILL_TAB_ICONS.zap}</span>
                        Autofill Application
                      </p>
                      <span id="ja-fields-count" class="ja-autofill-fields-badge">8/8 fields</span>
                    </div>
                    <div class="ja-status-area" id="ja-status-area">
                      <div class="ja-status-loader" id="ja-status-loader"></div>
                      <div class="ja-status ja-autofill-hero-sub" id="ja-status">One-click fill for this job application</div>
                    </div>
                    <div class="ja-autofill-progress-block">
                      <div class="ja-progress-label-row">
                        <span class="ja-progress-label">Progress</span>
                        <span id="ja-progress-text" class="ja-progress-pct">0%</span>
                      </div>
                      <div class="ja-autofill-progress-track">
                        <div id="ja-progress" class="ja-autofill-progress-bar" style="width:0%"></div>
                      </div>
                    </div>
                    <div class="ja-autofill-actions">
                      <button type="button" class="ja-btn-hero-fill" id="ja-run">
                        <span class="ja-btn-fill-inner" id="ja-run-inner">
                          <span class="ja-btn-fill-icon" aria-hidden="true">${AUTOFILL_TAB_ICONS.sparkles}</span>
                          <span class="ja-btn-fill-label">Autofill this page</span>
                        </span>
                      </button>
                      <div class="ja-fill-controls" id="ja-fill-controls" aria-hidden="true">
                        <span class="ja-fill-label">Autofilling</span>
                        <div class="ja-fill-controls-row">
                          <button type="button" class="ja-stop" id="ja-stop">Stop</button>
                          <button type="button" class="ja-skip-next" id="ja-skip-next">⏭ Skip to next input</button>
                        </div>
                      </div>
                      <button type="button" class="ja-continue-fill" id="ja-continue-fill" style="display:none">Continue filling</button>
                    </div>
                    <label class="ja-cache-enable" id="ja-cache-enable-wrap">
                      <input type="checkbox" id="ja-cache-enable" checked />
                      <span>Use cached answers for faster fills</span>
                    </label>
                    <label class="ja-auto-advance" id="ja-auto-advance-wrap">
                      <input type="checkbox" id="ja-auto-advance" />
                      Auto-advance through all steps
                    </label>
                  </div>
                </div>
              </div>
              <div class="ja-footer-links">
                <button type="button" class="ja-footer-link" id="ja-save-job">
                  <span class="ja-footer-link-ico" aria-hidden="true">${QUESTION_UI_ICONS.download}</span>
                  Save Job
                </button>
                <button type="button" class="ja-footer-link" id="ja-referrals">
                  <span class="ja-footer-link-ico" aria-hidden="true">${QUESTION_UI_ICONS.users}</span>
                  Referrals
                </button>
              </div>
              <div class="ja-accordions" id="ja-autofill-accordions"></div>
              <div class="ja-autofill-footer-stats">
                <span class="ja-autofill-footer-item" id="ja-autofill-last-fill"><span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.clock}</span> Last fill: —</span>
                <span class="ja-autofill-footer-item" id="ja-autofill-apps-filled"><span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.layers}</span> — applications filled</span>
              </div>
            </div>
            <div class="ja-quick-save-row" id="ja-quick-save-row" style="display:none;margin-top:10px;">
              <button type="button" class="ja-action ja-save-applied" id="ja-save-applied">Save & Mark Applied</button>
            </div>
          </div>
        </div>
        <div class="ja-panel" id="ja-panel-keywords">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta-keywords" style="display:none">
            <h3>Sign in to view keywords</h3>
            <p>Information is pulled from your OpsBrain profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-keywords-authenticated" id="ja-keywords-authenticated">
          <div class="ja-keywords-view" id="ja-keywords-view">
          <div class="ja-kw-tab">
            <div class="ja-kw-active-resume-row">
              <div class="ja-kw-active-resume-field">
                <label class="ja-kw-label-upper" for="ja-resume-select">Active Resume</label>
                <select class="ja-resume-select ja-kw-resume-select" id="ja-resume-select">
                  <option value="">Loading resumes...</option>
                </select>
              </div>
              <button type="button" class="ja-kw-tailor-btn" id="ja-tailor-resume-btn">${KEYWORD_TAB_ICONS.target}<span>Tailor</span></button>
            </div>
            <div class="ja-keyword-card ja-kw-score-card" id="ja-keyword-card">
              <div id="ja-keyword-analysis">
                <p class="ja-score-text">Loading keyword analysis...</p>
              </div>
            </div>
            <div id="ja-keyword-keywords-list" class="ja-keyword-keywords-list"></div>
            <button type="button" class="ja-kw-update-jd-btn" id="ja-update-jd-btn">${KEYWORD_TAB_ICONS.refreshCw}<span>Update Job Description</span></button>
          </div>
          </div>
          <div class="ja-job-form-panel" id="ja-job-form-panel" style="display:none">
            <h4 style="margin:0 0 10px 0;font-size:14px;">Edit Job Description</h4>
            <p style="font-size:12px;color:#6b7280;margin:0 0 12px 0;">With a job description you can view matching keywords and/or save this job to your tracker!</p>
            <form class="ja-job-form" id="ja-job-form">
              <label>Company</label>
              <input type="text" id="ja-job-company" placeholder="Company name">
              <label>Position Title</label>
              <input type="text" id="ja-job-position" placeholder="Lead Software Development Engineer">
              <label>Location</label>
              <input type="text" id="ja-job-location" placeholder="Bangalore">
              <label>Min. Salary ($)</label>
              <input type="text" id="ja-job-min-salary" placeholder="180">
              <label>Max. Salary ($)</label>
              <input type="text" id="ja-job-max-salary" placeholder="740000000">
              <label>Currency</label>
              <select id="ja-job-currency">
                <option value="USD">US Dollar (USD)</option>
                <option value="EUR">Euro (EUR)</option>
                <option value="GBP">British Pound (GBP)</option>
                <option value="INR">Indian Rupee (INR)</option>
              </select>
              <label>Period</label>
              <select id="ja-job-period">
                <option value="Yearly">Yearly</option>
                <option value="Monthly">Monthly</option>
                <option value="Hourly">Hourly</option>
              </select>
              <label>Job Type</label>
              <select id="ja-job-type">
                <option value="Full-Time">Full-Time</option>
                <option value="Part-Time">Part-Time</option>
                <option value="Contract">Contract</option>
                <option value="Internship">Internship</option>
              </select>
              <label>Application Status</label>
              <select id="ja-job-status">
                <option value="I have not yet applied">I have not yet applied</option>
                <option value="Applied">Applied</option>
                <option value="Interviewing">Interviewing</option>
                <option value="Offer">Offer</option>
                <option value="Rejected">Rejected</option>
                <option value="Withdrawn">Withdrawn</option>
              </select>
              <label>Job Description — Click to edit</label>
              <textarea id="ja-job-description" rows="6" placeholder="Auto-detected description available."></textarea>
              <label>Notes — Click to add</label>
              <textarea id="ja-job-notes" rows="2" placeholder="Add notes..."></textarea>
              <label>Job Posting URL</label>
              <input type="text" id="ja-job-url" placeholder="https://...">
              <div class="ja-job-form-actions">
                <button type="button" class="ja-go-back-btn" id="ja-job-go-back">Go Back</button>
                <button type="submit" class="ja-save-job-btn" id="ja-job-save">Save Job</button>
              </div>
            </form>
          </div>
          </div>
          </div>
        </div>
        <div class="ja-panel" id="ja-panel-profile">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta-profile" style="display:none">
            <h3>Sign in to view profile</h3>
            <p>Information is pulled from your OpsBrain profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-profile-authenticated" id="ja-profile-authenticated">
            <div class="ja-profile-tab">
              <div class="ja-profile-stats">
                <div class="ja-profile-stat">
                  <p class="ja-profile-stat-val" id="ja-profile-stat-apps">—</p>
                  <p class="ja-profile-stat-label">Applications</p>
                </div>
                <div class="ja-profile-stat">
                  <p class="ja-profile-stat-val ja-profile-stat-success" id="ja-profile-stat-interviews">—</p>
                  <p class="ja-profile-stat-label">Interviews</p>
                </div>
                <div class="ja-profile-stat">
                  <p class="ja-profile-stat-val ja-profile-stat-primary" id="ja-profile-stat-fill">—</p>
                  <p class="ja-profile-stat-label">Fill Rate</p>
                </div>
              </div>
              <div class="ja-prof-hero-wrap">
                <div class="ja-prof-hero">
                  <div class="ja-avatar ja-avatar-gradient" id="ja-profile-avatar">—</div>
                  <div class="ja-prof-hero-text">
                    <h3 class="ja-profile-name" id="ja-profile-name">—</h3>
                    <p class="ja-profile-title" id="ja-profile-title"></p>
                    <div class="ja-prof-actions">
                      <button type="button" class="ja-prof-act-btn" id="ja-profile-refresh">${PROFILE_TAB_ICONS.refreshCwSm}<span>Sync</span></button>
                      <button type="button" class="ja-prof-act-btn" id="ja-profile-edit">${PROFILE_TAB_ICONS.editSm}<span>Edit</span></button>
                      <button type="button" class="ja-prof-act-btn" id="ja-profile-preview">${PROFILE_TAB_ICONS.eyeSm}<span>Preview</span></button>
                    </div>
                  </div>
                </div>
                <div class="ja-profile-contact" id="ja-profile-contact"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.graduationCap}<span class="ja-prof-sec-title">Education</span></div>
                <div id="ja-profile-education"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.briefcase}<span class="ja-prof-sec-title">Experience</span></div>
                <div id="ja-profile-experience"></div>
              </div>
              <div class="ja-prof-block" id="ja-profile-cert-block" style="display:none">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.award}<span class="ja-prof-sec-title">Certifications</span></div>
                <div id="ja-profile-certifications"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.upload}<span class="ja-prof-sec-title">Uploads</span></div>
                <div class="ja-prof-upload-inner" id="ja-profile-uploads"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head ja-prof-sec-head-row">
                  <span class="ja-prof-sec-head-left">${PROFILE_TAB_ICONS.code}<span class="ja-prof-sec-title">Technical Skills</span></span>
                  <span class="ja-prof-sec-count" id="ja-profile-tech-count">0 skills</span>
                </div>
                <div id="ja-profile-tech-skills"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.messageSquare}<span class="ja-prof-sec-title">Soft Skills</span></div>
                <div id="ja-profile-soft-skills"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.globe}<span class="ja-prof-sec-title">Languages</span></div>
                <div id="ja-profile-languages"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <button class="ja-mini" id="ja-open">S</button>
  `;
  document.documentElement.appendChild(root);

  updateWidgetAuthUI(root);
  if (isCareerPage()) trackCareerPageView();
  updateSavedTimeDisplay(root);

  // Render autofill accordions (Resume, Cover Letter, Unique Questions, Common Questions)
  const accordionsContainer = root.querySelector("#ja-autofill-accordions");
  if (accordionsContainer) {
    renderAccordions(accordionsContainer, [
      { id: "resume", iconBg: "#e9d5ff", iconSvg: ACCORDION_ICONS.document, title: "Resume", showHelpIcon: true },
      { id: "cover-letter", iconBg: "#fed7aa", iconSvg: ACCORDION_ICONS.coverLetter, title: "Cover Letter", statusText: "No Field Found" },
      { id: "unique-questions", iconBg: "#ede9fe", iconColor: "#7c3aed", iconSvg: ACCORDION_ICONS.star, title: "Unique Questions", statusText: "0/0", statusCheckmark: true },
      { id: "common-questions", iconBg: "#d1fae5", iconColor: "#15803d", iconSvg: ACCORDION_ICONS.person, title: "Common Questions", statusText: "0/0", statusCheckmark: true },
    ], root);
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes.accessToken) {
      updateWidgetAuthUI(root);
    }
  });

  // Re-check auth when user switches back to this tab (e.g. after logging in on HireMate)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      updateWidgetAuthUI(root);
    }
  });

  const autoAdvanceWrap = root.querySelector("#ja-auto-advance-wrap");
  if (autoAdvanceWrap) {
    const isWorkday = /workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(window.location.href);
    autoAdvanceWrap.style.display = isWorkday ? "flex" : "none";
    const autoAdvanceCheck = autoAdvanceWrap?.querySelector('input[type="checkbox"]');
    if (isWorkday && autoAdvanceCheck) autoAdvanceCheck.checked = true;
  }

  const CACHE_ENABLED_KEY = "hm_cache_enabled";
  const cacheEnableWrap = root.querySelector("#ja-cache-enable-wrap");
  const cacheEnableCheck = root.querySelector("#ja-cache-enable");
  if (cacheEnableWrap && cacheEnableCheck) {
    chrome.storage.local.get([CACHE_ENABLED_KEY]).then((stored) => {
      const enabled = stored[CACHE_ENABLED_KEY] !== false;
      cacheEnableCheck.checked = enabled;
    });
    cacheEnableCheck.addEventListener("change", () => {
      chrome.storage.local.set({ [CACHE_ENABLED_KEY]: cacheEnableCheck.checked });
    });
  }

  const statusEl = root.querySelector("#ja-status");
  const statusArea = root.querySelector("#ja-status-area");
  const progressBar = root.querySelector("#ja-progress");
  const runBtn = root.querySelector("#ja-run");
  const stopBtn = root.querySelector("#ja-stop");
  const skipNextBtn = root.querySelector("#ja-skip-next");
  const fillControls = root.querySelector("#ja-fill-controls");
  const continueBtn = root.querySelector("#ja-continue-fill");
  const closeBtn = root.querySelector("#ja-close");
  const openBtn = root.querySelector("#ja-open");
  const dragHandle = root.querySelector("#ja-drag-handle");

  // Tab switching
  root.querySelectorAll(".ja-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      root.querySelectorAll(".ja-tab").forEach((t) => t.classList.remove("active"));
      root.querySelectorAll(".ja-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      const panel = root.querySelector("#ja-panel-" + tab.dataset.tab);
      if (panel) panel.classList.add("active");
      if (tab.dataset.tab === "profile") loadProfileIntoPanel(root);
      if (tab.dataset.tab === "keywords") loadKeywordsIntoPanel(root);
    });
  });

  root.querySelector("#ja-profile-refresh")?.addEventListener("click", () => loadProfileIntoPanel(root));
  root.querySelector("#ja-profile-edit")?.addEventListener("click", async () => {
    const data = await chrome.storage.local.get(["loginPageUrl"]);
    const base = data.loginPageUrl ? new URL(data.loginPageUrl).origin : "http://localhost:5173";
    chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url: `${base}/profile` });
  });
  root.querySelector("#ja-profile-preview")?.addEventListener("click", async () => {
    const ctx = root._profileCtx;
    if (!ctx) return;
    try {
      const got = await fetchProfileResumeBlob(ctx);
      if (!got) return;
      const url = URL.createObjectURL(got.blob);
      window.open(url, "_blank");
    } catch (_) { }
  });
  root.addEventListener("click", (e) => {
    const btn = e.target.closest(".ja-prof-copy");
    if (!btn || !root.contains(btn)) return;
    e.preventDefault();
    e.stopPropagation();
    const text = btn.getAttribute("data-copy") || "";
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      btn.classList.add("ja-prof-copy--done");
      setTimeout(() => btn.classList.remove("ja-prof-copy--done"), 1500);
    }).catch(() => { });
  });

  // Resume select change -> re-run keyword analysis
  root.addEventListener("change", (e) => {
    if (e.target.id === "ja-resume-select") loadKeywordsIntoPanel(root);
  });

  // Tailor Resume -> open /resume-generator
  root.querySelector("#ja-tailor-resume-btn")?.addEventListener("click", () => openResumeGeneratorUrl());

  // Update Job Description -> show form panel
  root.querySelector("#ja-update-jd-btn")?.addEventListener("click", async () => {
    const view = root.querySelector("#ja-keywords-view");
    const formPanel = root.querySelector("#ja-job-form-panel");
    if (view && formPanel) {
      view.style.display = "none";
      formPanel.style.display = "block";
      await prefillJobForm(root);
    }
  });

  // Go Back from job form
  root.querySelector("#ja-job-go-back")?.addEventListener("click", () => {
    const view = root.querySelector("#ja-keywords-view");
    const formPanel = root.querySelector("#ja-job-form-panel");
    if (view && formPanel) {
      formPanel.style.display = "none";
      view.style.display = "block";
    }
  });

  // Save Job form submit
  root.querySelector("#ja-job-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    await saveJobFromForm(root);
  });

  const setStatus = (text, type = "", asHtml = false) => {
    if (!statusEl) return;
    if (asHtml) statusEl.innerHTML = text;
    else statusEl.textContent = text;
    statusEl.className = `ja-status ja-autofill-hero-sub ${type}`.trim();
    statusArea?.classList.toggle("loading", type === "loading");
  };

  const setProgress = (percent) => {
    const p = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    if (progressBar) progressBar.style.width = `${p}%`;
    const pctEl = root.querySelector("#ja-progress-text");
    if (pctEl) pctEl.textContent = `${p}%`;
  };

  // Dragging (vertical only, stays on right side)
  let isDragging = false;
  let dragStartY = 0;
  let initialTop = 80;
  let didDrag = false;

  const startDrag = (e) => {
    if (e.target.closest('button') && !e.target.closest('#ja-open')) return;
    isDragging = true;
    didDrag = false;
    dragStartY = e.clientY;
    initialTop = parseInt(root.style.top) || 80;
  };

  dragHandle?.addEventListener("mousedown", startDrag);
  openBtn?.addEventListener("mousedown", startDrag);

  document.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    e.preventDefault();
    didDrag = true;
    const deltaY = e.clientY - dragStartY;
    let newTop = initialTop + deltaY;
    const minH = root.classList.contains("collapsed") ? 48 : root.offsetHeight;
    const maxY = window.innerHeight - minH - 20;
    newTop = Math.max(20, Math.min(newTop, maxY));
    root.style.top = newTop + "px";
    root.style.right = "20px";
    root.style.left = "auto";
  });

  document.addEventListener("mouseup", () => {
    if (isDragging) {
      initialTop = parseInt(root.style.top) || 80;
    }
    isDragging = false;
  });

  closeBtn?.addEventListener("click", () => root.classList.add("collapsed"));
  openBtn?.addEventListener("click", (e) => {
    if (didDrag) return;
    root.classList.remove("collapsed");
  });

  let abortRequested = false;
  let skipToNextRequested = false;

  const runOneStep = async (stepNum = 1) => {
    const t0 = Date.now();
    logInfo("runOneStep: start", { stepNum });
    setStatus(stepNum > 1 ? `Step ${stepNum} — Extracting fields...` : "Extracting form fields...", "loading");
    setProgress(5);
    setStatus("Loading profile...", "loading");
    try {
      logInfo("runOneStep: refreshTokenViaApi");
      await refreshTokenViaApi();
      logInfo("runOneStep: refreshToken done", { ms: Date.now() - t0 });
    } catch (_) { }
    logInfo("runOneStep: getAutofillContextFromApi");
    const context = await getAutofillContextFromApi();
    logInfo("runOneStep: context loaded", { profileKeys: Object.keys(context?.profile || {}).length, ms: Date.now() - t0 });
    const experiences = context?.profile?.experiences || [];
    const educations = context?.profile?.educations || [];
    const preExpandEmployment = Math.max(0, experiences.length - 1);
    const preExpandEducation = Math.max(0, educations.length - 1);
    let fields = [];
    for (let attempt = 0; attempt < 3; attempt++) {
      if (attempt > 0) {
        setStatus(`Waiting for form to load... (attempt ${attempt + 1}/3)`, "loading");
        await new Promise((r) => setTimeout(r, 1500 + attempt * 1000));
      }
      logInfo("runOneStep: sending SCRAPE_ALL_FRAMES", { attempt: attempt + 1 });
      const scrapeRes = await chrome.runtime.sendMessage({
        type: "SCRAPE_ALL_FRAMES",
        scope: "all",
        preExpandEmployment,
        preExpandEducation,
        maxEducationBlocks: educations.length || 999,
        maxEmploymentBlocks: experiences.length || 999,
      });
      logInfo("runOneStep: SCRAPE_ALL_FRAMES response", { ok: scrapeRes?.ok, fieldCount: scrapeRes?.fields?.length ?? 0 });
      if (scrapeRes?.ok && scrapeRes.fields?.length) {
        fields = scrapeRes.fields;
        break;
      }
    }
    if (!fields.length) throw new Error("No form fields found. Click \"Apply\" on a job to open the application form, then try again.");

    setStatus(`Found ${fields.length} fields — loading profile & resume...`, "loading");
    setProgress(15);
    let resumeData = await getResumeFromBackground();
    if (!resumeData && (context.resumeUrl || context.resumeFileName)) {
      resumeData = await fetchResumeFromContext(context);
    }
    if (!resumeData) resumeData = await getStaticResume();
    if (resumeData && context?.resumeName) {
      const displayName = sanitizeResumeFilename(context.resumeName);
      if (displayName) resumeData = { ...resumeData, name: displayName };
    }

    setStatus("Mapping fields with AI...", "loading");
    setProgress(35);
    const domain = location.hostname;
    const fps = fields.map((f) => f.fingerprint).filter(Boolean);
    const useCache = root.querySelector("#ja-cache-enable")?.checked !== false;
    let cachedByFp = {};
    if (useCache) {
      try {
        const res = await chrome.runtime.sendMessage({ type: "GET_CACHED_MAPPINGS_BY_FP", payload: { fps, domain } });
        if (res?.ok && res.data) cachedByFp = res.data;
      } catch (_) { }
    }
    const missFields = fields.filter((f) => !cachedByFp[f.fingerprint]);
    let mappings = {};
    for (const f of fields) {
      const m = cachedByFp[f.fingerprint];
      if (m) {
        mappings[f.fingerprint] = m;
        mappings[String(f.index)] = m;
      }
    }
    if (missFields.length > 0) {
      const apiMappings = await fetchMappingsFromApi(missFields, context);
      Object.assign(mappings, apiMappings);
      if (useCache) {
        const toCache = {};
        for (const f of missFields) {
          const m = apiMappings[f.fingerprint] ?? apiMappings[String(f.index)];
          if (m && m.value !== undefined) toCache[f.fingerprint] = m;
        }
        if (Object.keys(toCache).length > 0) {
          chrome.runtime.sendMessage({ type: "SET_CACHED_MAPPINGS_BY_FP", payload: { mappingsByFp: toCache, domain } }).catch(() => { });
        }
      }
    }
    if (!Object.keys(mappings).length) throw new Error("No mapping returned");

    setStatus("Preparing to fill...", "loading");
    setProgress(50);

    const maxEdu = educations.length > 0 ? educations.length : 999;
    const maxEmp = experiences.length > 0 ? experiences.length : 999;
    const valuesByFrame = buildValuesByFrameWithLimits(fields, mappings, maxEdu, maxEmp);
    const fieldsByFrame = buildFieldsByFrame(fields);
    const lastFill = { fields, mappings };

    const fillRes = await chrome.runtime.sendMessage({
      type: "FILL_ALL_FRAMES",
      payload: { valuesByFrame, fieldsByFrame, resumeData, lastFill },
    });

    if (!fillRes?.ok) throw new Error(fillRes?.error || "Fill failed");
    return { filledCount: fillRes.totalFilled || 0, resumeUploadCount: fillRes.totalResumes || 0, failedCount: 0, failedFields: [] };
  };

  const doContinueAndAdvance = async () => {
    const docs = getDocuments(true);
    let btn = null;
    for (const doc of docs) {
      btn = findContinueButton(doc);
      if (btn) break;
    }
    if (btn) {
      // Capture user-filled values before advancing (Workday multi-step: store for learning)
      await captureAndStoreCurrentStepFeedback();
      btn.click();
      await delay(3500);
      return true;
    }
    return false;
  };

  const scrollToField = (field) => {
    if (!field?.isConnected) return;
    scrollFieldIntoView(field);
    try {
      field.focus();
    } catch (_) { }
  };

  const runFlow = async (isContinueFromErrors = false) => {
    if (!runBtn) return;
    const SESSION_ID = crypto.randomUUID();
    window.__OPSBRAIN_SESSION_ID__ = SESSION_ID;
    runBtn.disabled = true;
    runBtn.style.display = "none";
    fillControls?.classList.add("visible");
    continueBtn?.style.setProperty("display", "none");
    abortRequested = false;
    skipToNextRequested = false;
    const saveAppliedBtn = root.querySelector("#ja-save-applied");
    if (saveAppliedBtn) {
      saveAppliedBtn.textContent = "Save & Mark Applied";
      saveAppliedBtn.disabled = false;
    }

    trackAutofillUsed();

    const scraper = window.__OPSBRAIN_SCRAPER__ || window.__HIREMATE_FIELD_SCRAPER__;
    const platform = scraper?.detectPlatform?.(document) || "unknown";
    const isWorkday = platform === "workday";

    // Workday: use step manager (multi-step SPA wizard)
    if (isWorkday) {
      const stepManager = window.__OPSBRAIN_WORKDAY_STEPS__;
      if (!stepManager) {
        setStatus("Workday step manager not loaded. Reload the page.", "error");
        runBtn.disabled = false;
        runBtn.style.display = "";
        fillControls?.classList.remove("visible");
        return;
      }
      try {
        setStatus("Loading profile & resume for Workday...", "loading");
        setProgress(15);
        await refreshTokenViaApi();
        const context = await getAutofillContextFromApi();
        let resumeData = await getResumeFromBackground();
        if (!resumeData && (context.resumeUrl || context.resumeFileName)) {
          resumeData = await fetchResumeFromContext(context);
        }
        if (!resumeData) resumeData = await getStaticResume();
        if (resumeData && context?.resumeName) {
          const displayName = sanitizeResumeFilename(context.resumeName);
          if (displayName) resumeData = { ...resumeData, name: displayName };
        }
        const profileValues = buildProfileValuesForWorkday(context);
        const autoContinue = root.querySelector("#ja-auto-advance")?.checked ?? false;
        setStatus("Starting Workday autofill...", "loading");
        setProgress(50);
        const profileData = {
          values: profileValues,
          resumeData,
          autoContinue,
          context: { profile: context.profile, customAnswers: context.customAnswers || {}, resumeText: context.resumeText || "" },
        };
        await chrome.runtime.sendMessage({
          type: "START_WORKDAY_AUTOFILL",
          payload: { profileData },
        });
        setProgress(100);
        setStatus("Workday autofill started. Fill steps as they appear.", "success");
      } catch (err) {
        setProgress(0);
        setStatus(err?.message || "Workday autofill failed", "error");
        logWarn("Workday autofill failed", { error: String(err) });
      } finally {
        runBtn.disabled = false;
        runBtn.style.display = "";
        fillControls?.classList.remove("visible");
      }
      return;
    }

    const autoAdvance = root.querySelector("#ja-auto-advance")?.checked;
    const maxSteps = 8;
    let totalFilled = 0;
    let totalResumes = 0;
    let totalFailed = 0;
    let lastFailedFields = [];

    try {
      for (let step = 1; step <= maxSteps; step++) {
        if (abortRequested) {
          setStatus("Stopped", "success");
          break;
        }
        const result = await runOneStep(step);
        totalFilled += result.filledCount;
        totalResumes += result.resumeUploadCount;
        totalFailed += result.failedCount;
        lastFailedFields = result.failedFields || [];

        setProgress(100);
        const bullets = [];
        if (totalFilled > 0) bullets.push(`✓ Filled ${totalFilled} field${totalFilled === 1 ? "" : "s"}`);
        if (totalResumes > 0) bullets.push(`✓ Uploaded resume`);
        if (totalFailed > 0) {
          if (lastFailedFields.length > 0) {
            const fieldItems = lastFailedFields.map((ff, idx) => {
              const label = String(ff.label || `Field ${idx + 1}`).replace(/</g, "&lt;").replace(/>/g, "&gt;");
              return `<li class="ja-failed-field-item"><button type="button" class="ja-failed-field-link" data-failed-index="${idx}">⚠ ${label}</button></li>`;
            }).join("");
            bullets.push(`<span class="ja-fields-need-attention">Fields need attention:</span><ul class="ja-failed-fields-list">${fieldItems}</ul>`);
          } else {
            bullets.push(`⚠ ${totalFailed} field${totalFailed === 1 ? "" : "s"} need attention`);
          }
        }
        const statusHtml = bullets.length > 0 ? `<ul class="ja-status-bullets">${bullets.map((b) => `<li>${b}</li>`).join("")}</ul>` : "Done";
        setStatus(statusHtml, "success", true);

        const quickSaveRow = root.querySelector("#ja-quick-save-row");
        if (quickSaveRow) quickSaveRow.style.display = totalFilled > 0 ? "block" : "none";

        if (lastFailedFields.length > 0) {
          root.querySelectorAll(".ja-failed-field-link").forEach((btn, idx) => {
            btn.onclick = () => {
              const ff = lastFailedFields[idx];
              if (ff?.element?.isConnected) scrollToField(ff.element);
            };
          });
        }

        if (!autoAdvance || !isWorkday || step >= maxSteps) break;

        const hasUnfilledFields = result.failedCount > 0;

        if (hasUnfilledFields) {
          bullets.push('<span class="ja-note">Fix the highlighted fields, then click Continue filling</span>');
          setStatus(`<ul class="ja-status-bullets">${bullets.map((b) => `<li>${b}</li>`).join("")}</ul>`, "success", true);
          if (lastFailedFields.length > 0) {
            root.querySelectorAll(".ja-failed-field-link").forEach((btn, idx) => {
              btn.onclick = () => {
                const ff = lastFailedFields[idx];
                if (ff?.element?.isConnected) scrollToField(ff.element);
              };
            });
          }
          continueBtn?.style.setProperty("display", "block");
          break;
        }

        const advanced = await doContinueAndAdvance();
        if (!advanced) break;

        setStatus(`Step ${step} done — advancing to next...`, "loading");
      }
    } catch (err) {
      setProgress(0);
      setStatus(err?.message || "Autofill failed", "error");
      logWarn("In-page autofill failed", { error: String(err) });
    } finally {
      runBtn.disabled = false;
      runBtn.style.display = "";
      fillControls?.classList.remove("visible");
      const qsr = root.querySelector("#ja-quick-save-row");
      if (qsr) qsr.style.display = "none";
    }
  };

  async function quickSaveAsApplied() {
    const btn = root.querySelector("#ja-save-applied");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Saving...";
    }
    setStatus("Saving to tracker...", "loading");
    try {
      const apiBase = await getApiBase();
      const headers = await getAuthHeaders();
      const { company, position, location } = extractCompanyAndPosition();
      const payload = {
        company: company || "",
        position_title: position || "",
        location: location || "",
        job_posting_url: window.location.href || null,
        application_status: "applied",
      };
      const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setStatus("Saved to tracker.", "success");
        if (btn) btn.textContent = "Saved!";
      } else {
        setStatus("Save failed. Try Save Job Instead.", "error");
        if (btn) {
          btn.disabled = false;
          btn.textContent = "Save & Mark Applied";
        }
      }
    } catch (err) {
      logWarn("Quick save as applied failed", { error: String(err) });
      setStatus("Save failed. Try Save Job Instead.", "error");
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Save & Mark Applied";
      }
    }
  }

  root.querySelector("#ja-save-applied")?.addEventListener("click", quickSaveAsApplied);

  root.querySelector("#ja-save-job-instead")?.addEventListener("click", async () => {
    root.querySelectorAll(".ja-tab").forEach((t) => t.classList.remove("active"));
    root.querySelectorAll(".ja-panel").forEach((p) => p.classList.remove("active"));
    const kwTab = root.querySelector('[data-tab="keywords"]');
    const kwPanel = root.querySelector("#ja-panel-keywords");
    if (kwTab) kwTab.classList.add("active");
    if (kwPanel) kwPanel.classList.add("active");
    loadKeywordsIntoPanel(root);
    const view = root.querySelector("#ja-keywords-view");
    const formPanel = root.querySelector("#ja-job-form-panel");
    if (view && formPanel) {
      view.style.display = "none";
      formPanel.style.display = "block";
      await prefillJobForm(root);
      const statusSelect = root.querySelector("#ja-job-status");
      if (statusSelect) statusSelect.value = "I have not yet applied";
    }
  });

  runBtn?.addEventListener("click", () => runFlow(false));

  stopBtn?.addEventListener("click", () => {
    abortRequested = true;
    chrome.runtime.sendMessage({ type: "STOP_WORKDAY_AUTOFILL" }).catch(() => { });
    window.__OPSBRAIN_WORKDAY_STEPS__?.stopWatching();
  });

  skipNextBtn?.addEventListener("click", () => {
    skipToNextRequested = true;
  });

  continueBtn?.addEventListener("click", async () => {
    continueBtn.style.display = "none";
    setStatus("Advancing to next step...", "loading");
    const advanced = await doContinueAndAdvance();
    if (advanced) {
      runFlow(false);
    } else {
      setStatus("Continue button not found. Click it manually.", "error");
    }
  });
}

// Sync token from website when user logs in on HireMate frontend.
// Content scripts share the page's origin and can read localStorage directly—no inline script injection (avoids CSP violations).
function syncTokenFromWebsite() {
  if (!LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o)) return;
  try {
    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    if (token) {
      chrome.storage.local.set({ accessToken: token });
      logInfo("Token synced from website");
    }
  } catch (e) { }
}
if (LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o)) {
  syncTokenFromWebsite();
  setTimeout(syncTokenFromWebsite, 2000);
  setTimeout(syncTokenFromWebsite, 5000);
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  logInfo("Received message", { type: msg?.type || "unknown" });

  if (msg.type === "SHOW_WIDGET") {
    mountInPageUI();
    if (isCareerPage() && !/workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(window.location.href)) {
      runKeywordAnalysisAndMaybeShowWidget();
    }
    const widget = document.getElementById(INPAGE_ROOT_ID);
    if (widget) {
      const card = widget.querySelector(".ja-card");
      if (card) card.classList.remove("collapsed");
    }
    sendResponse({ ok: true });
    return true;
  }

  if (msg.type === "STOP_WORKDAY_AUTOFILL") {
    window.__OPSBRAIN_WORKDAY_STEPS__?.stopWatching();
    sendResponse({ ok: true });
    return true;
  }

  if (msg.type === "START_WORKDAY_AUTOFILL") {
    const profileData = msg.payload?.profileData;
    if (!profileData) {
      sendResponse({ ok: false, error: "Missing profileData" });
      return true;
    }
    const url = (typeof location !== "undefined" && location?.href) || "";
    const isWorkdayFrame = /workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(url);
    // Only run in the frame that has the form — avoids duplicate runs across iframes that trigger definition API bursts
    const hasForm = document.body && (
      document.querySelector('[id*="primaryQuestionnaire"]') ||
      document.querySelector('[data-automation-id*="formField"]') ||
      document.querySelector('[data-automation-id*="textInput"]')
    );
    const stepManager = window.__OPSBRAIN_WORKDAY_STEPS__;
    if (stepManager && isWorkdayFrame && hasForm) {
      stepManager.startWorkdayAutofill(profileData).then(() => sendResponse({ ok: true })).catch((e) => sendResponse({ ok: false, error: String(e) }));
    } else {
      sendResponse({ ok: true });
    }
    return true;
  }

  if (msg.type === "SCRAPE_FIELDS") {
    const payload = msg.payload || {};
    const tScrape = Date.now();
    logInfo("SCRAPE_FIELDS received", { scope: payload.scope, frameId: typeof window !== "undefined" ? "(content)" : "?", url: location?.href?.slice(0, 60) });
    scrapeFields(payload)
      .then((result) => {
        logInfo("SCRAPE_FIELDS done", { fieldCount: result?.fields?.length || 0, ms: Date.now() - tScrape });
        sendResponse({ ok: true, ...result });
      })
      .catch((e) => {
        logWarn("SCRAPE_FIELDS failed", { error: String(e), ms: Date.now() - tScrape });
        sendResponse({ ok: false, error: String(e) });
      });
    return true;
  }

  if (msg.type === "FILL_WITH_VALUES") {
    const p = msg.payload || {};
    if (p.lastFill) {
      window.__OPSBRAIN_LAST_FILL__ = p.lastFill;
    }
    logInfo("Fill: received FILL_WITH_VALUES", {
      valueCount: Object.keys(p.values || {}).length,
      hasResume: !!p.resumeData,
      scope: p.scope,
    });
    const FILL_TIMEOUT_MS = 90000; // 90s max - prevents indefinite hang
    const startFill = Date.now();
    const payloadWithAbort = {
      ...p,
      shouldAbort: p.shouldAbort
        ? () => p.shouldAbort() || Date.now() - startFill > FILL_TIMEOUT_MS - 5000
        : () => Date.now() - startFill > FILL_TIMEOUT_MS - 5000,
    };
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Fill timed out after 90s — try fewer fields or refresh")), FILL_TIMEOUT_MS)
    );
    Promise.race([fillWithValues(payloadWithAbort), timeoutPromise])
      .then((result) => {
        if (result?.filledCount > 0) recordAutofillFieldsFilled(result.filledCount);
        sendResponse({ ok: true, ...result });
      })
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (msg.type === "FILL_FORM") {
    fillFormRuleBased(msg.payload || {})
      .then((result) => {
        if (result?.filledCount > 0) recordAutofillFieldsFilled(result.filledCount);
        sendResponse({ ok: true, ...result });
      })
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  return false;
});

// Workday step updates from step manager (can come from iframe via postMessage)
window.addEventListener("message", (e) => {
  if (e?.data?.type !== "OPSBRAIN_WORKDAY_STEP") return;
  const root = document.getElementById(INPAGE_ROOT_ID);
  if (!root) return;
  // Keep Autofill tab active during Workday autofill — prevent switching to Keywords/Profile
  const autofillTab = root.querySelector('[data-tab="autofill"]');
  const autofillPanel = root.querySelector("#ja-panel-autofill");
  if (autofillTab && autofillPanel && !autofillTab.classList.contains("active")) {
    root.querySelectorAll(".ja-tab").forEach((t) => t.classList.remove("active"));
    root.querySelectorAll(".ja-panel").forEach((p) => p.classList.remove("active"));
    autofillTab.classList.add("active");
    autofillPanel.classList.add("active");
  }
  const statusEl = root.querySelector("#ja-status");
  const statusArea = root.querySelector("#ja-status-area");
  if (!statusEl) return;
  const { stepName, phase, fieldCount, filledCount, error } = e.data;
  let text = stepName || "Workday";
  if (phase === "starting") text = `Step: ${text} — starting...`;
  else if (phase === "filling") text = `Step: ${text} — filling ${fieldCount || 0} fields`;
  else if (phase === "filled") text = `✓ ${text} — filled ${filledCount ?? "✓"}`;
  else if (phase === "review") text = `Step: ${text} — review & submit manually`;
  else if (phase === "retry") text = `Retrying: ${text}`;
  else if (phase === "error") text = `⚠ ${text}${error ? `: ${error}` : ""}`;
  statusEl.textContent = text;
  statusEl.className = `ja-status ja-autofill-hero-sub ${phase === "error" ? "error" : phase === "filled" || phase === "review" ? "success" : "loading"}`.trim();
  statusArea?.classList.toggle("loading", phase === "starting" || phase === "filling" || phase === "retry");
});

// Test hook: when page dispatches 'scraper-test-request', run scrape and respond
document.addEventListener("scraper-test-request", async () => {
  try {
    const { fields } = await scrapeFields({ scope: "all" });
    const elements = getFillableFields(true, true);
    document.dispatchEvent(new CustomEvent("scraper-test-response", {
      detail: { ok: true, fields, elementCount: elements.length },
    }));
  } catch (e) {
    document.dispatchEvent(new CustomEvent("scraper-test-response", {
      detail: { ok: false, error: String(e) },
    }));
  }
});

function looksLikeJobApplicationForm() {
  const fillable = getFillableFields(false);
  if (fillable.length < 2) return false;
  const jobKeywords = ["name", "email", "resume", "cv", "phone", "apply", "linkedin", "experience"];
  let matchCount = 0;
  let hasResumeField = false;
  for (const el of fillable) {
    const meta = getFieldMeta(el);
    const text = getFieldKeys(meta).join(" ").toLowerCase();
    if ((el.type || "").toLowerCase() === "file" && (text.includes("resume") || text.includes("cv"))) {
      hasResumeField = true;
    }
    if (jobKeywords.some((kw) => text.includes(kw))) matchCount++;
  }
  return hasResumeField || matchCount >= 2;
}

function isJobFormPage() {
  const hasApplicationForm = looksLikeJobApplicationForm();
  const bodyText = (document.body?.innerText || document.body?.textContent || "").trim();
  const hasSubstantialContent = bodyText.length >= 400;

  if (hasApplicationForm) return true;

  if (isJobListingPage()) return false;

  return isJobDetailPage() && hasSubstantialContent;
}

function isIntermediateStep() {
  const bodyText = (document.body?.innerText || "").toLowerCase();
  const confirmSignals = [
    "application submitted",
    "thank you for applying",
    "application received",
    "successfully submitted",
    "we have received your application",
    "application complete",
  ];
  if (confirmSignals.some((s) => bodyText.includes(s))) return false;
  const nextButtonExists = !!document.querySelector(
    'button[type="submit"][data-automation-id*="next"], ' +
    '[data-automation-id="continueButton"], [data-automation-id*="continue"], ' +
    'button[aria-label*="Next"], button[aria-label*="Continue"], ' +
    ".next-button, #nextButton, [data-testid='next-btn']"
  );
  const hasStepIndicator = !!document.querySelector(
    ".progress-steps, .step-indicator, [aria-label*='Step '], " +
    ".wday-wizard-step, [data-automation-id*='progress'], [data-automation-id*='wizard']"
  );
  const isWorkdayUrl = /workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(location.href);
  if (isWorkdayUrl && (nextButtonExists || hasStepIndicator)) return true;
  return nextButtonExists || hasStepIndicator;
}

function mergePendingFields(existing, incoming) {
  const map = {};
  [...(existing || []), ...(incoming || [])].forEach((f) => {
    if (f.fingerprint) map[f.fingerprint] = f;
  });
  return Object.values(map);
}

const PENDING_TTL_MS = 4 * 60 * 60 * 1000; // 4 hours — treat as new session if older

/** Capture current form values before advancing to next Workday step. Stores for submit-feedback on final submit. */
async function captureAndStoreCurrentStepFeedback() {
  const lastFill = window.__OPSBRAIN_LAST_FILL__;
  if (!lastFill?.fields?.length || !lastFill?.mappings) return;
  const currentSessionId = window.__OPSBRAIN_SESSION_ID__;
  const docs = getDocuments(true);
  for (const doc of docs) {
    let overlappingCount = 0;
    for (const f of lastFill.fields) {
      try {
        const sel = f.selector || (f.selectors?.[0]?.selector);
        if (sel && doc.querySelector(sel)) overlappingCount++;
      } catch (_) { }
    }
    if (overlappingCount < 2) continue;
    const currentPageFields = lastFill.fields.map((f) => {
      let el = null;
      try {
        const sel = f.selector || (f.selectors?.[0]?.selector);
        if (sel) el = doc.querySelector(sel);
      } catch (_) { }
      const domValue = el ? (el.value ?? el.textContent ?? "").trim() : null;
      const autofillVal = lastFill.mappings[f.fingerprint]?.value ?? lastFill.mappings[String(f.index)]?.value;
      return {
        fingerprint: f.fingerprint,
        label: f.label,
        type: f.type,
        options: f.options || [],
        ats_platform: window.__OPSBRAIN_ATS__ || window.__PAGE_DETECTOR__?.platform || "workday",
        selector_used: f.selector || (f.selectors?.[0]?.selector),
        selector_type: (f.selectors?.[0]?.type) || "id",
        autofill_value: autofillVal,
        submitted_value: domValue,
        was_edited: domValue != null && domValue !== autofillVal,
      };
    });
    const cacheManager = window.__CACHE_MANAGER__;
    const pending = cacheManager ? await cacheManager.getPendingSubmission().catch(() => null) : null;
    const sessionMatch = currentSessionId && pending?.sessionId === currentSessionId;
    const ttlOk = !pending?.timestamp || (Date.now() - pending.timestamp) < PENDING_TTL_MS;
    const existingFields = sessionMatch && ttlOk ? (pending?.fields || []) : [];
    const allFields = mergePendingFields(existingFields, currentPageFields);
    if (cacheManager) await cacheManager.setPendingSubmission({ url: location.href, fields: allFields, sessionId: currentSessionId, timestamp: Date.now() });
    logInfo("Workday step — stored", allFields.length, "fields before advance");
    return;
  }
}

let _submitFeedbackAttached = false;
function attachSubmitFeedbackListener() {
  if (_submitFeedbackAttached) return;
  _submitFeedbackAttached = true;
  document.addEventListener("submit", handleFormSubmitForFeedback, true);
  // Workday: capture on Continue/Next click (user may have filled manually)
  document.addEventListener("click", (e) => {
    if (!/workday\.com|myworkdayjobs\.com/i.test(location.href)) return;
    const btn = e.target?.closest?.("button, [role='button'], input[type='submit']") || e.target;
    if (!btn) return;
    const text = (btn.textContent || btn.innerText || btn.value || "").trim().toLowerCase();
    const aid = (btn.getAttribute?.("data-automation-id") || "").toLowerCase();
    if (text.includes("continue") || text.includes("next") || aid.includes("continue") || aid.includes("next")) {
      captureAndStoreCurrentStepFeedback();
    }
  }, true);
}

async function handleFormSubmitForFeedback(e) {
  const lastFill = window.__OPSBRAIN_LAST_FILL__;
  if (!lastFill?.fields?.length || !lastFill?.mappings) return;
  await new Promise((r) => setTimeout(r, 0));
  let overlappingCount = 0;
  for (const f of lastFill.fields) {
    try {
      const sel = f.selector || (f.selectors?.[0]?.selector);
      if (sel && document.querySelector(sel)) overlappingCount++;
    } catch (_) { }
  }
  if (overlappingCount < 2) return;
  const currentPageFields = lastFill.fields.map((f) => {
    let el = null;
    try {
      const sel = f.selector || (f.selectors?.[0]?.selector);
      if (sel) el = document.querySelector(sel);
    } catch (_) { }
    const domValue = el ? (el.value ?? el.textContent ?? "").trim() : null;
    const autofillVal = lastFill.mappings[f.fingerprint]?.value ?? lastFill.mappings[String(f.index)]?.value;
    return {
      fingerprint: f.fingerprint,
      label: f.label,
      type: f.type,
      options: f.options || [],
      ats_platform: window.__OPSBRAIN_ATS__ || window.__PAGE_DETECTOR__?.platform || "unknown",
      selector_used: f.selector || (f.selectors?.[0]?.selector),
      selector_type: (f.selectors?.[0]?.type) || "id",
      autofill_value: autofillVal,
      submitted_value: domValue,
      was_edited: domValue != null && domValue !== autofillVal,
    };
  });
  const cacheManager = window.__CACHE_MANAGER__;
  const pending = cacheManager ? await cacheManager.getPendingSubmission().catch(() => null) : null;
  const currentSessionId = window.__OPSBRAIN_SESSION_ID__;
  const sessionMatch = currentSessionId && pending?.sessionId === currentSessionId;
  const ttlOk = !pending?.timestamp || (Date.now() - pending.timestamp) < PENDING_TTL_MS;
  const existingFields = sessionMatch && ttlOk ? (pending?.fields || []) : [];
  const allFields = mergePendingFields(existingFields, currentPageFields);

  if (isIntermediateStep()) {
    if (cacheManager) await cacheManager.setPendingSubmission({ url: location.href, fields: allFields, sessionId: currentSessionId || undefined, timestamp: Date.now() });
    logInfo("Intermediate step — accumulated", allFields.length, "fields");
    return;
  }

  logInfo("Final submit — sending", allFields.length, "fields");
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    if (!headers?.Authorization) return;
    const payload = {
      url: location.href,
      domain: location.hostname,
      ats: window.__OPSBRAIN_ATS__ || window.__PAGE_DETECTOR__?.platform || "unknown",
      fields: allFields,
    };
    const token = headers.Authorization?.replace("Bearer ", "");
    const url = token ? `${apiBase}/chrome-extension/form-fields/submit-feedback?token=${encodeURIComponent(token)}` : `${apiBase}/chrome-extension/form-fields/submit-feedback`;
    const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
    let ok = false;
    if (navigator.sendBeacon && navigator.sendBeacon(url, blob)) {
      logInfo("Submit feedback sent via sendBeacon");
      ok = true;
    } else {
      const res = await fetch(`${apiBase}/chrome-extension/form-fields/submit-feedback`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true,
      });
      ok = res.ok;
    }
    if (cacheManager) await cacheManager.clearPendingSubmission();
    window.__OPSBRAIN_SESSION_ID__ = null;
    window.__OPSBRAIN_LAST_FILL__ = null;
    chrome.runtime.sendMessage({ type: "INVALIDATE_MAPPING_CACHE" }).catch(() => { });
  } catch (err) {
    const retryCount = (pending?.retryCount || 0) + 1;
    if (retryCount <= 3 && cacheManager) {
      await cacheManager.setPendingSubmission({
        url: location.href,
        fields: allFields,
        sessionId: currentSessionId,
        timestamp: Date.now(),
        retryCount,
      });
      logWarn("Submit feedback failed, will retry", { error: String(err), retryCount });
    } else {
      if (cacheManager) await cacheManager.clearPendingSubmission();
      logWarn("Submit feedback failed, max retries reached", { error: String(err) });
    }
  }
}

async function retryPendingSubmission() {
  const cacheManager = window.__CACHE_MANAGER__;
  if (!cacheManager) return;
  const pending = await cacheManager.getPendingSubmission().catch(() => null);
  if (!pending?.fields?.length) return;
  if (pending.timestamp && Date.now() - pending.timestamp < 30000) return;
  logInfo("Retrying pending submission", pending.fields.length, "fields");
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    if (!headers?.Authorization) return;
    const res = await fetch(`${apiBase}/chrome-extension/form-fields/submit-feedback`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        url: pending.url || location.href,
        domain: pending.url ? new URL(pending.url).hostname : location.hostname,
        ats: "unknown",
        fields: pending.fields,
      }),
    });
    await cacheManager.clearPendingSubmission();
    if (res.ok) chrome.runtime.sendMessage({ type: "INVALIDATE_MAPPING_CACHE" }).catch(() => { });
  } catch (_) { }
}

function tryAutoOpenPopup() {
  if (window.self !== window.top) return;
  if (window.__PAGE_DETECTOR__ && !window.__PAGE_DETECTOR__.shouldShowWidget()) return;
  if (!isJobFormPage()) return;
  mountInPageUI();
  if (window.__FORM_WATCHER__) window.__FORM_WATCHER__.start();
  attachSubmitFeedbackListener();
  const widget = document.getElementById(INPAGE_ROOT_ID);
  if (widget) {
    const card = widget.querySelector(".ja-card");
    if (card) card.classList.remove("collapsed");
  }
  if (!/workday\.com|myworkdayjobs\.com|wd\d+\.myworkday/i.test(window.location.href)) {
    runKeywordAnalysisAndMaybeShowWidget();
  }
}

const initAutoOpen = () => {
  tryAutoOpenPopup();
  setTimeout(tryAutoOpenPopup, 1500);
  setTimeout(tryAutoOpenPopup, 4000);
  retryPendingSubmission();
};

document.addEventListener("opsbrain-form-changed", () => {
  if (window.__REQUEST_MANAGER__) window.__REQUEST_MANAGER__.clearCache("form_fields:" + location.href);
});

window.addEventListener("message", (e) => {
  if (e.source !== window || e.data?.type !== "HIREMATE_PROFILE_SAVED") return;
  const origin = window.location.origin;
  if (LOGIN_PAGE_ORIGINS.some((o) => origin === o || origin.startsWith(o.replace(/\/$/, "") + "/"))) {
    chrome.runtime.sendMessage({ type: "INVALIDATE_MAPPING_CACHE" }).catch(() => { });
    logInfo("Profile saved — mapping cache invalidated");
  }
});

window.addEventListener("HIREMATE_RESUME_SAVED", (e) => {
  const resumeId = e.detail?.resumeId;
  if (resumeId != null) {
    chrome.runtime.sendMessage({ type: "RESUME_SAVED_FROM_TAILOR", resumeId }).catch(() => { });
  }
});

let _lastUrl = location.href;
const _urlObserver = new MutationObserver(() => {
  const current = location.href;
  if (current !== _lastUrl) {
    _lastUrl = current;
    if (window.__PAGE_DETECTOR__) window.__PAGE_DETECTOR__.reset();
    // Reset scraper's platform cache so the new URL is re-evaluated
    if (window.__OPSBRAIN_SCRAPER__?.resetPlatform) window.__OPSBRAIN_SCRAPER__.resetPlatform();
    if (window.__REQUEST_MANAGER__) window.__REQUEST_MANAGER__.clearCache("form_fields:" + current);
    tryAutoOpenPopup();
  }
});
if (document.body) _urlObserver.observe(document.body, { childList: true, subtree: true });

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => setTimeout(initAutoOpen, 500));
} else {
  setTimeout(initAutoOpen, 500);
}
