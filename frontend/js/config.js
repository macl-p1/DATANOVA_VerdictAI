"use strict";

/**
 * Where the frontend finds the backend.
 *
 * After `sam deploy`, take the ApiUrl value from the stack outputs and either
 * paste it into API_BASE_URL below, or set it at runtime from the browser
 * console without editing this file:
 *
 *     localStorage.setItem("verdictai-api-base", "https://xxxx.execute-api.us-east-1.amazonaws.com/prod")
 *
 * The stored value wins, so one build can be pointed at different stacks.
 */
window.VerdictConfig = (() => {
  // Deliberately empty. This repository is public and the API Gateway stage has
  // no authorizer, so committing a deployed URL here would let anyone read every
  // case record and create new ones. Set it per-machine with the localStorage
  // line above, or bake it in only once the API is actually protected.
  const FALLBACK = "";
  const OVERRIDE_KEY = "verdictai-api-base";

  function apiBaseUrl() {
    let stored = "";
    try {
      stored = localStorage.getItem(OVERRIDE_KEY) || "";
    } catch (_) {
      stored = "";
    }
    return (stored || FALLBACK).replace(/\/+$/, "");
  }

  function isConfigured() {
    return Boolean(apiBaseUrl());
  }

  return { apiBaseUrl, isConfigured, OVERRIDE_KEY };
})();
