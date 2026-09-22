document.addEventListener("DOMContentLoaded", async () => {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/mobile/sw.js");
  try {
    const session = await PrevClima.request("/auth/mobile-session");
    const user = session.user;
    if (user.role !== "USER") {
      window.location.replace("/mobile/");
      return;
    }
    document.querySelector("#mobile-user").textContent = user.name;
    document.querySelector("#mobile-location").textContent = user.city && user.state ? `${user.city}, ${user.state}` : "Brasil";
    PrevClima.applyTheme(user);
  } catch (_error) {
    window.location.replace("/mobile/");
    return;
  }

  try {
    const home = await PrevClima.request("/home");
    const forecast = home.forecast;
    if (forecast) {
      document.querySelector("#mobile-temperature").textContent = `${Math.round(Number(forecast.temperature_c))}°`;
      document.querySelector("#mobile-condition").textContent = forecast.condition;
      document.querySelector("#mobile-humidity").textContent = `${forecast.humidity}%`;
      document.querySelector("#mobile-wind").textContent = `${forecast.wind_kmh} km/h`;
      document.querySelector("#mobile-rain").textContent = `${forecast.rain_probability}%`;
      document.querySelector("#mobile-source").textContent = `Fonte: ${forecast.source_name}`;
    }
    const alerts = home.active_alerts || [];
    document.querySelector("#mobile-risk-title").textContent = alerts.length ? `${alerts.length} aviso(s) ativo(s)` : "Sem avisos ativos";
    document.querySelector("#mobile-risk-copy").textContent = alerts.length ? alerts[0].title : "Nenhum risco meteorológico ativo para sua área.";
    const list = document.querySelector("#mobile-alerts");
    list.replaceChildren();
    if (!alerts.length) {
      const empty = document.createElement("p");
      empty.textContent = "Tudo tranquilo por enquanto.";
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
        source.textContent = `Origem: ${alert.source_name}`;
        card.dataset.severity = alert.severity;
        card.append(level, title, area, source);
        list.append(card);
      });
    }
  } catch (error) {
    document.querySelector("#mobile-risk-title").textContent = "Dados temporariamente indisponíveis";
    document.querySelector("#mobile-risk-copy").textContent = error.message;
  }

  document.querySelector("#mobile-logout").addEventListener("click", async () => {
    try { await PrevClima.request("/auth/logout", { method: "POST" }); } finally { window.location.assign("/mobile/"); }
  });
});
