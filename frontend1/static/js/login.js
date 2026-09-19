"use strict";

(() => {
  if (Verdict.user()) { window.location.replace("dashboard.html"); return; }
  const form = document.querySelector("#login-form");
  const email = document.querySelector("#email");
  const password = document.querySelector("#password");
  const alert = document.querySelector("#login-alert");
  const emailError = document.querySelector("#email-error");
  const passwordError = document.querySelector("#password-error");
  const setError = (input, output, message) => { input.toggleAttribute("aria-invalid", Boolean(message)); output.hidden = !message; output.textContent = message || ""; };
  const validate = () => {
    let valid = true;
    const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim());
    setError(email, emailError, email.value.trim() ? (validEmail ? "" : "Enter a valid email address.") : "Enter your work email.");
    setError(password, passwordError, password.value ? (password.value.length >= 6 ? "" : "Password must have at least 6 characters.") : "Enter your password.");
    valid = validEmail && password.value.length >= 6;
    return valid;
  };
  form.addEventListener("submit", (event) => { event.preventDefault(); alert.hidden = true; if (validate()) Verdict.login(email.value.trim()); });
  document.querySelector("#demo-login").addEventListener("click", () => { email.value = "lawyer@legalaidsociety.in"; password.value = "demo1234"; setError(email, emailError, ""); setError(password, passwordError, ""); Verdict.login(email.value); });
  document.querySelector("#toggle-password").addEventListener("click", (event) => { const show = password.type === "password"; password.type = show ? "text" : "password"; event.currentTarget.textContent = show ? "Hide" : "Show"; event.currentTarget.setAttribute("aria-pressed", String(show)); event.currentTarget.setAttribute("aria-label", show ? "Hide password" : "Show password"); });
})();