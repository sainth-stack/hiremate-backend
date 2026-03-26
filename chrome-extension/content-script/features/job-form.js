// ─── Job Form Feature ──────────────────────────────────────────────────────
// Depends on: INPAGE_ROOT_ID (consts.js)
//             logWarn, getText (utils.js)
//             getApiBase, getAuthHeaders, fetchWithAuthRetry (api-service.js)
//             getPageHtmlForKeywordsApi, fetchJobDescriptionFromKeywordsApi (keyword-analysis.js)

function normalizeUrlForTailor(u) {
  if (!u || typeof u !== "string") return "";
  const s = u.trim();
  if (!s) return "";
  const withoutHash = s.split("#")[0] || s;
  return withoutHash.replace(/\/+$/, "") || withoutHash;
}

async function openResumeGeneratorUrl() {
  const data = await chrome.storage.local.get(["loginPageUrl"]);
  const base = data.loginPageUrl ? new URL(data.loginPageUrl).origin : "http://localhost:5173";
  let url = `${base}/resume-generator/build?tailor=1`;
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const widget = document.getElementById(INPAGE_ROOT_ID);
    const lastJobId = widget?.dataset?.lastJobId;
    const lastJobUrl = widget?.dataset?.lastJobUrl;
    const currentUrl = normalizeUrlForTailor(window.location.href);
    const useJobId = lastJobId && lastJobUrl && currentUrl === normalizeUrlForTailor(lastJobUrl);

    if (useJobId && headers?.Authorization) {
      const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/tailor-context`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: parseInt(lastJobId, 10) }),
      });
      if (res.ok) {
        url = `${base}/resume-generator/build?tailor=1&job_id=${lastJobId}`;
        chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url });
        return;
      }
    }
    const pageHtml = await getPageHtmlForKeywordsApi();
    if (pageHtml && pageHtml.length > 100 && headers?.Authorization) {
      const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/tailor-context`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          page_html: pageHtml,
          url: window.location.href,
          job_title: document.querySelector("h1, [data-automation-id='jobTitle'], .job-title, [class*='job-title']")?.textContent?.trim?.()?.slice(0, 100) || "",
        }),
      });
      if (res.ok) {
        const json = await res.json().catch(() => ({}));
        const jobId = json?.job_id;
        url = jobId ? `${base}/resume-generator/build?tailor=1&job_id=${jobId}` : `${base}/resume-generator/build?tailor=1`;
      }
    }
  } catch (err) {
    logWarn("Tailor context save failed", { error: String(err) });
  }
  chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url });
}

function extractCompanyAndPosition() {
  const title = document.title || "";
  const url = window.location.href || "";
  let company = "";
  let position = "";
  let location = "";

  // 1. Extract company from URL (Greenhouse, Lever, Workday, etc.)
  try {
    const u = new URL(url);
    const path = (u.pathname || "").replace(/^\/+|\/+$/g, "");
    const segments = path.split("/").filter(Boolean);
    if (u.hostname.includes("greenhouse.io") && segments.length >= 1) {
      company = segments[0];
    } else if (u.hostname.includes("lever.co") && segments.length >= 1) {
      company = segments[0];
    } else if (u.hostname.includes("jobs.workday.com") && segments.length >= 2) {
      company = segments[0];
    } else if (u.hostname.includes("ashbyhq.com") && segments.length >= 1) {
      company = segments[0];
    } else if (u.hostname.includes("bamboohr.com") && segments.length >= 1) {
      company = segments[0];
    }
    if (company) {
      company = company.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    }
  } catch (_) { }

  // 2. Try JSON-LD JobPosting on page
  if (!company || !position) {
    document.querySelectorAll('script[type="application/ld+json"]').forEach((script) => {
      try {
        const data = JSON.parse(script.textContent || "{}");
        const item = Array.isArray(data) ? data.find((i) => i["@type"] === "JobPosting") : data["@type"] === "JobPosting" ? data : null;
        if (item) {
          if (!company && item.hiringOrganization?.name) company = item.hiringOrganization.name;
          if (!position && item.title) position = item.title;
          if (!location && item.jobLocation) {
            const loc = item.jobLocation;
            location = typeof loc === "string" ? loc : loc.address?.addressLocality && loc.address?.addressCountry
              ? `${loc.address.addressLocality}, ${loc.address.addressCountry}`
              : loc.name || "";
          }
        }
      } catch (_) { }
    });
  }

  // 3. og:title — "Job Title | Company" or "Tagline | Company" (job titles usually 2+ words)
  const ogTitle = document.querySelector('meta[property="og:title"]')?.content;
  const isTagline = (t) => !t || /^(best|payment|gateway|online|financial|leading|top|number one)/i.test(t) || t.length > 55;
  const looksLikeJobTitle = (t) => t && t.length >= 5 && t.length < 80 && !isTagline(t) && t.split(/\s+/).length >= 2;
  if (ogTitle) {
    const parts = ogTitle.split(/[|\-–—]/).map((p) => p.trim()).filter(Boolean);
    if (parts.length >= 2) {
      const a = parts[0], b = parts[1];
      if (!company) company = (b.length <= 30 && b.split(/\s+/).length <= 3) ? b : (a.length <= 30 ? a : "");
      if (!position && looksLikeJobTitle(a)) position = a;
      else if (!position && looksLikeJobTitle(b)) position = b;
    } else if (!position && looksLikeJobTitle(ogTitle.trim())) {
      position = ogTitle.trim();
    }
  }

  // 4. Page content: h1 first (most reliable on job detail pages)
  const h1 = document.querySelector("h1");
  if (!position && h1) position = getText(h1);

  // 5. "Back to jobs JOB_TITLE Location Apply" pattern (Greenhouse / common ATS)
  const bodyText = document.body?.innerText?.slice(0, 1500) || "";
  if (!position && /Back to jobs\s+(.+?)\s+(?:Apply|Remote|Hybrid|Malaysia|India|Singapore|Bangalore|Kuala Lumpur)/i.test(bodyText)) {
    const m = bodyText.match(/Back to jobs\s+(.+?)\s+(?:Apply|Remote|Hybrid|Malaysia|India|Singapore|Bangalore|Kuala Lumpur|,\s*[A-Za-z]+)/i);
    if (m) {
      const candidate = m[1].trim();
      if (candidate.length >= 5 && candidate.length < 80 && !/^(payment|best|gateway|online|financial|leading|india)/i.test(candidate)) {
        position = candidate;
      }
    }
  }
  if (!position && /Back to jobs\s+(.+?)\s+Apply/i.test(bodyText)) {
    const m = bodyText.match(/Back to jobs\s+(.+?)\s+Apply/i);
    if (m && !position) {
      const candidate = m[1].trim();
      if (candidate.length >= 5 && candidate.length < 80) position = candidate;
    }
  }

  if (!company || !location) {
    if (!company && /About\s+([A-Za-z0-9&\s]+):/i.test(bodyText)) {
      const m = bodyText.match(/About\s+([A-Za-z0-9&\s]+):/i);
      if (m) company = m[1].trim();
    }
    if (!location && /([A-Za-z\s]+,\s*[A-Za-z\s]+)\s*(?:Apply|Remote|Hybrid)/i.test(bodyText)) {
      const m = bodyText.match(/([A-Za-z\s]+,\s*[A-Za-z\s]+)\s*(?:Apply|Remote|Hybrid)/i);
      if (m) location = m[1].trim();
    }
    if (!location && /([A-Za-z\s]+,\s+[A-Za-z]{2,})\s*$/.test(bodyText.slice(0, 800))) {
      const m = bodyText.slice(0, 800).match(/([A-Za-z][A-Za-z\s]+,\s*[A-Za-z]{2,})/);
      if (m && m[1].length < 50) location = m[1].trim();
    }
  }

  if (!position && ogTitle) {
    const parts = ogTitle.split(/[|\-–—]/).map((p) => p.trim()).filter(Boolean);
    for (const p of parts) {
      if (p.length >= 5 && p.length < 80 && !/^(payment|best|gateway|online|financial|leading|india|razorpay)/i.test(p)) {
        position = p;
        break;
      }
    }
  }
  if (!position && title) {
    const t = title.trim();
    if (t.length >= 5 && t.length < 80 && !/^(payment|best|gateway|online|financial)/i.test(t)) position = t;
  }
  return { company: company || "", position: position || "", location: location || "" };
}

async function prefillJobForm(root) {
  const { company, position, location } = extractCompanyAndPosition();
  const urlInput = root?.querySelector("#ja-job-url");
  const descInput = root?.querySelector("#ja-job-description");
  const companyInput = root?.querySelector("#ja-job-company");
  const positionInput = root?.querySelector("#ja-job-position");
  const locationInput = root?.querySelector("#ja-job-location");
  if (urlInput) urlInput.value = window.location.href || "";
  if (companyInput) companyInput.value = company || "";
  if (positionInput) positionInput.value = position || "";
  if (locationInput) locationInput.value = location || "";

  if (descInput) {
    descInput.placeholder = "Scraping job description...";
    descInput.value = "";
    const jobDesc = await fetchJobDescriptionFromKeywordsApi(window.location.href);
    descInput.value = jobDesc || "";
    descInput.placeholder = "Auto-detected description available.";
  }
}

async function saveJobFromForm(root) {
  const btn = root?.querySelector("#ja-job-save");
  const origText = btn?.textContent || "Save Job";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Saving...";
  }
  try {
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    const payload = {
      company: root.querySelector("#ja-job-company")?.value || "",
      position_title: root.querySelector("#ja-job-position")?.value || "",
      location: root.querySelector("#ja-job-location")?.value || "",
      min_salary: root.querySelector("#ja-job-min-salary")?.value || null,
      max_salary: root.querySelector("#ja-job-max-salary")?.value || null,
      currency: root.querySelector("#ja-job-currency")?.value || "USD",
      period: root.querySelector("#ja-job-period")?.value || "Yearly",
      job_type: root.querySelector("#ja-job-type")?.value || "Full-Time",
      job_description: root.querySelector("#ja-job-description")?.value || null,
      notes: root.querySelector("#ja-job-notes")?.value || null,
      application_status: root.querySelector("#ja-job-status")?.value || "I have not yet applied",
      job_posting_url: root.querySelector("#ja-job-url")?.value || null,
    };
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const view = root.querySelector("#ja-keywords-view");
      const formPanel = root.querySelector("#ja-job-form-panel");
      if (view && formPanel) {
        formPanel.style.display = "none";
        view.style.display = "block";
      }
    }
  } catch (err) {
    logWarn("Save job failed", { error: String(err) });
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origText;
    }
  }
}
