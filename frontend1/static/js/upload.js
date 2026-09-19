"use strict";

(() => {
  if (!Verdict.requireLogin()) return;
  const dropzone = document.querySelector("#dropzone");
  const fileInput = document.querySelector("#file-input");
  const error = document.querySelector("#upload-file-error");
  const progress = document.querySelector("#upload-progress-card");
  const filename = document.querySelector("#upload-filename");
  const status = document.querySelector("#upload-status-text");
  const actions = document.querySelector("#upload-actions");
  const steps = ["uploaded", "reading", "extracting", "checking", "done"];
  const messages = ["File received. Starting the pipeline...", "Running text extraction on scanned pages...", "Pulling out sections, dates and party details...", "Running the Section 479 rule engine...", "Done. The case has been added to the register."];
  let timer;

  function reset() { clearTimeout(timer); progress.hidden = true; actions.hidden = true; error.hidden = true; fileInput.value = ""; document.querySelectorAll("#upload-stepper li").forEach((item) => item.classList.remove("is-active", "is-done")); }
  function complete() {
    const id = `VA-2026-${Math.floor(100 + Math.random() * 800)}`;
    const newCase = { id, name: "Newly uploaded case", sections: ["BNS 303(2)"], arrestDate: Verdict.isoDaysAgo(950), firstTimeOffender: false, otherPendingCases: false, missingData: false, confidence: { sections: .9, arrestDate: .95, firstTimeOffender: .8, otherPendingCases: .8 }, quotes: { sections: "“charged under Section 303(2) BNS”", arrestDate: "“the accused was taken into custody on the date stated above”", firstTimeOffender: "“no previous convictions on record”", otherPendingCases: "“no other case shown pending”" } };
    const cases = Verdict.getCases(); cases.unshift(newCase); Verdict.setCases(cases);
    document.querySelector("#view-new-case-btn").href = Verdict.caseLink(id); actions.hidden = false;
  }
  function step(index) {
    const item = document.querySelector(`#upload-stepper li[data-step="${steps[index]}"]`);
    document.querySelectorAll("#upload-stepper li").forEach((node, nodeIndex) => { node.classList.toggle("is-done", nodeIndex < index); node.classList.remove("is-active"); });
    item.classList.add("is-active"); status.textContent = messages[index];
    timer = setTimeout(() => { item.classList.remove("is-active"); item.classList.add("is-done"); if (index === steps.length - 1) complete(); else step(index + 1); }, index === steps.length - 1 ? 350 : 800);
  }
  function handleFile(file) {
    error.hidden = true;
    if (!file) return;
    if (!(file.type === "application/pdf" || /\.pdf$/i.test(file.name))) { error.textContent = `“${file.name}” is not a PDF. Upload a chargesheet or FIR as a PDF file.`; error.hidden = false; return; }
    if (file.size > 20 * 1024 * 1024) { error.textContent = `“${file.name}” is larger than 20MB. Split or compress it and try again.`; error.hidden = false; return; }
    clearTimeout(timer); progress.hidden = false; actions.hidden = true; filename.textContent = file.name; document.querySelectorAll("#upload-stepper li").forEach((item) => item.classList.remove("is-active", "is-done")); step(0);
  }
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); fileInput.click(); } });
  fileInput.addEventListener("change", (event) => handleFile(event.target.files[0]));
  ["dragenter", "dragover"].forEach((eventName) => dropzone.addEventListener(eventName, (event) => { event.preventDefault(); dropzone.classList.add("is-dragover"); }));
  ["dragleave", "drop"].forEach((eventName) => dropzone.addEventListener(eventName, (event) => { event.preventDefault(); dropzone.classList.remove("is-dragover"); }));
  dropzone.addEventListener("drop", (event) => handleFile(event.dataTransfer.files[0]));
  document.querySelector("#upload-another-btn").addEventListener("click", reset);
})();