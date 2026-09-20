"use strict";

(() => {
  if (VerdictAuth.isSignedIn()) { window.location.replace("dashboard.html"); return; }

  const form = document.querySelector("#login-form");
  const email = document.querySelector("#email");
  const password = document.querySelector("#password");
  const alertBox = document.querySelector("#login-alert");
  const emailError = document.querySelector("#email-error");
  const passwordError = document.querySelector("#password-error");
  const submit = form.querySelector("button[type='submit']");

  // Shown only when Cognito says this account still has its temporary password.
  const newPasswordField = document.querySelector("#new-password-field");
  const newPassword = document.querySelector("#new-password");
  const newPasswordError = document.querySelector("#new-password-error");

  let challengeSession = null;

  const setError = (input, output, message) => {
    input.toggleAttribute("aria-invalid", Boolean(message));
    output.hidden = !message;
    output.textContent = message || "";
  };

  function showAlert(message) {
    alertBox.hidden = false;
    alertBox.textContent = message;
  }

  function validate() {
    const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim());
    setError(email, emailError, email.value.trim() ? (validEmail ? "" : "Enter a valid email address.") : "Enter your work email.");
    setError(password, passwordError, password.value ? "" : "Enter your password.");

    let ok = validEmail && Boolean(password.value);

    if (challengeSession) {
      // Mirrors the pool's password policy so the failure is caught here rather
      // than after a round trip.
      const value = newPassword.value;
      const strong = value.length >= 12 && /[a-z]/.test(value) && /[A-Z]/.test(value)
        && /[0-9]/.test(value) && /[^A-Za-z0-9]/.test(value);
      setError(newPassword, newPasswordError, value
        ? (strong ? "" : "At least 12 characters, with upper and lower case, a number and a symbol.")
        : "Choose a new password.");
      ok = ok && strong;
    }
    return ok;
  }

  function enterNewPasswordMode(session) {
    challengeSession = session;
    newPasswordField.hidden = false;
    newPassword.focus();
    submit.textContent = "Set password and sign in";
    showAlert("This account is still using its temporary password. Choose a new one to continue.");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    alertBox.hidden = true;
    if (!validate()) return;

    submit.disabled = true;
    const previousLabel = submit.textContent;
    submit.textContent = "Signing in…";

    try {
      if (challengeSession) {
        await VerdictAuth.completeNewPassword(email.value.trim(), challengeSession, newPassword.value);
        window.location.assign("dashboard.html");
        return;
      }

      const result = await VerdictAuth.signIn(email.value.trim(), password.value);
      if (result.challenge === "NEW_PASSWORD_REQUIRED") {
        enterNewPasswordMode(result.session);
        return;
      }
      window.location.assign("dashboard.html");
    } catch (error) {
      showAlert(error.message);
    } finally {
      submit.disabled = false;
      if (submit.textContent === "Signing in…") submit.textContent = previousLabel;
    }
  });

  document.querySelector("#toggle-password").addEventListener("click", (event) => {
    const show = password.type === "password";
    password.type = show ? "text" : "password";
    event.currentTarget.textContent = show ? "Hide" : "Show";
    event.currentTarget.setAttribute("aria-pressed", String(show));
    event.currentTarget.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });
})();
