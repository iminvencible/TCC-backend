document.addEventListener("DOMContentLoaded", async () => {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/mobile/sw.js");
  const loginForm = document.querySelector("#mobile-login-form");
  const registerForm = document.querySelector("#mobile-register-form");
  const loginTab = document.querySelector("#show-login");
  const registerTab = document.querySelector("#show-register");

  function show(register) {
    loginForm.hidden = register;
    registerForm.hidden = !register;
    loginTab.classList.toggle("active", !register);
    registerTab.classList.toggle("active", register);
  }
  loginTab.addEventListener("click", () => show(false));
  registerTab.addEventListener("click", () => show(true));

  try {
    const result = await PrevClima.request("/auth/mobile-session");
    if (result.user.role === "USER") window.location.replace("/mobile/inicio.html");
  } catch (_error) { /* A tela de entrada continua disponível. */ }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = loginForm.querySelector("button[type='submit']");
    const message = loginForm.querySelector(".mobile-message");
    message.textContent = "";
    PrevClima.setBusy(button, true);
    try {
      await PrevClima.request("/auth/login-mobile", {
        method: "POST",
        body: JSON.stringify({
          email: loginForm.elements["email"].value.trim(),
          password: loginForm.elements["password"].value,
        }),
      });
      window.location.assign("/mobile/inicio.html");
    } catch (error) {
      message.textContent = error.message;
      PrevClima.setBusy(button, false);
    }
  });

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = registerForm.querySelector("button[type='submit']");
    const message = registerForm.querySelector(".mobile-message");
    message.textContent = "";
    PrevClima.setBusy(button, true);
    try {
      const result = await PrevClima.request("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          name: registerForm.elements["name"].value.trim(),
          email: registerForm.elements["email"].value.trim(),
          password: registerForm.elements["password"].value,
          city: null,
          state: null,
        }),
      });
      if (result.user.role !== "USER") throw new Error("O aplicativo aceita somente contas de usuário.");
      await PrevClima.request("/auth/login-mobile", {
        method: "POST",
        body: JSON.stringify({
          email: registerForm.elements["email"].value.trim(),
          password: registerForm.elements["password"].value,
        }),
      });
      window.location.assign("/mobile/inicio.html");
    } catch (error) {
      message.textContent = error.message;
      PrevClima.setBusy(button, false);
    }
  });
});
