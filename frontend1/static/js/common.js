"use strict";

window.Verdict = (() => {
  const DAY = 86400000;
  const CASES_KEY = "verdictai-cases-v1";
  const USER_KEY = "verdictai-user";
  const THEME_KEY = "verdictai-theme";
  const API_URL_KEY = "verdictai-api-url";

  function getApiUrl() {
    return window.VERDICTAI_API_URL || localStorage.getItem(API_URL_KEY) || "";
  }

  function setApiUrl(url) {
    if (url) localStorage.setItem(API_URL_KEY, url.trim().replace(/\/+$/, ""));
    else localStorage.removeItem(API_URL_KEY);
  }

  const statutes = {
    "BNS 303(2)": { title: "Theft", maxYears: 5, lifeOrDeath: false },
    "BNS 305(a)": { title: "Theft in a dwelling house", maxYears: 7, lifeOrDeath: false },
    "BNS 316(2)": { title: "Criminal breach of trust", maxYears: 3, lifeOrDeath: false },
    "BNS 324(4)": { title: "Hurt with a dangerous weapon", maxYears: 7, lifeOrDeath: false },
    "BNS 331(4)": { title: "House-breaking by night", maxYears: 5, lifeOrDeath: false },
    "BNS 318(4)": { title: "Cheating", maxYears: 2, lifeOrDeath: false },
    "BNS 305": { title: "Dacoity", maxYears: 10, lifeOrDeath: false },
    "BNS 109": { title: "Attempt to murder", maxYears: 10, lifeOrDeath: false },
    "BNS 103(1)": { title: "Murder", maxYears: 0, lifeOrDeath: true },
    "IPC 379": { title: "Theft", maxYears: 3, lifeOrDeath: false },
    "IPC 302": { title: "Murder", maxYears: 0, lifeOrDeath: true }
  };

  const flags = {
    red: { key: "red", apiFlag: "PAST_MAX", label: "Past full term", headline: "Detention already exceeds the full maximum sentence" },
    amber: { key: "amber", apiFlag: "PAST_HALF", label: "Past half term", headline: "Eligible for release - past half the maximum sentence" },
    yellow: { key: "yellow", apiFlag: "PAST_THIRD", label: "First-time, past third", headline: "Eligible for release - first-time offender past one-third" },
    gray: { key: "gray", apiFlag: "NOT_YET", label: "Not yet eligible", headline: "Not yet eligible for release" },
    review: { key: "review", apiFlag: "NEEDS_REVIEW", label: "Needs review", headline: "Needs human review before a flag can be set" },
    barred: { key: "barred", apiFlag: "NOT_ELIGIBLE", label: "Barred by law", headline: "Barred from release under Section 479" }
  };

  const apiFlagToKey = {
    PAST_MAX: "red",
    PAST_HALF: "amber",
    PAST_THIRD: "yellow",
    NOT_ELIGIBLE: "barred",
    NOT_YET: "gray",
    NEEDS_REVIEW: "review"
  };

  const rank = { red: 0, amber: 1, yellow: 2, barred: 3, review: 4, gray: 5 };

  function resolveFlag(flagOrKey) {
    if (!flagOrKey) return flags.review;
    if (flags[flagOrKey]) return flags[flagOrKey];
    const key = apiFlagToKey[flagOrKey] || "review";
    return flags[key] || flags.review;
  }

  function today() {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }

  function isoDaysAgo(days) {
    const d = today();
    d.setDate(d.getDate() - days);
    return d.toISOString().slice(0, 10);
  }

  function asDate(value) {
    return value ? new Date(`${value.slice(0, 10)}T00:00:00`) : null;
  }

  function daysBetween(start, end = today()) {
    const s = asDate(start);
    return s ? Math.round((end - s) / DAY) : 0;
  }

  function formatDate(value) {
    const d = asDate(value);
    return d ? d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "Not extracted";
  }

  function escapeHtml(value) {
    const el = document.createElement("div");
    el.textContent = String(value ?? "");
    return el.innerHTML;
  }

  function quote(text) {
    return `“${text}”`;
  }

  function caseItem(id, name, sections, days, firstTime, pending, missing = false) {
    return {
      id,
      caseId: id,
      name,
      sections,
      arrestDate: missing ? null : isoDaysAgo(days),
      firstTimeOffender: missing ? null : firstTime,
      otherPendingCases: missing ? null : pending,
      missingData: missing,
      confidence: {
        sections: missing ? 0.62 : 0.96,
        arrestDate: missing ? 0.21 : 0.97,
        firstTimeOffender: missing ? 0.3 : 0.9,
        otherPendingCases: missing ? 0.28 : 0.89
      },
      quotes: {
        sections: quote(`charged under ${sections.join(" and ")} of the Bharatiya Nyaya Sanhita`),
        arrestDate: missing ? null : quote("the accused was taken into judicial custody on the date recorded in the remand register"),
        firstTimeOffender: missing ? null : quote(firstTime ? "first instance of offence, according to the antecedent report" : "no first-time-offender finding recorded"),
        otherPendingCases: missing ? null : quote(pending ? "a further FIR is pending against the same accused" : "no other case is shown pending against the accused")
      }
    };
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
    try {
      const saved = JSON.parse(localStorage.getItem(CASES_KEY));
      if (Array.isArray(saved) && saved.length) return saved;
    } catch (_) {
      /* use synthetic data */
    }
    const cases = seedCases();
    setCases(cases);
    return cases;
  }

  function setCases(cases) {
    localStorage.setItem(CASES_KEY, JSON.stringify(cases));
  }

  function evaluate(c) {
    // If evaluated by backend, use backend result directly
    if (c.flag && apiFlagToKey[c.flag]) {
      const status = apiFlagToKey[c.flag];
      const custodyDays = c.arrestDate ? daysBetween(c.arrestDate) : (c.daysInCustody ?? 0);
      return {
        status,
        apiFlag: c.flag,
        overdueDays: c.daysOverdue ?? c.overdueDays ?? (status === "review" || status === "barred" ? null : 0),
        custodyDays,
        maxDays: c.maxDays || 1825,
        half: c.half || 912,
        third: c.third || 608,
        rule: c.ruleFired || c.rule || flags[status].label
      };
    }

    if (c.missingData || !c.arrestDate || c.firstTimeOffender === null || c.otherPendingCases === null) {
      return {
        status: "review",
        apiFlag: "NEEDS_REVIEW",
        overdueDays: null,
        rule: "Extraction confidence is too low on a required field. The rule engine will not guess; a human must verify the document first."
      };
    }

    const charged = (c.sections || []).map((section) => statutes[section] || statutes[section.replace("#", " ")]).filter(Boolean);
    const maxYears = charged.length ? Math.max(...charged.map((item) => item.maxYears)) : 5;

    if (charged.some((item) => item.lifeOrDeath)) {
      return {
        status: "barred",
        apiFlag: "NOT_ELIGIBLE",
        overdueDays: null,
        rule: "A charged offence is punishable with death or life imprisonment. Section 479 BNSS does not apply."
      };
    }

    if (c.otherPendingCases) {
      return {
        status: "barred",
        apiFlag: "NOT_ELIGIBLE",
        overdueDays: null,
        rule: "Another case is pending. Release under this provision is barred while that proceeding remains open."
      };
    }

    const custodyDays = daysBetween(c.arrestDate);
    const maxDays = maxYears * 365;
    const half = maxDays / 2;
    const third = maxDays / 3;

    if (custodyDays >= maxDays) {
      return {
        status: "red",
        apiFlag: "PAST_MAX",
        overdueDays: custodyDays - maxDays,
        custodyDays,
        maxDays,
        half,
        third,
        rule: `Detention (${custodyDays} days) exceeds the full maximum sentence (${maxDays} days) for the most serious charge.`
      };
    }

    if (custodyDays >= half) {
      return {
        status: "amber",
        apiFlag: "PAST_HALF",
        overdueDays: custodyDays - half,
        custodyDays,
        maxDays,
        half,
        third,
        rule: `Detention (${custodyDays} days) has crossed half the maximum sentence (${Math.round(half)} days). Release is due under Section 479(1) BNSS.`
      };
    }

    if (c.firstTimeOffender && custodyDays >= third) {
      return {
        status: "yellow",
        apiFlag: "PAST_THIRD",
        overdueDays: custodyDays - third,
        custodyDays,
        maxDays,
        half,
        third,
        rule: `As a first-time offender, detention has crossed the one-third threshold (${Math.round(third)} days).`
      };
    }

    const threshold = c.firstTimeOffender ? third : half;
    return {
      status: "gray",
      apiFlag: "NOT_YET",
      overdueDays: -(threshold - custodyDays),
      custodyDays,
      maxDays,
      half,
      third,
      rule: `Detention has not yet crossed the ${c.firstTimeOffender ? "one-third" : "half"} threshold of ${Math.round(threshold)} days.`
    };
  }

  function normalizeCase(raw) {
    if (!raw) return null;
    const id = raw.caseId || raw.id || "UNKNOWN";
    const flagInfo = resolveFlag(raw.flag || (raw.status && flags[raw.status] ? raw.status : null));
    const sections = Array.isArray(raw.sections)
      ? raw.sections.map((s) => String(s).replace("#", " "))
      : [];
    const arrestDate = raw.arrestDate ? String(raw.arrestDate).slice(0, 10) : null;
    const overdueDays = raw.daysOverdue !== undefined && raw.daysOverdue !== null
      ? Number(raw.daysOverdue)
      : (raw.overdueDays !== undefined ? Number(raw.overdueDays) : null);

    return {
      id,
      caseId: id,
      name: raw.name || `Case ${id.slice(0, 8)}`,
      sections,
      rawSections: raw.sections || [],
      arrestDate,
      status: raw.status || "PROCESSED",
      flag: flagInfo.apiFlag,
      uiStatus: flagInfo.key,
      overdueDays,
      daysOverdue: overdueDays,
      rule: raw.ruleFired || raw.rule || "",
      ruleFired: raw.ruleFired || raw.rule || "",
      explanation: raw.explanation || "",
      firstTimeOffender: raw.firstTimeOffender ?? null,
      otherPendingCases: raw.otherPendingCases ?? null,
      missingData: raw.missingData ?? (!arrestDate || !sections.length),
      confidence: raw.confidence || {
        sections: sections.length ? 0.95 : 0.4,
        arrestDate: arrestDate ? 0.95 : 0.2,
        firstTimeOffender: 0.85,
        otherPendingCases: 0.85
      },
      quotes: raw.quotes || {
        sections: sections.length ? quote(`charged under ${sections.join(" and ")}`) : null,
        arrestDate: arrestDate ? quote(`custody commenced on ${arrestDate}`) : null,
        firstTimeOffender: null,
        otherPendingCases: null
      },
      createdAt: raw.createdAt || null,
      updatedAt: raw.updatedAt || null
    };
  }

  // --- API Methods with Mock Fallbacks ---

  async function fetchCases() {
    const baseUrl = getApiUrl();
    if (baseUrl) {
      try {
        const res = await fetch(`${baseUrl}/cases`);
        if (res.ok) {
          const data = await res.json();
          const items = Array.isArray(data) ? data : (data.items || data.Items || []);
          return items.map(normalizeCase);
        }
      } catch (err) {
        console.warn("API fetchCases error, using local data:", err);
      }
    }
    return getCases().map(normalizeCase);
  }

  async function fetchCase(id) {
    const baseUrl = getApiUrl();
    if (baseUrl) {
      try {
        const res = await fetch(`${baseUrl}/cases/${encodeURIComponent(id)}`);
        if (res.ok) {
          const data = await res.json();
          return normalizeCase(data);
        }
      } catch (err) {
        console.warn(`API fetchCase(${id}) error, using local data:`, err);
      }
    }
    const local = getCases().find((item) => (item.caseId || item.id) === id);
    return local ? normalizeCase(local) : null;
  }

  async function fetchBailDraft(id) {
    const baseUrl = getApiUrl();
    if (baseUrl) {
      const res = await fetch(`${baseUrl}/cases/${encodeURIComponent(id)}/bail-draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (res.ok) {
        const data = await res.json();
        return data.draft || null;
      }
      const err = await res.json().catch(() => ({}));
      if (err.error) throw new Error(err.error);
    }
    return null;
  }

  async function getUploadUrl() {
    const baseUrl = getApiUrl();
    if (!baseUrl) return null;
    const res = await fetch(`${baseUrl}/cases/upload-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });
    if (!res.ok) throw new Error(`Upload request failed with status ${res.status}`);
    return await res.json(); // { caseId, uploadUrl }
  }

  async function uploadFileToS3(uploadUrl, file) {
    const res = await fetch(uploadUrl, {
      method: "PUT",
      headers: { "Content-Type": "application/pdf" },
      body: file
    });
    if (!res.ok) throw new Error(`File upload to S3 failed (${res.status})`);
    return true;
  }

  async function pollCase(id, onProgress, maxAttempts = 30) {
    const baseUrl = getApiUrl();
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const res = await fetch(`${baseUrl}/cases/${encodeURIComponent(id)}`);
        if (res.ok) {
          const data = await res.json();
          if (onProgress) onProgress(data);
          if (data.status === "PROCESSED" || data.flag) {
            return normalizeCase(data);
          }
          if (data.status === "FAILED") {
            throw new Error("Case processing failed in the backend pipeline.");
          }
        }
      } catch (err) {
        if (err.message.includes("Case processing failed")) throw err;
        console.warn("Polling error:", err);
      }
    }
    throw new Error("Case processing timed out. Please check the dashboard in a few moments.");
  }

  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
    const dark = theme === "dark" || (!theme && matchMedia("(prefers-color-scheme: dark)").matches);
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-pressed", String(dark));
      const label = button.querySelector(".theme-toggle-label");
      if (label) label.textContent = dark ? "Light mode" : "Dark mode";
    });
  }

  function toggleTheme() {
    const current = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  }

  function initTheme() {
    applyTheme(localStorage.getItem(THEME_KEY));
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => button.addEventListener("click", toggleTheme));
  }

  function user() {
    return sessionStorage.getItem(USER_KEY);
  }

  function login(email) {
    sessionStorage.setItem(USER_KEY, email);
    window.location.assign("dashboard.html");
  }

  function requireLogin() {
    const email = user();
    if (!email) {
      window.location.replace("login.html");
      return false;
    }
    document.querySelectorAll(".app-user-email").forEach((node) => {
      node.textContent = email;
    });
    document.querySelectorAll("[data-logout]").forEach((button) => button.addEventListener("click", () => {
      sessionStorage.removeItem(USER_KEY);
      window.location.assign("login.html");
    }));
    return true;
  }

  function caseLink(id) {
    return `case-detail.html?id=${encodeURIComponent(id)}`;
  }

  initTheme();

  return {
    statutes,
    flags,
    rank,
    apiFlagToKey,
    resolveFlag,
    getApiUrl,
    setApiUrl,
    normalizeCase,
    getCases,
    setCases,
    fetchCases,
    fetchCase,
    fetchBailDraft,
    getUploadUrl,
    uploadFileToS3,
    pollCase,
    evaluate,
    formatDate,
    daysBetween,
    escapeHtml,
    user,
    login,
    requireLogin,
    caseLink,
    isoDaysAgo
  };
})();