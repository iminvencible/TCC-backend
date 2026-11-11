import { configureStateMap } from "../sao-paulo-map.js";
import { api, esc, empty } from "./ui.js";

export async function drawMap(container) {
  const data = await api("/map-data");
  if (!container.isConnected) return null;
  const status = document.createElement("p");
  status.className = "hint";
  status.textContent = PrevClima.feedStatus(data.warning_feed);
  container.after(status);
  const search = document.createElement("a");
  search.className = "btn";
  search.href = "/mapa.html";
  search.textContent = "Buscar cidade e ver lista completa de avisos ↗";
  status.after(search);
  if (!window.L) {
    container.innerHTML = empty(
      "Mapa indisponível. Consulte a lista de alertas e as estações.",
    );
    return null;
  }
  const map = L.map(container, { zoomAnimation: false, fadeAnimation: false, markerZoomAnimation: false }).setView([-23.8, -46.5], 6);
  try {
    await configureStateMap(map, () => { status.textContent = "Mapa-base indisponível. Use a lista de avisos. " + PrevClima.feedStatus(data.warning_feed); });
  } catch (_error) {
    map.remove();
    container.textContent = "O limite de São Paulo não carregou. Consulte a lista de avisos.";
    return null;
  }
  if (!container.isConnected) { map.remove(); return null; }
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
  for (const f of [...(data.forecast_areas || []), ...(data.severe_forecast_areas || [])]) {
    const popup = document.createElement("div");
    popup.textContent = `${f.area_name || f.city} · ${PrevClima.severityName(f.severity)} — ${f.description || "Área de previsão"} · Até ${new Date(f.valid_until).toLocaleString("pt-BR")}`;
    L.geoJSON(f.polygon, { style: { color: "#9b7af5", fillOpacity: 0.18 } }).bindPopup(popup).addTo(forecasts);
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
      "Previsões locais e de tempo severo": forecasts,
    })
    .addTo(map);
  return map;
}
