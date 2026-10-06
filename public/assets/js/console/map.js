import { api, esc, empty } from "./ui.js";

export async function drawMap(container) {
  const data = await api("/map-data");
  if (!container.isConnected) return null;
  if (!window.L) {
    container.innerHTML = empty(
      "Mapa indisponível. Consulte a lista de alertas e as estações.",
    );
    return null;
  }
  const map = L.map(container).setView([-23.8, -46.5], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);
  const alerts = L.layerGroup().addTo(map),
    forecasts = L.layerGroup().addTo(map);
  const colors = {
    LOW: "#13803f",
    MODERATE: "#b58900",
    HIGH: "#e8630a",
    CRITICAL: "#d11a33",
  };
  for (const a of data.alerts || []) {
    const options = { color: colors[a.severity], fillOpacity: 0.18 };
    const area = a.polygon
      ? L.geoJSON(a.polygon, { style: options })
      : a.latitude != null && a.longitude != null && a.radius_km
        ? L.circle([Number(a.latitude), Number(a.longitude)], {
            ...options,
            radius: Number(a.radius_km) * 1000,
          })
        : null;
    area
      ?.bindPopup(
        `<strong>${esc(a.title)}</strong><br>${esc(a.area_name)}<br>${esc(a.source_name)}`,
      )
      .addTo(alerts);
  }
  for (const f of data.forecast_points || []) {
    if (f.latitude != null && f.longitude != null)
      L.circleMarker([Number(f.latitude), Number(f.longitude)], {
        radius: 7,
        color: "#1447d4",
      })
        .bindPopup(
          `${esc(f.city)} · ${esc(f.temperature_c)} °C<br>${esc(f.source_name)}`,
        )
        .addTo(forecasts);
  }
  L.control
    .layers(null, {
      "Avisos meteorológicos": alerts,
      "Previsões pontuais": forecasts,
    })
    .addTo(map);
  return map;
}
