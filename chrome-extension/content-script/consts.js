// ─── Field / Form Constants ────────────────────────────────────────────────

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

// ─── Logging ───────────────────────────────────────────────────────────────

const LOG_PREFIX = "[Autofill][content]";

// ─── Widget / Storage Keys ─────────────────────────────────────────────────

const INPAGE_ROOT_ID = "job-autofill-inpage-root";
const AUTOFILL_TIME_SAVED_KEY = "hm_autofill_total_fields";
const AVG_SECONDS_PER_FIELD = 10; // ~10 sec manual typing per field on average

// ─── Login / Auth ──────────────────────────────────────────────────────────

const _visitedUrls = new Set();
const LOGIN_PAGE_ORIGINS = [
  "http://localhost:5173",
  "http://127.0.0.1:5173",
  "http://localhost:5174",
  "http://127.0.0.1:5174",
  "https://opsbrainai.com",
  "https://www.opsbrainai.com",
  "https://hiremate.ai",
  "https://www.hiremate.ai",
  "https://app.hiremate.ai",
  "https://hiremate.com",
  "https://www.hiremate.com",
];
const DEFAULT_LOGIN_PAGE_URL = "https://opsbrainai.com/login";

// ─── Autofill Highlight ────────────────────────────────────────────────────

const AUTOFILL_FAILED_CLASS = "ja-autofill-failed";

// ─── Scroll Timing ─────────────────────────────────────────────────────────

const SCROLL_DURATION_MS = 80;
const SCROLL_WAIT_AFTER_MS = 30;

// ─── API Timeouts ──────────────────────────────────────────────────────────

const ENRICH_TIMEOUT_MS = 2000;         // Never block scrape for more than 2s
const FORM_STRUCTURE_FETCH_TIMEOUT_MS = 1500;
