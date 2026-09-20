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
  const messages = [
    "File received. Requesting secure upload URL...",
    "Uploading document to S3 and triggering pipeline...",
    "Bedrock extracting sections, dates and custody details...",
    "Applying Section 479 BNSS statutory rules...",
    "Done. Case has been analyzed and added to the register."
  ];
  let timer;

  function reset() {
    clearTimeout(timer);
    progress.hidden = true;
    actions.hidden = true;
    error.hidden = true;
    fileInput.value = "";
    document.querySelectorAll("#upload-stepper li").forEach((item) => item.classList.remove("is-active", "is-done"));
  }

  function setStep(index, customMsg) {
    document.querySelectorAll("#upload-stepper li").forEach((node, nodeIndex) => {
      node.classList.toggle("is-done", nodeIndex < index);
      node.classList.toggle("is-active", nodeIndex === index);
    });
    status.textContent = customMsg || messages[index] || "";
  }

  function completeMock() {
    const id = `VA-2026-${Math.floor(100 + Math.random() * 800)}`;
    const newCase = {
      id,
      caseId: id,
      name: "Newly uploaded case",
      sections: ["BNS 303(2)"],
      arrestDate: Verdict.isoDaysAgo(950),
      firstTimeOffender: false,
      otherPendingCases: false,
      missingData: false,
      confidence: { sections: 0.9, arrestDate: 0.95, firstTimeOffender: 0.8, otherPendingCases: 0.8 },
      quotes: {
        sections: "“charged under Section 303(2) BNS”",
        arrestDate: "“the accused was taken into custody on the date stated above”",
        firstTimeOffender: "“no previous convictions on record”",
        otherPendingCases: "“no other case shown pending”"
      }
    };
    const cases = Verdict.getCases();
    cases.unshift(newCase);
    Verdict.setCases(cases);
    document.querySelector("#view-new-case-btn").href = Verdict.caseLink(id);
    actions.hidden = false;
  }

  function runMockPipeline(index = 0) {
    setStep(index);
    timer = setTimeout(() => {
      if (index === steps.length - 1) {
        document.querySelector(`#upload-stepper li[data-step="${steps[index]}"]`).classList.add("is-done");
        document.querySelector(`#upload-stepper li[data-step="${steps[index]}"]`).classList.remove("is-active");
        completeMock();
      } else {
        runMockPipeline(index + 1);
      }
    }, index === steps.length - 1 ? 350 : 900);
  }

  async function handleRealUpload(file) {
    try {
      setStep(0, "Requesting secure presigned S3 upload URL...");
      const uploadInfo = await Verdict.getUploadUrl();
      if (!uploadInfo || !uploadInfo.uploadUrl) {
        throw new Error("API did not return a valid presigned upload URL.");
      }

      setStep(1, "Uploading document to S3 and triggering Step Functions pipeline...");
      await Verdict.uploadFileToS3(uploadInfo.uploadUrl, file);

      setStep(2, "Pipeline running: Bedrock extracting case facts...");
      const processedCase = await Verdict.pollCase(uploadInfo.caseId, (data) => {
        if (data.status === "UPLOADED") {
          setStep(2, "Document text read. Model extracting facts...");
        } else if (data.flag) {
          setStep(3, "Evaluating Section 479 BNSS rules...");
        }
      });

      setStep(4, "Done. Case has been analyzed and recorded.");
      document.querySelector(`#upload-stepper li[data-step="done"]`).classList.add("is-done");
      document.querySelector(`#upload-stepper li[data-step="done"]`).classList.remove("is-active");
      document.querySelector("#view-new-case-btn").href = Verdict.caseLink(processedCase.id);
      actions.hidden = false;
    } catch (err) {
      console.error("Upload failed:", err);
      error.textContent = `Upload failed: ${err.message}`;
      error.hidden = false;
      progress.hidden = true;
    }
  }

  function handleFile(file) {
    error.hidden = true;
    if (!file) return;
    if (!(file.type === "application/pdf" || /\.pdf$/i.test(file.name))) {
      error.textContent = `“${file.name}” is not a PDF. Upload a chargesheet or FIR as a PDF file.`;
      error.hidden = false;
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      error.textContent = `“${file.name}” is larger than 20MB. Split or compress it and try again.`;
      error.hidden = false;
      return;
    }

    clearTimeout(timer);
    progress.hidden = false;
    actions.hidden = true;
    filename.textContent = file.name;
    document.querySelectorAll("#upload-stepper li").forEach((item) => item.classList.remove("is-active", "is-done"));

    if (Verdict.getApiUrl()) {
      handleRealUpload(file);
    } else {
      runMockPipeline(0);
    }
  }

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener("change", (event) => handleFile(event.target.files[0]));

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragover");
    });
  });

  dropzone.addEventListener("drop", (event) => handleFile(event.dataTransfer.files[0]));
  document.querySelector("#upload-another-btn").addEventListener("click", reset);
})();