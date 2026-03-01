/**
 * Professional Match Widget - LinkedIn/Grammarly-style keyword match display
 * Transforms API response { high_priority: [{keyword, matched}], low_priority: [...] } into actionable UI
 */
class ProfessionalMatchWidget {
  constructor() {
    this.container = null;
  }

  /** Transform API format to widget format.
   * API returns: high_priority: [{keyword: "React", matched: true}, ...] */
  transformApiData(data) {
    const toGroups = (arr) => {
      const matched = [];
      const missing = [];
      for (const item of arr || []) {
        const kw = typeof item === "object" ? (item.keyword || "") : String(item);
        if (!kw) continue;
        if (typeof item === "object" && item.matched === true) matched.push(kw);
        else missing.push(kw);
      }
      return { matched, missing };
    };
    return {
      percent: data.percent || 0,
      matched_count: data.matched_count || 0,
      total_keywords: data.total_keywords || 0,
      high_priority: toGroups(data.high_priority || []),
      low_priority: toGroups(data.low_priority || []),
      job_description: data.job_description,
    };
  }

  create(matchData) {
    const raw = typeof matchData.matched_count === "number" ? matchData : this.transformApiData(matchData);
    const { percent, matched_count, total_keywords, high_priority, low_priority } = raw;
    const level = this.getMatchLevel(percent);

    const html = `
      <div id="opsbrain-match-widget" class="opsbrain-widget opsbrain-slide-in">
        <div class="opsbrain-widget-header ${level.class}">
          <div class="opsbrain-score-circle">
            <svg class="opsbrain-progress-ring" width="80" height="80">
              <circle class="opsbrain-progress-ring-bg" cx="40" cy="40" r="35"/>
              <circle class="opsbrain-progress-ring-fill" cx="40" cy="40" r="35"
                style="stroke-dasharray: ${2 * Math.PI * 35}; stroke-dashoffset: ${2 * Math.PI * 35 * (1 - percent / 100)};"/>
            </svg>
            <div class="opsbrain-score-text">
              <div class="opsbrain-score-value">${Math.round(percent)}%</div>
              <div class="opsbrain-score-label">Match</div>
            </div>
          </div>
          <div class="opsbrain-match-summary">
            <h3 class="opsbrain-match-title">
              <span class="opsbrain-match-icon">${level.icon}</span> ${level.title}
            </h3>
            <p class="opsbrain-match-subtitle">${level.subtitle}</p>
          </div>
          <button class="opsbrain-close-btn" aria-label="Close">×</button>
        </div>
        <div class="opsbrain-widget-body">
          <div class="opsbrain-stats-grid">
            <div class="opsbrain-stat">
              <div class="opsbrain-stat-value">${matched_count}</div>
              <div class="opsbrain-stat-label">Keywords Matched</div>
            </div>
            <div class="opsbrain-stat">
              <div class="opsbrain-stat-value">${total_keywords}</div>
              <div class="opsbrain-stat-label">Total Keywords</div>
            </div>
          </div>
          ${this.renderKeywordSection("⚠ High Priority Missing", high_priority?.missing || [])}
          ${this.renderKeywordSection("✓ Matched Keywords", high_priority?.matched || [], "success")}
          ${this.renderKeywordSection("Optional Keywords", low_priority?.missing || [], "optional")}
          <div class="opsbrain-actions">
            <button class="opsbrain-btn opsbrain-btn-primary" id="opsbrain-tailor-resume">Tailor Resume</button>
            <button class="opsbrain-btn opsbrain-btn-secondary" id="opsbrain-dismiss">Continue Anyway</button>
          </div>
        </div>
      </div>
    `;

    this.container = document.createElement("div");
    this.container.innerHTML = html;
    document.body.appendChild(this.container.firstElementChild);
    this.injectStyles();
    this.attachEventListeners();
  }

  getMatchLevel(percent) {
    if (percent >= 80) return { class: "excellent", icon: "🎯", title: "Excellent Match!", subtitle: "Your profile aligns very well with this role" };
    if (percent >= 60) return { class: "good", icon: "✓", title: "Good Match", subtitle: "Consider adding a few keywords to improve" };
    if (percent >= 40) return { class: "fair", icon: "⚠", title: "Fair Match", subtitle: "Tailor your resume to improve your chances" };
    return { class: "poor", icon: "⚡", title: "Low Match", subtitle: "Strongly recommend tailoring your resume" };
  }

  renderKeywordSection(title, keywords, type = "default") {
    if (!keywords || keywords.length === 0) return "";
    const limit = type === "optional" ? 5 : 10;
    const tags = keywords.slice(0, limit).map((kw) => `<span class="opsbrain-keyword-tag ${type}">${this.escapeHtml(String(kw))}</span>`).join("");
    const more = keywords.length > limit ? `<span class="opsbrain-more-count">+${keywords.length - limit} more</span>` : "";
    return `<div class="opsbrain-keyword-section"><h4 class="opsbrain-section-title">${title}</h4><div class="opsbrain-keyword-list">${tags}${more}</div></div>`;
  }

  escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  injectStyles() {
    if (document.getElementById("opsbrain-widget-styles")) return;
    const style = document.createElement("style");
    style.id = "opsbrain-widget-styles";
    style.textContent = `
      .opsbrain-widget{position:fixed;top:20px;right:20px;width:420px;max-width:calc(100vw - 40px);background:#fff;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.12);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;z-index:2147483647;overflow:hidden}
      .opsbrain-slide-in{animation:opsbrainSlideIn .4s cubic-bezier(.16,1,.3,1)}
      @keyframes opsbrainSlideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
      @keyframes opsbrainSlideOut{from{transform:translateX(0);opacity:1}to{transform:translateX(100%);opacity:0}}
      .opsbrain-widget-header{padding:24px;color:#fff;position:relative}
      .opsbrain-widget-header.excellent{background:linear-gradient(135deg,#11998e 0%,#38ef7d 100%)}
      .opsbrain-widget-header.good{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%)}
      .opsbrain-widget-header.fair{background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%)}
      .opsbrain-widget-header.poor{background:linear-gradient(135deg,#fa709a 0%,#fee140 100%)}
      .opsbrain-score-circle{position:absolute;top:20px;right:20px}
      .opsbrain-progress-ring-bg{fill:none;stroke:rgba(255,255,255,.2);stroke-width:6}
      .opsbrain-progress-ring-fill{fill:none;stroke:#fff;stroke-width:6;stroke-linecap:round;transform:rotate(-90deg);transform-origin:center;transition:stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)}
      .opsbrain-score-text{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center}
      .opsbrain-score-value{font-size:24px;font-weight:700;line-height:1}
      .opsbrain-score-label{font-size:10px;opacity:.9;text-transform:uppercase;letter-spacing:.5px}
      .opsbrain-match-summary{max-width:280px}
      .opsbrain-match-title{font-size:20px;font-weight:700;margin:0 0 8px;display:flex;align-items:center;gap:8px}
      .opsbrain-match-icon{font-size:24px}
      .opsbrain-match-subtitle{margin:0;opacity:.9;font-size:14px;line-height:1.4}
      .opsbrain-close-btn{position:absolute;top:16px;right:100px;background:rgba(255,255,255,.2);border:none;color:#fff;width:32px;height:32px;border-radius:50%;font-size:24px;cursor:pointer;display:flex;align-items:center;justify-content:center}
      .opsbrain-close-btn:hover{background:rgba(255,255,255,.3)}
      .opsbrain-widget-body{padding:24px;max-height:500px;overflow-y:auto}
      .opsbrain-stats-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
      .opsbrain-stat{text-align:center;padding:16px;background:#f8f9fa;border-radius:8px}
      .opsbrain-stat-value{font-size:32px;font-weight:700;color:#667eea}
      .opsbrain-stat-label{font-size:12px;color:#6c757d;margin-top:4px}
      .opsbrain-keyword-section{margin-bottom:20px}
      .opsbrain-section-title{font-size:14px;font-weight:600;margin:0 0 12px;color:#2d3748}
      .opsbrain-keyword-list{display:flex;flex-wrap:wrap;gap:8px}
      .opsbrain-keyword-tag{display:inline-block;padding:6px 12px;background:#e9ecef;border-radius:16px;font-size:12px;color:#495057;font-weight:500}
      .opsbrain-keyword-tag.success{background:#d4edda;color:#155724}
      .opsbrain-keyword-tag.optional{background:#fff3cd;color:#856404}
      .opsbrain-more-count{color:#667eea;font-size:12px;font-weight:600}
      .opsbrain-actions{display:flex;gap:12px;margin-top:24px}
      .opsbrain-btn{flex:1;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;border:none;transition:all .2s}
      .opsbrain-btn-primary{background:#667eea;color:#fff}
      .opsbrain-btn-primary:hover{background:#5568d3;transform:translateY(-1px);box-shadow:0 4px 12px rgba(102,126,234,.4)}
      .opsbrain-btn-secondary{background:#e9ecef;color:#495057}
      .opsbrain-btn-secondary:hover{background:#dee2e6}
    `;
    document.head.appendChild(style);
  }

  attachEventListeners() {
    const widget = document.getElementById("opsbrain-match-widget");
    if (!widget) return;
    widget.querySelector(".opsbrain-close-btn")?.addEventListener("click", () => this.dismiss());
    widget.querySelector("#opsbrain-tailor-resume")?.addEventListener("click", () => {
      chrome.runtime.sendMessage({ type: "OPEN_RESUME_TAILOR", url: window.location.href });
      this.dismiss();
    });
    widget.querySelector("#opsbrain-dismiss")?.addEventListener("click", () => this.dismiss());
  }

  dismiss() {
    const widget = document.getElementById("opsbrain-match-widget");
    if (widget) {
      widget.style.animation = "opsbrainSlideOut 0.3s ease-out forwards";
      setTimeout(() => widget.remove(), 300);
    }
  }
}

if (typeof window !== "undefined") {
  window.__PROFESSIONAL_WIDGET__ = ProfessionalMatchWidget;
}
