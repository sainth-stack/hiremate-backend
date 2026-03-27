// ─── Widget HTML Template ─────────────────────────────────────────────────
// Autofill widget markup: header, tabs, panels (autofill, keywords, profile)
// Depends on: INPAGE_ROOT_ID (consts.js)
//             AUTOFILL_TAB_ICONS, QUESTION_UI_ICONS, KEYWORD_TAB_ICONS,
//             PROFILE_TAB_ICONS, ACCORDION_ICONS (icons.js)

function getWidgetHTML() {
  return `
    <button type="button" class="ja-mini" id="ja-open" title="Open OpsBrain">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 30px; height: 30px;">
        <path d="M12 5C7 5 3 9 3 14c0 2.5 1 4.5 2.5 6L3 22l2.5-1.5C7 21.5 9.5 22 12 22c5 0 9-4 9-8s-4-9-9-9z"/>
        <path d="M8 12h.01M12 12h.01M16 12h.01"/>
        <circle cx="12" cy="10" r="1" fill="currentColor"/>
        <circle cx="15" cy="11.5" r="0.8" fill="currentColor"/>
        <circle cx="9" cy="11.5" r="0.8" fill="currentColor"/>
      </svg>
    </button>
    <div class="ja-card">
      <div class="ja-head" id="ja-drag-handle">
        <div class="ja-logo-wrap">
          <img class="ja-logo-icon" src="${chrome.runtime.getURL('logo.png')}" alt="OpsBrain" />
        </div>
        <div class="ja-head-actions">
        <button class="ja-report-btn" id="ja-report-issue">Report Issue</button>

         <button type="button" class="ja-close ja-head-btn" id="ja-close" title="Close">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
    <line x1="18" y1="6" x2="6" y2="18"></line>
    <line x1="6" y1="6" x2="18" y2="18"></line>
  </svg>
</button>
        </div>
      </div>
      <div class="ja-tabs">
        <button type="button" class="ja-tab active" data-tab="autofill" id="ja-tab-autofill">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19l7-7 3 3-7 7-3-3z M4 4l7 7 3 3"/></svg>
          Autofill
        </button>
        <button type="button" class="ja-tab" data-tab="keywords">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          Keywords Score
        </button>
        <button type="button" class="ja-tab" data-tab="profile">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
          Profile
        </button>
      </div>
      <div class="ja-body">
        <div class="ja-panel active" id="ja-panel-autofill">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta" style="display:none">
            <h3>Sign in to autofill</h3>
            <p>Information is pulled from your OpsBrain profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill" id="ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-autofill-authenticated" id="ja-autofill-authenticated">
            <div class="ja-autofill-tab">
              <div class="ja-autofill-hero-wrap">
                <div class="ja-autofill-hero">
                  <div class="ja-autofill-hero-deco ja-autofill-hero-deco-1" aria-hidden="true"></div>
                  <div class="ja-autofill-hero-deco ja-autofill-hero-deco-2" aria-hidden="true"></div>
                  <div class="ja-autofill-hero-inner">
                    <div class="ja-autofill-hero-head">
                      <p class="ja-autofill-hero-title">
                        <span class="ja-autofill-hero-title-ico" aria-hidden="true">${AUTOFILL_TAB_ICONS.zap}</span>
                        Autofill Application
                      </p>
                      <span id="ja-fields-count" class="ja-autofill-fields-badge">8/8 fields</span>
                    </div>
                    <div class="ja-status-area" id="ja-status-area">
                      <div class="ja-status-loader" id="ja-status-loader"></div>
                      <div class="ja-status ja-autofill-hero-sub" id="ja-status">One-click fill for this job application</div>
                    </div>
                    <div class="ja-autofill-progress-block">
                      <div class="ja-progress-label-row">
                        <span class="ja-progress-label">Progress</span>
                        <span id="ja-progress-text" class="ja-progress-pct">0%</span>
                      </div>
                      <div class="ja-autofill-progress-track">
                        <div id="ja-progress" class="ja-autofill-progress-bar" style="width:0%"></div>
                      </div>
                    </div>
                    <div class="ja-autofill-actions">
                      <button type="button" class="ja-btn-hero-fill" id="ja-run">
                        <span class="ja-btn-fill-inner" id="ja-run-inner">
                          <span class="ja-btn-fill-icon" aria-hidden="true">${AUTOFILL_TAB_ICONS.sparkles}</span>
                          <span class="ja-btn-fill-label">Autofill this page</span>
                        </span>
                      </button>
                      <div class="ja-fill-controls" id="ja-fill-controls" aria-hidden="true">
                        <span class="ja-fill-label">Autofilling</span>
                        <div class="ja-fill-controls-row">
                          <button type="button" class="ja-stop" id="ja-stop">Stop</button>
                          <button type="button" class="ja-skip-next" id="ja-skip-next">⏭ Skip to next input</button>
                        </div>
                      </div>
                      <button type="button" class="ja-continue-fill" id="ja-continue-fill" style="display:none">Continue filling</button>
                    </div>
                    <label class="ja-cache-enable" id="ja-cache-enable-wrap">
                      <input type="checkbox" id="ja-cache-enable" checked />
                      <span>Use cached answers for faster fills</span>
                    </label>
                    <label class="ja-auto-advance" id="ja-auto-advance-wrap">
                      <input type="checkbox" id="ja-auto-advance" />
                      Auto-advance through all steps
                    </label>
                  </div>
                </div>
              </div>
              <div class="ja-footer-links">
                <button type="button" class="ja-footer-link" id="ja-save-job">
                  <span class="ja-footer-link-ico" aria-hidden="true">${QUESTION_UI_ICONS.download}</span>
                  Save Job
                </button>
                <button type="button" class="ja-footer-link" id="ja-referrals">
                  <span class="ja-footer-link-ico" aria-hidden="true">${QUESTION_UI_ICONS.users}</span>
                  Referrals
                </button>
              </div>
              <div class="ja-accordions" id="ja-autofill-accordions"></div>
              <div class="ja-autofill-footer-stats">
                <span class="ja-autofill-footer-item" id="ja-autofill-last-fill"><span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.clock}</span> Last fill: —</span>
                <span class="ja-autofill-footer-item" id="ja-autofill-apps-filled"><span class="ja-autofill-footer-ico" aria-hidden="true">${QUESTION_UI_ICONS.layers}</span> — applications filled</span>
              </div>
            </div>
            <div class="ja-quick-save-row" id="ja-quick-save-row" style="display:none;margin-top:10px;">
              <button type="button" class="ja-action ja-save-applied" id="ja-save-applied">Save & Mark Applied</button>
            </div>
          </div>
        </div>
        <div class="ja-panel" id="ja-panel-keywords">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta-keywords" style="display:none">
            <h3>Sign in to view keywords</h3>
            <p>Information is pulled from your OpsBrain profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-keywords-authenticated" id="ja-keywords-authenticated">
          <div class="ja-keywords-view" id="ja-keywords-view">
          <div class="ja-kw-tab">
            <div class="ja-kw-active-resume-row">
              <div class="ja-kw-active-resume-field">
                <label class="ja-kw-label-upper" for="ja-rs-trigger">Active Resume</label>
                <select class="ja-resume-select ja-kw-resume-select" id="ja-resume-select" aria-hidden="true" style="display:none"></select>
                <div class="ja-rs-dropdown" id="ja-rs-dropdown">
                  <button type="button" class="ja-rs-trigger" id="ja-rs-trigger" aria-haspopup="listbox" aria-expanded="false">
                    <span class="ja-rs-trigger-text" id="ja-rs-trigger-text">Loading resumes…</span>
                    <svg class="ja-rs-chevron" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M5 8l5 5 5-5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  </button>
                  <div class="ja-rs-panel" id="ja-rs-panel" hidden>
                    <div class="ja-rs-search-wrap">
                      <svg class="ja-rs-search-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="M15 15l-2.8-2.8" stroke-linecap="round"/></svg>
                      <input type="text" class="ja-rs-search" id="ja-rs-search" placeholder="Search resumes…" autocomplete="off" spellcheck="false" />
                    </div>
                    <ul class="ja-rs-list" id="ja-rs-list" role="listbox" aria-label="Resumes"></ul>
                    <p class="ja-rs-empty" id="ja-rs-empty" hidden>No resumes found</p>
                  </div>
                </div>
              </div>
              <button type="button" class="ja-kw-tailor-btn" id="ja-tailor-resume-btn">${KEYWORD_TAB_ICONS.target}<span>Tailor</span></button>
            </div>
            <div class="ja-keyword-card ja-kw-score-card" id="ja-keyword-card">
              <div id="ja-keyword-analysis">
                <p class="ja-score-text">Loading keyword analysis...</p>
              </div>
            </div>
            <div id="ja-keyword-keywords-list" class="ja-keyword-keywords-list"></div>
            <button type="button" class="ja-kw-update-jd-btn" id="ja-update-jd-btn">${KEYWORD_TAB_ICONS.refreshCw}<span>Update Job Description</span></button>
          </div>
          </div>
          <div class="ja-job-form-panel" id="ja-job-form-panel" style="display:none">
            <h4 style="margin:0 0 10px 0;font-size: 15px;">Edit Job Description</h4>
            <p style="font-size: 13px;color:#6b7280;margin:0 0 12px 0;">With a job description you can view matching keywords and/or save this job to your tracker!</p>
            <form class="ja-job-form" id="ja-job-form">
              <label>Company</label>
              <input type="text" id="ja-job-company" placeholder="Company name">
              <label>Position Title</label>
              <input type="text" id="ja-job-position" placeholder="Lead Software Development Engineer">
              <label>Location</label>
              <input type="text" id="ja-job-location" placeholder="Bangalore">
              <label>Min. Salary ($)</label>
              <input type="text" id="ja-job-min-salary" placeholder="180">
              <label>Max. Salary ($)</label>
              <input type="text" id="ja-job-max-salary" placeholder="740000000">
              <label>Currency</label>
              <select id="ja-job-currency">
                <option value="USD">US Dollar (USD)</option>
                <option value="EUR">Euro (EUR)</option>
                <option value="GBP">British Pound (GBP)</option>
                <option value="INR">Indian Rupee (INR)</option>
              </select>
              <label>Period</label>
              <select id="ja-job-period">
                <option value="Yearly">Yearly</option>
                <option value="Monthly">Monthly</option>
                <option value="Hourly">Hourly</option>
              </select>
              <label>Job Type</label>
              <select id="ja-job-type">
                <option value="Full-Time">Full-Time</option>
                <option value="Part-Time">Part-Time</option>
                <option value="Contract">Contract</option>
                <option value="Internship">Internship</option>
              </select>
              <label>Application Status</label>
              <select id="ja-job-status">
                <option value="I have not yet applied">I have not yet applied</option>
                <option value="Applied">Applied</option>
                <option value="Interviewing">Interviewing</option>
                <option value="Offer">Offer</option>
                <option value="Rejected">Rejected</option>
                <option value="Withdrawn">Withdrawn</option>
              </select>
              <label>Job Description — Click to edit</label>
              <textarea id="ja-job-description" rows="6" placeholder="Auto-detected description available."></textarea>
              <label>Notes — Click to add</label>
              <textarea id="ja-job-notes" rows="2" placeholder="Add notes..."></textarea>
              <label>Job Posting URL</label>
              <input type="text" id="ja-job-url" placeholder="https://...">
              <div class="ja-job-form-actions">
                <button type="button" class="ja-go-back-btn" id="ja-job-go-back">Go Back</button>
                <button type="submit" class="ja-save-job-btn" id="ja-job-save">Save Job</button>
              </div>
            </form>
          </div>
          </div>
          </div>
        </div>
        <div class="ja-panel" id="ja-panel-profile">
          <div class="ja-signin-cta ja-autofill-box" id="ja-signin-cta-profile" style="display:none">
            <h3>Sign in to view profile</h3>
            <p>Information is pulled from your OpsBrain profile</p>
            <button type="button" class="ja-action ja-signin-to-autofill">Log in to apply</button>
          </div>
          <div class="ja-profile-authenticated" id="ja-profile-authenticated">
            <div class="ja-profile-tab">
              <div class="ja-profile-stats">
                <div class="ja-profile-stat">
                  <p class="ja-profile-stat-val" id="ja-profile-stat-apps">—</p>
                  <p class="ja-profile-stat-label">Applications</p>
                </div>
                <div class="ja-profile-stat">
                  <p class="ja-profile-stat-val ja-profile-stat-success" id="ja-profile-stat-interviews">—</p>
                  <p class="ja-profile-stat-label">Interviews</p>
                </div>
                <div class="ja-profile-stat">
                  <p class="ja-profile-stat-val ja-profile-stat-primary" id="ja-profile-stat-fill">—</p>
                  <p class="ja-profile-stat-label">Fill Rate</p>
                </div>
              </div>
              <div class="ja-prof-hero-wrap">
                <div class="ja-prof-hero">
                  <div class="ja-avatar ja-avatar-gradient" id="ja-profile-avatar">—</div>
                  <div class="ja-prof-hero-text">
                    <h3 class="ja-profile-name" id="ja-profile-name">—</h3>
                    <p class="ja-profile-title" id="ja-profile-title"></p>
                    <div class="ja-prof-actions">
                      <button type="button" class="ja-prof-act-btn" id="ja-profile-refresh">${PROFILE_TAB_ICONS.refreshCwSm}<span>Sync</span></button>
                      <button type="button" class="ja-prof-act-btn" id="ja-profile-edit">${PROFILE_TAB_ICONS.editSm}<span>Edit</span></button>
                      <button type="button" class="ja-prof-act-btn" id="ja-profile-preview">${PROFILE_TAB_ICONS.eyeSm}<span>Preview</span></button>
                    </div>
                  </div>
                </div>
                <div class="ja-profile-contact" id="ja-profile-contact"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.graduationCap}<span class="ja-prof-sec-title">Education</span></div>
                <div id="ja-profile-education"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.briefcase}<span class="ja-prof-sec-title">Experience</span></div>
                <div id="ja-profile-experience"></div>
              </div>
              <div class="ja-prof-block" id="ja-profile-cert-block" style="display:none">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.award}<span class="ja-prof-sec-title">Certifications</span></div>
                <div id="ja-profile-certifications"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.upload}<span class="ja-prof-sec-title">Uploads</span></div>
                <div class="ja-prof-upload-inner" id="ja-profile-uploads"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head ja-prof-sec-head-row">
                  <span class="ja-prof-sec-head-left">${PROFILE_TAB_ICONS.code}<span class="ja-prof-sec-title">Technical Skills</span></span>
                  <span class="ja-prof-sec-count" id="ja-profile-tech-count">0 skills</span>
                </div>
                <div id="ja-profile-tech-skills"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.messageSquare}<span class="ja-prof-sec-title">Soft Skills</span></div>
                <div id="ja-profile-soft-skills"></div>
              </div>
              <div class="ja-prof-block">
                <div class="ja-prof-sec-head">${PROFILE_TAB_ICONS.globe}<span class="ja-prof-sec-title">Languages</span></div>
                <div id="ja-profile-languages"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}
