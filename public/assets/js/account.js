window.addEventListener("hashchange", () => window.location.reload());
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#account-form");
  const message = document.querySelector("#account-message");
  const mode = location.hash === "#reset" ? "reset" : "verify";
  document.querySelector("#account-title").textContent = mode === "reset" ? "Redefinir senha" : "Confirmar e-mail";
  document.querySelector("#password-field").hidden = mode !== "reset";
  form.password.required = mode === "reset";
  document.querySelector("#submit-code").textContent = mode === "reset" ? "Salvar nova senha" : "Confirmar cadastro";
  const stored = sessionStorage.getItem("prevclima-pending-email");
  if (stored) form.email.value = stored;
  const mobile = location.pathname.startsWith("/mobile/");
  document.querySelector("#back-login").href = mobile ? "/mobile/" : "/";
  async function run(button, path, body) {
    message.textContent = "";
    PrevClima.setBusy(button, true);
    try {
      const result = await PrevClima.request(path, { method: "POST", body: JSON.stringify(body) });
      message.textContent = result.message;
      return true;
    } catch (error) { message.textContent = error.message; return false; }
    finally { PrevClima.setBusy(button, false); }
  }
  document.querySelector("#send-code").onclick = async (event) => {
    if (!form.email.reportValidity()) return;
    await run(event.currentTarget, mode === "reset" ? "/auth/forgot-password" : "/auth/resend-verification", { email: form.email.value.trim() });
    form.code.focus();
  };
  form.onsubmit = async (event) => {
    event.preventDefault();
    const body = { email: form.email.value.trim(), code: form.code.value.trim() };
    if (mode === "reset") body.password = form.password.value;
    if (await run(document.querySelector("#submit-code"), mode === "reset" ? "/auth/reset-password" : "/auth/verify-email", body)) {
      form.querySelectorAll("input,button").forEach((el) => { el.disabled = true; });
      sessionStorage.removeItem("prevclima-pending-email");
      document.querySelector("#back-login").focus();
    }
  };
});
