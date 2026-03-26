// ─── Keyword Match UI Helpers ──────────────────────────────────────────────
// Depends on: KEYWORD_TAB_ICONS (icons.js), escapeHtml (utils.js)

function keywordGaugeDashArray(percent) {
  const c = 213.628;
  const p = Math.max(0, Math.min(100, Number(percent) || 0));
  return `${(p / 100) * c} ${c}`;
}

/** @returns {{ label: string, color: string, badgeBg: string, stroke: string }} */
function keywordMatchTheme(matchPercent, totalKeywords) {
  if (!totalKeywords) {
    return { label: "No skills found", color: "#6b7280", badgeBg: "rgba(243, 244, 246, 0.9)", stroke: "#e5e7eb" };
  }
  const p = Number(matchPercent) || 0;
  if (p >= 70) return { label: "Strong Match", color: "#16a34a", badgeBg: "rgba(34, 197, 94, 0.12)", stroke: "#22c55e" };
  if (p >= 40) return { label: "Needs Improvement", color: "#d97706", badgeBg: "rgba(245, 158, 11, 0.12)", stroke: "#f59e0b" };
  return { label: "Weak Match", color: "#dc2626", badgeBg: "rgba(239, 68, 68, 0.1)", stroke: "#ef4444" };
}

function renderKeywordMatchChip(item) {
  const freq = item.frequency != null ? Number(item.frequency) : 1;
  const m = item.matched;
  return `<div class="ja-kw-chip ${m ? "ja-kw-chip--on" : "ja-kw-chip--off"}">
    <span class="ja-kw-chip-box">${m ? KEYWORD_TAB_ICONS.chipCheck : ""}</span>
    <span class="ja-kw-chip-name">${escapeHtml(item.keyword)}</span>
    <span class="ja-kw-chip-freq">×${Number.isFinite(freq) ? freq : 1}</span>
  </div>`;
}
