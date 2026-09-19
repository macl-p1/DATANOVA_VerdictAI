"use strict";

window.Verdict = (() => {
  const DAY = 86400000;
  const CASES_KEY = "verdictai-cases-v1";
  const USER_KEY = "verdictai-user";
  const THEME_KEY = "verdictai-theme";
  const statutes = {
    "BNS 303(2)": { title: "Theft", maxYears: 5, lifeOrDeath: false },
    "BNS 305(a)": { title: "Theft in a dwelling house", maxYears: 7, lifeOrDeath: false },
    "BNS 316(2)": { title: "Criminal breach of trust", maxYears: 3, lifeOrDeath: false },
    "BNS 324(4)": { title: "Hurt with a dangerous weapon", maxYears: 7, lifeOrDeath: false },
    "BNS 331(4)": { title: "House-breaking by night", maxYears: 5, lifeOrDeath: false },
    "BNS 318(4)": { title: "Cheating", maxYears: 2, lifeOrDeath: false },
    "BNS 305": { title: "Dacoity", maxYears: 10, lifeOrDeath: false },
    "BNS 109": { title: "Attempt to murder", maxYears: 10, lifeOrDeath: false },
    "BNS 103(1)": { title: "Murder", maxYears: 0, lifeOrDeath: true }
  };
  const flags = {
    red: { label: "Past full term" }, amber: { label: "Past half term" }, yellow: { label: "First-time, past third" }, gray: { label: "Not yet eligible" }, review: { label: "Needs review" }, barred: { label: "Barred by law" }
  };
  const rank = { red: 0, amber: 1, yellow: 2, barred: 3, review: 4, gray: 5 };

  function today() { const d = new Date(); d.setHours(0, 0, 0, 0); return d; }
  function isoDaysAgo(days) { const d = today(); d.setDate(d.getDate() - days); return d.toISOString().slice(0, 10); }
  function asDate(value) { return value ? new Date(`${value}T00:00:00`) : null; }
  function daysBetween(start, end = today()) { return Math.round((end - asDate(start)) / DAY); }
  function formatDate(value) { const d = asDate(value); return d ? d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "Not extracted"; }
  function escapeHtml(value) { const el = document.createElement("div"); el.textContent = String(value ?? ""); return el.innerHTML; }
  function quote(text) { return `“${text}”`; }
  function caseItem(id, name, sections, days, firstTime, pending, missing = false) {
    return { id, name, sections, arrestDate: missing ? null : isoDaysAgo(days), firstTimeOffender: missing ? null : firstTime, otherPendingCases: missing ? null : pending, missingData: missing, confidence: { sections: missing ? .62 : .96, arrestDate: missing ? .21 : .97, firstTimeOffender: missing ? .3 : .9, otherPendingCases: missing ? .28 : .89 }, quotes: { sections: quote(`charged under ${sections.join(" and ")} of the Bharatiya Nyaya Sanhita`), arrestDate: missing ? null : quote("the accused was taken into judicial custody on the date recorded in the remand register"), firstTimeOffender: missing ? null : quote(firstTime ? "first instance of offence, according to the antecedent report" : "no first-time-offender finding recorded"), otherPendingCases: missing ? null : quote(pending ? "a further FIR is pending against the same accused" : "no other case is shown pending against the accused") } };
  }
  function seedCases() {
    return [
      caseItem("VA-2026-014", "Rajesh Yadav", ["BNS 303(2)"], 1900, false, false),
      caseItem("VA-2026-021", "Suresh Pawar", ["BNS 316(2)", "BNS 305(a)"], 1400, false, false),
      caseItem("VA-2026-033", "Anita Devi", ["BNS 316(2)"], 450, true, false),
      caseItem("VA-2026-045", "Farhan Sheikh", ["BNS 331(4)"], 940, false, false),
      caseItem("VA-2026-052", "Meena Kumari", ["BNS 103(1)"], 2000, false, false),
      caseItem("VA-2026-059", "Deepak More", ["BNS 305"], 2000, false, true),
      caseItem("VA-2026-066", "Priya Nair", ["BNS 305(a)"], 400, false, false),
      caseItem("VA-2026-071", "Vikram Solanki", ["BNS 318(4)"], 0, false, false, true),
      caseItem("VA-2026-078", "Kavita Joshi", ["BNS 109"], 1300, true, false),
      caseItem("VA-2026-083", "Naseer Ahmed", ["BNS 316(2)"], 140, true, false)
    ];
  }
  function getCases() {
    try { const saved = JSON.parse(localStorage.getItem(CASES_KEY)); if (Array.isArray(saved) && saved.length) return saved; } catch (_) { /* use synthetic data */ }
    const cases = seedCases(); setCases(cases); return cases;
  }
  function setCases(cases) { localStorage.setItem(CASES_KEY, JSON.stringify(cases)); }
  function evaluate(c) {
    if (c.missingData || !c.arrestDate || c.firstTimeOffender === null || c.otherPendingCases === null) return { status: "review", overdueDays: null, rule: "Extraction confidence is too low on a required field. The rule engine will not guess; a human must verify the document first." };
    const charged = c.sections.map((section) => statutes[section]).filter(Boolean);
    const maxYears = Math.max(...charged.map((item) => item.maxYears));
    if (charged.some((item) => item.lifeOrDeath)) return { status: "barred", overdueDays: null, rule: "A charged offence is punishable with death or life imprisonment. Section 479 BNSS does not apply." };
    if (c.otherPendingCases) return { status: "barred", overdueDays: null, rule: "Another case is pending. Release under this provision is barred while that proceeding remains open." };
    const custodyDays = daysBetween(c.arrestDate), maxDays = maxYears * 365, half = maxDays / 2, third = maxDays / 3;
    if (custodyDays > maxDays) return { status: "red", overdueDays: custodyDays - maxDays, custodyDays, maxDays, half, third, rule: `Detention (${custodyDays} days) exceeds the full maximum sentence (${maxDays} days) for the most serious charge.` };
    if (custodyDays > half) return { status: "amber", overdueDays: custodyDays - half, custodyDays, maxDays, half, third, rule: `Detention (${custodyDays} days) has crossed half the maximum sentence (${Math.round(half)} days). Release is due under Section 479(1) BNSS.` };
    if (c.firstTimeOffender && custodyDays > third) return { status: "yellow", overdueDays: custodyDays - third, custodyDays, maxDays, half, third, rule: `As a first-time offender, detention has crossed the one-third threshold (${Math.round(third)} days).` };
    const threshold = c.firstTimeOffender ? third : half;
    return { status: "gray", overdueDays: -(threshold - custodyDays), custodyDays, maxDays, half, third, rule: `Detention has not yet crossed the ${c.firstTimeOffender ? "one-third" : "half"} threshold of ${Math.round(threshold)} days.` };
  }
  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme; else delete document.documentElement.dataset.theme;
    const dark = theme === "dark" || (!theme && matchMedia("(prefers-color-scheme: dark)").matches);
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => { button.setAttribute("aria-pressed", String(dark)); const label = button.querySelector(".theme-toggle-label"); if (label) label.textContent = dark ? "Light mode" : "Dark mode"; });
  }
  function toggleTheme() { const current = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); const next = current === "dark" ? "light" : "dark"; localStorage.setItem(THEME_KEY, next); applyTheme(next); }
  function initTheme() { applyTheme(localStorage.getItem(THEME_KEY)); document.querySelectorAll("[data-theme-toggle]").forEach((button) => button.addEventListener("click", toggleTheme)); }
  function user() { return sessionStorage.getItem(USER_KEY); }
  function login(email) { sessionStorage.setItem(USER_KEY, email); window.location.assign("dashboard.html"); }
  function requireLogin() { const email = user(); if (!email) { window.location.replace("login.html"); return false; } document.querySelectorAll(".app-user-email").forEach((node) => { node.textContent = email; }); document.querySelectorAll("[data-logout]").forEach((button) => button.addEventListener("click", () => { sessionStorage.removeItem(USER_KEY); window.location.assign("login.html"); })); return true; }
  function caseLink(id) { return `case-detail.html?id=${encodeURIComponent(id)}`; }
  initTheme();
  return { statutes, flags, rank, getCases, setCases, evaluate, formatDate, daysBetween, escapeHtml, user, login, requireLogin, caseLink, isoDaysAgo };
})();