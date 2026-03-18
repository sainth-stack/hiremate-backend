# Chrome Extension – Styling & API Revamp Plan

This plan aligns the Chrome extension’s **styles**, **format**, and **APIs** with the revamped HireMate product (hiremate-pro), and ensures popup and in-page UIs show **new data** (e.g. **how many jobs applied / applications filled**, last fill time) end-to-end.

**Deep-audit (end-to-end):** Full API inventory (Section 1.2), all extension assets (1.1), API contract check (Section 2), new data flow (2.7), styling tasks (Section 3), implementation order (Section 5), files to touch (Section 6), and gaps/assumptions (Section 7) have been reviewed and updated.

---

## 1. Current State Summary

### 1.1 Extension assets

| Asset | Purpose |
|-------|--------|
| **popup.html / popup.css / popup.js** | Popup UI: login, signup, “Scan & Auto-Fill”, progress, mapping results |
| **content.js** | In-page panel (accordions: Resume, Cover Letter, Keywords, etc.) + messaging |
| **content-script/professionalWidget.js** | In-page “match %” widget (keyword analysis) |
| **content-script/** (requestManager, cacheManager, fieldScraper, humanFiller, etc.) | Scraping, fill, selectors, Workday; no styling changes in revamp |
| **config.js** | apiBase, loginPageUrl, appUrl, env detection |
| **background.js** | Resume storage, token sync, OPEN_RESUME_TAILOR (opens loginPageUrl + `/resume-generator/build?tailor=1`) |
| **security-manager.js** | Token storage/retrieval; no revamp change |
| **manifest.json** | Name “OpsBrain - Job Auto-Fill”; update for HireMate branding if desired |

### 1.2 Backend APIs used by extension (full inventory)

| Endpoint | Method | Used by | Purpose |
|----------|--------|---------|---------|
| `/api/auth/login` | POST | popup.js | Login → `access_token` |
| `/api/auth/register` | POST | popup.js | Signup → `access_token` |
| `/api/auth/refresh` | POST | popup.js, content.js | Token refresh (Bearer) |
| `/api/chrome-extension/autofill/context` | GET | popup.js, content.js | Profile + `resume_text`, `resume_url`, `resume_name`, `custom_answers` |
| `/api/chrome-extension/autofill/resume/{file_name}` | GET | popup.js, content.js | Resume PDF for file inputs |
| `/api/chrome-extension/form-fields/map` | POST | popup.js, content.js | Field → value mappings (by fingerprint + index) |
| `/api/chrome-extension/form-fields/submit-feedback` | POST | content.js | Learn from submission; selector performance |
| `/api/chrome-extension/keywords/analyze` | POST | content.js (widget) | JD keywords vs resume → match %, high/low priority |
| `/api/chrome-extension/tailor-context` | POST | content.js | Store JD for resume-generator |
| `/api/chrome-extension/jobs` | GET / POST | content.js | List saved jobs; save job (company, title, url, etc.) |
| `/api/chrome-extension/cover-letter/upsert` | POST | content.js | Generate/return cover letter for job |
| `/api/chrome-extension/form-structure/check` | GET | content.js | Known form structure + best selectors by domain |
| `/api/chrome-extension/selectors/best-batch` | POST | content.js | Best selectors for given fingerprints + ATS |
| `/api/chrome-extension/profile/invalidate-field-answers` | POST | (optional) | Invalidate learned answers when profile changes |
| `/api/resume/workspace` | GET | content.js | Resumes list + tailor_context (fetch-and-clear) |
| `/api/resume/{id}/file` | GET | content.js | Resume PDF by id (preview) |
| `/api/activity/track` | POST | popup.js, content.js | `event_type`, `page_url` |
| **`/api/dashboard/summary`** | **GET** | **popup.js (to add), hiremate-pro** | **Stats: jobs_applied, jobs_saved, applications_filled, last_autofill_at** |

**Gap:** `content.js` calls **`POST /api/chrome-extension/job-page-detect`** (url, title, snippet → `is_job_page`). This endpoint **does not exist** in the backend. Either implement it or make the content script tolerate 404 and fall back to heuristic detection.

### 1.3 Design sources to align with

- **hiremate-pro**: Tailwind + shadcn-style; CSS variables in `index.css` (HSL: `--primary`, `--background`, `--foreground`, `--radius`, etc.).
- **hiremate-frontend**: `App.css` OpsBrain tokens (hex: `--primary`, `--success`, `--error`, `--warning`, `--btn-primary`, etc.).

Extension currently uses **hardcoded colors** in `popup.css` and inline styles in `professionalWidget.js`, with no shared design tokens.

---

## 2. API Contract & Data Format Check

### 2.1 Auth

- **Login/Register**: Backend returns `{ "access_token": "..." }`. Popup uses `data.access_token` ✓.
- **Refresh**: Popup expects `access_token` or `accessToken`; backend returns `access_token` ✓.
- **Storage**: Popup and security-manager store token; popup uses `apiBase` from storage (e.g. `http://localhost:8000/api`). Ensure `loginPageUrl` / `appUrl` point to the **revamped app** (e.g. hiremate-pro origin) when deployed.

**Action**: Confirm `config.js` and any options page use the correct frontend URL for “Log in via website” and post-login redirects (hiremate-pro vs hiremate-frontend).

### 2.2 Autofill context – `GET /api/chrome-extension/autofill/context`

**Response (backend):**

- `profile`: dict (flat + structured: `experiences[]`, `educations[]`, `skills_list`, etc.)
- `resume_text`: string
- `resume_url`: string (proxy path like `/api/chrome-extension/autofill/resume/{filename}`)
- `resume_name`: string | null
- `custom_answers`: dict (currently empty from backend)

**Popup usage**: `loadAndCacheAutofillData()` → `profile`, `customAnswers`, `resumeText`, `resumeName`, `resumeUrl`. Uses `autofillCtx.custom_answers` (snake_case from API) as `customAnswers` ✓.

**Action**: None for format. Optional: if revamped app adds new profile fields or custom_answers, ensure backend `_profile_to_autofill_format` and response schema expose them so popup/content can show them if needed.

### 2.3 Form field mapping – `POST /api/chrome-extension/form-fields/map`

**Request**: `fields[]`, `profile`, `custom_answers`, `resume_text`, `sync_llm`.

**Response**: `mappings` (keyed by fingerprint and by index), `unfilled_profile_keys` (optional).

**Popup usage**: `showMappingProgress(CURRENT_FIELDS, mappings)` expects:

- `mappings[field.fingerprint]` or `mappings[field.index]` with `{ value, confidence }`.
- Backend returns `value`, `confidence`, `reason`, `type` ✓.

**Action**: None. Ensure popup never assumes missing keys; it already uses `mapData.value != null` and confidence classes (high/medium/low).

### 2.4 Keywords analyze – `POST /api/chrome-extension/keywords/analyze`

**Response**: `KeywordsAnalyzeOut`: `total_keywords`, `matched_count`, `percent`, `high_priority[]`, `low_priority[]` (items: `keyword`, `matched`), optional `job_description`, `job_id`.

**Widget (professionalWidget.js)**: `transformApiData()` maps API to internal shape (`high_priority: { matched, missing }`, etc.) ✓.

**Action**: None for API format. Styling of the widget should follow the new design system (see Section 3).

### 2.5 Resume file – `GET /api/chrome-extension/autofill/resume/{file_name}`

- Extension builds URL from `resume_url` (e.g. strip to filename). Backend serves file by name from same source as context ✓.
- **Action**: None.

### 2.6 Activity – `POST /api/activity/track`

- Body: `event_type`, `page_url`. Extension sends `event_type: "autofill_used"` ✓.
- **Action**: None.

### 2.7 New data: “How many jobs applied” / applications filled

**Requirement (from hiremate-pro revamp):** Popup and dashboard must show:

- **Applications filled** – count of times the user used autofill (CareerPageVisit with `action_type: "autofill_used"`).
- **Last fill** – “Last fill: X min ago” (or hours/days) from the most recent autofill event.

**Backend (done):**

- **`GET /api/dashboard/summary`** (existing) now returns in `stats`:
  - **`applications_filled`** (int) – count of CareerPageVisit where `action_type == "autofill_used"` (respects `days` / `from_date` / `to_date` when provided).
  - **`last_autofill_at`** (str | null) – ISO datetime of the most recent autofill_used event (no date filter, so “Last fill” is always global).

**Extension popup (to do):**

- Add a **footer** (or reuse existing footer) that:
  - Calls **`GET /api/dashboard/summary`** with auth (e.g. `?days=365` or no params for default range).
  - Displays **“X applications filled”** using `stats.applications_filled`.
  - Displays **“Last fill: X ago”** using `stats.last_autofill_at` formatted as relative time (e.g. “2 min ago”, “1 hour ago”, “3 days ago”). If `last_autofill_at` is null, show “Last fill: Never” or hide the line.

**hiremate-pro ChromeExtension.tsx (to do):**

- The preview page currently shows **hardcoded** “47 applications filled” and “Last fill: 2 min ago”.
- When the page is used with a logged-in user (or when embedding real extension logic), **fetch `GET /api/dashboard/summary`** and render:
  - `stats.applications_filled` → “X applications filled”
  - `stats.last_autofill_at` → format as “Last fill: X ago” (same relative-time helper as extension popup).

**Response shape (dashboard/summary):**

```json
{
  "stats": {
    "jobs_applied": 12,
    "jobs_saved": 20,
    "companies_checked": 15,
    "applications_filled": 47,
    "last_autofill_at": "2025-03-17T10:30:00.000Z"
  },
  "recent_applications": [...],
  "companies_viewed": [...],
  "applications_by_day": [...]
}
```

### 2.8 Other extension APIs (content script)

- **GET/POST /api/chrome-extension/jobs**, **GET /api/resume/workspace**, **GET /api/resume/{id}/file**, **POST /api/chrome-extension/cover-letter/upsert**, **GET /api/chrome-extension/form-structure/check**, **POST /api/chrome-extension/selectors/best-batch**, **POST /api/chrome-extension/form-fields/submit-feedback**: All implemented and used by content.js. No contract or format changes required for the revamp.
- **POST /api/chrome-extension/job-page-detect**: Called by content.js; **not implemented** in backend. See Section 7.1.

---

## 3. Styling & Format Revamp – Tasks

### 3.1 Design tokens (popup + in-page)

**Goal**: One set of variables for the extension so popup and content script match hiremate-pro/frontend.

**Tasks:**

1. **Add a shared tokens file or block** (e.g. in `popup.css` and inject same vars in content script):
   - Prefer **hiremate-pro** tokens where the revamped app is the primary surface (e.g. `--primary`, `--background`, `--foreground`, `--radius`, `--success`, `--destructive`, `--muted`).
   - Alternatively mirror **hiremate-frontend** `App.css` (hex) if that’s the canonical app.
   - Include: primary, secondary, success, error, warning, muted, background, foreground, border, radius, font family.

2. **Popup (`popup.css`)**:
   - Replace hardcoded colors (e.g. `#1a73e8`, `#2f80ff`, `#667eea`, `#764ba2`, `#0d8050`, `#c5221f`) with `var(--primary)`, `var(--success)`, `var(--error)`, etc.
   - Use token for body background, card background, borders, button states, progress bar, badges (high/medium/low), status text (info/loading/error/success/warning).
   - Keep or adapt existing layout (width 380px, sections, progress card, mapping list).

3. **Popup HTML**:
   - No structural change required; ensure class names used in JS (e.g. `#mapping-progress`, `.mapping-row`, `.progress-card`) remain and are styled via the new tokens.

### 3.2 Popup – “newly showing data” and format

**Data currently shown in popup:**

- Login/signup form and errors.
- After login: “Scan & Auto-Fill” button, hint, progress card (stage, %, detail), status line, **AI Mapping Results** (list of label, confidence %, value preview).

**New data to show (align with hiremate-pro revamp):**

- **Footer:** “X applications filled” and “Last fill: X ago” (from `GET /api/dashboard/summary` → `stats.applications_filled`, `stats.last_autofill_at`).

**Tasks:**

4. **Progress card**: Style with tokens (border, background, progress bar fill). Optionally add a subtle animation (e.g. progress-fill) to match hiremate-pro.

5. **Mapping results** (`#mapping-progress`, `.mapping-list`, `.mapping-row`):
   - Use tokens for text (foreground/muted), borders, confidence colors (success/warning/error).
   - Ensure truncation and “(empty)” for long/missing values remain; no API change.

6. **Status line** (`.status.info`, `.loading`, `.error`, `.success`, `.warning`): Use semantic tokens (e.g. `--success`, `--error`, `--warning`) and keep spinner for loading.

7. **Login/signup**: Inputs, buttons, links, error text – all via tokens. “Log in via website” button: primary style; ensure link opens correct revamped app URL.

8. **Profile gap tip** (e.g. “Add X to your profile…”): Currently inline styles in `showProfileGapTip()`. Replace with a small class block in `popup.css` using tokens (e.g. warning background/border).

9. **Footer – applications filled & last fill**:
   - In **popup.html**: Add a footer block (e.g. `.popup-footer` or extend existing `footer`) with two spans: one for “Last fill: X ago”, one for “X applications filled” (icons optional; match hiremate-pro layout).
   - In **popup.js**: On showApp(), call `GET /api/dashboard/summary` with auth headers, then update footer with `stats.applications_filled` and a relative-time string from `stats.last_autofill_at`. Add a small helper (e.g. `formatLastFillAgo(isoString)`) that returns “Never”, “X min ago”, “X hours ago”, “X days ago”. **On failure** (network error, 401): show fallback (e.g. “— applications filled”, “Last fill: —”) or hide footer stats; do not throw.
   - In **popup.css**: Style footer with tokens (muted text, small font); match hiremate-pro “Footer Stats” look (e.g. two-column footer with muted background).

### 3.3 Content script – in-page panel (content.js)

**Goal**: Accordions and panels (Resume, Cover Letter, Keywords, etc.) use the same design language.

**Tasks:**

10. **Injected panel styles** (content.js or separate injected CSS):
    - Define or reuse the same design tokens (e.g. in a `:root` block injected into the page).
    - Update accordion header/body, buttons, inputs, and copy to use tokens (primary, background, border, radius).

11. **Class names**: Current `ja-accordion-*` and similar – keep for stability; only change colors/sizing via tokens so the new styles don’t break existing JS selectors.

### 3.4 Professional match widget (professionalWidget.js)

**Goal**: Keyword match widget (score circle, keyword tags, buttons) matches new look.

**Tasks:**

12. **injectStyles()** in `professionalWidget.js`:
    - Replace hardcoded hex (e.g. gradients, `#667eea`, `#11998e`, `#f5576c`) with CSS variables. Either inject the same tokens as popup or define a small set (e.g. `--ob-primary`, `--ob-success`, `--ob-error`, `--ob-warning`) in the injected style block.
    - Use tokens for: header gradients by level, score ring, stat values, keyword tags (success/optional/default), primary/secondary buttons.

13. **Layout/size**: Keep widget width (420px) and positioning; only colors and typography (and optional radius/shadow) to align with design system.

### 3.5 Branding and copy

- Popup and widget currently say **“OpsBrain”**. If the revamped product name is **“HireMate”** (or both), decide and:
  - Update `popup.html` title and headings.
  - Update widget title if visible.
  - Ensure “Log in via website” and any “Open resume generator” / “Tailor Resume” links use the correct app URL (hiremate-pro or frontend).

---

## 4. API and Config Checklist

| Item | Action |
|------|--------|
| Auth response `access_token` | Already correct; no change. |
| Refresh response | Already correct; no change. |
| Autofill context shape | No change; optional: extend when backend adds fields. |
| Form-fields map request/response | No change. |
| Keywords analyze response | No change; widget already transforms. |
| Activity track | No change. |
| **Dashboard summary** | **Extended:** `stats.applications_filled` (int), `stats.last_autofill_at` (ISO str \| null). Extension and hiremate-pro consume these for “applications filled” and “Last fill: X ago”. |
| `config.js` / storage | Set `loginPageUrl` and `appUrl` to revamped app base URL for production. |
| CORS / base URL | Ensure extension’s `apiBase` matches backend (e.g. `https://api.hiremate.com/api` or same-origin frontend proxy). |

---

## 5. Implementation Order (End-to-End)

1. **Backend** – Dashboard summary: `applications_filled`, `last_autofill_at` (done).
2. **Design tokens** – Add shared variables (popup.css + content-injected block).
3. **Popup** – Replace colors; add footer that fetches `GET /api/dashboard/summary` and shows “X applications filled” and “Last fill: X ago” (with `formatLastFillAgo()` helper).
4. **Config** – Point login/app URLs to revamped app; verify apiBase for prod.
5. **Content panel** – Apply tokens to accordion and panel UI.
6. **Professional widget** – Apply tokens to injected styles; optional small layout tweaks.
7. **hiremate-pro ChromeExtension.tsx** – Replace hardcoded “47 applications filled” and “Last fill: 2 min ago” with API: fetch `GET /api/dashboard/summary` when user is authenticated, show `stats.applications_filled` and format `stats.last_autofill_at` as “Last fill: X ago”.
8. **Branding** – OpsBrain vs HireMate in popup, manifest name, and any link labels.
9. **job-page-detect (optional)** – Either implement `POST /api/chrome-extension/job-page-detect` or make content.js handle 404 and skip LLM job-page detection (see Section 7.1).
10. **Manual QA** – Login → confirm footer shows applications filled and last fill; Scan & Auto-Fill → check mapping and progress; trigger keyword widget and tailor flow; confirm resume fetch and activity track; verify Tailor Resume opens correct app.

---

## 6. Files to Touch

| File | Changes |
|------|--------|
| **Backend:** `backend/app/api/v1/dashboard/routes.py` | **Done:** Add `applications_filled`, `last_autofill_at` to `stats`. |
| **Backend:** `backend/tests/test_dashboard.py` | **Done:** Assert new stats keys. |
| `popup.css` | Design tokens; replace hardcoded colors; footer styles. |
| `popup.html` | Footer block for “Last fill” and “applications filled”; optional branding. |
| `popup.js` | Fetch `GET /api/dashboard/summary` on showApp(); `formatLastFillAgo(iso)`; update footer DOM; optional profile gap tip class. |
| `config.js` | `loginPageUrl`, `appUrl` for revamped app. |
| `content.js` | Injected CSS with same tokens; accordion/panel styles. |
| `content-script/professionalWidget.js` | Injected styles use tokens; optional layout tweaks. |
| **hiremate-pro:** `src/pages/ChromeExtension.tsx` | **Wire to API:** Fetch dashboard/summary when authenticated; display real `applications_filled` and “Last fill: X ago” from `last_autofill_at`. |
| **hiremate-pro:** `src/contexts/AuthContext.tsx` | **Optional:** Replace mock login/register with real `/api/auth/login` and `/api/auth/register` + store `access_token` so ChromeExtension can call dashboard/summary with auth. If kept as preview-only, ChromeExtension can continue to show mock “47 applications filled” / “Last fill: 2 min ago”. |
| **hiremate-pro:** routes (e.g. `App.tsx`) | **Align with extension:** Extension’s “Tailor Resume” opens `loginPageUrl + /resume-generator/build?tailor=1`. Ensure the app pointed to by `loginPageUrl` (hiremate-frontend or hiremate-pro) actually has that route; hiremate-pro currently only has `/` → ChromeExtension. |
| `manifest.json` | **Branding:** Change `name` (and optionally `description`) from “OpsBrain - Job Auto-Fill” to “HireMate” (or chosen product name) when rebranding. |
| `background.js` | **Config:** Uses `loginPageUrl` from storage for OPEN_RESUME_TAILOR and OPEN_LOGIN_TAB; no code change if config.js/storage set loginPageUrl correctly for revamped app. |

---

## 7. Deep audit – gaps and assumptions

### 7.1 API gaps

- **job-page-detect:** Content script calls `POST /api/chrome-extension/job-page-detect` with `{ url, title, snippet }` expecting `{ is_job_page: boolean }`. This route **is not implemented** in the backend. **Action:** Either add the endpoint (e.g. lightweight heuristic or LLM) or remove/guard the call in content.js and rely only on URL/heuristic detection so 404 does not break flows.

### 7.2 hiremate-pro vs extension

- **Auth:** hiremate-pro `AuthContext` is **mock** (no real backend auth). To show real “applications filled” and “Last fill” on the ChromeExtension preview page, either (a) add real auth (login/register against `/api/auth/*`) and an API client that sends `Authorization: Bearer`, or (b) keep the page as a static preview with mock data.
- **Routes:** hiremate-pro `App.tsx` currently routes only `/` and `*` to ChromeExtension. The extension’s “Tailor Resume” opens `loginPageUrl + /resume-generator/build?tailor=1`. If `loginPageUrl` points to hiremate-pro, that app must expose `/resume-generator/build` (and optionally `/login`); otherwise point `loginPageUrl` to hiremate-frontend (or whichever app has resume-generator and workspace).

### 7.3 Config and environment

- **config.js:** `loginPageUrl` and `appUrl` are identical in dev and production (localhost:5173). For production deployment, these must be overridden (e.g. via extension options or build-time env) to the revamped app’s URL.
- **host_permissions:** Extension has `<all_urls>`. Dashboard/summary is called to the same origin as apiBase (e.g. localhost:8000 or production API). No extra permissions needed for dashboard/summary.

### 7.4 Dashboard summary cache

- Backend caches by `dashboard_summary:{user_id}:{start_str}:{end_str}`. Cache is invalidated on job save and profile update. After an autofill, `activity/track` is called (which does not invalidate dashboard cache); `applications_filled` and `last_autofill_at` will update on **next** summary fetch (cache TTL or nocache). Acceptable for popup open; optional: invalidate dashboard cache when activity/track receives `autofill_used` so next popup open shows fresh count.

### 7.5 Security and resilience

- Popup and content script use `fetchWithAuthRetry` (or equivalent) for auth; 401 triggers refresh and retry. Dashboard/summary should use the same pattern in popup.js.
- Token sync: background syncs token to HireMate tab localStorage; popup can also sync from tab via message. Ensure `loginPageUrl` origin is in the allowed list in background.js (`HIREMATE_ORIGINS` or derived from loginPageUrl) so token sync works for the revamped app.
