document.addEventListener("DOMContentLoaded", async () => {
  const status = document.querySelector("#map-status");
  if (typeof window.L === "undefined") {
    status.textContent = "Mapa indisponivel";
    return;
  }

  const colors = { LOW: "#2fe342", MODERATE: "#ffd42a", HIGH: "#ff8426", CRITICAL: "#ef3045" };
  const map = L.map("weather-map", { zoomControl: false }).setView([-23.5, -47.2], 5);
  L.control.zoom({ position: "topleft" }).addTo(map);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const alertLayer = L.layerGroup().addTo(map);
  const forecastLayer = L.layerGroup().addTo(map);

  function popup(title, subtitle, demo) {
    const node = document.createElement("div");
    const heading = document.createElement("strong");
    const detail = document.createElement("p");
    heading.textContent = `${demo ? "DEMO - " : ""}${title}`;
    detail.textContent = subtitle;
    node.append(heading, detail);
    return node;
  }

  function polygonOptions(severity, fillOpacity = 0.3) {
    const color = colors[severity] || colors.MODERATE;
    return { color, fillColor: color, fillOpacity, weight: 2 };
  }

  try {
    const data = await PrevClima.request("/map-data");
    data.forecast_areas.forEach((area) => {
      L.geoJSON(area.polygon, { style: polygonOptions(area.severity, 0.2) })
        .bindPopup(popup(`Previsao: ${area.city}, ${area.state}`, area.source_name, false))
        .addTo(forecastLayer);
    });
    data.alerts.forEach((alert) => {
      let shape = null;
      if (alert.polygon) {
        shape = L.geoJSON(alert.polygon, { style: polygonOptions(alert.severity, 0.38) });
      } else if (alert.latitude !== null && alert.longitude !== null && alert.radius_km !== null) {
        shape = L.circle([Number(alert.latitude), Number(alert.longitude)], {
          ...polygonOptions(alert.severity, 0.38),
          radius: Number(alert.radius_km) * 1000,
        });
      }
      if (shape) shape.bindPopup(popup(alert.title, alert.area_name, alert.is_demo)).addTo(alertLayer);
    });
    status.textContent = `${data.alerts.length} alerta${data.alerts.length === 1 ? "" : "s"}`;
  } catch (error) {
    status.textContent = error.message;
  }

  document.querySelector("#forecast-layer").addEventListener("change", (event) => {
    if (event.target.checked) forecastLayer.addTo(map); else forecastLayer.removeFrom(map);
  });
  document.querySelector("#alert-layer").addEventListener("change", (event) => {
    if (event.target.checked) alertLayer.addTo(map); else alertLayer.removeFrom(map);
  });

  const panel = document.querySelector("#layer-panel");
  const toggle = document.querySelector("#toggle-layers");
  function setPanel(open) {
    panel.classList.toggle("closed", !open);
    toggle.setAttribute("aria-expanded", String(open));
  }
  toggle.addEventListener("click", () => setPanel(panel.classList.contains("closed")));
  document.querySelector("#close-layers").addEventListener("click", () => setPanel(false));
});
