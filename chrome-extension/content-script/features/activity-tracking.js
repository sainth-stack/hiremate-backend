// ─── Activity Tracking Feature ─────────────────────────────────────────────
// Depends on: _visitedUrls (consts.js)
//             logWarn (utils.js)
//             getApiBase, getAuthHeaders (api-service.js)
//             extractCompanyAndPosition (job-form.js)

function trackCareerPageView() {
  if (!_visitedUrls.has(location.href)) {
    _visitedUrls.add(location.href);
    getApiBase().then((apiBase) =>
      getAuthHeaders().then((headers) => {
        if (!headers?.Authorization) return;
        const { company } = extractCompanyAndPosition();
        fetch(`${apiBase}/activity/track`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...headers },
          body: JSON.stringify({
            event_type: "career_page_view",
            page_url: location.href,
            metadata: { company_name: company || null, job_url: location.href || null, job_title: null },
          }),
        }).catch((e) => logWarn("Failed to track career page view", { error: String(e) }));
      })
    );
  }
}

function trackAutofillUsed() {
  const currentUrl = window.location.href || "";
  getApiBase().then((apiBase) =>
    getAuthHeaders().then((headers) => {
      if (!headers?.Authorization) return;
      const { company, position } = extractCompanyAndPosition();
      fetch(`${apiBase}/activity/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({
          event_type: "autofill_used",
          page_url: currentUrl,
          metadata: { company_name: company || null, job_url: currentUrl || null, job_title: position || null },
        }),
      }).catch((e) => logWarn("Failed to track autofill", { error: String(e) }));
    })
  );
}
