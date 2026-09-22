document.addEventListener("DOMContentLoaded", async () => {
  const form = document.querySelector("#login-form");
  const message = document.querySelector("#form-message");
  const professional = document.body.dataset.professional === "true";
  const next = new URLSearchParams(window.location.search).get("next");
  const destination = next && next.startsWith("/") && !next.startsWith("//") ? next : "/inicio.html";
  if (!form) return;

  try {
    const user = await PrevClima.request("/users/me");
    if (!professional || ["METEOROLOGIST", "ADMIN"].includes(user.role)) {
      window.location.replace(destination);
      return;
    }
    message.textContent = "Esta conta não possui acesso profissional.";
  } catch (error) {
    if (error.status !== 401) message.textContent = error.message;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    message.textContent = "";
    PrevClima.setBusy(button, true);
    try {
      const result = await PrevClima.request(professional ? "/auth/login-professional" : "/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: form.email.value.trim(),
          password: form.password.value,
        }),
      });
      if (professional) {
        window.location.assign(result.user.role === "ADMIN" ? "/admin.html" : "/profissional.html");
      } else {
        window.location.assign(destination);
      }
    } catch (error) {
      message.textContent = error.message;
    } finally {
      PrevClima.setBusy(button, false);
    }
  });
});
