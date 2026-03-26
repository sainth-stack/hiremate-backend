// ─── Fill Engine ───────────────────────────────────────────────────────────
// Depends on: FIELD_MAP, TEXTLIKE_INPUT_TYPES (consts.js)
//             logInfo, logWarn, normalizeKey, getText, delay (utils.js)
//             getFillableFields, getFieldMeta, getClosestQuestionText,
//             setNativeValue, fillFileInput, scrollFieldIntoView,
//             highlightFailedField, highlightUnfilledRequiredFields,
//             dispatchFrameworkEvents, formatDateForInput (dom-utils.js)
//             getAutofillContextFromApi (autofill-context.js)
//             getApiBase, getAuthHeaders, fetchWithAuthRetry (api-service.js)

// ─── Field Helpers ─────────────────────────────────────────────────────────

function isEmptyField(field) {
  const tag = (field.tagName || "").toLowerCase();
  if (field.isContentEditable) return !normalizeKey(getText(field));
  if (tag === "input") {
    const type = (field.type || "").toLowerCase();
    if (type === "checkbox" || type === "radio") return !field.checked;
    return !String(field.value || "").trim();
  }
  if (tag === "textarea") return !String(field.value || "").trim();
  if (tag === "select") return !String(field.value || "").trim();
  return !normalizeKey(getText(field));
}

function getFieldKeys(meta) {
  const sources = [meta.label, meta.name, meta.id, meta.placeholder, meta.type, meta.role, meta.tag].filter(Boolean);
  return sources.map((s) => normalizeKey(s)).filter(Boolean);
}

function pickRuleBasedValue(meta, profile, customAnswers) {
  const keys = getFieldKeys(meta);
  const allText = keys.join(" ");

  const customEntries = Object.entries(customAnswers || {});
  for (const [question, answer] of customEntries) {
    const normQ = normalizeKey(question);
    if (!normQ || !answer) continue;
    if (keys.includes(normQ) || allText.includes(normQ) || normQ.includes(allText)) return answer;
  }

  for (const [profileKey, aliases] of Object.entries(FIELD_MAP)) {
    if (!profile?.[profileKey]) continue;
    const match = aliases.some((alias) => {
      const normAlias = normalizeKey(alias);
      return keys.includes(normAlias) || allText.includes(normAlias);
    });
    if (match) return profile[profileKey];
  }

  if (meta.tag === "input" && TEXTLIKE_INPUT_TYPES.has(meta.type)) {
    if (meta.type === "email" && profile?.email) return profile.email;
    if (meta.type === "tel" && profile?.phone) return profile.phone;
    if (meta.type === "url") {
      if (allText.includes("linkedin") && profile?.linkedin) return profile.linkedin;
      if (allText.includes("github") && profile?.github) return profile.github;
      if (profile?.portfolio) return profile.portfolio;
    }
  }

  if (meta.tag === "textarea" && profile?.experience) {
    if (allText.includes("experience") || allText.includes("summary") || allText.includes("about")) {
      return profile.experience;
    }
  }

  return null;
}

async function getResumeFromBackground() {
  try {
    const res = await chrome.runtime.sendMessage({ type: "GET_RESUME" });
    if (res?.ok) return res.data || null;
  } catch (_) {
    // Ignore resume retrieval errors for non-file fields.
  }
  return null;
}

// ─── Fill With Values ──────────────────────────────────────────────────────

async function fillWithValues(payload) {
  const humanFiller = typeof window !== "undefined" && window.__HIREMATE_HUMAN_FILLER__;
  if (humanFiller) {
    try {
      const includeNestedDocuments = payload.scope !== "current_document";
      const { values = {}, fieldsForFrame = [], resumeData, onProgress, shouldAbort } = payload;
      logInfo("Fill: starting (human-like)", { providedValues: Object.keys(values).length, fieldsWithSelectors: fieldsForFrame.length, scope: payload.scope });
      let fillable = getFillableFields(includeNestedDocuments, true);
      if (fillable.length === 0) fillable = getFillableFields(true, false);
      const resumeWithTimeout = () =>
        Promise.race([
          getResumeFromBackground(),
          new Promise((_, rej) => setTimeout(() => rej(new Error("Resume timeout")), 8000)),
        ]).catch(() => null);
      const effectiveResumeData = resumeData || (await resumeWithTimeout()) || (await getStaticResume());

      const result = await humanFiller.fillWithValuesHumanLike({
        elements: fillable,
        values,
        valuesByIndex: values,
        fieldsForFrame,
        resumeData: effectiveResumeData,
        getFieldMeta,
        getFieldKeys,
        dispatchFrameworkEvents,
        onProgress,
        shouldAbort,
        formatDateForInput,
        highlightFailedField,
      });

      logInfo("Fill: completed (human-like)", { totalFillable: fillable.length, filled: result.filledCount, resumes: result.resumeUploadCount, failed: result.failedCount });
      highlightUnfilledRequiredFields(includeNestedDocuments);
      return result;
    } catch (e) {
      logWarn("Human filler failed, falling back to legacy", { error: String(e) });
    }
  }

  const includeNestedDocuments = payload.scope !== "current_document";
  const { values = {}, resumeData, onProgress, shouldAbort, shouldSkip } = payload;
  logInfo("Fill: starting (legacy)", { providedValues: Object.keys(values).length, scope: payload.scope });
  let fillable = getFillableFields(includeNestedDocuments, false);
  if (fillable.length === 0) fillable = getFillableFields(true, true);
  const resumeWithTimeout = () =>
    Promise.race([
      getResumeFromBackground(),
      new Promise((_, rej) => setTimeout(() => rej(new Error("Resume timeout")), 8000)),
    ]).catch(() => null);
  const effectiveResumeData = resumeData || (await resumeWithTimeout()) || (await getStaticResume());
  const fillDelay = 60 + Math.floor(Math.random() * 60);
  let filledCount = 0;
  let resumeUploadCount = 0;
  let failedCount = 0;
  const failedFields = [];
  const indexed = fillable.map((el, i) => ({ element: el, originalIndex: i }));
  const totalToFill = indexed.length;

  for (let idx = 0; idx < indexed.length; idx++) {
    if (shouldAbort?.()) break;
    if (shouldSkip?.()) continue;
    const { element: field, originalIndex: i } = indexed[idx];
    const id = field.getAttribute("id");
    let val;

    await scrollFieldIntoView(field);

    const meta = getFieldMeta(field);
    const fieldLabel = meta.label || meta.name || meta.placeholder || getClosestQuestionText(field) || `Field ${i + 1}`;
    const isResumeField =
      (field.type || "").toLowerCase() === "file" &&
      (getFieldKeys(meta).join(" ").includes("resume") || getFieldKeys(meta).join(" ").includes("cv"));
    const progressMessage = isResumeField ? "Filling resume..." : `Filling field ${idx + 1} of ${totalToFill}`;
    if (onProgress) {
      onProgress({ phase: "filling", current: idx + 1, total: totalToFill, message: progressMessage, label: fieldLabel });
    }

    if (id && values[id] !== undefined) {
      val = typeof values[id] === "object" && values[id] !== null ? values[id].value : values[id];
    } else if (values[i] !== undefined) {
      val = typeof values[i] === "object" && values[i] !== null ? values[i].value : values[i];
    }

    if ((field.type || "").toLowerCase() === "file") {
      const fieldKeysText = getFieldKeys(meta).join(" ");
      const looksLikeResumeField = fieldKeysText.includes("resume") || fieldKeysText.includes("cv");
      const shouldUploadResume = val === "RESUME_FILE" || looksLikeResumeField;
      if (shouldUploadResume && effectiveResumeData) {
        const ok = await fillFileInput(field, effectiveResumeData);
        if (ok) {
          resumeUploadCount += 1;
          logInfo("Filled resume field", { index: i, label: meta.label });
        } else {
          failedCount += 1;
          highlightFailedField(field);
          failedFields.push({ element: field, label: fieldLabel });
        }
      } else if (shouldUploadResume) {
        failedCount += 1;
        highlightFailedField(field);
        failedFields.push({ element: field, label: fieldLabel });
        logWarn("Resume field found but no resume data available", { index: i, id: id || null, label: meta.label || null });
      }
      await delay(fillDelay);
      continue;
    }

    if (val === undefined || val === null || val === "") {
      if (meta.required) {
        failedCount += 1;
        highlightFailedField(field);
        failedFields.push({ element: field, label: fieldLabel });
      }
      await delay(fillDelay);
      continue;
    }

    const success = setNativeValue(field, val);
    if (success) {
      filledCount += 1;
      logInfo("Filled field", { index: i, label: meta.label, value: String(val).substring(0, 50) });
    } else {
      failedCount += 1;
      highlightFailedField(field);
      failedFields.push({ element: field, label: fieldLabel });
    }
    await delay(fillDelay);
  }
  logInfo("Fill: completed (legacy)", { totalFillable: fillable.length, filled: filledCount, resumes: resumeUploadCount, failed: failedCount });
  highlightUnfilledRequiredFields(includeNestedDocuments);
  return { filledCount, resumeUploadCount, failedCount, failedFields };
}

async function fillFormRuleBased(payload = {}) {
  const includeNestedDocuments = payload.scope !== "current_document";
  logInfo("Starting rule-based fill");
  const [{ profile = {}, customAnswers = {} }, resumeData] = await Promise.all([
    chrome.storage.local.get(["profile", "customAnswers"]),
    getResumeFromBackground(),
  ]);

  const fillable = getFillableFields(includeNestedDocuments);
  const fillDelay = 60 + Math.floor(Math.random() * 60);
  let filledCount = 0;
  let resumeUploadCount = 0;

  for (const field of fillable) {
    if (!isEmptyField(field)) continue;
    const meta = getFieldMeta(field);
    if (meta.type === "file") {
      const shouldUseResume = getFieldKeys(meta).join(" ").includes("resume");
      if (shouldUseResume && resumeData) {
        const ok = await fillFileInput(field, resumeData);
        if (ok) { filledCount += 1; resumeUploadCount += 1; }
      }
      await delay(fillDelay);
      continue;
    }
    const val = pickRuleBasedValue(meta, profile, customAnswers);
    if (!val) continue;
    const ok = setNativeValue(field, val);
    if (ok) { filledCount += 1; await delay(fillDelay); }
  }

  logInfo("Rule-based fill completed", { totalFillable: fillable.length, totalFilled: filledCount, resumeUploads: resumeUploadCount });
  return { filledCount };
}

// ─── Fill Orchestration Helpers ────────────────────────────────────────────

const EDUCATION_ATS = new Set(["school", "degree", "major", "graduation_year"]);
const EMPLOYMENT_ATS = new Set(["company", "job_title", "start_date", "end_date"]);

/** Build flat profileValues for Workday step manager from context. */
function buildProfileValuesForWorkday(context) {
  const p = context?.profile || {};
  const custom = context?.customAnswers || {};
  const exp0 = p.experiences?.[0] || {};
  const edu0 = p.educations?.[0] || {};
  const values = {
    first_name: p.firstName || "",
    last_name: p.lastName || "",
    full_name: (p.firstName && p.lastName ? `${p.firstName} ${p.lastName}` : p.name || "").trim(),
    email: p.email || "",
    phone: p.phone || "",
    linkedin: p.linkedin || "",
    portfolio: p.portfolio || "",
    github: p.github || "",
    address: p.location || p.address || "",
    city: p.city || "",
    state: p.state || "",
    country: p.country || "",
    postal_code: p.postalCode || p.zip || "",
    work_authorization: p.workAuthorization || p.work_authorization || "Yes",
    sponsorship: p.sponsorship || "No",
    school: edu0.institution || p.school || "",
    degree: edu0.degree || p.degree || "",
    major: edu0.fieldOfStudy || p.major || p.fieldOfStudy || "",
    graduation_year: String(edu0.endYear || edu0.graduationYear || p.graduationYear || ""),
    company: exp0.companyName || p.company || "",
    job_title: exp0.jobTitle || p.title || p.jobTitle || "",
    years_experience: p.yearsExperience || p.experience || "",
    salary: p.expectedSalary || p.salary || "",
    notice_period: p.noticePeriod || p.availability || "",
    referral_source: p.referralSource || "LinkedIn",
    gender: p.gender || "",
    ethnicity: p.ethnicity || p.race || "",
    veteran_status: p.veteranStatus || "I am not a protected veteran",
    disability_status: p.disabilityStatus || "I don't wish to answer",
  };
  for (const [k, v] of Object.entries(custom)) {
    if (v != null && String(v).trim() !== "") {
      const norm = String(k).toLowerCase().trim().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
      if (norm) values[norm] = String(v).trim();
    }
  }
  return values;
}

function buildValuesByFrameWithLimits(fields, mappings, maxEducationBlocks, maxEmploymentBlocks) {
  const occurrenceByFp = {};
  const valuesByFrame = {};
  for (const field of fields) {
    const mapData = mappings[String(field.index)] || mappings[field.index] || mappings[field.fingerprint];
    let val = mapData?.value;
    if ((field.type || "").toLowerCase() === "file" && !val) val = "RESUME_FILE";
    if (val === undefined || val === null || val === "") continue;
    const ats = (field.atsFieldType || "").toLowerCase();
    const fp = field.fingerprint;
    if (EDUCATION_ATS.has(ats) || EMPLOYMENT_ATS.has(ats)) {
      const capKey = fp || `__synthetic__${ats}_${(field.label || "").slice(0, 20).toLowerCase().replace(/\s+/g, "_")}`;
      const seen = occurrenceByFp[capKey] ?? 0;
      occurrenceByFp[capKey] = seen + 1;
      const maxBlocks = EDUCATION_ATS.has(ats) ? maxEducationBlocks : maxEmploymentBlocks;
      if (seen >= maxBlocks) continue;
    }
    const fid = String(field.frameId ?? 0);
    const localKey = String(field.frameLocalIndex ?? field.index);
    if (!valuesByFrame[fid]) valuesByFrame[fid] = {};
    valuesByFrame[fid][localKey] = val;
  }
  return valuesByFrame;
}

function buildFieldsByFrame(fields) {
  const fieldsByFrame = {};
  for (const field of fields) {
    const frameId = String(field.frameId ?? 0);
    if (!fieldsByFrame[frameId]) fieldsByFrame[frameId] = [];
    const localKey = String(field.frameLocalIndex ?? field.index);
    fieldsByFrame[frameId].push({
      index: localKey,
      frameLocalIndex: field.frameLocalIndex ?? field.index,
      selector: field.selector || null,
      id: field.domId || field.id || null,
      domId: field.domId || field.id || null,
      label: field.label || null,
      type: field.type || null,
      tag: field.tag || null,
      atsFieldType: field.atsFieldType || null,
      options: field.options || [],
    });
  }
  return fieldsByFrame;
}

async function fetchMappingsFromApi(fields, context) {
  const apiBase = await getApiBase();
  const headers = await getAuthHeaders();
  const mapRes = await fetchWithAuthRetry(`${apiBase}/chrome-extension/form-fields/map`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({
      fields: fields.map((field) => ({ ...field, id: null })),
      profile: context.profile,
      custom_answers: context.customAnswers,
      resume_text: context.resumeText,
      sync_llm: true,
    }),
  });
  if (!mapRes.ok) throw new Error(`AI mapping failed (${mapRes.status})`);
  const mapData = await mapRes.json();
  return mapData.mappings || {};
}
if (typeof window !== "undefined") window.__FETCH_MAPPINGS_FROM_API__ = fetchMappingsFromApi;
