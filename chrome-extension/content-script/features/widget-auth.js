// ─── Widget Auth UI Feature ────────────────────────────────────────────────
// Depends on: DEFAULT_LOGIN_PAGE_URL, LOGIN_PAGE_ORIGINS (consts.js)
//             logInfo, logWarn (utils.js)
//             updateAutofillFooterStats (autofill-stats.js)

async function updateWidgetAuthUI(root) {
  let data = {};
  let hasToken = false;
  let loginUrl = DEFAULT_LOGIN_PAGE_URL;

  try {
    data = await chrome.storage.local.get(["accessToken", "loginPageUrl"]);
    hasToken = !!data.accessToken;
    if (data.loginPageUrl) loginUrl = data.loginPageUrl;
  } catch (e) {
    if (e?.message?.includes("Extension context invalidated")) return;
    throw e;
  }

  let isHireMateOrigin = LOGIN_PAGE_ORIGINS.some((o) => window.location.origin === o);
  if (!isHireMateOrigin && data.loginPageUrl) {
    try {
      isHireMateOrigin = new URL(data.loginPageUrl).origin === window.location.origin;
    } catch (_) { }
  }

  // 1) If no token in chrome.storage, try localStorage (when on HireMate frontend - same origin)
  if (!hasToken && isHireMateOrigin) {
    try {
      const localToken = localStorage.getItem("token") || localStorage.getItem("access_token");
      if (localToken) {
        hasToken = true;
        await chrome.storage.local.set({ accessToken: localToken });
        logInfo("Token synced from localStorage to extension storage");
      }
    } catch (e) {
      if (e?.message?.includes("Extension context invalidated")) return;
    }
  }

  // 2) If still no token, try fetching from any open HireMate tab (works when on job sites)
  if (!hasToken) {
    try {
      const res = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
      if (res?.ok && res?.token) hasToken = true;
    } catch (e) {
      if (e?.message?.includes("Extension context invalidated")) return;
    }
  }

  const signinCta = root?.querySelector("#ja-signin-cta");
  const autofillAuth = root?.querySelector("#ja-autofill-authenticated");
  if (signinCta) signinCta.style.display = hasToken ? "none" : "block";
  if (autofillAuth) autofillAuth.style.display = hasToken ? "block" : "none";

  const signinCtaKeywords = root?.querySelector("#ja-signin-cta-keywords");
  const keywordsAuth = root?.querySelector("#ja-keywords-authenticated");
  if (signinCtaKeywords) signinCtaKeywords.style.display = hasToken ? "none" : "block";
  if (keywordsAuth) keywordsAuth.style.display = hasToken ? "block" : "none";

  const signinCtaProfile = root?.querySelector("#ja-signin-cta-profile");
  const profileAuth = root?.querySelector("#ja-profile-authenticated");
  if (signinCtaProfile) signinCtaProfile.style.display = hasToken ? "none" : "block";
  if (profileAuth) profileAuth.style.display = hasToken ? "block" : "none";

  const signinBtns = root?.querySelectorAll(".ja-signin-to-autofill");
  signinBtns?.forEach((btn) => {
    btn.onclick = (e) => {
      e.preventDefault();
      try {
        chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB", url: loginUrl });
      } catch (err) {
        if (!err?.message?.includes("Extension context invalidated")) logWarn("Sign-in click failed", err);
      }
    };
  });

  void updateAutofillFooterStats(root);
}
