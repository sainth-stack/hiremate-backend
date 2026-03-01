/**
 * Page Detector - Intelligent job application page detection
 * Only show widget on actual job pages to reduce 95% unnecessary mounts
 */
class PageDetector {
  constructor() {
    this._cachedResult = undefined;
    this.JOB_PAGE_PATTERNS = {
      urls: [
        /greenhouse\.io\/.*\/jobs\//,
        /boards\.greenhouse\.io/,
        /myworkdayjobs\.com\/.+\/job\//,
        /\.wd\d+\.myworkdayjobs\.com/,
        /lever\.co\/.+\/jobs\//,
        /jobs\.lever\.co/,
        /smartrecruiters\.com\/.*\/\d+/,
        /ashbyhq\.com\/.+\/application/,
        /taleo\.net\/careersection/,
        /icims\.com\/jobs\//,
        /jobvite\.com\/.*\/job\//,
        /successfactors\.com\/.*\/career/,
        /linkedin\.com\/jobs\/view\//,
        /indeed\.com\/viewjob/,
        /glassdoor\.com\/job-listing/,
        /monster\.com\/job-openings/,
        /ziprecruiter\.com\/jobs\//,
        /careers\./,
        /\/jobs?\//,
        /\/careers?\//,
        /\/apply\//,
        /\/application\//,
        /\/job-openings\//,
        /\/opportunities\//,
      ],
      domSignals: [
        { selector: 'input[type="file"][accept*="pdf"]', weight: 3 },
        { selector: 'input[name*="resume"]', weight: 3 },
        { selector: 'input[type="file"][name*="cv"]', weight: 3 },
        { selector: 'input[name*="first_name"]', weight: 2 },
        { selector: 'input[name*="last_name"]', weight: 2 },
        { selector: 'textarea[name*="cover"]', weight: 2 },
        { selector: 'form[action*="apply"]', weight: 2 },
        { selector: '[data-automation-id*="formField"]', weight: 2 },
        { selector: ".application-question", weight: 2 },
        { selector: '[class*="job-apply"]', weight: 1 },
        { selector: '[class*="application"]', weight: 1 },
        { selector: 'button[type="submit"][class*="apply"]', weight: 1 },
      ],
      textSignals: [
        { text: "upload resume", weight: 3 },
        { text: "attach resume", weight: 3 },
        { text: "upload your resume", weight: 3 },
        { text: "cover letter", weight: 2 },
        { text: "work authorization", weight: 2 },
        { text: "years of experience", weight: 2 },
        { text: "submit application", weight: 2 },
        { text: "apply now", weight: 1 },
        { text: "job application", weight: 1 },
      ],
    };
  }

  isJobApplicationPage() {
    if (typeof document === "undefined" || !document.body) return false;
    const url = (window.location?.href || "").toLowerCase();
    const title = (document.title || "").toLowerCase();

    if (this.JOB_PAGE_PATTERNS.urls.some((p) => p.test(url))) {
      if (window.__CONFIG__?.log) window.__CONFIG__.log("[PageDetector] Job page by URL");
      return true;
    }

    if (this.hasTitleSignals(title)) {
      const domScore = this.calculateDOMScore();
      if (domScore >= 3) {
        if (window.__CONFIG__?.log) window.__CONFIG__.log("[PageDetector] Job page by title+DOM", domScore);
        return true;
      }
    }

    const fullScore = this.calculateDOMScore() + this.calculateTextScore();
    if (fullScore >= 5) {
      if (window.__CONFIG__?.log) window.__CONFIG__.log("[PageDetector] Job page by full analysis", fullScore);
      return true;
    }
    return false;
  }

  hasTitleSignals(title) {
    return (
      title.includes("apply") ||
      title.includes("application") ||
      title.includes("job") ||
      title.includes("career") ||
      title.includes("opening") ||
      title.includes("position")
    );
  }

  calculateDOMScore() {
    let score = 0;
    try {
      for (const signal of this.JOB_PAGE_PATTERNS.domSignals) {
        if (document.querySelector(signal.selector)) {
          score += signal.weight;
          if (score >= 5) break;
        }
      }
    } catch (_) {}
    return score;
  }

  calculateTextScore() {
    try {
      const bodyText = (document.body?.textContent || "").toLowerCase();
      let score = 0;
      for (const signal of this.JOB_PAGE_PATTERNS.textSignals) {
        if (bodyText.includes(signal.text)) {
          score += signal.weight;
          if (score >= 3) break;
        }
      }
      return score;
    } catch (_) {
      return 0;
    }
  }

  shouldShowWidget() {
    if (this._cachedResult !== undefined) return this._cachedResult;
    this._cachedResult = this.isJobApplicationPage();
    return this._cachedResult;
  }

  reset() {
    this._cachedResult = undefined;
  }
}

if (typeof window !== "undefined") {
  window.__PAGE_DETECTOR__ = new PageDetector();
}
