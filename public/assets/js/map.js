document.addEventListener("DOMContentLoaded", () => {
  const status = document.querySelector("#map-status");
  const fallback = document.querySelector("#map-fallback");
  const fallbackMessage = document.querySelector("#map-fallback-message");
  const fallbackList = document.querySelector("#map-fallback-list");
  const mapElement = document.querySelector("#weather-map");
  const locationButton = document.querySelector("#map-location");
  const colors = { LOW: "#2fe342", MODERATE: "#ffd42a", HIGH: "#ff8426", CRITICAL: "#ef3045" };
  let map = null;
  let forecastLayer = null;
  let alertLayer = null;
  let tileError = false;
  let lastData = null;

  function sourceLink(url) {
    if (!url) return null;
    let parsed;
    try { parsed = new URL(url); } catch (_error) { return null; }
    const host = parsed.hostname.toLowerCase();
    const trusted = ["inmet.gov.br", "open-meteo.com"].some((domain) =>
      host === domain || host.endsWith(`.${domain}`));
    if (parsed.protocol !== "https:" || !trusted || parsed.username || parsed.password) return null;
    const link = document.createElement("a");
    link.href = parsed.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Ver fonte";
    return link;
  }

  function addLine(node, value) {
    const line = document.createElement("p");
    line.textContent = value;
    node.append(line);
  }

  function popup(title, detail, { demo = false, sourceName = "", sourceUrl = "", stale = false } = {}) {
    const node = document.createElement("div");
    const heading = document.createElement("strong");
    heading.textContent = `${demo ? "DEMONSTRAÇÃO — " : ""}${title}`;
    node.append(heading);
    addLine(node, detail);
    if (sourceName) addLine(node, `Fonte: ${sourceName}${stale ? " (último dado salvo)" : ""}`);
    const link = sourceLink(sourceUrl);
    if (link) node.append(link);
    return node;
  }

  function hasAlertGeometry(alert) {
    return Boolean(alert.polygon) || (alert.latitude != null && alert.longitude != null &&
      alert.radius_km != null && Number(alert.radius_km) > 0);
  }

  function showFallback(message, { unmappedOnly = false } = {}) {
    fallbackMessage.textContent = message;
    fallback.hidden = false;
    fallbackList.replaceChildren();
    if (!lastData) return;
    for (const point of unmappedOnly ? [] : lastData.forecast_points || []) {
      const item = document.createElement("li");
      const title = document.createElement("strong");
      title.textContent = `Previsão pontual: ${point.city}, ${point.state}`;
      item.append(title);
      addLine(item, `${point.condition}, ${Math.round(Number(point.temperature_c))} °C · Chuva: ${point.rain_probability}%`);
      addLine(item, `Fonte: ${point.source_name}${point.is_stale ? " (último dado salvo)" : ""}`);
      const link = sourceLink(point.source_url);
      if (link) item.append(link);
      fallbackList.append(item);
    }
    for (const area of unmappedOnly ? [] : lastData.forecast_areas || []) {
      const item = document.createElement("li");
      const title = document.createElement("strong");
      title.textContent = `Área de previsão: ${area.city}, ${area.state}`;
      item.append(title);
      addLine(item, `Fonte: ${area.source_name}`);
      fallbackList.append(item);
    }
    for (const alert of lastData.alerts || []) {
      if (unmappedOnly && hasAlertGeometry(alert)) continue;
      const item = document.createElement("li");
      const title = document.createElement("strong");
      title.textContent = `${alert.is_demo ? "DEMONSTRAÇÃO — " : ""}${alert.title}`;
      item.append(title);
      addLine(item, `${alert.area_name} · ${PrevClima.severityName(alert.severity)}`);
      addLine(item, `Fonte: ${alert.source_name}`);
      const link = sourceLink(alert.source_url);
      if (link) item.append(link);
      fallbackList.append(item);
    }
    if (!fallbackList.childElementCount) {
      const item = document.createElement("li");
      item.textContent = "Nenhum dado meteorológico disponível. Consulte os avisos oficiais do INMET antes de tomar decisões.";
      fallbackList.append(item);
    }
  }

  if (typeof window.L === "undefined") {
    mapElement.hidden = true;
    status.textContent = "Mapa visual indisponível";
    showFallback("O mapa visual não carregou. Verifique a conexão; os dados disponíveis aparecem abaixo.");
  } else {
    map = L.map("weather-map", { zoomControl: false }).setView([-15.7, -51.5], 4);
    L.control.zoom({ position: "topleft" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors",
    }).on("tileerror", () => {
      if (!tileError) {
        tileError = true;
        showFallback("O mapa-base não pôde ser carregado. As previsões e os avisos disponíveis estão listados abaixo.");
      }
    }).addTo(map);
    alertLayer = L.layerGroup().addTo(map);
    forecastLayer = L.layerGroup().addTo(map);
  }

  function polygonOptions(severity, fillOpacity = 0.3) {
    const color = colors[severity] || colors.MODERATE;
    return { color, fillColor: color, fillOpacity, weight: 2 };
  }

  async function load(params = new URLSearchParams()) {
    status.textContent = "Atualizando dados...";
    let fetched = false;
    try {
      const suffix = params.size ? `?${params}` : "";
      const data = await PrevClima.request(`/map-data${suffix}`);
      lastData = data;
      fetched = true;
      const points = data.forecast_points || [];
      if (map) {
        forecastLayer.clearLayers();
        alertLayer.clearLayers();
        for (const area of data.forecast_areas || []) {
          L.geoJSON(area.polygon, { style: {
            color: "#6aa7ec", fillColor: "#6aa7ec", fillOpacity: 0.12,
            weight: 2, dashArray: "6 5",
          } })
            .bindPopup(popup(`Área de previsão: ${area.city}, ${area.state}`, "Consulte a fonte e a validade da previsão.", {
              demo: area.source_name.includes("DEMONSTRA"), sourceName: area.source_name,
            })).addTo(forecastLayer);
        }
        for (const point of points) {
          L.circleMarker([Number(point.latitude), Number(point.longitude)], {
            radius: 10, color: "#a7d9ff", fillColor: "#2079f6", fillOpacity: 0.9, weight: 2,
          }).bindPopup(popup(`Previsão pontual: ${point.city}, ${point.state}`,
            `${point.condition} · ${Math.round(Number(point.temperature_c))} °C · Chuva: ${point.rain_probability}%`,
            { sourceName: point.source_name, sourceUrl: point.source_url, stale: point.is_stale },
          )).addTo(forecastLayer);
        }
        for (const alert of data.alerts || []) {
          let shape = null;
          if (alert.polygon) {
            shape = L.geoJSON(alert.polygon, { style: polygonOptions(alert.severity, 0.38) });
          } else if (hasAlertGeometry(alert)) {
            shape = L.circle([Number(alert.latitude), Number(alert.longitude)], {
              ...polygonOptions(alert.severity, 0.38), radius: Number(alert.radius_km) * 1000,
            });
          }
          if (shape) shape.bindPopup(popup(alert.title, alert.area_name, {
            demo: alert.is_demo, sourceName: alert.source_name, sourceUrl: alert.source_url,
          })).addTo(alertLayer);
        }
        if (points.length) {
          map.setView([Number(points[0].latitude), Number(points[0].longitude)], 9);
        } else if (alertLayer.getLayers().length) {
          const bounds = L.featureGroup(alertLayer.getLayers()).getBounds();
          if (bounds.isValid()) map.fitBounds(bounds.pad(0.2), { maxZoom: 9 });
        }
        map.invalidateSize();
      }
      const count = (data.alerts || []).length;
      const unmappedCount = (data.alerts || []).filter((alert) => !hasAlertGeometry(alert)).length;
      const mappedCount = count - unmappedCount;
      status.textContent = `${points.length ? "Previsão pontual carregada" : "Sem previsão pontual"} · ${mappedCount} aviso${mappedCount === 1 ? "" : "s"} com geometria` +
        (unmappedCount ? ` · ${unmappedCount} aviso${unmappedCount === 1 ? "" : "s"} apenas em texto` : "");
      if (!count) status.title = "A ausência de avisos disponíveis não confirma ausência de risco; confira o INMET.";
      else status.removeAttribute("title");
      if (!map || tileError) {
        showFallback(map ? "O mapa-base está indisponível; consulte os dados abaixo e os avisos oficiais do INMET." :
          "O mapa visual não carregou; consulte os dados abaixo e os avisos oficiais do INMET.");
      } else if (unmappedCount) {
        showFallback("Avisos sem delimitação geográfica fornecida pelo INMET: consulte a área descrita abaixo. Não é possível posicioná-los com precisão no mapa.", { unmappedOnly: true });
      } else {
        fallback.hidden = true;
      }
    } catch (error) {
      if (!fetched) lastData = null;
      if (map) {
        alertLayer.clearLayers();
        forecastLayer.clearLayers();
      }
      status.textContent = fetched ? "Mapa visual indisponível" : "Dados indisponíveis";
      showFallback(fetched
        ? "Os dados foram obtidos, mas não puderam ser desenhados no mapa. Consulte a lista e os avisos oficiais do INMET."
        : `${error.message} Consulte os avisos oficiais do INMET antes de tomar decisões.`);
    }
  }

  document.querySelector("#forecast-layer").addEventListener("change", (event) => {
    if (!map) return;
    if (event.target.checked) forecastLayer.addTo(map); else forecastLayer.removeFrom(map);
  });
  document.querySelector("#alert-layer").addEventListener("change", (event) => {
    if (!map) return;
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

  if (!navigator.geolocation) locationButton.disabled = true;
  locationButton.addEventListener("click", async () => {
    locationButton.disabled = true;
    try {
      await PrevClima.request("/users/me");
    } catch (error) {
      locationButton.disabled = false;
      if (error.status === 401) {
        status.textContent = "Entre para consultar sua localização";
        showFallback("Entre na sua conta para usar a geolocalização. O mapa por cidade continua público.");
        const link = document.createElement("a");
        link.href = "/?next=/mapa.html";
        link.textContent = "Entrar";
        fallbackMessage.append(" ", link);
      } else {
        status.textContent = error.message;
      }
      return;
    }
    status.textContent = "Obtendo localização...";
    navigator.geolocation.getCurrentPosition(
      (position) => {
        locationButton.disabled = false;
        const params = new URLSearchParams({
          latitude: position.coords.latitude.toFixed(2),
          longitude: position.coords.longitude.toFixed(2),
        });
        load(params);
      },
      () => {
        locationButton.disabled = false;
        status.textContent = "Localização não autorizada; exibindo a localidade anterior";
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 900000 },
    );
  });

  load();
});
