"use strict";

/**
 * Sign-in against the Cognito user pool.
 *
 * This replaces a sign-in screen that only wrote an email into sessionStorage
 * and gated nothing — the API itself had no authorizer, so the screens were
 * decoration. Every API call now carries a real ID token.
 *
 * Cognito's InitiateAuth is a public, unsigned JSON endpoint, so this talks to
 * it with plain fetch rather than pulling in the AWS SDK. The password goes
 * directly to Cognito over TLS and is never stored.
 *
 * Tokens live in sessionStorage: per-tab, cleared when the tab closes, and not
 * shared with other origins. An XSS bug on this page could still read them,
 * which is why they are short-lived (60 minutes) and the refresh token lasts a
 * day rather than indefinitely.
 */
window.VerdictAuth = (() => {
  const TOKENS_KEY = "verdictai-tokens";
  const EMAIL_KEY = "verdictai-user";
  // Refresh a little before expiry so a call in flight never lands on a token
  // that expired in transit.
  const REFRESH_MARGIN_MS = 120000;

  class AuthError extends Error {
    constructor(message, code) {
      super(message);
      this.name = "AuthError";
      this.code = code;
    }
  }

  function endpoint() {
    const { region } = VerdictConfig.cognito();
    return `https://cognito-idp.${region}.amazonaws.com/`;
  }

  async function idpCall(target, body) {
    const { userPoolId, clientId, region } = VerdictConfig.cognito();
    if (!userPoolId || !clientId || !region) {
      throw new AuthError(
        "Sign-in is not configured. Set the Cognito values in js/config.js from the sam deploy outputs.",
        "NotConfigured"
      );
    }
    let response;
    try {
      response = await fetch(endpoint(), {
        method: "POST",
        headers: {
          "Content-Type": "application/x-amz-json-1.1",
          "X-Amz-Target": `AWSCognitoIdentityProviderService.${target}`,
        },
        body: JSON.stringify(body),
      });
    } catch (_) {
      throw new AuthError("Could not reach the sign-in service.", "NetworkError");
    }

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const code = String(payload.__type || "").split("#").pop() || "UnknownError";
      throw new AuthError(friendlyMessage(code, payload.message), code);
    }
    return payload;
  }

  function friendlyMessage(code, fallback) {
    switch (code) {
      case "NotAuthorizedException":
        return "That email and password combination was not recognised.";
      case "UserNotFoundException":
        return "That email and password combination was not recognised.";
      case "PasswordResetRequiredException":
        return "This account needs its password reset. Ask an administrator.";
      case "UserNotConfirmedException":
        return "This account has not been confirmed yet. Ask an administrator.";
      case "TooManyRequestsException":
      case "LimitExceededException":
        return "Too many attempts. Wait a minute and try again.";
      case "InvalidPasswordException":
        return "That password does not meet the policy: at least 12 characters, with upper and lower case, a number and a symbol.";
      default:
        return fallback || "Sign-in failed.";
    }
  }

  function storeTokens(result) {
    const tokens = {
      idToken: result.IdToken,
      accessToken: result.AccessToken,
      // A refresh response does not return a new refresh token; keep the old one.
      refreshToken: result.RefreshToken || readTokens()?.refreshToken || null,
      expiresAt: Date.now() + (Number(result.ExpiresIn || 3600) * 1000),
    };
    sessionStorage.setItem(TOKENS_KEY, JSON.stringify(tokens));
    sessionStorage.setItem(EMAIL_KEY, emailFromToken(tokens.idToken) || "");
    return tokens;
  }

  function readTokens() {
    try {
      return JSON.parse(sessionStorage.getItem(TOKENS_KEY)) || null;
    } catch (_) {
      return null;
    }
  }

  /** Reads the email claim for display only. The API verifies the signature. */
  function emailFromToken(idToken) {
    try {
      const payload = idToken.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      return JSON.parse(atob(payload)).email || null;
    } catch (_) {
      return null;
    }
  }

  async function signIn(email, password) {
    const { clientId } = VerdictConfig.cognito();
    const result = await idpCall("InitiateAuth", {
      AuthFlow: "USER_PASSWORD_AUTH",
      ClientId: clientId,
      AuthParameters: { USERNAME: email, PASSWORD: password },
    });

    // Accounts created by an administrator arrive with a temporary password and
    // must choose a real one before any token is issued.
    if (result.ChallengeName === "NEW_PASSWORD_REQUIRED") {
      return { challenge: "NEW_PASSWORD_REQUIRED", session: result.Session, email };
    }
    if (result.ChallengeName) {
      throw new AuthError(`This account requires ${result.ChallengeName}, which this app cannot complete.`,
                          result.ChallengeName);
    }
    storeTokens(result.AuthenticationResult);
    return { challenge: null };
  }

  async function completeNewPassword(email, session, newPassword) {
    const { clientId } = VerdictConfig.cognito();
    const result = await idpCall("RespondToAuthChallenge", {
      ChallengeName: "NEW_PASSWORD_REQUIRED",
      ClientId: clientId,
      Session: session,
      ChallengeResponses: { USERNAME: email, NEW_PASSWORD: newPassword },
    });
    if (!result.AuthenticationResult) {
      throw new AuthError("The password was set but no session was returned. Sign in again.", "NoSession");
    }
    storeTokens(result.AuthenticationResult);
  }

  async function refresh() {
    const tokens = readTokens();
    if (!tokens?.refreshToken) return null;
    const { clientId } = VerdictConfig.cognito();
    try {
      const result = await idpCall("InitiateAuth", {
        AuthFlow: "REFRESH_TOKEN_AUTH",
        ClientId: clientId,
        AuthParameters: { REFRESH_TOKEN: tokens.refreshToken },
      });
      return storeTokens(result.AuthenticationResult);
    } catch (_) {
      signOut({ redirect: false });
      return null;
    }
  }

  /** The current ID token, refreshed first if it is close to expiring. */
  async function idToken() {
    let tokens = readTokens();
    if (!tokens) return null;
    if (Date.now() > tokens.expiresAt - REFRESH_MARGIN_MS) {
      tokens = await refresh();
    }
    return tokens?.idToken || null;
  }

  function isSignedIn() {
    const tokens = readTokens();
    return Boolean(tokens?.refreshToken || (tokens && Date.now() < tokens.expiresAt));
  }

  function email() {
    return sessionStorage.getItem(EMAIL_KEY) || null;
  }

  function signOut({ redirect = true } = {}) {
    sessionStorage.removeItem(TOKENS_KEY);
    sessionStorage.removeItem(EMAIL_KEY);
    if (redirect) window.location.assign("login.html");
  }

  return { AuthError, signIn, completeNewPassword, idToken, isSignedIn, email, signOut };
})();
