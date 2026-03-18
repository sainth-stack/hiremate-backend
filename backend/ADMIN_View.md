# Admin View — Detailed Documentation

This document describes the HireMate admin area: **frontend pages**, **backend APIs**, and **database tables** used for platform analytics and management. All admin APIs require an authenticated user with `is_admin=True` (enforced via `get_admin_user`).

---

## 1. Admin Access

- **Auth:** User must be logged in and have `users.is_admin = true`.
- **Promotion:** Set `ADMIN_EMAIL` in `.env`; that email is auto-promoted to admin on login/register (`auth_service.py`).
- **Frontend guard:** `AdminRoute` and sidebar show Admin only when `user.is_admin === true`.

---

## 2. Frontend Admin Pages & Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/admin` | `AdminOverview` | Platform-wide stats dashboard |
| `/admin/users` | `AdminUsers` | Paginated users list with search |
| `/admin/users/:id` | `AdminUserDetail` | Single user usage breakdown |
| `/admin/companies` | `AdminCompaniesViewed` | Companies aggregated from visits/jobs |
| `/admin/career-pages` | `AdminCareerPages` | Top career page URLs by visits/autofill |
| `/admin/learning` | `AdminLearning` | Form structures, user answers, submissions |

**Layout:** `AdminLayout` wraps all admin routes and provides sidebar nav (Overview, Users, Companies Viewed, Career Page Links, Learning).

---

## 3. Backend Admin APIs

**Base path:** `GET /api/admin/...`  
**Auth:** Bearer token; user must have `is_admin=True` (403 otherwise).

### 3.1 Overview

| Method | Endpoint | Query params | Description |
|--------|----------|--------------|-------------|
| GET | `/api/admin/overview` | — | Platform-wide stats and new users by day |

**Response shape:**
- `stats`: `total_users`, `active_users_7d`, `active_users_30d`, `career_page_visits`, `autofill_uses`, `jobs_saved`, `jobs_applied`, `form_submissions`
- `new_users_by_day`: `[{ date, count }]` for last 30 days

---

### 3.2 Users

| Method | Endpoint | Query params | Description |
|--------|----------|--------------|-------------|
| GET | `/api/admin/users` | `page`, `limit`, `search` | Paginated users with jobs_count, career_visits_count, last_activity_at |
| GET | `/api/admin/users/{user_id}/usage` | — | Per-user usage: jobs saved/applied, visits by action_type, field answers, submissions, resumes |

**`/users` response:** `users[]`, `total`, `page`, `limit`. Each user: `id`, `email`, `first_name`, `last_name`, `created_at`, `last_activity_at`, `jobs_count`, `career_visits_count`.

**`/users/{id}/usage` response:** `user_id`, `email`, `jobs.saved`, `jobs.applied`, `career_page_visits` (by action_type), `user_field_answers_count`, `user_submission_history_count`, `resumes_count`.

---

### 3.3 Companies Viewed

| Method | Endpoint | Query params | Description |
|--------|----------|--------------|-------------|
| GET | `/api/admin/companies-viewed` | `page`, `limit`, `from_date`, `to_date` | Companies from CareerPageVisit + UserJob: unique_users, total_visits, autofill_uses, last_visited_at |

**Response:** `companies[]`, `total`, `page`, `limit`. Each company: `company_name`, `unique_users`, `total_visits`, `autofill_uses`, `last_visited_at`.

---

### 3.4 Career Page Links

| Method | Endpoint | Query params | Description |
|--------|----------|--------------|-------------|
| GET | `/api/admin/career-page-links` | `page`, `limit`, `from_date`, `to_date` | Top career page URLs: visit_count, autofill_count, unique_users |

**Response:** `links[]`, `total`, `page`, `limit`. Each link: `page_url`, `visit_count`, `autofill_count`, `unique_users`.

---

### 3.5 Learning (Form-field training)

| Method | Endpoint | Query params | Description |
|--------|----------|--------------|-------------|
| GET | `/api/admin/learning/form-structures` | — | SharedFormStructure: total, top_domains, ats_platforms |
| GET | `/api/admin/learning/user-answers` | — | UserFieldAnswer: total, top_users, by_source |
| GET | `/api/admin/learning/submissions` | `from_date`, `to_date` | UserSubmissionHistory: total, by_day, by_domain, top_users |

**form-structures:** `total`, `top_domains[]` (domain, count, sample_count), `ats_platforms[]` (ats_platform, count).  
**user-answers:** `total`, `top_users[]` (user_id, answers_count, total_used_count), `by_source[]` (source, count).  
**submissions:** `total`, `by_day[]`, `by_domain[]`, `top_users[]`.

---

### 3.6 Extension (placeholder)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/extension/errors` | Placeholder; extension errors not stored in DB. Returns `errors: []`, message. |

---

## 4. Database Tables (used by Admin)

### 4.1 `users`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | User ID |
| first_name | String | First name |
| last_name | String | Last name |
| email | String (unique) | Email |
| hashed_password | String | Password hash |
| is_active | Integer | 1 = active |
| is_admin | Boolean | Admin flag (required for admin APIs) |
| created_at | DateTime | Registration time |
| updated_at | DateTime | Last update |

---

### 4.2 `profiles`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | Profile ID |
| user_id | Integer FK(users.id) | Owner |
| resume_url | String(512) | Resume file URL |
| resume_last_updated | String(64) | ISO date |
| first_name, last_name, email, phone, city, country | String | Profile fields |
| willing_to_work_in | JSON | List of locations |
| professional_headline | String | Headline |
| professional_summary | Text | Summary |
| experiences, educations, tech_skills, soft_skills, projects | JSON | Structured data |
| preferences, links | JSON | Extra |
| created_at, updated_at | DateTime | Timestamps |

Used in admin user usage for resume presence (resume_url counts as a resume).

---

### 4.3 `user_jobs`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | Job record ID |
| user_id | Integer FK(users.id) | Owner |
| company | String(255) | Company name |
| position_title | String(255) | Job title |
| location | String(255) | Location |
| min_salary, max_salary | String(50) | Salary range |
| currency | String(20) | e.g. USD |
| period | String(50) | Yearly/Monthly/Hourly |
| job_type | String(50) | Full-Time, etc. |
| job_description | Text | Description |
| notes | Text | Notes |
| application_status | String(100) | saved / applied / interview / closed / etc. |
| job_posting_url | String(1024) | URL |
| created_at, updated_at | DateTime | Timestamps |

Admin uses this for: overview (jobs_saved, jobs_applied), users list (jobs_count, last_activity), user usage (saved vs applied), companies-viewed (company list), active user counts.

---

### 4.4 `user_resumes`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | Resume ID |
| user_id | Integer FK(users.id) | Owner |
| resume_url | String(512) | File URL |
| resume_name | String(255) | Display name |
| resume_text | Text | Extracted text |
| is_default | Integer | 1 = default |
| created_at | DateTime | Created |

Used in admin user usage for `resumes_count` (with profile.resume_url as fallback).

---

### 4.5 `career_page_visits`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | Visit ID |
| user_id | Integer FK(users.id) | User |
| page_url | String(2048) | Career/job page URL |
| company_name | String(255) | Company (from page or input) |
| job_url | String(2048) | Job posting URL |
| action_type | String(50) | `page_view`, `autofill_used`, `save_job` |
| job_title | String(255) | When available |
| created_at | DateTime | When |

Used for: overview (career_visits, autofill_uses), active users (7d/30d), users list (visits_count, last_activity), user usage (visits by action_type), companies-viewed, career-page-links.

---

### 4.6 `shared_form_structures`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | Structure ID |
| domain | String(255) | Domain (indexed) |
| url_pattern | String(500) | URL pattern |
| ats_platform | String(50) | ATS name |
| field_count | Integer | Number of fields |
| field_fps | JSON | Field fingerprints |
| has_resume_upload | Boolean | Has resume upload |
| has_cover_letter | Boolean | Has cover letter |
| is_multi_step | Boolean | Multi-step form |
| step_count | Integer | Steps |
| confidence | Float | Confidence |
| sample_count | Integer | Sample count |
| last_seen, created_at | DateTime | Timestamps |

Used in admin: `/admin/learning/form-structures` (total, by domain, by ats_platform).

---

### 4.7 `user_field_answers`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | Answer ID |
| user_id | Integer FK(users.id) | User |
| field_fp | String(64) | Field fingerprint |
| label_norm | String(255) | Normalized label |
| value | Text | Stored value |
| source | String(20) | llm / user_edit / form_submit |
| confidence | Float | Confidence |
| used_count | Integer | Usage count |
| last_used, created_at | DateTime | Timestamps |
| UNIQUE(user_id, field_fp) | — | One answer per user per field |

Used in admin: user usage (`user_field_answers_count`), `/admin/learning/user-answers`.

---

### 4.8 `user_submission_history`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | Submission ID |
| user_id | Integer FK(users.id) | User |
| domain | String(255) | Domain |
| url | String(500) | Page URL |
| ats_platform | String(50) | ATS |
| submitted_at | DateTime | Submit time |
| field_count | Integer | Fields on form |
| filled_count | Integer | Filled count |
| unfilled_profile_keys | JSON | Unfilled keys |
| submitted_fields | JSON | Submitted field data |

Used in admin: overview (`form_submissions`), user usage (`user_submission_history_count`), `/admin/learning/submissions`.

---

### 4.9 Other learning tables (not exposed in admin APIs)

- **shared_selector_performance:** field_fp, ats_platform, selector_type, selector, success/fail counts.
- **shared_field_profile_keys:** field_fp, ats_platform, label_norm, profile_key, confidence, vote_count.

---

## 5. Summary

| Area | Frontend route | Main API(s) | Main tables |
|------|----------------|-------------|-------------|
| Overview | `/admin` | GET `/api/admin/overview` | users, career_page_visits, user_jobs, user_submission_history |
| Users | `/admin/users`, `/admin/users/:id` | GET `/api/admin/users`, GET `/api/admin/users/:id/usage` | users, user_jobs, career_page_visits, user_field_answers, user_submission_history, user_resumes, profiles |
| Companies | `/admin/companies` | GET `/api/admin/companies-viewed` | career_page_visits, user_jobs |
| Career pages | `/admin/career-pages` | GET `/api/admin/career-page-links` | career_page_visits |
| Learning | `/admin/learning` | GET `/api/admin/learning/form-structures`, `user-answers`, `submissions` | shared_form_structures, user_field_answers, user_submission_history |
| Extension | (no dedicated page) | GET `/api/admin/extension/errors` | (placeholder; no DB) |

All admin endpoints require a valid JWT and `users.is_admin = true`.
