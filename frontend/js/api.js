"use strict";

/**
 * The only place in the frontend that talks to the backend.
 *
 * Nothing here interprets the law. The rule engine lives in the rules Lambda;
 * this module moves its output to the screen unchanged.
 */
window.VerdictApi = (() => {
  class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  }

  function requireBase() {
    const base = VerdictConfig.apiBaseUrl();
    if (!base) {
      throw new ApiError(
        "No API URL is configured. Deploy the backend, then run " +
        `localStorage.setItem("${VerdictConfig.OVERRIDE_KEY}", "<ApiUrl from sam deploy>") and reload.`,
        0
      );
    }
    return base;
  }

  async function request(path, options = {}) {
    const base = requireBase();
    let response;
    try {
      response = await fetch(`${base}${path}`, {
        ...options,
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      });
    } catch (cause) {
      throw new ApiError("Could not reach the API. Check the API URL and that the stack is deployed.", 0);
    }

    const raw = await response.text();
    let payload = null;
    if (raw) {
      try {
        payload = JSON.parse(raw);
      } catch (_) {
        payload = null;
      }
    }

    if (!response.ok) {
      const message = (payload && (payload.error || payload.message)) || `Request failed (${response.status}).`;
      throw new ApiError(message, response.status);
    }
    return payload;
  }

  /** GET /cases — optionally filtered by backend flag (PAST_MAX, PAST_HALF, ...). */
  function listCases(flag) {
    const query = flag && flag !== "all" ? `?flag=${encodeURIComponent(flag)}` : "";
    return request(`/cases${query}`);
  }

  /** GET /cases/{caseId} */
  function getCase(caseId) {
    return request(`/cases/${encodeURIComponent(caseId)}`);
  }

  /** POST /cases/{caseId}/bail-draft */
  function getBailDraft(caseId) {
    return request(`/cases/${encodeURIComponent(caseId)}/bail-draft`, { method: "POST" });
  }

  /** POST /cases/upload-url */
  function createUpload(filename) {
    return request("/cases/upload-url", {
      method: "POST",
      body: JSON.stringify({ filename }),
    });
  }

  /**
   * PUT the file straight to S3 with the presigned URL. The Content-Type must
   * match what upload_url signed, or S3 rejects the signature.
   */
  async function uploadFile(uploadUrl, file, contentType) {
    let response;
    try {
      response = await fetch(uploadUrl, {
        method: "PUT",
        headers: { "Content-Type": contentType },
        body: file,
      });
    } catch (_) {
      throw new ApiError("The file could not be uploaded to storage.", 0);
    }
    if (!response.ok) {
      throw new ApiError(`Storage rejected the upload (${response.status}).`, response.status);
    }
  }

  /**
   * The pipeline is asynchronous (S3 -> EventBridge -> Step Functions), so the
   * case record is polled until the backend marks it PROCESSED or FAILED.
   */
  async function waitForProcessing(caseId, { onTick, intervalMs = 3000, timeoutMs = 300000 } = {}) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
      let record;
      try {
        record = await getCase(caseId);
      } catch (error) {
        if (error.status === 404) continue; // not written yet
        throw error;
      }
      if (onTick) onTick(record);
      if (record.status === "PROCESSED" || record.status === "FAILED") return record;
    }
    throw new ApiError("The document is taking longer than expected. Check the case register shortly.", 0);
  }

  return { ApiError, listCases, getCase, getBailDraft, createUpload, uploadFile, waitForProcessing };
})();
