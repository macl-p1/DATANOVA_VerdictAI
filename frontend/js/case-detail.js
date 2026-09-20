"use strict";

(() => {
  if (!Verdict.requireLogin()) return;

  const root = document.querySelector("#case-detail-content");
  const caseId = new URLSearchParams(window.location.search).get("id");

  const ELIGIBLE_FLAGS = ["PAST_MAX", "PAST_HALF", "PAST_THIRD"];

  const HEADLINES = {
    red: "Detention already exceeds the full maximum sentence",
    amber: "Eligible for release - past half the maximum sentence",
    yellow: "Eligible for release - first-time offender past one-third",
    gray: "Not yet eligible for release",
    review: "Needs human review before a flag can be set",
    barred: "Barred from release under Section 479",
    pending: "Still being processed",
  };

  const esc = Verdict.escapeHtml;

  function panel(title, sub, inner, full = false) {
    return `<section class="panel${full ? " panel-full" : ""}"><h2>${esc(title)}${sub ? ` <span class="panel-sub">${esc(sub)}</span>` : ""}</h2>${inner}</section>`;
  }

  function definitionList(pairs) {
    const rows = pairs
      .filter(([, value]) => value !== undefined)
      .map(([label, value]) => {
        const missing = value === null || value === "";
        return `<li><div class="fact-row"><span class="fact-label">${esc(label)}</span></div><div class="fact-value ${missing ? "is-missing" : ""}">${missing ? "Not extracted - verify manually" : esc(value)}</div></li>`;
      })
      .join("");
    return `<ul class="facts-list">${rows}</ul>`;
  }

  /** Every entry the extract Lambda returned, with its quote and score. */
  function evidenceList(record) {
    const evidence = record.evidence || {};
    const ordered = Object.keys(Verdict.FACT_LABELS).filter((key) => key in evidence);
    const extra = Object.keys(evidence).filter((key) => !(key in Verdict.FACT_LABELS));
    const keys = [...ordered, ...extra];

    if (!keys.length) {
      return `<p class="explanation-text">No extraction evidence was stored for this case. This happens when the document could not be parsed, or when the case was uploaded before evidence capture was enabled.</p>`;
    }

    return `<ul class="facts-list">${keys.map((key) => {
      const item = evidence[key] || {};
      const label = Verdict.FACT_LABELS[key] || key.replace(/_/g, " ");
      const hasConfidence = item.confidence !== null && item.confidence !== undefined;
      const score = hasConfidence ? `${Math.round(Number(item.confidence) * 100)}% confidence` : "No score";
      const missing = item.value === null || item.value === undefined || item.value === "";
      return `<li>
        <div class="fact-row"><span class="fact-label">${esc(label)}</span><span class="fact-confidence">${esc(score)}</span></div>
        <div class="fact-value ${missing ? "is-missing" : ""}">${missing ? "Not extracted - verify manually" : esc(item.value)}</div>
        ${item.source_quote ? `<blockquote class="fact-quote">${esc(`“${item.source_quote}”`)}</blockquote>` : ""}
      </li>`;
    }).join("")}</ul>`;
  }

  /** Drawn from the thresholds the rule engine returned, never recomputed here. */
  function timeline(record) {
    const custody = Number(record.daysInCustody);
    const max = Number(record.maxDays);
    if (!record.arrestDate || !Number.isFinite(custody) || !Number.isFinite(max) || max <= 0) {
      return `<p class="explanation-text">A timeline cannot be drawn without a confirmed arrest date and an applicable maximum sentence.</p>`;
    }
    const half = Number(record.halfDays);
    const third = Number(record.thirdDays);
    const span = Math.max(max, custody) * 1.05;
    const pct = (days) => `${Math.min(100, (days / span) * 100).toFixed(1)}%`;

    const maxDate = new Date(`${record.arrestDate}T00:00:00`);
    maxDate.setDate(maxDate.getDate() + max);

    const marks = [
      Number.isFinite(third) ? `<div class="timeline-tick" style="--pos:${pct(third)}"></div><span class="timeline-marker" style="--pos:${pct(third)}">1/3</span>` : "",
      Number.isFinite(half) ? `<div class="timeline-tick" style="--pos:${pct(half)}"></div><span class="timeline-marker" style="--pos:${pct(half)}">1/2</span>` : "",
      `<div class="timeline-tick" style="--pos:${pct(max)}"></div><span class="timeline-marker" style="--pos:${pct(max)}">Full term</span>`,
      `<span class="timeline-marker is-today" style="--pos:${pct(custody)}">Today</span>`,
    ].join("");

    return `<div class="timeline"><div class="timeline-track"><div class="timeline-fill ${custody > max ? "is-overdue" : ""}" style="--fill:${pct(custody)}"></div>${marks}</div>
      <div class="timeline-labels"><span>Arrested ${esc(Verdict.formatDate(record.arrestDate))}</span><span>Max sentence reached ${esc(maxDate.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }))}</span></div></div>`;
  }

  function overdueValue(record, status) {
    if (status === "barred" || status === "review" || status === "pending") return null;
    const days = Number(record.daysOverdue ?? 0);
    return days >= 0 ? `${days} days past the threshold` : `${Math.abs(days)} days still to serve`;
  }

  function bailPanel(record) {
    const eligible = record.status === "PROCESSED" && ELIGIBLE_FLAGS.includes(record.flag);
    if (!eligible) {
      return panel(
        "Bail application draft",
        "Available once the rule engine flags the case as eligible",
        `<p class="explanation-text">A draft can only be generated for a case flagged Past full term, Past half term, or First-time past third. This case is flagged ${esc(Verdict.flags[Verdict.statusOf(record)].label)}.</p>`,
        true
      );
    }
    return panel(
      "Bail application draft",
      "Generated by the backend from the stored case facts - verify every fact before filing",
      `<div class="bail-actions"><button type="button" class="btn btn-primary" id="generate-draft">Generate draft</button><span id="draft-status" class="copy-confirm" hidden></span></div>
       <div id="draft-wrap" hidden><label class="sr-only" for="bail-draft">Bail application draft</label><textarea class="bail-textarea" id="bail-draft" spellcheck="true"></textarea>
       <div class="bail-actions"><button type="button" class="btn btn-primary" id="copy-draft">Copy draft</button><button type="button" class="btn btn-ghost" id="download-draft">Download as .txt</button><span id="copy-confirm" class="copy-confirm" hidden>Copied to clipboard</span></div></div>`,
      true
    );
  }

  function render(record) {
    const status = Verdict.statusOf(record);
    const flag = Verdict.flags[status];
    const name = Verdict.displayName(record);

    const pendingNotice = Verdict.isPending(record)
      ? `<div class="form-alert" role="status">This case is still moving through the pipeline. Reload in a moment to see the extracted facts.</div>`
      : "";

    root.innerHTML = `<a class="case-back" href="dashboard.html">← Back to case register</a>
      <div class="case-detail-header">
        <div><p class="case-detail-id">${esc(record.caseId)}</p><h1 class="case-detail-name">${esc(name)}</h1></div>
        <span class="flag-tag flag-${status}">${esc(flag.label)}</span>
      </div>
      ${pendingNotice}
      <div class="verdict-banner flag-${status}">
        <p class="verdict-banner-flag">${esc(flag.label)}${record.flag ? ` · ${esc(record.flag)}` : ""}</p>
        <p class="verdict-banner-headline">${esc(HEADLINES[status] || "")}</p>
        <p class="verdict-banner-rule">${esc(record.ruleFired || "No rule reason was recorded.")}</p>
      </div>
      <div class="case-grid">
        ${panel("Custody timeline", "Thresholds come from the rule engine", timeline(record), true)}
        ${panel("Custody figures", "Computed by the rule engine, not a model", definitionList([
          ["Days in custody", record.daysInCustody ?? null],
          ["Days relative to threshold", overdueValue(record, status)],
          ["Maximum sentence (days)", record.maxDays ?? null],
          ["Half threshold (days)", record.halfDays ?? null],
          ["One-third threshold (days)", record.thirdDays ?? null],
        ]))}
        ${panel("Case facts", "As stored on the case record", definitionList([
          ["Section(s) charged", Array.isArray(record.sections) && record.sections.length ? Verdict.formatSections(record.sections) : null],
          ["Arrest date", record.arrestDate ? Verdict.formatDate(record.arrestDate) : null],
          ["Release date", record.releaseDate ? Verdict.formatDate(record.releaseDate) : null],
          ["Currently in custody", Verdict.formatBool(record.inCustody)],
          ["First-time offender", Verdict.formatBool(record.firstTimeOffender)],
          ["Other cases pending", Verdict.formatBool(record.otherPendingCases)],
        ]))}
        ${panel("Extracted facts", "Each fact is paired with its source quote and model confidence", evidenceList(record), true)}
        ${panel("Plain-language explanation", "Written after the rule engine decided - it cannot change the flag",
          `<p class="explanation-text">${esc(record.explanation || "No explanation was generated for this case.")}</p>`)}
        ${panel("Document provenance", "Where this case came from", definitionList([
          ["Processing status", record.status || null],
          ["Backend flag", record.flag || null],
          ["Source file", record.sourceFilename || null],
          ["Stored object", record.s3Key || null],
          ["Uploaded", record.createdAt ? Verdict.formatTimestamp(record.createdAt) : null],
          ["Last updated", record.updatedAt ? Verdict.formatTimestamp(record.updatedAt) : null],
          ["Last re-checked against today", record.reevaluatedAt ? Verdict.formatTimestamp(record.reevaluatedAt) : null],
          ["Record expires", record.expiresAt ? Verdict.formatTimestamp(Number(record.expiresAt) * 1000) : null],
        ]))}
        ${bailPanel(record)}
      </div>`;

    wireBailDraft(record);
  }

  function wireBailDraft(record) {
    const generate = document.querySelector("#generate-draft");
    if (!generate) return;
    const wrap = document.querySelector("#draft-wrap");
    const field = document.querySelector("#bail-draft");
    const draftStatus = document.querySelector("#draft-status");

    generate.addEventListener("click", async () => {
      generate.disabled = true;
      draftStatus.hidden = false;
      draftStatus.textContent = "Generating draft…";
      try {
        const result = await VerdictApi.getBailDraft(record.caseId);
        field.value = result.draft || "";
        wrap.hidden = false;
        draftStatus.textContent = "Draft ready. Verify every fact before filing.";
      } catch (error) {
        draftStatus.textContent = error.message;
      } finally {
        generate.disabled = false;
      }
    });

    document.querySelector("#copy-draft").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(field.value);
      } catch (_) {
        field.select();
        document.execCommand("copy");
      }
      const notice = document.querySelector("#copy-confirm");
      notice.hidden = false;
      setTimeout(() => { notice.hidden = true; }, 1800);
    });

    document.querySelector("#download-draft").addEventListener("click", () => {
      const blob = new Blob([field.value], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const link = Object.assign(document.createElement("a"), { href: url, download: `${record.caseId}-bail-draft.txt` });
      link.click();
      URL.revokeObjectURL(url);
    });
  }

  function showError(title, detail) {
    root.innerHTML = `<a class="case-back" href="dashboard.html">← Back to case register</a>
      <div class="empty-state"><h2>${esc(title)}</h2><p>${esc(detail)}</p></div>`;
  }

  async function load() {
    if (!caseId) {
      showError("No case selected", "Open a case from the register.");
      return;
    }
    root.innerHTML = `<p class="explanation-text">Loading case…</p>`;
    try {
      render(await VerdictApi.getCase(caseId));
    } catch (error) {
      showError(error.status === 404 ? "Case not found" : "Could not load this case", error.message);
    }
  }

  load();
})();
