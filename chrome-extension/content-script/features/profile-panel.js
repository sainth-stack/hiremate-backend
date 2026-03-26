// ─── Profile Panel Feature ─────────────────────────────────────────────────
// Depends on: PROFILE_TAB_ICONS (icons.js)
//             logInfo, logWarn, escapeHtml (utils.js)
//             getApiBase, getAuthHeaders, fetchWithAuthRetry (api-service.js)
//             getAutofillContextFromApi (autofill-context.js)

async function fetchProfileResumeBlob(ctx) {
  const resumeUrl = ctx?.resumeUrl || ctx?.resume_url;
  const resumeFilename = resumeUrl ? (resumeUrl.split("/").pop() || "").split("?")[0] : null;
  if (!resumeFilename) return null;
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const res = await fetchWithAuthRetry(
    `${apiBase}/chrome-extension/autofill/resume/${encodeURIComponent(resumeFilename)}`,
    { headers }
  );
  if (!res.ok) return null;
  return { blob: await res.blob(), filename: resumeFilename };
}

async function fetchResumesFromApi() {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const res = await fetchWithAuthRetry(`${apiBase}/resume/workspace`, { headers });
  if (!res.ok) return [];
  const data = await res.json();
  console.log(data);
  return data.resumes || [];
}

/** GET /chrome-extension/summary — same auth pattern as autofill-stats.js */
async function fetchExtensionSummary() {
  try {
    let hasToken = false;
    try {
      const t = await chrome.storage.local.get(["accessToken"]);
      hasToken = !!t.accessToken;
    } catch (_) {}
    if (!hasToken) {
      try {
        const res = await chrome.runtime.sendMessage({ type: "FETCH_TOKEN_FROM_OPEN_TAB" });
        if (res?.ok && res?.token) hasToken = true;
      } catch (_) {}
    }
    if (!hasToken) return null;
    const apiBase = await getApiBase();
    const headers = await getAuthHeaders();
    if (!headers.Authorization) return null;
    const res = await fetchWithAuthRetry(`${apiBase}/chrome-extension/summary`, { headers });
    if (!res.ok) return null;
    return await res.json().catch(() => null);
  } catch (_) {
    return null;
  }
}

function _sk(w, h, r) {
  return `<div class="ja-kw-skel" style="width:${w};height:${h}px;border-radius:${r != null ? r : 4}px;display:block"></div>`;
}

function applyProfileSkeleton(root) {
  const q = (id) => root?.querySelector(id);

  // Stats
  [q("#ja-profile-stat-apps"), q("#ja-profile-stat-interviews"), q("#ja-profile-stat-fill")].forEach((el) => {
    if (el) el.innerHTML = _sk("32px", 20, 4);
  });

  // Hero
  const nameEl = q("#ja-profile-name");
  if (nameEl) nameEl.innerHTML = _sk("130px", 16, 4);
  const titleEl = q("#ja-profile-title");
  if (titleEl) titleEl.innerHTML = _sk("80px", 11, 4);
  const avatarEl = q("#ja-profile-avatar");
  if (avatarEl) { avatarEl.textContent = ""; avatarEl.style.background = "#e5e7eb"; }

  // Contact
  const contactEl = q("#ja-profile-contact");
  if (contactEl) {
    const row = (w) => `<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">${_sk("14px", 14, 50)}${_sk(w, 12, 4)}</div>`;
    contactEl.innerHTML = `<div class="ja-prof-contact-grid">${["70%","55%","60%","50%"].map(row).join("")}</div>`;
  }

  // Education
  const eduEl = q("#ja-profile-education");
  if (eduEl) eduEl.innerHTML = `${_sk("58%", 13, 4)}<div style="margin-top:6px">${_sk("40%", 11, 4)}</div><div style="margin-top:4px">${_sk("30%", 10, 4)}</div>`;

  // Experience
  const expEl = q("#ja-profile-experience");
  if (expEl) expEl.innerHTML = `${_sk("52%", 13, 4)}<div style="margin-top:6px">${_sk("36%", 11, 4)}</div><div style="margin-top:5px">${_sk("78%", 10, 4)}</div><div style="margin-top:4px">${_sk("65%", 10, 4)}</div>`;

  // Uploads
  const uploadsEl = q("#ja-profile-uploads");
  if (uploadsEl) uploadsEl.innerHTML = `<div style="display:flex;align-items:center;gap:10px;padding:4px 0">${_sk("32px", 32, 6)}<div style="flex:1">${_sk("55%", 12, 4)}<div style="margin-top:5px">${_sk("38%", 10, 4)}</div></div></div>`;

  // Skills / Languages
  const chipsSkel = (n, w) => `<div style="display:flex;flex-wrap:wrap;gap:6px;padding:2px 0">${Array(n).fill(_sk(w, 24, 20)).join("")}</div>`;
  const techEl = q("#ja-profile-tech-skills");
  if (techEl) techEl.innerHTML = chipsSkel(6, "58px");
  const softEl = q("#ja-profile-soft-skills");
  if (softEl) softEl.innerHTML = chipsSkel(4, "52px");
  const langEl = q("#ja-profile-languages");
  if (langEl) langEl.innerHTML = chipsSkel(3, "46px");
}

async function loadProfileIntoPanel(root) {
  applyProfileSkeleton(root);

  const nameEl = root?.querySelector("#ja-profile-name");
  const contactEl = root?.querySelector("#ja-profile-contact");
  const educationEl = root?.querySelector("#ja-profile-education");
  const experienceEl = root?.querySelector("#ja-profile-experience");
  const uploadsEl = root?.querySelector("#ja-profile-uploads");
  const certificationsEl = root?.querySelector("#ja-profile-certifications");
  const techSkillsEl = root?.querySelector("#ja-profile-tech-skills");
  const softSkillsEl = root?.querySelector("#ja-profile-soft-skills");
  const languagesEl = root?.querySelector("#ja-profile-languages");
  const avatarEl = root?.querySelector("#ja-profile-avatar");
  const titleEl = root?.querySelector("#ja-profile-title");
  const statApps = root?.querySelector("#ja-profile-stat-apps");
  const statInt = root?.querySelector("#ja-profile-stat-interviews");
  const statFill = root?.querySelector("#ja-profile-stat-fill");
  const techCountEl = root?.querySelector("#ja-profile-tech-count");

  const setHtml = (el, html) => {
    if (el) el.innerHTML = html || "—";
  };
  const setText = (el, text) => {
    if (el) el.textContent = text || "—";
  };

  const clearStats = () => {
    if (statApps) statApps.textContent = "—";
    if (statInt) statInt.textContent = "—";
    if (statFill) statFill.textContent = "—";
  };

  try {
    const ctx = await getAutofillContextFromApi();
    root._profileCtx = ctx;
    const flat = ctx.profile || {};
    const detail = ctx.profileDetail;

    try {
      const summary = await fetchExtensionSummary();
      if (summary && typeof summary === "object") {
        const apps = summary.applications;
        const ints = summary.interviews;
        const fr = summary.fill_rate;
        if (statApps) statApps.textContent = typeof apps === "number" && Number.isFinite(apps) ? String(apps) : "—";
        if (statInt) statInt.textContent = typeof ints === "number" && Number.isFinite(ints) ? String(ints) : "—";
        if (statFill) statFill.textContent = typeof fr === "number" && Number.isFinite(fr) ? `${fr}%` : "—";
      } else {
        const st = await chrome.storage.local.get(["hm_stat_applications", "hm_stat_interviews", "hm_stat_fill_rate"]);
        if (statApps) statApps.textContent = st.hm_stat_applications != null ? String(st.hm_stat_applications) : "—";
        if (statInt) statInt.textContent = st.hm_stat_interviews != null ? String(st.hm_stat_interviews) : "—";
        if (statFill) {
          const r = st.hm_stat_fill_rate;
          statFill.textContent = r != null ? (String(r).includes("%") ? String(r) : `${r}%`) : "—";
        }
      }
    } catch (_) {
      clearStats();
    }

    const fullName = [flat.firstName, flat.lastName].filter(Boolean).join(" ") || flat.name || "—";
    setText(nameEl, fullName);
    setText(titleEl, flat.title || flat.professionalHeadline || "");
    try {
      if (avatarEl) {
        const initials = (fullName || "")
          .split(" ")
          .filter(Boolean)
          .slice(0, 2)
          .map((s) => s[0]?.toUpperCase() || "")
          .join("");
        avatarEl.textContent = initials || (flat.name || flat.firstName || "—").charAt(0).toUpperCase();
        avatarEl.style.background = "";
      }
    } catch (_) { }

    const location = [flat.city, flat.country].filter(Boolean).join(", ") || "—";
    const contactRows = [
      { icon: PROFILE_TAB_ICONS.mapPin, key: "Location", copy: location === "—" ? "" : location, display: location },
      { icon: PROFILE_TAB_ICONS.mail, key: "Email", copy: flat.email || "", display: flat.email || "—" },
      { icon: PROFILE_TAB_ICONS.phone, key: "Phone", copy: flat.phone || "", display: flat.phone || "—" },
      { icon: PROFILE_TAB_ICONS.linkedin, key: "LinkedIn", copy: flat.linkedin || "", display: flat.linkedin || "—" },
      { icon: PROFILE_TAB_ICONS.github, key: "GitHub", copy: flat.github || "", display: flat.github || "—" },
      { icon: PROFILE_TAB_ICONS.globe, key: "Portfolio", copy: flat.portfolio || "", display: flat.portfolio || "—" },
    ];
    setHtml(
      contactEl,
      `<div class="ja-prof-contact-grid">${contactRows
        .map(
          (r) => `
      <div class="ja-prof-contact-row">
        <span class="ja-prof-contact-ico">${r.icon}</span>
        <span class="ja-prof-contact-val" title="${escapeHtml(r.display)}">${escapeHtml(r.display)}</span>
        <button type="button" class="ja-prof-copy" data-copy="${escapeHtml(r.copy)}" aria-label="Copy ${escapeHtml(r.key)}">${PROFILE_TAB_ICONS.copy}</button>
      </div>`
        )
        .join("")}</div>`
    );

    const educations = detail?.educations ?? flat.educations ?? [];
    if (educations.length) {
      const eduHtml = educations
        .map((e) => {
          const dates = [e.startYear, e.endYear].filter(Boolean).join(" — ");
          const degreeLine = [e.degree, e.fieldOfStudy].filter(Boolean).join(" · ");
          const gpa = e.grade ? `<span class="ja-prof-badge ja-prof-badge-muted">GPA: ${escapeHtml(e.grade)}</span>` : "";
          return `
        <div class="ja-prof-edu-card">
          <p class="ja-prof-edu-school">${escapeHtml(e.institution || "—")}</p>
          <p class="ja-prof-edu-degree">${escapeHtml(degreeLine || "—")}</p>
          <div class="ja-prof-edu-meta">
            <span class="ja-prof-edu-dates">${escapeHtml(dates || "—")}</span>
            ${gpa}
          </div>
        </div>`;
        })
        .join("");
      setHtml(educationEl, eduHtml);
    } else {
      setHtml(educationEl, `<p class="ja-prof-empty">${escapeHtml(flat.education || "—")}</p>`);
    }

    const experiences = detail?.experiences ?? flat.experiences ?? [];
    if (experiences.length) {
      const expHtml = experiences
        .map((e) => {
          const locDate = [e.location, [e.startDate, e.endDate].filter(Boolean).join(" — ")].filter(Boolean).join(" · ");
          const bullets = (e.description || "")
            .split(/\n|•/)
            .map((s) => s.trim())
            .filter(Boolean)
            .map((b) => `<li class="ja-prof-exp-li"><span class="ja-prof-exp-dot"></span><span>${escapeHtml(b)}</span></li>`)
            .join("");
          const typeBadge = escapeHtml(e.employmentType || "Full-time");
          return `
          <div class="ja-prof-exp-card">
            <div class="ja-prof-exp-top">
              <p class="ja-prof-exp-title">${escapeHtml(e.jobTitle || "—")}</p>
              <span class="ja-prof-badge ja-prof-badge-muted">${typeBadge}</span>
            </div>
            <p class="ja-prof-exp-company">${escapeHtml(e.companyName || "")}</p>
            <p class="ja-prof-exp-meta">${escapeHtml(locDate || "—")}</p>
            ${bullets ? `<ul class="ja-prof-exp-bullets">${bullets}</ul>` : ""}
          </div>`;
        })
        .join("");
      setHtml(experienceEl, expHtml);
    } else {
      setHtml(experienceEl, `<p class="ja-prof-empty">${escapeHtml((flat.experience || flat.professionalSummary || "—").slice(0, 800))}</p>`);
    }

    const certs = flat.certifications || flat.certifications_list || [];
    const certList = Array.isArray(certs) ? certs.map((c) => (typeof c === "string" ? c : c.name || c.title || "")).filter(Boolean) : [];
    const certBlock = root?.querySelector("#ja-profile-cert-block");
    if (certList.length && certificationsEl) {
      if (certBlock) certBlock.style.display = "";
      setHtml(
        certificationsEl,
        `<div class="ja-prof-cert-wrap">${certList.map((c) => `<span class="ja-prof-cert-pill">${PROFILE_TAB_ICONS.awardSm}<span>${escapeHtml(c)}</span></span>`).join("")}</div>`
      );
    } else {
      if (certBlock) certBlock.style.display = "none";
      if (certificationsEl) setHtml(certificationsEl, "");
    }

    const resumeName = ctx.resumeName || ctx.resumeFileName || (ctx.resumeUrl || "").split("/").pop() || "Resume";
    const resumeDate = detail?.resumeLastUpdated ? new Date(detail.resumeLastUpdated).toLocaleString() : "";
    const hasResume = !!(ctx.resumeUrl || ctx.resumeFileName);
    const uploadsHtml = hasResume
      ? `
      <div class="ja-prof-upload-card">
        <div class="ja-prof-upload-left">
          <div class="ja-prof-upload-icon">${PROFILE_TAB_ICONS.fileText}</div>
          <div>
            <p class="ja-prof-upload-name">${escapeHtml(resumeName)}</p>
            <p class="ja-prof-upload-meta">${resumeDate ? `${escapeHtml(resumeDate)}` : "Resume on file"}</p>
          </div>
        </div>
        <div class="ja-prof-upload-actions">
          <button type="button" class="ja-prof-file-btn" id="ja-profile-upload-preview" title="Preview">${PROFILE_TAB_ICONS.eyeFile}</button>
          <button type="button" class="ja-prof-file-btn" id="ja-profile-upload-download" title="Download">${PROFILE_TAB_ICONS.downloadFile}</button>
        </div>
      </div>`
      : `<p class="ja-prof-empty">No uploads</p>`;
    setHtml(uploadsEl, uploadsHtml);
    if (hasResume) {
      const runResume = async (mode) => {
        try {
          const got = await fetchProfileResumeBlob(ctx);
          if (!got) return;
          const url = URL.createObjectURL(got.blob);
          if (mode === "open") window.open(url, "_blank");
          else {
            const a = document.createElement("a");
            a.href = url;
            a.download = got.filename || "resume.pdf";
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 2000);
          }
        } catch (_) { }
      };
      const pPrev = uploadsEl.querySelector("#ja-profile-upload-preview");
      const pDown = uploadsEl.querySelector("#ja-profile-upload-download");
      if (pPrev) pPrev.onclick = () => runResume("open");
      if (pDown) pDown.onclick = () => runResume("download");
    }

    let techSkills = Array.isArray(flat.tech_skills_list) ? [...flat.tech_skills_list] : [];
    let softSkills = Array.isArray(flat.soft_skills_list) ? [...flat.soft_skills_list] : [];
    if (!techSkills.length && !softSkills.length && Array.isArray(flat.skills_list) && flat.skills_list.length) {
      techSkills = [...flat.skills_list];
    } else if (!techSkills.length && !softSkills.length && flat.skills) {
      techSkills = String(flat.skills).split(",").map((s) => s.trim()).filter(Boolean);
    }

    if (techSkills.length) {
      setHtml(
        techSkillsEl,
        `<div class="ja-prof-skill-wrap">${techSkills.map((s) => `<button type="button" class="ja-prof-chip ja-prof-chip-tech ja-prof-skill-copy" data-copy="${escapeHtml(s)}">${escapeHtml(s)}</button>`).join("")}</div>`
      );
      techSkillsEl?.querySelectorAll(".ja-prof-skill-copy").forEach((node) => {
        node.addEventListener("click", () => navigator.clipboard.writeText(node.getAttribute("data-copy") || node.textContent || "").catch(() => { }));
      });
    } else {
      setHtml(techSkillsEl, `<p class="ja-prof-empty">—</p>`);
    }
    if (techCountEl) techCountEl.textContent = `${techSkills.length} skills`;

    if (softSkills.length) {
      setHtml(
        softSkillsEl,
        `<div class="ja-prof-skill-wrap">${softSkills.map((s) => `<span class="ja-prof-chip ja-prof-chip-soft">${escapeHtml(s)}</span>`).join("")}</div>`
      );
    } else {
      setHtml(softSkillsEl, `<p class="ja-prof-empty">—</p>`);
    }

    const langs = Array.isArray(flat.languages_list) ? flat.languages_list : detail?.willingToWorkIn || [];
    if (langs.length) {
      setHtml(
        languagesEl,
        `<div class="ja-prof-skill-wrap">${langs.map((l) => `<span class="ja-prof-chip ja-prof-chip-lang">${escapeHtml(l)}</span>`).join("")}</div>`
      );
    } else {
      setHtml(languagesEl, `<p class="ja-prof-empty">—</p>`);
    }
  } catch (_) {
    clearStats();
    setText(nameEl, "Sign in to load profile");
    setHtml(contactEl, "");
    setHtml(educationEl, "—");
    setHtml(experienceEl, "—");
    setHtml(uploadsEl, "—");
    setHtml(root?.querySelector("#ja-profile-certifications"), "");
    setHtml(techSkillsEl, "—");
    setHtml(softSkillsEl, "—");
    setHtml(languagesEl, "—");
  }
}
