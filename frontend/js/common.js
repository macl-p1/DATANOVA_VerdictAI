"use strict";

/**
 * Shared presentation helpers.
 *
 * This file used to carry a second copy of the rule engine and the statute
 * table. Both are gone: eligibility is decided once, in the rules Lambda, and
 * the frontend only renders what the backend decided. If a flag looks wrong,
 * the fix belongs in backend/functions/rules/app.py.
 */
window.Verdict = (() => {
  const DAY = 86400000;
  const THEME_KEY = "verdictai-theme";

  // Mirrors FLAG_TO_STATUS in backend/shared/schemas.py. The backend flag is
  // the source of truth; these are only the colour and wording for each one.
  const FLAG_TO_STATUS = {
    PAST_MAX: "red",
    PAST_HALF: "amber",
    PAST_THIRD: "yellow",
    NOT_ELIGIBLE: "barred",
    NOT_YET: "gray",
    NEEDS_REVIEW: "review",
  };
  const STATUS_TO_FLAG = Object.fromEntries(Object.entries(FLAG_TO_STATUS).map(([f, s]) => [s, f]));

  const flags = {
    red: { label: "Past full term" },
    amber: { label: "Past half term" },
    yellow: { label: "First-time, past third" },
    gray: { label: "Not yet eligible" },
    review: { label: "Needs review" },
    barred: { label: "Barred by law" },
    pending: { label: "Processing" },
  };
  const rank = { red: 0, amber: 1, yellow: 2, barred: 3, review: 4, gray: 5, pending: 6 };

  const FACT_LABELS = {
    accused_name: "Accused name",
    sections: "Section(s) charged",
    arrest_date: "Arrest date",
    in_custody: "Currently in custody",
    release_date: "Release date",
    first_time_offender: "First-time offender",
    other_pending_cases: "Other cases pending",
  };

  function today() { const d = new Date(); d.setHours(0, 0, 0, 0); return d; }
  function asDate(value) { return value ? new Date(`${value}T00:00:00`) : null; }
  function daysBetween(start, end = today()) { const d = asDate(start); return d ? Math.round((end - d) / DAY) : null; }
  function formatDate(value) {
    const d = asDate(value);
    return d && !Number.isNaN(d.getTime())
      ? d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
      : "Not extracted";
  }
  function formatTimestamp(value) {
    if (!value) return "—";
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
  }
  function escapeHtml(value) { const el = document.createElement("div"); el.textContent = String(value ?? ""); return el.innerHTML; }

  /** "BNS#303(2)" is the storage key; "BNS 303(2)" is what a lawyer reads. */
  function formatSection(code) { return String(code ?? "").replace("#", " "); }
  function formatSections(list) {
    return Array.isArray(list) && list.length ? list.map(formatSection).join(", ") : "Not extracted";
  }
  function formatBool(value, { yes = "Yes", no = "No" } = {}) {
    if (value === null || value === undefined || value === "") return null;
    return value ? yes : no;
  }

  /**
   * A case is only shown with its rule-engine flag once the pipeline has
   * finished. While it is still moving through Step Functions the record
   * carries a placeholder flag, so status is checked first.
   */
  function statusOf(record) {
    if (!record) return "review";
    if (record.status === "UPLOADED") return "pending";
    if (record.status === "FAILED") return "review";
    return FLAG_TO_STATUS[record.flag] || "review";
  }

  function isPending(record) { return record && record.status === "UPLOADED"; }

  /** Name to show in the register before extraction has produced one. */
  function displayName(record) {
    if (record.accusedName) return record.accusedName;
    if (record.sourceFilename) return record.sourceFilename;
    return isPending(record) ? "Processing…" : "Name not extracted";
  }

  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme; else delete document.documentElement.dataset.theme;
    const dark = theme === "dark" || (!theme && matchMedia("(prefers-color-scheme: dark)").matches);
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => { button.setAttribute("aria-pressed", String(dark)); const label = button.querySelector(".theme-toggle-label"); if (label) label.textContent = dark ? "Light mode" : "Dark mode"; });
  }
  function toggleTheme() { const current = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); const next = current === "dark" ? "light" : "dark"; localStorage.setItem(THEME_KEY, next); applyTheme(next); }
  function initTheme() { applyTheme(localStorage.getItem(THEME_KEY)); document.querySelectorAll("[data-theme-toggle]").forEach((button) => button.addEventListener("click", toggleTheme)); }

  // Sign-in is enforced by the Cognito authorizer on the API, not here. This
  // only keeps the screens coherent: it hides pages from a signed-out user and
  // wires the sign-out button. Skipping it would gain nothing — every API call
  // is rejected without a valid token.
  function user() { return VerdictAuth.email(); }
  function requireLogin() {
    if (!VerdictAuth.isSignedIn()) { window.location.replace("login.html"); return false; }
    const email = user() || "";
    document.querySelectorAll(".app-user-email").forEach((node) => { node.textContent = email; });
    document.querySelectorAll("[data-logout]").forEach((button) =>
      button.addEventListener("click", () => VerdictAuth.signOut()));
    return true;
  }
  function caseLink(id) { return `case-detail.html?id=${encodeURIComponent(id)}`; }

  initTheme();
  return {
    flags, rank, FLAG_TO_STATUS, STATUS_TO_FLAG, FACT_LABELS,
    statusOf, isPending, displayName,
    formatDate, formatTimestamp, formatSection, formatSections, formatBool,
    daysBetween, escapeHtml, user, requireLogin, caseLink,
  };
})();
