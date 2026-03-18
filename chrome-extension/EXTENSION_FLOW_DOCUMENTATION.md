# Chrome Extension & AI Resume Studio – Flow and Architecture

This document describes how the Hiremate Chrome extension and **AI Resume Studio** work end-to-end: backend resume APIs, extension flows, and frontend (OpsBrain/Hiremate) architecture and styles.

---

## 1. AI Resume Studio – Overview

**AI Resume Studio** is the resume hub in the Hiremate frontend. It is a landing page at `/ai-resume-studio` that offers three tools via cards:

| Card              | Route               | Description |
|-------------------|---------------------|-------------|
| **Resume Generator** | `/resume-generator`   | Build JD-tailored resumes from profile; upload PDF/DOC/DOCX; generate PDF via Jinja2 + WeasyPrint. |
| **ATS Scanner**      | `/job-scan`           | Upload resume + job description → ATS score and report (keyword match, searchability, hard/soft skills, recruiter tips). |
| **Resume Scan**      | `/resume-analyzer`    | Upload resume → deep insights (score, top fixes, issues, did-well). |

All three tools are wired to the **backend resume API** (`/api/resume/*`) and work end-to-end with the current architecture.

---

## 2. Backend Architecture – Resume API

### 2.1 Mount and structure

- **Base URL:** `/api`
- **Resume router:** `backend/app/api/v1/resume/` → mounted at **`/api/resume`**
- **Chrome extension router:** `backend/app/api/v1/chrome_extension/routes.py` → mounted at **`/api/chrome-extension`** (no extra prefix in `main.py`)

```text
main.py:
  app.include_router(resume_router, prefix="/api/resume", tags=["resume"])
  app.include_router(chrome_extension_router, prefix="/api")   # router has prefix="/chrome-extension"
```

- **Static uploads:** `app.mount("/uploads/resumes", StaticFiles(...))` for local resume files when S3 is not configured.

### 2.2 Resume API package (`/api/resume`)

Aggregates:

- **User resume (CRUD, workspace, generate, file):** `backend/app/api/v1/user/resume.py`
- **ATS Scan:** `backend/app/api/v1/resume/ats_scan.py`
- **Resume Analyze:** `backend/app/api/v1/resume/analyze.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/resume/list` | List user resumes (UserResume + profile fallback). |
| GET    | `/api/resume/workspace` | **Resumes + tailor context** (fetch-and-clear). Used by extension and resume-generator. |
| POST   | `/api/resume/upload` | Upload PDF/DOC/DOCX → S3/local, LLM extract profile, update Profile, add UserResume, clear autofill cache. |
| POST   | `/api/resume/generate` | JD-optimized resume: `job_title` + `job_description` → Jinja2 HTML + WeasyPrint PDF; returns `resume_id`, `resume_url`, etc. |
| GET    | `/api/resume/{id}/file` | Proxy resume PDF (S3 or local) for preview/download; avoids CORS. |
| PATCH  | `/api/resume/{id}` | Update name/text; regenerates PDF when text changes. |
| DELETE | `/api/resume/{id}` | Delete UserResume (id &gt; 0); DELETE `/api/resume/profile` for profile resume. |
| POST   | `/api/resume/ats-scan` | **ATS Scan:** `file` (PDF) + `job_description` (form) → score, categories, searchability/hard/soft/recruiter/formatting rows; optional LLM tips. |
| POST   | `/api/resume/analyze` | **Resume Analyze:** `file` (PDF) → score, top_fixes, completed, issues, did_well; optional LLM insights. |

### 2.3 Resume services (backend)

- **`resume_service`:** `list_resumes()` (UserResume first, profile fallback), `delete_file_from_storage()` (S3 or local).
- **`resume_generator`:** `generate_resume_html()` – profile + JD keywords → Jinja2 template, WeasyPrint → PDF, upload S3/local, create/update UserResume.
- **`resume_extractor`:** PDF text/hyperlinks; LLM extraction to profile payload on upload.
- **`resume_analysis_llm`:** Optional LLM enrichment for ATS scan (`get_ats_improvements`) and analyze (`get_resume_insights`).
- **`keyword_analyzer`:** Extract JD keywords (LLM), match against resume text; used by resume generator and by extension keyword analysis.
- **`tailor_context_store`:** In-memory, TTL 300s. `set_tailor_context(user_id, job_description, job_title, url)`; `get_and_clear_tailor_context(user_id)` used by `GET /api/resume/workspace`.

### 2.4 Chrome extension – resume-related endpoints (`/api/chrome-extension`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/chrome-extension/autofill/context` | Merged autofill: profile + resume_text + resume_url/name; cached 300s. |
| GET    | `/api/chrome-extension/autofill/resume/{file_name}` | Serve resume PDF by filename (same source as context: UserResume + profile). |
| POST   | `/api/chrome-extension/keywords/analyze` | Extract keywords from JD (page_html or job_description), match vs resume; returns high_priority/low_priority, matched_count, percent. |
| POST   | `/api/chrome-extension/tailor-context` | Store JD + job_title + url for “Tailor Resume”; resume-generator consumes via `GET /api/resume/workspace`. |

---

## 3. Frontend Architecture – AI Resume Studio & Resume Generator

### 3.1 Routes (current)

- `/ai-resume-studio` → **AiResumeStudio** (landing with 3 cards).
- `/resume-generator` → **ResumeGeneratorStart** (entry; can list resumes, upload, quick generate).
- `/resume-generator/build` → **ResumeGenerator** (full build UI: JD input, generate, preview, edit, delete).
- `/job-scan` → **JobScan** (ATS scan upload + JD).
- `/resume-analyzer` → **ResumeAnalyzer** (resume analyze upload).
- `/resume-analyze-score` → **ResumeAnalyzeScore** (analyze result view).

### 3.2 Frontend resume services

- **Base:** `axiosClient` with `BASE_URL` (e.g. `http://127.0.0.1:8000/api`); token from localStorage in interceptor.
- **resumeService.js:**
  - `getResumeWorkspaceAPI()` → `GET /resume/workspace`
  - `listResumesAPI()` → `GET /resume/list`
  - `uploadResumeAPI(file)` → `POST /resume/upload`
  - `generateResumeAPI({ job_title, job_description })` → `POST /resume/generate`
  - `updateResumeAPI(id, { resume_name, resume_text })` → `PATCH /resume/{id}`
  - `deleteResumeAPI(id)` → `DELETE /resume/{id}` or `DELETE /resume/profile` for id 0
  - `atsScanResumeAPI(file, jobDescription)` → `POST /resume/ats-scan`
  - `analyzeResumeAPI(file)` → `POST /resume/analyze`

Preview/download uses: `GET /resume/{id}/file` with `Authorization: Bearer <token>`.

### 3.3 AI Resume Studio – styles and layout

- **File:** `hiremate-frontend/src/pages/ai-resume-studio/aiResumeStudio.css`
- **Design:** Centered hero + 3-column card grid; CSS variables: `--bg-light`, `--text-primary`, `--text-secondary`, `--primary`, `--font-family`, `--font-size-page-title`, `--font-size-helper`, `--font-size-section-header`.
- **Hero:** Title “Accelerate Your Path to Employment”, subtitle with emphasized “enhancing”, blue underline bar.
- **Grid:** `grid-template-columns: repeat(3, minmax(0, 320px))`; 2 columns &lt; 1200px; 1 column &lt; 600px; gap 24px.

### 3.4 Resume Generator – flow and tailor context

- **ResumeGenerator (build):**
  - On load: `getResumeWorkspaceAPI()` → gets `resumes` and `tailor_context`.
  - If `?tailor=1` and `tailor_context` is present: prefill `jobDescription` and `jobRole` from `tailor_context.job_description` and `tailor_context.job_title`, show input form.
  - Generate: `generateResumeAPI({ job_title, job_description })` → backend creates JD-optimized resume; UI updates list and shows preview.
  - Preview: PDF via `GET /resume/{id}/file` with auth; edit/delete via PATCH/DELETE.
- **ResumeGeneratorStart:** Uses `listResumesAPI()` (or workspace) for recent resumes; can upload and generate; navigates to `/resume-generator/build` when building.

---

## 4. Chrome Extension – Resume and Tailor flow

### 4.1 In-page UI (content script)

- **Resume accordion:** “Resume” section loads resumes from `GET /api/resume/workspace` (same as frontend). Dropdown to pick resume; “Preview” opens PDF via `GET /api/resume/{id}/file`.
- **Keyword analysis:** Panel sends `POST /api/chrome-extension/keywords/analyze` with `page_html` and/or `job_description`, and `resume_id` or resume_text from context. Renders match % and keyword list (matched/unmatched).
- **Tailor Resume button:** Calls **Tailor Resume** flow then opens resume-generator with pre-filled JD.

### 4.2 Tailor Resume – end-to-end flow

1. User clicks **“Tailor Resume”** on a job page (in extension panel).
2. Extension collects current page JD (e.g. from `page_html` or scraped text) and optional `job_title`, `url`.
3. **POST /api/chrome-extension/tailor-context** with body: `{ job_description, job_title, page_html?, url? }`. Backend parses JD from `page_html` if needed; stores in `tailor_context_store` (TTL 300s).
4. Extension opens new tab: **`{frontendBase}/resume-generator?tailor=1`** (e.g. `https://app.hiremate.com/resume-generator?tailor=1`).
5. Resume Generator page loads and calls **GET /api/resume/workspace** (with auth). Backend returns `{ resumes, tailor_context }` and **clears** tailor context.
6. If `tailor_context` exists and `?tailor=1`: frontend prefills job description and job title and shows the input form so user can generate a tailored resume immediately.

So: **Extension (job page) → tailor-context (store JD) → open resume-generator?tailor=1 → workspace (fetch-and-clear JD) → prefill → generate.**

### 4.3 Autofill and resume file in extension

- **Autofill context:** Popup/content call **GET /api/chrome-extension/autofill/context** to get profile + `resume_text`, `resume_url`, `resume_name`. Used for form mapping and for building “resume text” for keyword/LLM.
- **Resume file for file inputs:** Extension gets PDF via **GET /api/chrome-extension/autofill/resume/{filename}** (filename from `resume_url`). Can cache in IndexedDB by hash; fills file inputs with Blob when autofilling.
- **Background:** Handles `GET_RESUME` (from IndexedDB or API), so content script can request resume binary for file-field fill without re-fetching context.

---

## 5. End-to-end summary

| Flow | Steps |
|------|--------|
| **AI Resume Studio → Resume Generator** | Open `/ai-resume-studio` → click “Resume Generator” → `/resume-generator` or `/resume-generator/build` → GET workspace → upload or generate → GET `/{id}/file` for preview. |
| **AI Resume Studio → ATS Scan** | Open `/job-scan` → upload PDF + paste JD → POST `/api/resume/ats-scan` → show score and report. |
| **AI Resume Studio → Resume Scan** | Open `/resume-analyzer` → upload PDF → POST `/api/resume/analyze` → show score, issues, did-well. |
| **Extension → Tailor Resume** | On job page: Tailor Resume → POST `/api/chrome-extension/tailor-context` → open `/resume-generator?tailor=1` → GET `/api/resume/workspace` (clears tailor context) → prefill JD → user clicks Generate → POST `/api/resume/generate`. |
| **Extension → Keyword match** | Keywords panel → POST `/api/chrome-extension/keywords/analyze` with JD + resume_id/resume_text → display % and keyword list. |
| **Extension → Autofill (resume)** | GET `/api/chrome-extension/autofill/context`; GET `/api/chrome-extension/autofill/resume/{filename}` for PDF; fill file inputs with Blob when field is resume/CV. |

---

## 6. Current styles and architecture notes

- **Backend:** FastAPI; resume routes under `/api/resume`; chrome-extension under `/api/chrome-extension`; auth via dependencies; resume list from `resume_service.list_resumes()`; tailor context in-memory with TTL; S3 or local `uploads/resumes` for files.
- **Frontend:** React (React Router); Dashboard layout for `/ai-resume-studio`, `/resume-generator`, `/job-scan`, `/resume-analyzer`; MUI components on resume-generator and related pages; AI Resume Studio uses custom CSS with design tokens (e.g. `var(--primary)`, `var(--bg-light)`).
- **Extension:** Content script injects in-page panel (accordions: Resume, Cover Letter, etc.); popup for auth and autofill trigger; background for resume storage and messages; API base from options/storage; all resume and keyword calls go to the same backend as the web app.

This architecture keeps AI Resume Studio (landing + Resume Generator, ATS Scanner, Resume Scan) and the extension’s resume/tailor flows using one backend and one set of resume APIs, with consistent auth and file handling.
