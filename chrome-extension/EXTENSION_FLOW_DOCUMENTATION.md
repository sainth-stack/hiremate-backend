# OpsBrain Job Auto-Fill — Chrome Extension End-to-End Documentation

> Complete technical documentation covering architecture, flows, scraping, filling, Chrome APIs, techniques, and fallbacks.

---

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [Directory Structure & Packages](#2-directory-structure--packages)
3. [Manifest & Permissions](#3-manifest--permissions)
4. [Chrome APIs Reference](#4-chrome-apis-reference)
5. [End-to-End Scraping Flow](#5-end-to-end-scraping-flow)
6. [End-to-End Filling Flow](#6-end-to-end-filling-flow)
7. [Component Methods & Flows](#7-component-methods--flows)
8. [Field Detection Techniques](#8-field-detection-techniques)
9. [Human-Like Filling Techniques](#9-human-like-filling-techniques)
10. [Fallback Mechanisms](#10-fallback-mechanisms)
11. [Message Protocol](#11-message-protocol)
12. [APIs Used in the Extension (End-to-End Detailed)](#12-apis-used-in-the-extension-end-to-end-detailed)
13. [Extraction Techniques Over Different Forms / ATS Platforms](#13-extraction-techniques-over-different-forms--ats-platforms)

---

## 1. Overview & Architecture

### What the Extension Does

- **Scans** job application forms across all frames/iframes
- **Maps** detected fields to user profile/resume via LLM
- **Fills** forms with human-like typing to avoid bot detection
- **Supports** ATS platforms: Workday, Greenhouse, Lever, SmartRecruiters, Ashby, Taleo, Jobvite, iCIMS, SuccessFactors

### Architecture Diagram (Conceptual)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              popup.html + popup.js                           │
│  UI: Login, Profile, Scan & Auto-Fill, Saved Answers                         │
│  APIs: chrome.storage.local, chrome.tabs, chrome.runtime, chrome.scripting   │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                    chrome.runtime.sendMessage / chrome.tabs.sendMessage
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         background.js (Service Worker)                       │
│  Handlers: SAVE_RESUME, GET_RESUME, SCRAPE_ALL_FRAMES, FILL_ALL_FRAMES       │
│  APIs: chrome.runtime, chrome.tabs, chrome.scripting, chrome.webNavigation   │
│  Storage: IndexedDB (JobAutofillDB.resume)                                   │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
              chrome.tabs.sendMessage({ frameId })  (per frame)
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│   content.js (injected into each frame via content_scripts)                  │
│   Depends on: fieldScraper.js, humanFiller.js                                 │
│   Orchestrates: scrapeFields(), fillWithValues(), mountInPageUI()            │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
         Uses getScrapedFields()     Uses fillWithValuesHumanLike()
                                       │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────────────┐
│  fieldScraper.js │    │    humanFiller.js     │    │  In-page floating widget │
│  DOM traversal   │    │  humanType, humanSelect│    │  Profile, Resume, Cover  │
│  Shadow DOM      │    │  humanDateInput       │    │  Letter, Keywords, Jobs  │
│  Label detection │    │  humanUploadFile      │    │  chrome.storage.local    │
└─────────────────┘    └──────────────────────┘    └─────────────────────────┘
```

### Execution Context

| Component    | Context          | Access                              |
|-------------|------------------|-------------------------------------|
| `popup.js`  | Extension popup  | Extension APIs, `chrome.storage`     |
| `background.js` | Service worker | Extension APIs, IndexedDB          |
| `content.js`   | Web page        | DOM, `chrome.runtime.sendMessage`  |
| `fieldScraper.js` | Web page     | DOM (runs in content script)       |
| `humanFiller.js`  | Web page     | DOM (runs in content script)       |

---

## 2. Directory Structure & Packages

### File Layout

```
chrome-extension/
├── manifest.json              # MV3 manifest
├── background.js              # Service worker
├── content.js                 # Content script orchestrator (~4k lines)
├── popup.html                 # Popup UI
├── popup.css                  # Popup styles
├── popup.js                   # Popup logic & orchestration (~820 lines)
├── logo.png                   # Web-accessible asset
├── content-script/
│   ├── fieldScraper.js        # Field scraping engine (~1.1k lines)
│   └── humanFiller.js         # Human-like form filler (~1.1k lines)
├── test/
│   ├── README.md              # Test docs
│   ├── test_field_scraper.py  # Python tests
│   └── conftest.py            # Pytest config
├── test-pages/                # ATS simulation pages
│   ├── scraper-test.html
│   ├── greenhouse-style.html
│   ├── workday-style.html
│   ├── lever-style.html
│   └── linkedin-easy-apply-style.html
└── README.md
```

### Dependencies

**No npm/package.json** — pure JavaScript extension. Uses only:

- Native Chrome Extension APIs
- IndexedDB (browser)
- Fetch API
- DOM APIs

---

## 3. Manifest & Permissions

### manifest.json (Manifest V3)

```json
{
  "manifest_version": 3,
  "name": "OpsBrain - Job Auto-Fill",
  "version": "1.0.0",
  "permissions": ["storage", "activeTab", "scripting", "webNavigation", "tabs"],
  "host_permissions": ["<all_urls>"],
  "web_accessible_resources": [{"resources": ["logo.png"], "matches": ["<all_urls>"]}],
  "action": {
    "default_title": "Open Auto-Fill Assistant",
    "default_popup": "popup.html"
  },
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content-script/fieldScraper.js", "content-script/humanFiller.js", "content.js"],
    "run_at": "document_idle",
    "all_frames": true
  }],
  "background": {
    "service_worker": "background.js"
  }
}
```

### Permission Usage

| Permission     | Purpose                                                         |
|----------------|-----------------------------------------------------------------|
| `storage`      | `chrome.storage.local` — profile, custom answers, tokens        |
| `activeTab`    | Access active tab without explicit host permission on click     |
| `scripting`    | `chrome.scripting.executeScript` — inject content into frames    |
| `webNavigation` | `chrome.webNavigation.getAllFrames` — enumerate iframes      |
| `tabs`         | `chrome.tabs.query`, `chrome.tabs.create`, `chrome.tabs.sendMessage` |
| `<all_urls>`   | Inject content scripts and scrape/fill on any job site          |

### Content Script Loading Order

1. `fieldScraper.js` — defines `getScrapedFields`, `getScrapedFieldsWithExpandedOptions`, etc.
2. `humanFiller.js` — defines `fillWithValuesHumanLike`, `humanType`, etc.
3. `content.js` — orchestrator that uses both; registers message listeners.

---

## 4. Chrome APIs Reference

### chrome.storage

| Method                    | Usage                                                        |
|---------------------------|--------------------------------------------------------------|
| `storage.local.get(keys)` | Profile, customAnswers, accessToken, apiBase, loginPageUrl    |
| `storage.local.set(obj)`  | Persist tokens, profile, autofill context                    |
| `storage.local.remove(keys)` | Clear accessToken, AUTOFILL_CTX_KEY on 401                |
| `storage.onChanged`       | content.js listens for auth/config changes                    |

**Keys stored:**

- `accessToken`, `profile`, `customAnswers`, `resumeText`, `apiBase`, `loginPageUrl`, `AUTOFILL_CTX_KEY`

---

### chrome.tabs

| Method                          | Usage                                                      |
|---------------------------------|------------------------------------------------------------|
| `tabs.query({ active, currentWindow })` | Get active tab in popup                            |
| `tabs.create({ url })`          | Open login page, HireMate app                              |
| `tabs.sendMessage(tabId, msg, { frameId })` | Send SCRAPE_FIELDS, FILL_WITH_VALUES to content script |

---

### chrome.runtime

| Method / Event                 | Usage                                                       |
|--------------------------------|-------------------------------------------------------------|
| `runtime.sendMessage(msg)`      | popup/content → background (SCRAPE_ALL_FRAMES, FILL_ALL_FRAMES, etc.) |
| `runtime.onMessage`            | background.js — central message router                     |
| `runtime.onInstalled`          | background.js — optional setup                              |
| `runtime.getURL('logo.png')`   | content.js — resolve extension asset URL                    |

---

### chrome.scripting

| Method                               | Usage                                                    |
|--------------------------------------|----------------------------------------------------------|
| `scripting.executeScript({ target: { tabId, frameIds }, files: [...] })` | Inject content script into frame when “Receiving end does not exist” |
| `scripting.executeScript({ target: { tabId, allFrames: true }, func })`   | GET_ALL_FRAMES_HTML — run inline function in all frames  |
| `scripting.executeScript({ target: { tabId }, func, args })`             | SYNC_TOKEN_TO_HIREMATE_TAB, FETCH_TOKEN_FROM_OPEN_TAB     |

---

### chrome.webNavigation

| Method                          | Usage                                               |
|---------------------------------|-----------------------------------------------------|
| `webNavigation.getAllFrames({ tabId })` | Enumerate frame IDs for scraping/filling across frames |

Returns: `[{ frameId, url, parentFrameId }]`

---

### chrome.action

| Event / Property        | Usage                                          |
|-------------------------|------------------------------------------------|
| `action.onClicked`      | When extension icon clicked without popup — sends SHOW_WIDGET |

---

### IndexedDB (via background.js)

| Database / Store      | Purpose                          |
|------------------------|----------------------------------|
| `JobAutofillDB`       | Database name                    |
| `resume` (object store) | Resume blob; key: `"current"`  |

- **put**: `{ id: "current", buffer, name, updatedAt }`
- **get**: `store.get("current")`

---

## 5. End-to-End Scraping Flow

### High-Level Sequence

```
User clicks "Scan & Auto-Fill" in popup
    ↓
popup.js: getLLMMappingContext() — fetch profile, customAnswers, resumeText
    ↓
popup.js: sendMessageToAllFrames(tabId, () => ({ type: "SCRAPE_FIELDS", payload }))
    ↓
For each frame: chrome.tabs.sendMessage(tabId, msg, { frameId })
    ↓
content.js: onMessage("SCRAPE_FIELDS") → scrapeFields(payload)
    ↓
content.js → fieldScraper.getScrapedFields(options)
    ↓
fieldScraper: pre-expand Add another, query selectors, traverse Shadow DOM, extract labels
    ↓
Return fields[] per frame
    ↓
popup.js: merge fields from all frames, assign global index
    ↓
popup.js: POST /chrome-extension/form-fields/map with fields + profile + custom_answers + resume_text
    ↓
Backend LLM → mappings { index: { value, confidence, reason } }
    ↓
Trigger fill flow
```

### Scraping Payload

```javascript
{
  scope: "all",              // "all" | "current_document"
  expandSelectOptions: true,  // open dropdowns to get options
  preExpandEmployment: N,    // click "Add another" N times for employment
  preExpandEducation: M,      // click "Add another" M times for education
}
```

### Field Output Shape

```javascript
{
  index: number,           // global index
  frameId: number,         // frame
  frameLocalIndex: number, // index within frame
  selector: string,        // unique CSS/XPath-like selector
  domId: string | null,    // element id if available
  label: string,           // human-readable label
  name: string,
  id: string,
  type: string,            // text | select | date | file | checkbox | radio | richtext
  tag: string,
  required: boolean,
  placeholder: string,
  value: string,
  options: string[],       // for select fields
  validation: object,
  atsFieldType: string | null,  // resume | cover_letter | first_name | ...
  isStandardField: boolean,
}
```

### Background Alternative: SCRAPE_ALL_FRAMES

popup can also use background for scraping:

```javascript
chrome.runtime.sendMessage({
  type: "SCRAPE_ALL_FRAMES",
  tabId: tab.id,
  scope: "all",
  preExpandEmployment,
  preExpandEducation,
});
```

Background then:

1. Uses `chrome.webNavigation.getAllFrames({ tabId })` for frame IDs
2. For each frame: `chrome.tabs.sendMessage(tabId, { type: "SCRAPE_FIELDS", payload }, { frameId })`
3. On "Receiving end does not exist": `chrome.scripting.executeScript` with `files: ["content.js"]`, then retry
4. Merges results and returns `{ ok: true, fields: mergedFields }`

---

## 6. End-to-End Filling Flow

### High-Level Sequence

```
popup.js: fillMappedValuesForTab(tabId, fields, mappings, context)
    ↓
GET_RESUME → background → IndexedDB
    ↓
buildValuesByFrame(fields, mappings)  →  { frameId: { localIndex: value } }
buildFieldsByFrame(fields)            →  { frameId: [ { index, selector, domId, type } ] }
    ↓
sendMessageToAllFrames(tabId, (frameId) => ({
  type: "FILL_WITH_VALUES",
  payload: {
    values: valuesByFrame[frameId],
    fieldsForFrame: fieldsByFrame[frameId],
    resumeData,
    scope: "current_document",
  },
}))
    ↓
content.js: onMessage("FILL_WITH_VALUES") → fillWithValues(payload)
    ↓
content.js → humanFiller.fillWithValuesHumanLike(payload)
    ↓
humanFiller: for each field
  - Resolve element by selector / domId / index
  - Scroll into view, humanScrollTo()
  - Dispatch: file → humanUploadFile, select → humanSelect, date → humanDateInput,
    checkbox/radio → humanClick, contenteditable → humanTypeContentEditable,
    default → humanType
    ↓
Return { filledCount, resumeUploadCount, failedCount }
    ↓
popup.js: show completion status
```

### Background Alternative: FILL_ALL_FRAMES

```javascript
chrome.runtime.sendMessage({
  type: "FILL_ALL_FRAMES",
  payload: {
    tabId,
    valuesByFrame: { "0": { "0": "John", "1": "john@example.com" }, ... },
    resumeData: { buffer, name },
  },
});
```

Background sends `FILL_WITH_VALUES` per frame and aggregates `totalFilled`, `totalResumes`.

---

## 7. Component Methods & Flows

### fieldScraper.js — Exported / Used Functions

| Method                          | Description                                                                 |
|---------------------------------|-----------------------------------------------------------------------------|
| `getScrapedFields(options)`     | Main scraper: query DOM, traverse Shadow DOM, extract labels, return fields |
| `getScrapedFieldsWithExpandedOptions(options)` | Same + expand dropdowns to read options                              |
| `findAddAnotherLinks(doc, sectionHint)` | Find "Add another" buttons for employment/education                    |
| `expandDropdownForOptions(el, doc)` | Open dropdown, read options, close                                         |
| `traverseAllShadowRoots(root, callback, seen)` | Recursive Shadow DOM + slot traversal                               |
| `getSmartLabel(el, doc)`        | 13-strategy label detection                                                 |
| `normalizeFieldType(el)`        | Map element to normalized type (text, select, date, file, etc.)             |
| `detectATSFieldType(el, label)` | ATS-specific field type (first_name, resume, cover_letter, etc.)           |
| `createUniqueSelector(el, doc)` | Generate stable CSS selector                                                |
| `extractOptions(el)`            | Extract options from native `<select>`                                      |
| `isElementVisible(el, doc)`     | Visibility check via computed style                                         |
| `getAccessibleFrames(doc)`      | Get accessible iframes                                                       |

### humanFiller.js — Main Functions

| Method                            | Description                                                  |
|-----------------------------------|--------------------------------------------------------------|
| `fillWithValuesHumanLike(payload)`| Orchestrates fill for all fields in payload                 |
| `fillFieldHumanLike(field, value, meta, resumeData)` | Fill single field with type-specific logic            |
| `humanType(element, text)`        | Character-by-character typing with random delays             |
| `humanTypeContentEditable(element, text)` | Rich text editor filling via Selection API              |
| `humanSelect(element, value, knownOptions)` | Dropdown fill with async option wait                     |
| `humanDateInput(element, value)`   | Native date / Workday / generic datepicker support            |
| `humanUploadFile(input, resumeData)` | File upload via DataTransfer / native setter              |
| `humanClick(element, options)`    | Human-like click with mousemove, mousedown, mouseup          |
| `humanScrollTo(element)`          | Smooth scroll into view                                      |
| `setReactValue(element, value)`   | React-compatible value setter                                |
| `getNativeInputSetter(element)`   | Get native value setter from prototype                       |
| `clearField(element)`             | Ctrl+A + Delete, then native setter to ""                     |
| `fallbackFill(element, value)`    | Direct value set when human simulation fails                 |
| `waitForOptions(doc, triggerEl)`   | Wait for async dropdown options (max ~2.5s)                  |
| `detectPlatform(doc)`             | Detect ATS (greenhouse, workday, lever, etc.)                 |

### content.js — Main Functions

| Method                                 | Description                                                |
|----------------------------------------|------------------------------------------------------------|
| `scrapeFields(options)`                | Calls fieldScraper, returns `{ fields }`                   |
| `fillWithValues(payload)`              | Calls humanFiller, returns `{ filledCount, resumeUploadCount, failedCount }` |
| `fillFormRuleBased(payload)`           | Fallback rule-based fill (FIELD_MAP matching)              |
| `mountInPageUI()`                      | Mount floating widget                                      |
| `runKeywordAnalysisAndMaybeShowWidget()` | Keyword analysis, show match widget                     |
| `getAutofillContextFromApi()`           | Fetch profile from backend                                 |
| `fetchMappingsFromApi(fields, context)`| POST form-fields/map, return mappings                     |
| `updateWidgetAuthUI(root)`             | Sync auth state in widget                                  |

### popup.js — Main Functions

| Method                            | Description                                                |
|-----------------------------------|------------------------------------------------------------|
| `checkAuth()`                      | Show login vs app based on accessToken                     |
| `handleLogin(e)` / `handleSignup(e)` | Auth form handlers                                     |
| `loadAndCacheAutofillData()`       | Load profile, custom answers (10 min TTL)                  |
| `getLLMMappingContext()`           | Profile, customAnswers, resumeText for mapping             |
| `fillMappedValuesForTab(...)`      | Build valuesByFrame, fieldsByFrame, send to frames         |
| `sendMessageToAllFrames(tabId, msgBuilder)` | Broadcast to all frames                              |
| `sendMessageToFrame(tabId, frameId, msg)` | Single frame; inject content script and retry on error |
| `refreshTokenViaApi()`             | POST auth/refresh on 401                                   |
| `fetchWithAuthRetry(url, options)` | Fetch with 401 → refresh → retry                          |
| `getMappingCacheKey()` / `getCachedMapping()` | 5 min mapping cache                               |

---

## 8. Field Detection Techniques

### Selector Groups (fieldScraper.js)

| Category         | Selectors (concise)                                                                 |
|------------------|--------------------------------------------------------------------------------------|
| Text inputs      | `input[type=text|email|tel|url|search|number]`, `textarea`, `[contenteditable]`, `[role="textbox"]`, Workday `data-automation-id*="input"` |
| Selects          | `select`, React Select, MUI, Ant Design, ARIA combobox/listbox, Workday dropdowns    |
| Dates            | `input[type=date]`, datepicker classes, Workday dateSection*                         |
| Files            | `input[type=file]`, dropzone, Workday `file-upload-input`, Greenhouse `attachment-input` |
| Checkbox/Radio   | `input[type=checkbox|radio]`, `[role=checkbox|radio|switch]`, Workday automation ids |
| Multiselect      | `select[multiple]`, chip/tag patterns                                                |

### 13 Label Detection Strategies (getSmartLabel)

1. **`<label for="id">`** — explicit association
2. **Wrapping `<label>`** — parent label, text excluding inputs
3. **`aria-label`**
4. **`aria-labelledby`** — resolve referenced IDs
5. **Workday `data-automation-id`** — wrapper label or humanized automation id
6. **Placeholder** — used as label
7. **`name`** — humanized
8. **Preceding sibling text**
9. **Fieldset legend**
10. **Section heading** (h1–h6 in section/`[role="group"]`)
11. **`data-label`, `data-field-name`, `data-testid`, `data-field`**
12. **`formcontrolname`, `v-model`, `ng-model`**
13. **Greenhouse/Lever question wrapper** — `.application-question`, `.field`, `.question-text`, etc.

### Shadow DOM Traversal

```javascript
traverseAllShadowRoots(root, callback, seen)
```

- Uses `TreeWalker` for performance
- Processes `node.shadowRoot` when present
- Optional: `chrome.dom.openOrClosedShadowRoot` for closed roots
- Handles `<slot>` and `assignedElements({ flatten: true })`

### Iframe Handling

- `getAccessibleFrames(doc)` — `doc.querySelectorAll("iframe, frame")`, access via `contentDocument`
- Scraping runs per frame; background merges by `frameId`
- Filling sends payload per frame with `valuesByFrame[frameId]`

### Visibility Check (isElementVisible)

- Walk up DOM, check `getComputedStyle`: `display`, `visibility`, `opacity`
- Skip `aria-hidden="true"`
- Avoid `getBoundingClientRect` for off-screen elements

### ATS Platform Detection (detectPlatform)

- URL + first 5k chars of HTML
- Patterns: greenhouse, workday, lever, smartrecruiters, ashby, taleo, jobvite, icims, successfactors
- Returns `"greenhouse" | "workday" | "lever" | ... | "generic"`

---

## 9. Human-Like Filling Techniques

### humanType (Text Inputs)

1. Focus field
2. Clear: Ctrl+A + Delete + native setter to `""`
3. Per character:
   - Dispatch `keydown`
   - Set value via native setter (React-aware)
   - Dispatch `input` (InsertText)
   - Dispatch `keyup`
   - Random delay 8–20 ms (occasional 20–30 ms pause)
4. Dispatch `change`, `blur`

### humanTypeContentEditable

1. Scroll, click, focus
2. Clear via Selection API: `selectNodeContents`, then `textContent = ""`
3. Per character: append to `textContent`, move cursor, dispatch `input`
4. Random delay 6–15 ms per char

### humanSelect (Dropdowns)

1. Click center of combobox/input
2. If `knownOptions` provided: find text match, click option
3. Else: type search text, call `waitForOptions` (max ~2.5 s)
4. Match option by text (exact, startswith, includes)
5. Support `aria-activedescendant` (Workday)
6. Click matching option, verify selection

### humanDateInput

- **Native `input[type=date]`**: set value via native setter, dispatch change/blur
- **Workday**: separate MM/DD/YYYY inputs; type only relevant part per automation id
- **Generic datepicker**: type `MM Tab DD Tab YYYY` with `sendTabKey`

### humanUploadFile

1. Create `File` from resume buffer
2. Create `DataTransfer`, set `files`
3. Use native `HTMLInputElement` value setter or `Object.defineProperty` to assign files
4. Dispatch `change`, `input`

### React Value Handling

```javascript
getNativeInputSetter(element)  // HTMLInputElement.prototype.value setter
setReactValue(element, value)  // native setter + _valueTracker reset + input/change
```

---

## 10. Fallback Mechanisms

### Scraping Fallbacks

| Scenario              | Fallback                                         |
|-----------------------|--------------------------------------------------|
| Enhanced scraper fails| Legacy scraper (content.js `getFillableFields`)   |
| Include hidden        | Try both include/exclude hidden                   |
| Dropdown options      | `expandSelectOptions: false` → skip expansion    |
| Content script missing| `executeScript` inject, then retry message        |

### Filling Fallbacks

| Scenario           | Fallback                                      |
|-------------------|-----------------------------------------------|
| humanType fails   | `fallbackFill` (direct setReactValue)         |
| Selector invalid  | Resolve by domId, then by index               |
| React value stuck | `_valueTracker.setValue("")` + native setter  |
| Async dropdown    | `waitForOptions` retry loop                   |

### Auth Fallbacks

| Scenario      | Fallback                                         |
|---------------|--------------------------------------------------|
| 401           | `refreshTokenViaApi` → retry with new token       |
| Refresh fails | `FETCH_TOKEN_FROM_OPEN_TAB` (sync from HireMate) |
| No token      | Clear `AUTOFILL_CTX_KEY`, show login             |

### Frame Injection Fallback

When `chrome.tabs.sendMessage` throws "Receiving end does not exist":

```javascript
await chrome.scripting.executeScript({
  target: { tabId, frameIds: [frameId] },
  files: ["content.js"]
});
// Retry sendMessage
```

---

## 11. Message Protocol

### Messages: popup/content → background

| Type                  | Payload                                           | Response                         |
|-----------------------|---------------------------------------------------|----------------------------------|
| `SAVE_RESUME`         | `{ buffer, name }`                                | `{ ok, error? }`                 |
| `GET_RESUME`          | —                                                 | `{ ok, data: { buffer, name } }` |
| `OPEN_LOGIN_TAB`      | `{ url }`                                        | `{ ok, error? }`                 |
| `SYNC_TOKEN_TO_HIREMATE_TAB` | `{ token }`                               | Fire-and-forget                  |
| `FETCH_TOKEN_FROM_OPEN_TAB` | —                                        | `{ ok, token }`                  |
| `GET_ALL_FRAMES_HTML` | —                                                 | `{ ok, html, error? }`            |
| `SCRAPE_ALL_FRAMES`   | `{ tabId, scope, preExpandEmployment, preExpandEducation }` | `{ ok, fields, error? }` |
| `FILL_ALL_FRAMES`     | `{ tabId, valuesByFrame, resumeData }`            | `{ ok, totalFilled, totalResumes }` |

### Messages: background/popup → content

| Type                | Payload                                                                 | Response                          |
|---------------------|-------------------------------------------------------------------------|-----------------------------------|
| `SHOW_WIDGET`       | —                                                                      | `{ ok }`                          |
| `SCRAPE_FIELDS`     | `{ scope, expandSelectOptions, preExpandEmployment, preExpandEducation }` | `{ ok, fields, error? }`       |
| `FILL_WITH_VALUES`  | `{ values, fieldsForFrame, resumeData, scope }`                         | `{ ok, filledCount, resumeUploadCount, failedCount }` |
| `FILL_FORM`         | Rule-based payload                                                     | `{ ok, ... }`                     |

---

## 12. APIs Used in the Extension (End-to-End Detailed)

### API Base & Auth Flow

| Item | Value |
|------|-------|
| **Default API Base** | `http://localhost:8000/api` |
| **Config key** | `apiBase` in `chrome.storage.local` |
| **Auth header** | `Authorization: Bearer {accessToken}` |
| **401 handling** | `refreshTokenViaApi()` → retry once with new token |

### Backend APIs — Complete Reference

#### 1. Autofill Context

| Property | Value |
|----------|-------|
| **Method** | `GET` |
| **Path** | `{apiBase}/chrome-extension/autofill/context` |
| **Headers** | `Authorization: Bearer {token}`, `Content-Type: application/json` |
| **Response** | `{ profile, resume_text, resume_url, resume_name, custom_answers }` |
| **Used by** | popup.js (`getLLMMappingContext`), content.js widget |
| **Caching** | 10 min TTL in `chrome.storage.local` under `AUTOFILL_CTX_KEY` |

**Flow**: Popup opens → `loadAndCacheAutofillData()` → fetch context → store in `AUTOFILL_CTX_KEY` → use for mapping and fill.

---

#### 2. Form Field Mapping (LLM)

| Property | Value |
|----------|-------|
| **Method** | `POST` |
| **Path** | `{apiBase}/chrome-extension/form-fields/map` |
| **Headers** | `Authorization: Bearer {token}`, `Content-Type: application/json` |
| **Request body** | `{ fields, profile, custom_answers, resume_text }` |
| **Response** | `{ mappings: { "0": { value, confidence, reason }, ... } }` |
| **Used by** | popup.js (Scan & Auto-Fill), content.js in-page widget |
| **Cache** | 5 min TTL by `getMappingCacheKey(fields, context)` |

**Request shape**:
```json
{
  "fields": [
    { "index": 0, "label": "First name", "type": "text", "required": true, "selector": "...", "options": [] }
  ],
  "profile": { "firstName": "John", "lastName": "Doe", "email": "...", "skills": "..." },
  "custom_answers": { "question": "answer" },
  "resume_text": "..." 
}
```

**Response shape**:
```json
{
  "mappings": {
    "0": { "value": "John", "confidence": 1.0, "reason": "Mapped from profile first_name", "type": "input" }
  }
}
```

---

#### 3. Resume File Proxy

| Property | Value |
|----------|-------|
| **Method** | `GET` |
| **Path** | `{apiBase}/chrome-extension/autofill/resume/{file_name}` |
| **Headers** | `Authorization: Bearer {token}` |
| **Response** | Binary PDF/file stream |
| **Used by** | content.js widget (when autofill context provides `resume_url`) |

---

#### 4. Keywords / Job Description Analysis

| Property | Value |
|----------|-------|
| **Method** | `POST` |
| **Path** | `{apiBase}/chrome-extension/keywords/analyze` |
| **Headers** | `Authorization: Bearer {token}`, `Content-Type: application/json` |
| **Request body** | `{ job_description?, page_html?, url?, resume_text?, resume_id? }` |
| **Response** | `{ total_keywords, matched_count, percent, high_priority, low_priority, job_description }` |
| **Used by** | content.js (`runKeywordAnalysisAndMaybeShowWidget`), popup.js |

**Fallback**: If `job_description` is short/missing and `page_html` is long enough, backend parses JD from HTML via `parse_job_description_from_html()`.

---

#### 5. Tailor Context (Resume Generator)

| Property | Value |
|----------|-------|
| **Method** | `POST` |
| **Path** | `{apiBase}/chrome-extension/tailor-context` |
| **Request body** | `{ job_description?, job_title?, url?, page_html? }` |
| **Used by** | content.js before opening resume-generator page |

---

#### 6. Cover Letter Upsert

| Property | Value |
|----------|-------|
| **Method** | `POST` |
| **Path** | `{apiBase}/chrome-extension/cover-letter/upsert` |
| **Request body** | `{ job_url?, page_html?, job_title? }` |
| **Response** | `{ content, job_title }` |
| **Used by** | content.js widget |

---

#### 7. Jobs CRUD

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `{apiBase}/chrome-extension/jobs` | Save job (company, position, location, job_description, etc.) |
| `GET` | `{apiBase}/chrome-extension/jobs` | List saved jobs (`?status=applied` optional) |
| `PATCH` | `{apiBase}/chrome-extension/jobs/{job_id}` | Update job status |

**Used by**: content.js widget (job save form), popup.js.

---

#### 8. Activity Tracking

| Property | Value |
|----------|-------|
| **Method** | `POST` |
| **Path** | `{apiBase}/activity/track` |
| **Request body** | `{ event_type, page_url?, metadata? }` |
| **Event types** | `career_page_view`, `autofill_used` |
| **Used by** | content.js, popup.js |

---

#### 9. Auth APIs

| Method | Path | Request | Response |
|--------|------|---------|----------|
| `POST` | `{apiBase}/auth/login` | `{ email, password }` | `{ access_token }` |
| `POST` | `{apiBase}/auth/register` | `{ name, email, password }` | `{ access_token }` |
| `POST` | `{apiBase}/auth/refresh` | `Authorization: Bearer {oldToken}` | `{ access_token }` |

---

#### 10. Other Resume APIs (Used by Extension)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `{apiBase}/resume/workspace` | List resumes + tailor context |
| `GET` | `{apiBase}/resume/{id}/file` | Download resume PDF |

---

#### 11. Job Page Detection (Optional / LLM)

| Property | Value |
|----------|-------|
| **Method** | `POST` |
| **Path** | `{apiBase}/chrome-extension/job-page-detect` |
| **Request body** | `{ url, title, snippet }` |
| **Response** | `{ is_job_page: boolean }` |
| **Used by** | content.js (`isJobPageViaLLM`) when URL does not match known career patterns |

**Note**: Used as fallback when `isCareerPage(url)` returns false, to decide whether to run keyword analysis.

---

### API Call Flow (Scan & Auto-Fill)

```
1. getLLMMappingContext()
   → GET /chrome-extension/autofill/context (or use cached)

2. sendMessageToAllFrames("SCRAPE_FIELDS")
   → (Chrome messaging, no HTTP)

3. fetchWithAuthRetry(POST /chrome-extension/form-fields/map)
   → { fields, profile, custom_answers, resume_text }

4. chrome.runtime.sendMessage("GET_RESUME")
   → (IndexedDB via background, no HTTP)

5. sendMessageToAllFrames("FILL_WITH_VALUES")
   → (Chrome messaging, no HTTP)

6. fetchWithAuthRetry(POST /activity/track)
   → { event_type: "autofill_used", page_url }
```

---

## 13. Extraction Techniques Over Different Forms / ATS Platforms

### Platform-Specific Detection

The scraper and filler adapt to ATS platforms via:

- **URL patterns**: `greenhouse.io`, `boards.greenhouse`, `workday.com`, `myworkdayjobs`, `lever.co`, `smartrecruiters.com`, `ashbyhq.com`, `taleo.net`, `jobvite.com`, `icims.com`, `successfactors`
- **DOM markers**: First ~5k chars of `documentElement.innerHTML`

---

### Greenhouse-Style Forms

| Technique | Implementation |
|-----------|----------------|
| **Container** | `.application-question`, `.field`, `.question`, `.field-wrapper` |
| **Label** | `.question-text`, `.application-label`, `label`, `.label`, `legend` |
| **Name pattern** | `job_application[first_name]`, `job_application[answers][custom_question_N]` |
| **Selects** | `[data-provides="select"]`, `[data-provides="typeahead"]` |
| **File** | `[data-field="resume"]`, `.attachment-input` |

**Extraction**: `getSmartLabel` strategy 13 — question wrapper with `.question-text` / `.application-label`.

---

### Workday-Style Forms

| Technique | Implementation |
|-----------|----------------|
| **IDs** | `data-automation-id` on inputs and wrappers |
| **Input pattern** | `data-automation-id*="input"`, `*="textInput"`, `*="textArea"` |
| **Dropdown** | `*="dropdown"`, `*="selectWidget"`, `*="formSelect"` |
| **Date** | `*="dateSectionDay"`, `*="dateSectionMonth"`, `*="dateSectionYear"` |
| **File** | `*="file-upload-input"`, `*="resume-upload"`, `*="file"` |
| **Checkbox/Radio** | `*="checkbox"`, `*="radioButton"` |
| **Label** | Strategy 5: `data-automation-id` wrapper with sibling label or humanized automation id |

**Filling**: Separate MM/DD/YYYY inputs; `humanDateInput` types only the relevant part per `data-automation-id`.

---

### Lever-Style Forms

| Technique | Implementation |
|-----------|----------------|
| **Container** | `.application-field`, `.application-form`, `.custom-question-field` |
| **Label** | `.application-label`, `label[for]` |
| **Select** | `.application-field select` |

---

### Generic / React / Radix / MUI Forms

| Technique | Implementation |
|-----------|----------------|
| **Text inputs** | `input[formcontrolname]`, `input[v-model]`, `mat-input-element`, `[role="textbox"]` |
| **Selects** | `[class*="react-select"]`, `.MuiSelect-root`, `.ant-select`, `[role="combobox"]`, `[aria-haspopup="listbox"]` |
| **Dates** | `.react-datepicker__input-container input`, `.MuiDatePicker-root input`, `.ant-picker-input` |
| **Rich text** | `.ql-editor`, `.DraftEditor-root`, `.ProseMirror`, `.tox-edit-area`, `.ck-editor__editable` |

---

### Dropdown Option Extraction

| Scenario | Method |
|----------|--------|
| **Native `<select>`** | `extractOptions()` — `Array.from(el.options)` |
| **ARIA combobox** | `aria-controls` / `aria-owns` → `querySelectorAll('[role="option"]')` |
| **Expand-on-demand** | `expandDropdownForOptions()` — click to open, read options, close (skips phone country pickers via `isPhoneCountryOption`) |

---

### Deduplication & Filtering

| Technique | Purpose |
|-----------|---------|
| **Element reference** | Primary dedup key to avoid counting the same field twice |
| **Selector + name + label** | Fallback dedup when element ref is unavailable |
| **isNonFillableAuxiliaryElement** | Skips Back to jobs, Submit, extension UI, intl-tel-input internals, duplicate Remix selects |
| **Visibility** | `isElementVisible()` — `display`, `visibility`, `opacity`, `aria-hidden` |

---

### ATS Field Type Detection (`detectATSFieldType`)

Merges `name`, `id`, `label`, `placeholder`, `data-automation-id`, `aria-label`, `data-field` into one string; matches regex for:

`resume`, `cover_letter`, `first_name`, `last_name`, `full_name`, `email`, `phone`, `linkedin`, `portfolio`, `city`, `state`, `country`, `postal_code`, `address`, `school`, `degree`, `major`, `graduation_year`, `notice_period`, `company`, `job_title`, `start_date`, `end_date`, `salary`, `work_authorization`, `sponsorship`, `gender`, `veteran_status`, `disability_status`, `ethnicity`, `referral_source`, `years_experience`, `skills`, `languages`, `certification`, `custom`

---

### Unique Selector Generation (`createUniqueSelector`)

1. `#id` if unique
2. `form input[name="x"]` if unique within form
3. `[data-testid]`, `[data-field]`, `[data-automation-id]`, etc. if unique
4. Fallback: DOM path with `tag:nth-of-type(N)` and up to 2 classes (excluding `ng-`, `_`, `js-`)

---

## Appendix: Quick Reference

### Default URLs

- **API Base**: `http://localhost:8000/api`
- **Login page**: `http://localhost:5173/login`

### Log Prefixes

- `[JobAutofill][background]`
- `[JobAutofill][popup]`
- `[JobAutofill][content]`
- `[JobAutofill][scraper]`
- `[JobAutofill][filler]`

### Testing

1. Load unpacked extension from `chrome-extension/`
2. Use `test-pages/` for ATS-style forms
3. `scraper-test-request` / `scraper-test-response` custom events for scraper tests
4. Inspect popup: right-click → Inspect → Network tab for API calls
