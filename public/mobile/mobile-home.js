document.addEventListener("DOMContentLoaded", async () => {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/mobile/sw.js");
  try {
    const session = await PrevClima.request("/auth/mobile-session");
    const user = session.user;
    if (user.role !== "USER") {
      window.location.replace("/mobile/");
      return;
    }
    document.querySelector("#mobile-user").textContent = user.name?.trim().split(/\s+/)[0] || "você";
    document.querySelector("#mobile-location").textContent = user.city && user.state ? `${user.city}, ${user.state}` : "Brasil";
    PrevClima.applyTheme(user);
  } catch (_error) {
    window.location.replace("/mobile/");
    return;
  }

  try {
    const home = await PrevClima.request("/home");
    const forecast = home.forecast;
    const source = document.querySelector("#mobile-source");
    if (forecast) {
      const temperature = Number(forecast.temperature_c);
      document.querySelector("#mobile-temperature").textContent = Number.isFinite(temperature) ? `${Math.round(temperature)}°` : "--°";
      document.querySelector("#mobile-condition").textContent = forecast.condition || "Condição não informada";
      document.querySelector("#mobile-humidity").textContent = forecast.humidity == null ? "--" : `${forecast.humidity}%`;
      document.querySelector("#mobile-wind").textContent = forecast.wind_kmh == null ? "--" : `${forecast.wind_kmh} km/h`;
      document.querySelector("#mobile-rain").textContent = forecast.rain_probability == null ? "--" : `${forecast.rain_probability}%`;
      source.textContent = `Fonte: ${forecast.source_name || "PrevClima"}${forecast.is_stale ? " (último dado salvo)" : ""}`;
      try {
        const url = new URL(forecast.source_url);
        if (url.protocol === "https:") source.href = url.href;
        else source.removeAttribute("href");
      } catch (_error) { source.removeAttribute("href"); }
    } else {
      document.querySelector("#mobile-condition").textContent = "Previsão indisponível no momento";
      source.textContent = "Acompanhe os avisos abaixo";
    }
    const alerts = home.active_alerts || [];
    const risk = document.querySelector("#mobile-risk-card");
    const highestSeverity = alerts.some((alert) => ["CRITICAL", "HIGH"].includes(alert.severity));
    risk.dataset.risk = alerts.length ? (highestSeverity ? "high" : "moderate") : "clear";
    risk.querySelector(".mobile-risk-icon").textContent = alerts.length ? "!" : "✓";
    document.querySelector("#mobile-risk-title").textContent = alerts.length ? `${alerts.length} aviso(s) ativo(s)` : "Sem avisos ativos";
    document.querySelector("#mobile-risk-copy").textContent = alerts.length ? (alerts.find((alert) => ["CRITICAL", "HIGH"].includes(alert.severity)) || alerts[0]).title : "Nenhum aviso ativo nas áreas acompanhadas.";
    const list = document.querySelector("#mobile-alerts");
    list.replaceChildren();
    if (!alerts.length) {
      const empty = document.createElement("p");
      empty.className = "mobile-list-state";
      empty.textContent = "Nenhum aviso nas áreas acompanhadas. Confira também os avisos oficiais do INMET.";
      list.append(empty);
    } else {
      alerts.slice(0, 3).forEach((alert) => {
        const card = document.createElement("article");
        const level = document.createElement("small");
        level.textContent = PrevClima.severityName(alert.severity);
        const title = document.createElement("strong");
        title.textContent = alert.title;
        const area = document.createElement("span");
        area.textContent = alert.area_name;
        const source = document.createElement("span");
        source.textContent = `Origem: ${alert.source_name || "PrevClima"}`;
        card.dataset.severity = alert.severity;
        card.append(level, title, area, source);
        list.append(card);
      });
    }
  } catch (error) {
    document.querySelector("#mobile-risk-card").dataset.risk = "error";
    document.querySelector("#mobile-risk-label").textContent = "CONEXÃO INDISPONÍVEL";
    document.querySelector("#mobile-risk-title").textContent = "Dados temporariamente indisponíveis";
    document.querySelector("#mobile-risk-copy").textContent = error.message;
    document.querySelector("#mobile-condition").textContent = "Não foi possível carregar a previsão";
    const list = document.querySelector("#mobile-alerts");
    const notice = document.createElement("p");
    notice.className = "mobile-list-state";
    notice.textContent = "Não foi possível carregar os avisos. Verifique sua conexão e atualize a página.";
    list.replaceChildren(notice);
  }

  document.querySelector("#mobile-logout").addEventListener("click", async () => {
    try { await PrevClima.request("/auth/logout", { method: "POST" }); } finally { window.location.assign("/mobile/"); }
  });
});
