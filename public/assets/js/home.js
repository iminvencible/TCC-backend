document.addEventListener("DOMContentLoaded", () => {
  const modal = document.querySelector("#location-modal");
  const form = document.querySelector("#location-form");
  const message = document.querySelector("#location-message");
  let currentUser = null;

  function showForecast(data) {
    const forecast = data.forecast;
    if (forecast) {
      document.querySelector("#temperature").textContent = Math.round(Number(forecast.temperature_c));
      document.querySelector("#condition").textContent = forecast.condition;
      document.querySelector("#max-temperature").textContent = Math.round(Number(forecast.maximum_c));
      document.querySelector("#min-temperature").textContent = Math.round(Number(forecast.minimum_c));
      document.querySelector("#humidity").textContent = `${forecast.humidity}%`;
      document.querySelector("#wind").textContent = `${Number(forecast.wind_kmh)} km/h`;
      document.querySelector("#rain").textContent = `${forecast.rain_probability}%`;
      document.querySelector("#data-source").textContent = forecast.source_name;
    } else {
      document.querySelector("#condition").textContent = "Sem previsao cadastrada para esta localidade";
      ["temperature", "max-temperature", "min-temperature", "humidity", "wind", "rain"].forEach((id) => {
        document.querySelector(`#${id}`).textContent = "--";
      });
      document.querySelector("#data-source").textContent = "";
    }

    const first = data.active_alerts[0];
    document.querySelector("#warning-title").textContent = first
      ? `${first.is_demo ? "DEMO - " : ""}${first.title}`
      : "Sem alertas ativos";
    document.querySelector("#warning-message").textContent = first
      ? first.message
      : "Nenhum alerta meteorologico esta ativo no momento.";
    document.querySelector("#alert-badge").textContent = data.unread_alert_count || "";
  }

  async function load(city, state) {
    const params = new URLSearchParams();
    if (city && state) {
      params.set("city", city);
      params.set("state", state);
    }
    const suffix = params.size ? `?${params}` : "";
    try {
      showForecast(await PrevClima.request(`/home${suffix}`));
    } catch (error) {
      document.querySelector("#condition").textContent = error.message;
    }
  }

  async function initialize() {
    try {
      currentUser = await PrevClima.request("/users/me");
      PrevClima.applyTheme(currentUser);
      document.querySelector("#auth-state").textContent = currentUser.name;
      if (currentUser.city && currentUser.state) {
        document.querySelector("#location-name").textContent = `${currentUser.city}, ${currentUser.state}`;
        form.city.value = currentUser.city;
        form.state.value = currentUser.state;
      }
    } catch (error) {
      if (error.status !== 401) document.querySelector("#auth-state").textContent = "Indisponivel";
    }
    await load(currentUser && currentUser.city, currentUser && currentUser.state);
  }

  document.querySelector("#open-location").addEventListener("click", () => modal.classList.add("open"));
  document.querySelector("#close-location").addEventListener("click", () => modal.classList.remove("open"));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    message.textContent = "";
    const city = form.city.value.trim();
    const state = form.state.value.trim().toUpperCase();
    try {
      if (currentUser) {
        currentUser = await PrevClima.request("/users/me", {
          method: "PATCH",
          body: JSON.stringify({ city, state }),
        });
      }
      document.querySelector("#location-name").textContent = `${city}, ${state}`;
      await load(city, state);
      modal.classList.remove("open");
    } catch (error) {
      message.textContent = error.message;
    }
  });

  initialize();
});
