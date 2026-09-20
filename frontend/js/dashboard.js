"use strict";

(() => {
  if (!Verdict.requireLogin()) return;

  const body = document.querySelector("#case-table-body");
  const table = document.querySelector("#case-table");
  const empty = document.querySelector("#dashboard-empty");
  const count = document.querySelector("#results-count");
  const search = document.querySelector("#case-search");

  let filter = "all";
  let records = [];

  function setCaption(text) { count.textContent = text; }

  function showMessage(title, detail) {
    table.hidden = true;
    empty.hidden = false;
    empty.querySelector("h2").textContent = title;
    empty.querySelector("p").textContent = detail;
  }

  /** Days-overdue wording. The backend sends a negative figure when the case
   *  has not yet reached its threshold, so the sign carries the meaning. */
  function overdueText(record, status) {
    if (status === "pending") return "Processing";
    if (status === "review") return "—";
    if (status === "barred") return "Not applicable";
    const days = Number(record.daysOverdue ?? 0);
    return days >= 0 ? `${days} days overdue` : `${Math.abs(days)} days until eligible`;
  }

  function custodyText(record) {
    if (record.daysInCustody === null || record.daysInCustody === undefined) {
      return record.arrestDate ? Verdict.formatDate(record.arrestDate) : "Unclear from document";
    }
    return record.arrestDate
      ? `${record.daysInCustody} days (since ${Verdict.formatDate(record.arrestDate)})`
      : `${record.daysInCustody} days`;
  }

  function visibleRows() {
    const query = search.value.trim().toLowerCase();
    return records
      .map((record) => ({ record, status: Verdict.statusOf(record) }))
      .filter(({ record, status }) => {
        if (filter !== "all" && status !== filter) return false;
        if (!query) return true;
        const haystack = [
          record.caseId,
          Verdict.displayName(record),
          Verdict.formatSections(record.sections),
          record.sourceFilename,
        ].join(" ").toLowerCase();
        return haystack.includes(query);
      })
      .sort((a, b) =>
        Verdict.rank[a.status] - Verdict.rank[b.status] ||
        Number(b.record.daysOverdue ?? -99999) - Number(a.record.daysOverdue ?? -99999)
      );
  }

  function render() {
    const rows = visibleRows();
    setCaption(`${rows.length} case${rows.length === 1 ? "" : "s"} shown of ${records.length} total`);
    table.hidden = rows.length === 0;
    empty.hidden = rows.length !== 0;
    if (!rows.length) {
      showMessage("No cases match", "Try a different search term or clear the flag filter.");
      return;
    }

    body.innerHTML = rows.map(({ record, status }) => {
      const label = Verdict.flags[status].label;
      return `<tr class="case-row" tabindex="0" role="link" data-case-id="${Verdict.escapeHtml(record.caseId)}" aria-label="Open case ${Verdict.escapeHtml(record.caseId)}, ${Verdict.escapeHtml(Verdict.displayName(record))}">
        <td data-label="Flag"><div class="flag-bar flag-${status}"><span class="flag-tag flag-${status}">${label}</span></div></td>
        <td data-label="Case"><span class="case-id">${Verdict.escapeHtml(record.caseId.slice(0, 8))}</span></td>
        <td data-label="Person">${Verdict.escapeHtml(Verdict.displayName(record))}</td>
        <td data-label="Section(s)" class="case-sections">${Verdict.escapeHtml(Verdict.formatSections(record.sections))}</td>
        <td data-label="In custody">${Verdict.escapeHtml(custodyText(record))}</td>
        <td data-label="Days overdue" class="overdue-figure">${Verdict.escapeHtml(overdueText(record, status))}</td>
        <td data-label="Updated">${Verdict.escapeHtml(Verdict.formatTimestamp(record.updatedAt || record.createdAt))}</td>
      </tr>`;
    }).join("");

    body.querySelectorAll(".case-row").forEach((row) => {
      const open = () => window.location.assign(Verdict.caseLink(row.dataset.caseId));
      row.addEventListener("click", open);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); }
      });
    });
  }

  async function load() {
    setCaption("Loading cases…");
    table.hidden = true;
    empty.hidden = true;
    try {
      // A flag chip is pushed to the backend so the flag-daysOverdue index does
      // the work; free-text search then narrows the result in the browser.
      const backendFlag = filter === "all" || filter === "pending" ? null : Verdict.STATUS_TO_FLAG[filter];
      records = (await VerdictApi.listCases(backendFlag)) || [];
      if (filter === "pending") records = records.filter((record) => Verdict.isPending(record));
      render();
    } catch (error) {
      records = [];
      setCaption("");
      showMessage("Could not load cases", error.message);
    }
  }

  search.addEventListener("input", render);

  document.querySelectorAll(".filter-chip").forEach((chip) =>
    chip.addEventListener("click", () => {
      filter = chip.dataset.filter;
      document.querySelectorAll(".filter-chip").forEach((button) => button.classList.toggle("is-active", button === chip));
      load();
    })
  );

  document.querySelector("#clear-filters-btn").addEventListener("click", () => {
    filter = "all";
    search.value = "";
    document.querySelector("[data-filter='all']").classList.add("is-active");
    document.querySelectorAll(".filter-chip:not([data-filter='all'])").forEach((chip) => chip.classList.remove("is-active"));
    load();
  });

  document.querySelector("#refresh-btn")?.addEventListener("click", load);

  load();
})();
