"use strict";

(() => {
  if (!Verdict.requireLogin()) return;
  const body = document.querySelector("#case-table-body");
  const table = document.querySelector("#case-table");
  const empty = document.querySelector("#dashboard-empty");
  const count = document.querySelector("#results-count");
  const search = document.querySelector("#case-search");
  let filter = "all";

  function listCases() {
    const query = search.value.trim().toLowerCase();
    return Verdict.getCases().map((caseItem) => ({ caseItem, result: Verdict.evaluate(caseItem) }))
      .filter(({ caseItem, result }) => (filter === "all" || result.status === filter) && (!query || [caseItem.name, caseItem.id, caseItem.sections.join(" ")].join(" ").toLowerCase().includes(query)))
      .sort((a, b) => Verdict.rank[a.result.status] - Verdict.rank[b.result.status] || (b.result.overdueDays ?? -99999) - (a.result.overdueDays ?? -99999));
  }
  function overdueText(result) {
    if (result.status === "review") return "-";
    if (result.status === "barred") return "Not applicable";
    return result.overdueDays >= 0 ? `${Math.round(result.overdueDays)} days overdue` : `${Math.round(-result.overdueDays)} days until eligible`;
  }
  function render() {
    const rows = listCases();
    count.textContent = `${rows.length} case${rows.length === 1 ? "" : "s"} shown of ${Verdict.getCases().length} total`;
    table.hidden = rows.length === 0; empty.hidden = rows.length !== 0;
    body.innerHTML = rows.map(({ caseItem, result }) => {
      const label = Verdict.flags[result.status].label;
      const custody = caseItem.arrestDate ? `${Verdict.daysBetween(caseItem.arrestDate)} days (since ${Verdict.formatDate(caseItem.arrestDate)})` : "Unclear from document";
      return `<tr class="case-row" tabindex="0" role="link" data-case-id="${Verdict.escapeHtml(caseItem.id)}" aria-label="Open case ${Verdict.escapeHtml(caseItem.id)}, ${Verdict.escapeHtml(caseItem.name)}">
        <td data-label="Flag"><div class="flag-bar flag-${result.status}"><span class="flag-tag flag-${result.status}">${label}</span></div></td>
        <td data-label="Case"><span class="case-id">${Verdict.escapeHtml(caseItem.id)}</span></td>
        <td data-label="Person">${Verdict.escapeHtml(caseItem.name)}</td>
        <td data-label="Section(s)" class="case-sections">${Verdict.escapeHtml(caseItem.sections.join(", "))}</td>
        <td data-label="In custody">${Verdict.escapeHtml(custody)}</td>
        <td data-label="Days overdue" class="overdue-figure">${Verdict.escapeHtml(overdueText(result))}</td>
      </tr>`;
    }).join("");
    body.querySelectorAll(".case-row").forEach((row) => {
      const open = () => window.location.assign(Verdict.caseLink(row.dataset.caseId));
      row.addEventListener("click", open);
      row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); } });
    });
  }
  search.addEventListener("input", render);
  document.querySelectorAll(".filter-chip").forEach((chip) => chip.addEventListener("click", () => { filter = chip.dataset.filter; document.querySelectorAll(".filter-chip").forEach((button) => button.classList.toggle("is-active", button === chip)); render(); }));
  document.querySelector("#clear-filters-btn").addEventListener("click", () => { filter = "all"; search.value = ""; document.querySelector("[data-filter='all']").classList.add("is-active"); document.querySelectorAll(".filter-chip:not([data-filter='all'])").forEach((chip) => chip.classList.remove("is-active")); render(); });
  render();
})();