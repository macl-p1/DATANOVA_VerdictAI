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
  const viewButton = document.querySelector("#view-new-case-btn");

  // The pipeline runs inside Step Functions, so the browser can only observe
  // two real transitions: the upload landing in S3, and the case record coming
  // back PROCESSED. The middle steps are shown as one indeterminate stage
  // rather than a timed animation that pretends to know more than it does.
  const MIDDLE_STEPS = ["reading", "extracting", "checking"];
  const MAX_BYTES = 20 * 1024 * 1024;
  let busy = false;

  function stepNode(name) { return document.querySelector(`#upload-stepper li[data-step="${name}"]`); }
  function clearSteps() {
    document.querySelectorAll("#upload-stepper li").forEach((item) => item.classList.remove("is-active", "is-done"));
  }
  function markDone(name) { const node = stepNode(name); if (node) { node.classList.remove("is-active"); node.classList.add("is-done"); } }
  function markActive(name) { const node = stepNode(name); if (node) node.classList.add("is-active"); }

  function showError(message) {
    error.textContent = message;
    error.hidden = false;
  }

  function reset() {
    progress.hidden = true;
    actions.hidden = true;
    error.hidden = true;
    fileInput.value = "";
    busy = false;
    clearSteps();
  }

  function validate(file) {
    const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
    // The backend routes on the file's actual bytes, not this name, so a text
    // file always takes the text route even when Textract is unavailable.
    const isText = /^text\//.test(file.type || "") || /\.(txt|text|md)$/i.test(file.name);
    if (!isPdf && !isText) {
      return `“${file.name}” is not a PDF or text file. Upload a chargesheet or FIR as a PDF, or paste-ready text as .txt.`;
    }
    if (file.size > MAX_BYTES) {
      return `“${file.name}” is larger than 20MB. Split or compress it and try again.`;
    }
    return null;
  }

  async function handleFile(file) {
    if (!file || busy) return;
    error.hidden = true;

    const problem = validate(file);
    if (problem) { showError(problem); return; }

    busy = true;
    clearSteps();
    progress.hidden = false;
    actions.hidden = true;
    filename.textContent = file.name;
    status.textContent = "Requesting an upload slot…";

    let caseId;
    try {
      const slot = await VerdictApi.createUpload(file.name);
      caseId = slot.caseId;

      status.textContent = "Uploading the document…";
      await VerdictApi.uploadFile(slot.uploadUrl, file, slot.contentType);
      markDone("uploaded");

      MIDDLE_STEPS.forEach(markActive);
      status.textContent = "Reading the document, extracting facts and checking Section 479. This usually takes 30–90 seconds.";

      const record = await VerdictApi.waitForProcessing(caseId);
      MIDDLE_STEPS.forEach(markDone);

      if (record.status === "FAILED") {
        markActive("done");
        status.textContent = record.ruleFired || "The document could not be processed. Verify it manually.";
        showError("Processing failed. The case has been added to the register so it can be reviewed by hand.");
      } else {
        markDone("done");
        const flagStatus = Verdict.statusOf(record);
        status.textContent = `Done — flagged “${Verdict.flags[flagStatus].label}”. ${record.ruleFired || ""}`.trim();
      }

      viewButton.href = Verdict.caseLink(caseId);
      actions.hidden = false;
    } catch (failure) {
      status.textContent = "Upload stopped.";
      showError(failure.message);
      if (caseId) {
        // The record exists even if the wait timed out, so still offer the link.
        viewButton.href = Verdict.caseLink(caseId);
        actions.hidden = false;
      }
    } finally {
      busy = false;
    }
  }

  dropzone.addEventListener("click", () => { if (!busy) fileInput.click(); });
  dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); if (!busy) fileInput.click(); }
  });
  fileInput.addEventListener("change", (event) => handleFile(event.target.files[0]));

  ["dragenter", "dragover"].forEach((name) =>
    dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.add("is-dragover"); })
  );
  ["dragleave", "drop"].forEach((name) =>
    dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.remove("is-dragover"); })
  );
  dropzone.addEventListener("drop", (event) => handleFile(event.dataTransfer.files[0]));

  document.querySelector("#upload-another-btn").addEventListener("click", reset);
})();
