// ─── Widget Styles (Components) ───────────────────────────────────────────
// Questions, keywords, profile, uploads, skills, collapsed state
// Depends on: INPAGE_ROOT_ID (consts.js)

function getWidgetStylesComponents() {
  return `
      /* Common Questions — SaaS field navigator */
      #${INPAGE_ROOT_ID} .ja-cq-panel {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        overflow: hidden;
        background: #fff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
      }
      #${INPAGE_ROOT_ID} .ja-cq-panel-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 9px 12px;
        background: #f9fafb;
        border-bottom: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-cq-panel-count {
        font-size: 11px;
        font-weight: 600;
        color: #374151;
        letter-spacing: 0.02em;
        text-transform: uppercase;
      }
      #${INPAGE_ROOT_ID} .ja-cq-panel-hint {
        font-size: 11px;
        color: #9ca3af;
      }
      #${INPAGE_ROOT_ID} .ja-cq-items { display: flex; flex-direction: column; }
      #${INPAGE_ROOT_ID} .ja-cq-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 11px 12px;
        cursor: pointer;
        transition: background 0.12s;
        gap: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-cq-item:hover { background: #f0f7ff; }
      #${INPAGE_ROOT_ID} .ja-cq-item:active { background: #e0effe; }
      #${INPAGE_ROOT_ID} .ja-cq-item-b { border-bottom: 1px solid #f3f4f6; }
      #${INPAGE_ROOT_ID} .ja-cq-item-label {
        flex: 1;
        min-width: 0;
        font-size: 13px;
        font-weight: 500;
        color: #111827;
        line-height: 1.35;
      }
      #${INPAGE_ROOT_ID} .ja-cq-item:hover .ja-cq-item-label { color: #2563eb; }
      #${INPAGE_ROOT_ID} .ja-cq-item-arrow {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        color: #d1d5db;
        transition: color 0.12s, transform 0.12s;
      }
      #${INPAGE_ROOT_ID} .ja-cq-item-arrow svg { width: 13px; height: 13px; }
      #${INPAGE_ROOT_ID} .ja-cq-item:hover .ja-cq-item-arrow { color: #2563eb; transform: translateX(2px); }
      #${INPAGE_ROOT_ID} .ja-cq-editbar {
        padding: 9px 12px;
        background: #f9fafb;
        border-top: 1px solid #e5e7eb;
      }
      #${INPAGE_ROOT_ID} .ja-cq-editall {
        border: none;
        background: none;
        padding: 0;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 11px;
        font-weight: 600;
        color: #2563eb;
        letter-spacing: 0.01em;
      }
      #${INPAGE_ROOT_ID} .ja-cq-editall:hover { color: #1d4ed8; text-decoration: underline; }
      #${INPAGE_ROOT_ID} .ja-cq-editall .ja-q-svg-tiny { width: 10px; height: 10px; }
      /* legacy row styles kept for unique-questions path */
      #${INPAGE_ROOT_ID} .ja-cq-shell {
        border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; background: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-cq-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 12px; font-size: 13px; }
      #${INPAGE_ROOT_ID} .ja-cq-row-b { border-bottom: 1px solid #e5e7eb; }
      #${INPAGE_ROOT_ID} .ja-cq-q { flex: 1; min-width: 0; color: #6b7280; line-height: 1.35; padding-right: 8px; }
      #${INPAGE_ROOT_ID} .ja-cq-ans { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
      #${INPAGE_ROOT_ID} .ja-cq-val { font-weight: 500; color: #111827; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      #${INPAGE_ROOT_ID} .ja-cq-ico { display: flex; }
      #${INPAGE_ROOT_ID} .ja-cq-ico .ja-q-svg { width: 12px; height: 12px; }
      #${INPAGE_ROOT_ID} .ja-cq-ico .ja-cq-state { color: #22c55e; }
      #${INPAGE_ROOT_ID} .ja-cq-ico .ja-cq-warn { color: #d97706; }
      #${INPAGE_ROOT_ID} .ja-cq-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 10px; padding-top: 10px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-cq-meta-item { display: inline-flex; align-items: center; gap: 4px; }
      #${INPAGE_ROOT_ID} .ja-q-meta { width: 12px; height: 12px; stroke-width: 2; }
      #${INPAGE_ROOT_ID} .ja-accordion-content {
        padding: 10px 8px;
        font-size: 14px;
        color: #6b7280;
      }
      /* Map Answers button */
      #${INPAGE_ROOT_ID} .ja-map-btn-row {
        margin-top: 10px;
        display: flex;
        justify-content: center;
      }
      #${INPAGE_ROOT_ID} .ja-map-answers-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 7px 16px;
        background: #2563eb;
        color: #fff;
        border: none;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-map-answers-btn:hover { background: #1d4ed8; }
      #${INPAGE_ROOT_ID} .ja-map-answers-btn:disabled { opacity: 0.65; cursor: default; }
      #${INPAGE_ROOT_ID} .ja-map-answers-btn .ja-q-svg { width: 13px; height: 13px; }
      #${INPAGE_ROOT_ID} .ja-map-spinner {
        width: 12px;
        height: 12px;
        border: 2px solid rgba(255,255,255,0.4);
        border-top-color: #fff;
        border-radius: 50%;
        animation: ja-spin 0.7s linear infinite;
        flex-shrink: 0;
      }
      @keyframes ja-spin { to { transform: rotate(360deg); } }
      #${INPAGE_ROOT_ID} .ja-keywords-section { margin-bottom: 12px; }
      #${INPAGE_ROOT_ID} .ja-keywords-section label {
        display: block;
        font-size: 13px;
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
        border-radius: 6px;
        margin-bottom: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-resume-row span { flex: 1; font-size: 14px; color: #374151; }
      #${INPAGE_ROOT_ID} .ja-resume-row button {
        background: none;
        border: none;
        color: #0ea5e9;
        cursor: pointer;
        padding: 4px;
      }
      #${INPAGE_ROOT_ID} .ja-resume-select { display: none !important; }

      /* ── Searchable resume dropdown ─────────────────────────── */
      #${INPAGE_ROOT_ID} .ja-rs-dropdown {
        position: relative;
        width: 100%;
      }
      #${INPAGE_ROOT_ID} .ja-rs-trigger {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        height: 36px;
        padding: 0 10px;
        background: #fff;
        border: 1.5px solid #e5e7eb;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        color: #111827;
        cursor: pointer;
        transition: border-color 0.15s, box-shadow 0.15s;
        white-space: nowrap;
        overflow: hidden;
      }
      #${INPAGE_ROOT_ID} .ja-rs-trigger:hover {
        border-color: #93c5fd;
      }
      #${INPAGE_ROOT_ID} .ja-rs-trigger[aria-expanded="true"] {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.12);
      }
      #${INPAGE_ROOT_ID} .ja-rs-trigger-text {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        text-align: left;
      }
      #${INPAGE_ROOT_ID} .ja-rs-chevron {
        width: 14px;
        height: 14px;
        flex-shrink: 0;
        color: #9ca3af;
        transition: transform 0.18s;
      }
      #${INPAGE_ROOT_ID} .ja-rs-trigger[aria-expanded="true"] .ja-rs-chevron {
        transform: rotate(180deg);
      }
      #${INPAGE_ROOT_ID} .ja-rs-panel {
        position: absolute;
        top: calc(100% + 4px);
        left: 0;
        right: 0;
        z-index: 9999;
        background: #fff;
        border: 1.5px solid #e5e7eb;
        border-radius: 10px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06);
        overflow: hidden;
      }
      #${INPAGE_ROOT_ID} .ja-rs-search-wrap {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 10px;
        border-bottom: 1px solid #f3f4f6;
      }
      #${INPAGE_ROOT_ID} .ja-rs-search-ico {
        width: 14px;
        height: 14px;
        flex-shrink: 0;
        color: #9ca3af;
      }
      #${INPAGE_ROOT_ID} .ja-rs-search {
        flex: 1;
        border: none;
        outline: none;
        font-size: 13px;
        color: #111827;
        background: transparent;
        padding: 0;
        line-height: 1.4;
      }
      #${INPAGE_ROOT_ID} .ja-rs-search::placeholder { color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-rs-list {
        list-style: none;
        margin: 0;
        padding: 4px;
        max-height: 180px;
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: #e5e7eb transparent;
      }
      #${INPAGE_ROOT_ID} .ja-rs-list::-webkit-scrollbar { width: 5px; }
      #${INPAGE_ROOT_ID} .ja-rs-list::-webkit-scrollbar-track { background: transparent; }
      #${INPAGE_ROOT_ID} .ja-rs-list::-webkit-scrollbar-thumb { background: #e5e7eb; border-radius: 4px; }
      #${INPAGE_ROOT_ID} .ja-rs-option {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 7px 8px;
        border-radius: 6px;
        font-size: 13px;
        color: #374151;
        cursor: pointer;
        transition: background 0.1s;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      #${INPAGE_ROOT_ID} .ja-rs-option:hover,
      #${INPAGE_ROOT_ID} .ja-rs-option--focus {
        background: #f0f7ff;
        color: #1d4ed8;
      }
      #${INPAGE_ROOT_ID} .ja-rs-option--selected {
        background: #eff6ff;
        color: #1d4ed8;
        font-weight: 600;
      }
      #${INPAGE_ROOT_ID} .ja-rs-option--selected::after {
        content: "";
        display: inline-block;
        width: 8px;
        height: 8px;
        border-right: 2px solid #2563eb;
        border-bottom: 2px solid #2563eb;
        transform: rotate(45deg) translateY(-2px);
        flex-shrink: 0;
        margin-left: auto;
      }
      #${INPAGE_ROOT_ID} .ja-rs-badge-default {
        font-size: 10px;
        font-weight: 600;
        color: #2563eb;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 4px;
        padding: 1px 5px;
        flex-shrink: 0;
      }
      #${INPAGE_ROOT_ID} .ja-rs-empty {
        padding: 10px 12px;
        font-size: 12px;
        color: #9ca3af;
        text-align: center;
        margin: 0;
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
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.15s, border-color 0.15s;
      }
      #${INPAGE_ROOT_ID} .ja-kw-update-jd-btn .ja-kw-ico { width: 12px; height: 12px; flex-shrink: 0; }
      #${INPAGE_ROOT_ID} .ja-kw-update-jd-btn:hover { background: #f9fafb; border-color: #d1d5db; }
      #${INPAGE_ROOT_ID} .ja-job-form input, #${INPAGE_ROOT_ID} .ja-job-form select, #${INPAGE_ROOT_ID} .ja-job-form textarea {
        width: 100%;
        padding: 8px 10px;
        font-size: 14px;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        margin-bottom: 10px;
      }
      #${INPAGE_ROOT_ID} .ja-job-form label { display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px; }
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
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #9ca3af;
        margin: 0;
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
        font-size: 13px;
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
      #${INPAGE_ROOT_ID} .ja-keyword-card .ja-score-text { font-size: 13px; color: #6b7280; margin-bottom: 0; padding: 12px 14px; }
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
        font-size: 19px;
        font-weight: 700;
        line-height: 1;
      }
      #${INPAGE_ROOT_ID} .ja-kw-pct-sub {
        font-size: 9px;
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
        font-size: 11px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 6px;
        border: 0;
      }
      #${INPAGE_ROOT_ID} .ja-kw-line { margin: 0; font-size: 13px; line-height: 1.45; }
      #${INPAGE_ROOT_ID} .ja-kw-line-muted { color: #6b7280; }
      #${INPAGE_ROOT_ID} .ja-kw-strong { color: #111827; font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-kw-hilo { display: flex; gap: 12px; font-size: 11px; color: #9ca3af; }
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
      #${INPAGE_ROOT_ID} .ja-kw-tip-text { margin: 0; font-size: 12px; color: #111827; line-height: 1.4; }
      #${INPAGE_ROOT_ID} .ja-keyword-keywords-list {
        margin-top: 0;
        display: flex;
        flex-direction: column;
        gap: 16px;
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
      #${INPAGE_ROOT_ID} .ja-kw-priority-name { font-size: 13px; font-weight: 700; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-kw-priority-meta { font-size: 11px; font-weight: 600; color: #9ca3af; }
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
        font-size: 12px;
        line-height: 1.25;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      #${INPAGE_ROOT_ID} .ja-kw-chip--on .ja-kw-chip-name { color: #111827; font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-kw-chip--off .ja-kw-chip-name { color: #9ca3af; font-weight: 400; }
      #${INPAGE_ROOT_ID} .ja-kw-chip-freq { font-size: 10px; font-weight: 600; color: #9ca3af; flex-shrink: 0; }
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
      #${INPAGE_ROOT_ID} .ja-kw-suggest-title { font-size: 13px; font-weight: 700; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-sub { margin: 0 0 8px 0; font-size: 12px; color: #6b7280; }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-pills { display: flex; flex-wrap: wrap; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-kw-suggest-pill {
        display: inline-flex;
        align-items: center;
        padding: 4px 8px;
        font-size: 11px;
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
      /* Keyword tab — skeleton loading */
      @keyframes ja-kw-shimmer {
        0%   { background-position: -400px 0; }
        100% { background-position:  400px 0; }
      }
      #${INPAGE_ROOT_ID} .ja-kw-skel {
        background: linear-gradient(90deg, #f3f4f6 25%, #e9eaec 50%, #f3f4f6 75%);
        background-size: 400px 100%;
        animation: ja-kw-shimmer 1.3s ease infinite;
        border-radius: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-skeleton-score {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 16px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-skel-circle {
        width: 80px; height: 80px;
        border-radius: 50%;
        flex-shrink: 0;
      }
      #${INPAGE_ROOT_ID} .ja-kw-skel-copy {
        flex: 1; display: flex; flex-direction: column; gap: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-skel-badge  { height: 18px; width: 90px; border-radius: 6px; }
      #${INPAGE_ROOT_ID} .ja-kw-skel-line   { height: 13px; border-radius: 4px; }
      #${INPAGE_ROOT_ID} .ja-kw-skel-line-w80 { width: 80%; }
      #${INPAGE_ROOT_ID} .ja-kw-skel-line-w55 { width: 55%; }
      #${INPAGE_ROOT_ID} .ja-kw-skel-tip {
        height: 38px; margin: 0 0 0 0; border-top: 1px solid #e5e7eb; border-radius: 0;
        background: linear-gradient(90deg, #f3f4f6 25%, #e9eaec 50%, #f3f4f6 75%);
        background-size: 400px 100%;
        animation: ja-kw-shimmer 1.3s ease infinite;
      }
      #${INPAGE_ROOT_ID} .ja-kw-skeleton-list {
        display: flex; flex-direction: column; gap: 16px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-skel-section-head {
        display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
      }
      #${INPAGE_ROOT_ID} .ja-kw-skel-dot  { width: 8px; height: 8px; border-radius: 50%; }
      #${INPAGE_ROOT_ID} .ja-kw-skel-htitle { height: 13px; width: 90px; border-radius: 4px; }
      #${INPAGE_ROOT_ID} .ja-kw-skel-meta  { height: 11px; width: 60px; border-radius: 4px; margin-left: auto; }
      #${INPAGE_ROOT_ID} .ja-kw-skel-chip  {
        height: 34px; border-radius: 8px;
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
        font-size: 19px;
        font-weight: 700;
        color: #111827;
        line-height: 1.2;
      }
      #${INPAGE_ROOT_ID} .ja-profile-stat-success { color: #16a34a; }
      #${INPAGE_ROOT_ID} .ja-profile-stat-primary { color: #2563eb; }
      #${INPAGE_ROOT_ID} .ja-profile-stat-label {
        margin: 4px 0 0 0;
        font-size: 10px;
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
        font-size: 15px;
        flex-shrink: 0;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
      }
      #${INPAGE_ROOT_ID} .ja-prof-hero-text { flex: 1; min-width: 0; }
      #${INPAGE_ROOT_ID} .ja-profile-name { margin: 0; font-size: 15px; font-weight: 700; color: #111827; line-height: 1.25; }
      #${INPAGE_ROOT_ID} .ja-profile-title { margin: 2px 0 0 0; font-size: 13px; color: #9ca3af; }
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
        font-size: 11px;
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
        font-size: 13px;
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
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #6b7280;
      }
      #${INPAGE_ROOT_ID} .ja-prof-sec-count { font-size: 11px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-prof-empty { margin: 0; font-size: 13px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-prof-edu-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px;
        background: #fff;
      }
      #${INPAGE_ROOT_ID} .ja-prof-edu-school { margin: 0 0 4px 0; font-size: 13px; font-weight: 700; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-prof-edu-degree { margin: 0 0 6px 0; font-size: 12px; color: #6b7280; }
      #${INPAGE_ROOT_ID} .ja-prof-edu-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
      #${INPAGE_ROOT_ID} .ja-prof-edu-dates { font-size: 11px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-prof-badge {
        display: inline-flex;
        align-items: center;
        font-size: 10px;
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
      #${INPAGE_ROOT_ID} .ja-prof-exp-title { margin: 0; font-size: 13px; font-weight: 700; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-prof-exp-company { margin: 4px 0 0 0; font-size: 12px; font-weight: 500; color: #2563eb; }
      #${INPAGE_ROOT_ID} .ja-prof-exp-meta { margin: 4px 0 0 0; font-size: 11px; color: #9ca3af; }
      #${INPAGE_ROOT_ID} .ja-prof-exp-bullets {
        list-style: none;
        padding: 0;
        margin: 8px 0 0 0;
      }
      #${INPAGE_ROOT_ID} .ja-prof-exp-li {
        display: flex;
        gap: 8px;
        font-size: 12px;
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
        font-size: 11px;
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
      #${INPAGE_ROOT_ID} .ja-prof-upload-name { margin: 0; font-size: 13px; font-weight: 600; color: #111827; }
      #${INPAGE_ROOT_ID} .ja-prof-upload-meta { margin: 2px 0 0 0; font-size: 11px; color: #9ca3af; }
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
        font-size: 11px;
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
        font-size: 25px;
        cursor: move;
        box-shadow: 0 8px 24px rgba(14, 165, 233, 0.4);
        align-items: center;
        justify-content: center;
        transition: transform 0.2s;
      }
      #${INPAGE_ROOT_ID} .ja-mini:hover { transform: translateY(-50%) scale(1.05); }
      #${INPAGE_ROOT_ID}.collapsed .ja-mini { display: flex; }
    </style>
  `;
}
