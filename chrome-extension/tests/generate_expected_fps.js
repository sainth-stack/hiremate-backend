/**
 * Run: node chrome-extension/tests/generate_expected_fps.js
 * Outputs expected fingerprints to populate test_fingerprint_parity.py
 * CRITICAL: key order {label, options, type} must match Python sort_keys=True
 */
const { webcrypto } = require("crypto");

function normalizeLabel(text) {
  return (text || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9 ]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function computeFieldFingerprint(field) {
  const label = normalizeLabel(field.label || field.placeholder || field.name || "");
  const ftype = (field.type || "").toLowerCase().trim();
  const options = (field.options || []).map(normalizeLabel).sort();
  const payload = JSON.stringify({ label, options, type: ftype });
  const buf = await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode(payload));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
}

const cases = [
  { label: "Email Address", type: "email", options: [] },
  { label: "First Name", type: "text", options: [] },
  { label: "Phone Number", type: "tel", options: [] },
  { label: "Current Location", type: "select", options: ["United States", "Canada", "United Kingdom"] },
  { label: "", type: "text", options: [] },
  { label: "Are you authorized to work?", type: "radio", options: ["Yes", "No"] },
];

(async () => {
  console.log("# Paste these into test_fingerprint_parity.py PARITY_CASES:\n");
  for (const field of cases) {
    const fp = await computeFieldFingerprint(field);
    console.log(`    # ${JSON.stringify(field)}`);
    console.log(`    "${fp}",\n`);
  }
})();
