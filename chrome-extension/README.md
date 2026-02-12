# Job Auto-Apply Autofill (Chrome Extension)

Chrome extension that fills job application forms with your profile and resume. **V1: local storage only** — no backend required. It learns new questions: you save answers once in the popup, and next time they are auto-filled.

> Login is optional. If you do not log in, autofill still works using local profile/sample data and saved answers.

## Features

- **Scan & Auto-Fill (LLM-only)** — One click: scrape page (all frames), map with LLM, generate missing-but-derivable answers from user data, and auto-fill. Popup stays open for multiple applications.
- **Real-time mapping display** — Shows field mappings with confidence scores as they're applied to the form.
- **Multi-tab support** — Each tab works independently; popup remains open for applying to multiple jobs.
- **Multi-frame support** — Automatically detects and fills fields across all same-origin frames and iframes.
- **LLM uses full local context** — Mapping request includes `profile`, `customAnswers`, and `resumeText` so missing but derivable answers can be generated before fill.
- **Broader JS form support** — Detects and fills classic fields and many JS-driven fields (`contenteditable`, ARIA textbox/combobox patterns, shadow DOM fields).
- **Saved answers** — For custom questions (e.g. "Why do you want to join?"), add the question and answer in the "Saved answers" tab; next time the same question is auto-filled.
- **Sample test data** — One click loads default profile + saved answers + resume from `sample-data/default-autofill-data.json`. **Must load before first use.**
- **Automatic resume upload during fill** — Resume file fields are auto-mapped to `RESUME_FILE` and uploaded from extension storage.
- **Detailed debug logs** — Scrape, mapping request/response, and fill stages now log structured details in popup/content/background consoles.
- **No auto-submit** — Only fills fields; you review and submit yourself (avoids bot detection).

## How to load the extension (testing)

1. Open Chrome and go to `chrome://extensions/`.
2. Turn **Developer mode** ON (top-right).
3. Click **Load unpacked**.
4. Select the folder that contains this extension (the folder where `manifest.json` lives):
   - e.g. `.../autoapply/chrome-extension`
5. The extension should appear in the toolbar. Pin it if needed (puzzle icon → pin "Job Auto-Apply Autofill").

## How to test

### 1. Set up profile and resume

1. Click the extension icon to open the popup.
2. **Profile** tab: fill in name, email, phone, LinkedIn, GitHub, skills, experience, education. Click **Save profile**.
3. Under **Resume (PDF)**: choose a PDF file. You should see "Resume saved."

### 1b. Load sample default data (quick testing)

1. Open the extension popup.
2. In **Profile**, click **Load sample test data**.
3. This writes sample `profile` and `customAnswers` into `chrome.storage.local` so you can test autofill quickly.
4. You can edit the values in `chrome-extension/sample-data/default-autofill-data.json`.

### 2. Test “Scan & Auto-Fill” (LLM mapping)

1. Start the backend (from `backend/`): `uvicorn app.main:app --reload` (and set `OPENAI_API_KEY` in `.env`).
2. Open a job application page in Chrome.
3. Click the extension icon → click **Scan & Auto-Fill**.
4. The extension scrapes the page, calls `POST /api/v1/form-fields/map`, gets LLM mapping/generated values, then fills automatically. Review and submit yourself.

### 4. Test saved answers (new questions)

1. If a form has a question that wasn’t filled (e.g. "Why do you want to join this company?"), type your answer manually this time.
2. Open the extension → **Saved answers** tab.
3. In **Question** enter the same (or similar) text, e.g. `why do you want to join this company`.
4. In **Your answer** paste your answer. Click **Save answer**.
5. Next time you see a field with that question (or similar label), the extension will auto-fill it using your saved answer.

Matching is by **normalized label**: lowercase, trimmed, single spaces. So "Why do you want to join?" and "why do you want to join this company" are different keys; use the exact phrasing you see on forms for best results, or add multiple variants in Saved answers if needed.

## Project layout

```
chrome-extension/
├── manifest.json   # MV3 manifest, permissions, content script, popup
├── popup.html      # Popup UI
├── popup.css       # Popup styles
├── popup.js        # Profile + resume upload + custom answers + "Scan & Auto-Fill" flow
├── background.js   # Service worker: IndexedDB for resume, message handlers
├── content.js      # Injected on all pages: field matching, fill on message only
├── sample-data/
│   └── default-autofill-data.json # Sample profile + saved answers
└── README.md       # This file
```

## Storage

| Data           | Where                |
|----------------|----------------------|
| Profile        | `chrome.storage.local` |
| Custom answers | `chrome.storage.local` |
| Resume PDF     | IndexedDB (in background script) |

## Safety / anti-ban

- Filling runs **only** when you click "Fill form on this page" (no automatic fill on page load).
- There is a 300–800 ms delay between filling fields to mimic human typing.
- The extension **never** auto-clicks submit; you always submit the form yourself.

## Optional: add icons

To add icons, create an `icons` folder and add `icon16.png`, `icon48.png`, `icon128.png`. Then in `manifest.json` add:

```json
"action": {
  "default_popup": "popup.html",
  "default_icon": { "16": "icons/icon16.png", "48": "icons/icon48.png", "128": "icons/icon128.png" },
  "default_title": "Fill job form"
},
"icons": { "16": "icons/icon16.png", "48": "icons/icon48.png", "128": "icons/icon128.png" }
```

Without these, Chrome uses a default puzzle-piece icon.

## Where to check the API call from the extension

- **Popup → Network**: Open the extension popup, then right‑click inside the popup and choose **Inspect**. In the DevTools that open, go to the **Network** tab. Click **Process job and fill data**; you should see a request to `http://localhost:8000/api/v1/form-fields/map` (method POST). Click that request to see request payload and response.
- **Backend logs**: When the extension calls the API, your FastAPI server (e.g. uvicorn) will log the request (method, path, status). Watch the terminal where the backend is running.
- **Console**: In popup/content/background DevTools, filter logs by `JobAutofill` to inspect scrape, mapping, resume upload, and fill details.
