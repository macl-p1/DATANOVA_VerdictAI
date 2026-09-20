"use strict";

(async () => {
  if (!Verdict.requireLogin()) return;
  const root = document.querySelector("#case-detail-content");
  root.innerHTML = `<p style="padding: 2rem; color: var(--text-sub);">Loading case details...</p>`;

  const id = new URLSearchParams(window.location.search).get("id");
  let caseItem = null;
  if (id) {
    try {
      caseItem = await Verdict.fetchCase(id);
    } catch (err) {
      console.warn("Error fetching case:", err);
    }
  }

  if (!caseItem) {
    const cases = await Verdict.fetchCases();
    caseItem = cases[0] || Verdict.normalizeCase(Verdict.getCases()[0]);
  }

  const result = Verdict.evaluate(caseItem);
  const flagInfo = Verdict.resolveFlag(result.apiFlag || result.status);
  const headline = flagInfo.headline;

  const facts = [
    ["Section(s) charged", (caseItem.sections || []).join(", "), "sections"],
    ["Arrest date", caseItem.arrestDate ? Verdict.formatDate(caseItem.arrestDate) : null, "arrestDate"],
    ["First-time offender", caseItem.firstTimeOffender === null ? null : (caseItem.firstTimeOffender ? "Yes" : "No"), "firstTimeOffender"],
    ["Other cases pending", caseItem.otherPendingCases === null ? null : (caseItem.otherPendingCases ? "Yes" : "No"), "otherPendingCases"]
  ];

  function getExplanation() {
    if (caseItem.explanation) return caseItem.explanation;
    if (result.status === "review") return "This document could not be read with enough confidence. Verify the source document and enter the missing facts before assigning an eligibility flag.";
    if (result.status === "barred") return "The rule engine found a statutory bar. This result is based on the extracted facts and should be reviewed against the original case record.";
    if (result.status === "red") return `${caseItem.name} has spent ${result.custodyDays} days in custody, beyond the maximum possible sentence for the most serious charge. This is shown as a shocking-detention flag.`;
    if (result.status === "amber") return `${caseItem.name} has spent ${result.custodyDays} days in custody, more than half the maximum sentence for the most serious charge.`;
    if (result.status === "yellow") return `${caseItem.name} is recorded as a first-time offender and has crossed the lower one-third custody threshold.`;
    return `${caseItem.name} has not yet crossed the custody threshold required for this route. Recheck the case as time in custody increases.`;
  }

  function defaultBailDraft() {
    const custody = caseItem.arrestDate
      ? `The applicant has been in judicial custody since ${Verdict.formatDate(caseItem.arrestDate)}, a period of ${result.custodyDays ?? "under verification"} days as of today.`
      : "The applicant's exact date of arrest is under verification.";

    return `IN THE COURT OF THE CHIEF JUDICIAL MAGISTRATE\n\nAPPLICATION FOR RELEASE UNDER SECTION 479, BHARATIYA NAGARIK SURAKSHA SANHITA, 2023\n\nIn the matter of: State vs. ${caseItem.name}\nCase reference: ${caseItem.id}\nSections charged: ${(caseItem.sections || []).join(", ")}\n\nTo,\nThe Presiding Officer,\n\nThe applicant, ${caseItem.name}, through counsel, respectfully submits as follows:\n\n1. ${custody}\n\n2. ${result.rule}\n\n3. The applicant undertakes to comply with any conditions this Hon'ble Court considers appropriate.\n\nIn view of the above, it is prayed that this Hon'ble Court direct release on such terms and conditions as it considers appropriate.\n\n[Advocate name]\n[Bar registration number]\n[Date]\n\n- Draft generated for review. Verify all facts, dates and citations against the case record before filing.`;
  }

  function timeline() {
    if (["review", "barred"].includes(result.status) || !caseItem.arrestDate) {
      return `<p class="explanation-text">A timeline cannot be drawn without a confirmed arrest date and an applicable maximum sentence.</p>`;
    }
    const maxDays = result.maxDays || 1825;
    const custodyDays = result.custodyDays || 0;
    const displayMax = Math.max(maxDays, custodyDays) * 1.05;
    const pct = (days) => `${Math.min(100, (days / displayMax) * 100).toFixed(1)}%`;
    const maxDate = new Date(`${caseItem.arrestDate}T00:00:00`);
    maxDate.setDate(maxDate.getDate() + maxDays);

    return `<div class="timeline">
      <div class="timeline-track">
        <div class="timeline-fill ${custodyDays > maxDays ? "is-overdue" : ""}" style="--fill:${pct(custodyDays)}"></div>
        <div class="timeline-tick" style="--pos:${pct(result.third || maxDays / 3)}"></div>
        <span class="timeline-marker" style="--pos:${pct(result.third || maxDays / 3)}">1/3</span>
        <div class="timeline-tick" style="--pos:${pct(result.half || maxDays / 2)}"></div>
        <span class="timeline-marker" style="--pos:${pct(result.half || maxDays / 2)}">1/2</span>
        <div class="timeline-tick" style="--pos:${pct(maxDays)}"></div>
        <span class="timeline-marker" style="--pos:${pct(maxDays)}">Full term</span>
        <span class="timeline-marker is-today" style="--pos:${pct(custodyDays)}">Today</span>
      </div>
      <div class="timeline-labels">
        <span>Arrested ${Verdict.formatDate(caseItem.arrestDate)}</span>
        <span>Max sentence reached ${maxDate.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>
      </div>
    </div>`;
  }

  root.innerHTML = `
    <a class="case-back" href="dashboard.html">← Back to case register</a>
    <div class="case-detail-header">
      <div>
        <p class="case-detail-id">${Verdict.escapeHtml(caseItem.id)}</p>
        <h1 class="case-detail-name">${Verdict.escapeHtml(caseItem.name)}</h1>
      </div>
      <span class="flag-tag flag-${result.status}">${flagInfo.label}</span>
    </div>
    <div class="verdict-banner flag-${result.status}">
      <p class="verdict-banner-flag">${flagInfo.label}</p>
      <p class="verdict-banner-headline">${headline}</p>
      <p class="verdict-banner-rule">${Verdict.escapeHtml(result.rule)}</p>
    </div>
    <div class="case-grid">
      <section class="panel panel-full">
        <h2>Custody timeline</h2>
        ${timeline()}
      </section>
      <section class="panel">
        <h2>Extracted facts <span class="panel-sub">Each fact is paired with its source quote</span></h2>
        <ul class="facts-list">
          ${facts.map(([label, value, key]) => {
            const conf = caseItem.confidence && caseItem.confidence[key] !== undefined
              ? `${Math.round(caseItem.confidence[key] * 100)}% confidence`
              : "Extracted";
            const quoteText = caseItem.quotes && caseItem.quotes[key];
            return `<li>
              <div class="fact-row">
                <span class="fact-label">${label}</span>
                <span class="fact-confidence">${conf}</span>
              </div>
              <div class="fact-value ${value === null ? "is-missing" : ""}">
                ${value === null ? "Not extracted - verify manually" : Verdict.escapeHtml(value)}
              </div>
              ${quoteText ? `<blockquote class="fact-quote">${Verdict.escapeHtml(quoteText)}</blockquote>` : ""}
            </li>`;
          }).join("")}
        </ul>
      </section>
      <section class="panel">
        <h2>Plain-language explanation <span class="panel-sub">Generated by Bedrock model - cannot change the flag</span></h2>
        <p class="explanation-text">${Verdict.escapeHtml(getExplanation())}</p>
      </section>
      <section class="panel panel-full">
        <h2>Bail application draft <span class="panel-sub">Section 479 BNSS application generated from case facts</span></h2>
        <label class="sr-only" for="bail-draft">Bail application draft</label>
        <textarea class="bail-textarea" id="bail-draft" spellcheck="true">${Verdict.escapeHtml(defaultBailDraft())}</textarea>
        <div class="bail-actions">
          <button type="button" class="btn btn-primary" id="copy-draft">Copy draft</button>
          <button type="button" class="btn btn-ghost" id="download-draft">Download as .txt</button>
          ${["red", "amber", "yellow"].includes(result.status) && Verdict.getApiUrl() ? `<button type="button" class="btn btn-ghost" id="generate-ai-draft">Regenerate via Bedrock AI</button>` : ""}
          <span id="copy-confirm" class="copy-confirm" hidden>Copied to clipboard</span>
        </div>
      </section>
    </div>
  `;

  document.querySelector("#copy-draft").addEventListener("click", async () => {
    const text = document.querySelector("#bail-draft").value;
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      const field = document.querySelector("#bail-draft");
      field.select();
      document.execCommand("copy");
    }
    const notice = document.querySelector("#copy-confirm");
    notice.hidden = false;
    setTimeout(() => { notice.hidden = true; }, 1800);
  });

  document.querySelector("#download-draft").addEventListener("click", () => {
    const blob = new Blob([document.querySelector("#bail-draft").value], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = Object.assign(document.createElement("a"), {
      href: url,
      download: `${caseItem.id}-bail-draft.txt`
    });
    link.click();
    URL.revokeObjectURL(url);
  });

  const generateBtn = document.querySelector("#generate-ai-draft");
  if (generateBtn) {
    generateBtn.addEventListener("click", async () => {
      generateBtn.disabled = true;
      generateBtn.textContent = "Drafting with Bedrock...";
      try {
        const draft = await Verdict.fetchBailDraft(caseItem.id);
        if (draft) {
          document.querySelector("#bail-draft").value = draft;
        }
      } catch (err) {
        alert("Failed to generate AI bail draft: " + err.message);
      } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = "Regenerate via Bedrock AI";
      }
    });
  }
})();