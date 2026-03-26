// ─── Job Page Detection ────────────────────────────────────────────────────
// Depends on: getText (utils.js)
//             getApiBase, getAuthHeaders, fetchWithAuthRetry (api-service.js)

function isCareerPage(urlStr = window.location.href) {
  const url = String(urlStr || "").toLowerCase();
  return (
    url.includes("/careers") ||
    url.includes("careers.") ||
    url.includes("jobs.") ||
    url.includes("/jobs") ||
    url.includes("/apply") ||
    url.includes("/job/") ||
    url.includes("greenhouse.io") ||
    url.includes("lever.co") ||
    url.includes("myworkdayjobs.com") ||
    url.includes("workday.com") ||
    url.includes("smartrecruiters.com") ||
    url.includes("icims.com") ||
    url.includes("ashbyhq.com") ||
    url.includes("bamboohr.com") ||
    url.includes("jobvite.com") ||
    url.includes("recruit") ||
    url.includes("talent")
  );
}

/** Content hint: page shows multiple job listings (cards/links). */
function hasListingPageContent() {
  const body = document.body;
  if (!body) return false;
  const sel = [
    "a[href*='job']",
    "a[href*='career']",
    "a[href*='position']",
    "[data-job-id]",
    "[data-testid*='job-card']",
    "[class*='job-card']",
    "[class*='job-listing']",
    "[class*='position-card']",
  ].join(",");
  const matches = body.querySelectorAll(sel);
  const jobLikeCount = Array.from(matches).filter((el) => {
    const text = (el.textContent || "").trim();
    const href = (el.getAttribute("href") || "").toLowerCase();
    return text.length >= 10 && text.length < 120 && (href.includes("job") || href.includes("detail") || href.includes("position"));
  }).length;
  const headings = body.querySelectorAll("h2, h3, h4");
  const multiTitle = headings.length >= 4 && Array.from(headings).filter((h) => (h.textContent || "").trim().length >= 5 && (h.textContent || "").trim().length < 100).length >= 3;
  return jobLikeCount >= 5 || multiTitle;
}

/** Content hint: page has single JD (Apply button + JD keywords). */
function hasJobDetailContent() {
  const body = document.body;
  if (!body) return false;
  const text = (body.innerText || body.textContent || "").toLowerCase();
  if (text.length < 400) return false;
  const jdKeywords = ["responsibilities", "requirements", "qualifications", "experience", "about the role", "what you will"];
  const jdScore = jdKeywords.filter((k) => text.includes(k)).length;
  const hasApply =
    /apply|submit application|apply now/i.test(text) ||
    !!body.querySelector('a[href*="apply"]') ||
    !!body.querySelector("[class*='apply']") ||
    Array.from(body.querySelectorAll("a, button")).some((el) => /^\s*apply\s*$/i.test((el.textContent || "").trim()));
  return jdScore >= 2 && hasApply;
}

/** True when page is a job LISTING (many jobs). No popup. */
function isJobListingPage(urlStr = window.location.href) {
  try {
    const path = new URL(urlStr || "").pathname.toLowerCase().replace(/\/+$/, "") || "/";
    const listingPaths = [
      "/jobs", "/careers", "/positions", "/opportunities", "/vacancies", "/openings",
      "/open-positions", "/current-openings", "/jobs/all", "/jobs/search",
      "/careers/all", "/careers/search", "/positions/all", "/opportunities/all",
      "/join", "/join-us", "/work-with-us",
    ];
    if (listingPaths.some((p) => path === p)) return true;
    if (/\/jobs\/?$|\/careers\/?$|\/positions\/?$/.test(path)) return true;
    if (path === "/" && /jobs\.|careers\.|greenhouse\.|lever\.|workday\.|ashbyhq\.|bamboohr\.|icims\.|smartrecruiters\./i.test(urlStr || "")) return true;
    if (hasListingPageContent() && !isJobDetailPage(urlStr)) return true;
    return false;
  } catch (_) {
    return false;
  }
}

/** True when page is a single JD. Popup allowed. */
function isJobDetailPage(urlStr = window.location.href) {
  const url = (urlStr || "").toLowerCase();
  try {
    const path = new URL(urlStr || "").pathname.toLowerCase();
    const search = new URL(urlStr || "").search.toLowerCase();

    if (path === "/jobs" || path === "/jobs/" || path === "/careers" || path === "/careers/") return false;

    const hasJdInPath = /\/(detail|job|position|opportunity|vacancy|posting|role|opening)\/?([^/]|$)/.test(path);
    const hasJdInQuery = /[?&](gh_jid|jid|job_id|jobid|position_id|opportunity_id|posting_id|req_id|reqid|id)=/.test(search);
    const hasNestedJobPath =
      /\/jobs\/[^/]+\/detail/.test(path) ||
      (/\/careers\/[^/]+/.test(path) && !/\/careers\/(all|search)\/?$/.test(path)) ||
      /\/job\/[^/]+|\/position\/[^/]+|\/opportunity\/[^/]+|\/posting\/[^/]+|\/role\/[^/]+|\/vacancy\/[^/]+/.test(path);
    const atsJdPattern = /(greenhouse|lever|workday|ashbyhq|bamboohr|icims|smartrecruiters|jobvite)[^/]*\/[^/]+\/[^/\s]+/.test(url);

    if (hasJdInPath || hasJdInQuery || hasNestedJobPath || atsJdPattern) return true;
    if (isCareerPage(urlStr) && hasJobDetailContent()) return true;
    return false;
  } catch (_) {
    return false;
  }
}

async function isJobPageViaLLM(url, title, snippet) {
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/job-page-detect`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ url: url || "", title: title || "", snippet: (snippet || "").slice(0, 800) }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.is_job_page === true;
  } catch (_) {
    return null;
  }
}
