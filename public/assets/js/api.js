(function () {
  function cookie(name) {
    const prefix = `${encodeURIComponent(name)}=`;
    const item = document.cookie.split("; ").find((part) => part.startsWith(prefix));
    return item ? decodeURIComponent(item.slice(prefix.length)) : "";
  }

  async function request(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      const csrf = cookie("prevclima_csrf");
      if (csrf) headers.set("X-CSRF-Token", csrf);
    }

    const response = await fetch(`/api/v1${path}`, {
      ...options,
      method,
      headers,
      credentials: "same-origin",
    });
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const detail = data && data.detail;
      const message = Array.isArray(detail)
        ? detail.map((item) => item.msg).join(". ")
        : detail || "Nao foi possivel concluir a solicitacao.";
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function setBusy(button, busy) {
    if (!button) return;
    if (!button.dataset.label) button.dataset.label = button.textContent;
    button.disabled = busy;
    button.textContent = busy ? "Aguarde..." : button.dataset.label;
  }

  function applyTheme(user) {
    if (user) document.documentElement.classList.toggle("light", !user.dark_theme);
  }

  window.PrevClima = { request, setBusy, applyTheme };
})();
