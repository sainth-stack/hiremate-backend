// ─── LinkedIn AI Generation API ───────────────────────────────────────────
// Depends on: getApiBase, getAuthHeaders, fetchWithAuthRetry (api-service.js)

async function _hmApiPost(path, payload) {
  const base = (await getApiBase()).replace(/\/+$/, "");
  const authHeaders = await getAuthHeaders();
  const response = await fetchWithAuthRetry(`${base}${path}`, {
    method: "POST",
    headers: { ...authHeaders, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }
  return response.json(); // { message: string }
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
