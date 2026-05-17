// ─── LinkedIn AI Generation API ───────────────────────────────────────────
// Depends on: getApiBase, getAuthHeaders, fetchWithAuthRetry (api-service.js)

async function _hmApiPost(path, payload) {
  const base = (await getApiBase()).replace(/\/+$/, "");
  const authHeaders = await getAuthHeaders();
  const url = `${base}${path}`;
  console.log("[HM API] POST", url, payload);
  const response = await fetchWithAuthRetry(url, {
    method: "POST",
    headers: { ...authHeaders, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    console.error("[HM API] Error", response.status, err);
    throw new Error(err.detail || `HTTP ${response.status}`);
  }
  const result = await response.json();
  console.log("[HM API] Success", result);
  return result; // { message: string }
}

async function generateColdMessage(payload) {
  return _hmApiPost("/chrome-extension/cold-message/generate", payload);
}

async function generateComment(payload) {
  return _hmApiPost("/chrome-extension/cold-message/generate-comment", payload);
}

async function generateJobAnswer(payload) {
  return _hmApiPost("/chrome-extension/cold-message/generate-job-answer", payload);
}
