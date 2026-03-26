// ─── Widget Styles (Base) ─────────────────────────────────────────────────
// Layout, header, tabs, body, autofill hero, action buttons, accordions
// Depends on: INPAGE_ROOT_ID (consts.js)

function getWidgetStylesBase() {
  return `
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
        font-size: 17px;
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
        font-size: 13px;
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
  font-size: 13px; /* text-xs */
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
        font-size: 15px;
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

      #${INPAGE_ROOT_ID} .ja-autofill-tab { display: flex; flex-direction: column; }
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
        font-size: 11px;
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
        font-size: 12px;
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
        font-size: 11px;
        margin-bottom: 6px;
      }
      #${INPAGE_ROOT_ID} .ja-progress-label-row .ja-progress-label { font-weight: 600; color: rgba(255,255,255,0.72); }
      #${INPAGE_ROOT_ID} .ja-progress-label-row .ja-progress-pct { font-weight: 700; color: #fff; font-size: 11px; }
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
        font-size: 14px;
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

  font-size: 15px;
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
      #${INPAGE_ROOT_ID} .ja-fill-controls .ja-fill-label { font-size: 13px; color: rgba(255,255,255,0.9); font-weight: 600; }
      #${INPAGE_ROOT_ID} .ja-fill-controls-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
      #${INPAGE_ROOT_ID} .ja-stop { padding: 8px 14px; background: #dc2626; color: #fff; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-stop:hover { background: #b91c1c; }
      #${INPAGE_ROOT_ID} .ja-skip-next { padding: 8px 14px; background: rgba(255,255,255,0.2); color: #fff; border: 1px solid rgba(255,255,255,0.4); border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; }
      #${INPAGE_ROOT_ID} .ja-skip-next:hover { background: rgba(255,255,255,0.3); }
      #${INPAGE_ROOT_ID} .ja-continue-fill { width: 100%; padding: 10px 16px; background: #16a34a; color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 0; }
      #${INPAGE_ROOT_ID} .ja-continue-fill:hover { background: #15803d; }
      #${INPAGE_ROOT_ID} .ja-auto-advance { display: flex; align-items: center; gap: 8px; margin-top: 2px; font-size: 12px; color: rgba(255,255,255,0.88); cursor: pointer; }
      #${INPAGE_ROOT_ID} .ja-auto-advance input { cursor: pointer; }
    #${INPAGE_ROOT_ID} .ja-cache-enable {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(255,255,255,0.88);
  font-size: 12px;
  margin-top: 2px;
}
      #${INPAGE_ROOT_ID} .ja-cache-enable input { cursor: pointer; }

      #${INPAGE_ROOT_ID} .ja-autofill-footer-stats {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        padding: 8px 14px;
        font-size: 11px;
        color: #64748b;
        background: rgba(241, 245, 249, 0.65);
        border-top: 1px solid #e5e7eb;
        margin: 0 -8px -10px;
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
  font-size: 12px;
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

  stroke: currentColor;
  stroke-width: 2;
  color: #374151;
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
        font-size: 12px;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-status {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: #9ca3af;
        font-weight: 400;
      }
      #${INPAGE_ROOT_ID} .ja-accordion-status-text {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 12px;
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
        font-size: 11px;
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
  font-size: 14px;

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
  font-size: 15px;
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
      #${INPAGE_ROOT_ID} .ja-resume-accordion-row .ja-resume-select { flex: 1; padding: 6px 10px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 14px; }
      #${INPAGE_ROOT_ID} .ja-resume-preview-hint { font-size: 12px; color: #6b7280; margin: 4px 0 0 0; }
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
  font-size: 13px;
  color: #111827;
}

/* Letter text */
#${INPAGE_ROOT_ID} .ja-cover-letter-text {
  font-size: 13px;
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
        font-size: 13px;
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
        font-size: 13px;
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
        font-size: 10px;
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
        font-size: 11px;
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

  `;
}
