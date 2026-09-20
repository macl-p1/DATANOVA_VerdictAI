"use strict";

/**
 * Where the frontend finds the backend, and which user pool signs people in.
 *
 * After `sam deploy`, take ApiUrl, UserPoolId, UserPoolClientId and Region from
 * the stack outputs and paste them below, or set them at runtime from the
 * browser console without editing this file:
 *
 *     localStorage.setItem("verdictai-api-base", "https://xxxx.execute-api.us-east-1.amazonaws.com/prod")
 *     localStorage.setItem("verdictai-user-pool-id", "us-east-1_xxxxxxxxx")
 *     localStorage.setItem("verdictai-client-id", "xxxxxxxxxxxxxxxxxxxxxxxxxx")
 *
 * Stored values win, so one build can be pointed at different stacks.
 *
 * None of these four values is a secret. The user pool id and client id are
 * public identifiers — the client has no secret precisely because a browser
 * cannot keep one — and the API is protected by the Cognito authorizer, not by
 * the URL being hard to guess.
 */
window.VerdictConfig = (() => {
  const FALLBACK_API_BASE = "https://id89xaka4f.execute-api.us-east-1.amazonaws.com/prod";
  const FALLBACK_USER_POOL_ID = "us-east-1_agAuQxfKR";
  const FALLBACK_CLIENT_ID = "3nugd2li1bvb0n4vd36vqded19";
  const FALLBACK_REGION = "us-east-1";

  const API_KEY = "verdictai-api-base";
  const POOL_KEY = "verdictai-user-pool-id";
  const CLIENT_KEY = "verdictai-client-id";
  const REGION_KEY = "verdictai-region";

  function stored(key) {
    try {
      return localStorage.getItem(key) || "";
    } catch (_) {
      return "";
    }
  }

  function apiBaseUrl() {
    return (stored(API_KEY) || FALLBACK_API_BASE).replace(/\/+$/, "");
  }

  function cognito() {
    const userPoolId = stored(POOL_KEY) || FALLBACK_USER_POOL_ID;
    return {
      userPoolId,
      clientId: stored(CLIENT_KEY) || FALLBACK_CLIENT_ID,
      // The pool id is prefixed with its region, so it is the most reliable source.
      region: stored(REGION_KEY) || (userPoolId.split("_")[0] || FALLBACK_REGION),
    };
  }

  function isConfigured() {
    const { userPoolId, clientId } = cognito();
    return Boolean(apiBaseUrl() && userPoolId && clientId);
  }

  return { apiBaseUrl, cognito, isConfigured, OVERRIDE_KEY: API_KEY, POOL_KEY, CLIENT_KEY, REGION_KEY };
})();
