document.addEventListener("DOMContentLoaded", () => {
  const $ = (selector) => document.querySelector(selector);
  const form = $("#map-search");
  const status = $("#map-status");
  const locationButton = $("#map-location");
  const refreshButton = $("#map-refresh");
  const colors = { LOW: "#24875a", MODERATE: "#d4a017", HIGH: "#e57928", CRITICAL: "#d84758" };
  let map, forecastLayer, alertLayer;
  let requestId = 0;
  let currentParams = new URLSearchParams();
  let lastData = null;
  let tileError = false;
  const shapes = new Map();
  const states = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
  $("#map-state").replaceChildren(...states.map((state) => new Option(state, state, state === "SP", state === "SP")));

  function element(tag, text, className) {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function sourceLink(url) {
    try {
      const parsed = new URL(url);
      const trusted = ["inmet.gov.br", "open-meteo.com"].some((host) => parsed.hostname === host || parsed.hostname.endsWith(`.${host}`));
      if (!trusted || parsed.protocol !== "https:" || parsed.username || parsed.password) return null;
      const link = element("a", "Consultar fonte ↗");
      link.href = parsed.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      return link;
    } catch (_error) { return null; }
  }
  function visualNotice(message) {
    $("#map-visual-status").textContent = message;
    $("#map-visual-status").hidden = !message;
  }
  function popup(title, detail, source, url, date) {
    const node = element("div", "");
    node.append(element("strong", title), element("p", detail), element("p", `Fonte: ${source}`));
    if (date) node.append(element("p", `Válido até ${new Date(date).toLocaleString("pt-BR")}`));
    const link = sourceLink(url);
    if (link) node.append(link);
    return node;
  }
  function fitAll() {
    if (!map) return;
    const layers = [...alertLayer.getLayers(), ...forecastLayer.getLayers()];
    if (layers.length) {
      const bounds = L.featureGroup(layers).getBounds();
      if (bounds.isValid()) map.fitBounds(bounds.pad(.15), { maxZoom: 10 });
    }
  }
  function renderForecast(data) {
    const host = $("#map-forecast");
    const point = data.forecast_points?.[0];
    host.replaceChildren();
    if (!point) {
      host.append(element("span", "SEM PREVISÃO DISPONÍVEL", "data-tag"), element("h2", "Não foi possível obter a previsão"), element("p", "Confira a cidade e a UF ou tente atualizar em instantes. Nenhum valor estimado foi inserido."));
      return;
    }
    host.append(element("span", point.is_stale ? "Último dado salvo" : `Previsão · ${point.source_name}`, "data-tag"), element("h2", `${point.city}, ${point.state}`), element("div", `${Math.round(Number(point.temperature_c))}°`, "point-temperature"), element("p", `${point.condition} · Chuva: ${point.rain_probability}%`), element("p", `Atualizado ${PrevClima.relativeTime(point.issued_at)}`));
    const link = sourceLink(point.source_url);
    if (link) host.append(link);
    if (states.includes(point.state)) {
      form.elements.city.value = point.city;
      form.elements.state.value = point.state;
    }
  }
  function renderWarnings(data) {
    const list = $("#map-warning-list");
    list.replaceChildren();
    const alerts = [...(data.alerts || [])].sort((a, b) => ["CRITICAL", "HIGH", "MODERATE", "LOW"].indexOf(a.severity) - ["CRITICAL", "HIGH", "MODERATE", "LOW"].indexOf(b.severity));
    $("#map-warning-count").textContent = alerts.length;
    if (!alerts.length) {
      const item = element("li", "");
      item.append(element("strong", "Nenhum aviso disponível"), element("p", "Confira o estado da sincronização acima e consulte a fonte oficial."));
      list.append(item);
    }
    for (const alert of alerts) {
      const item = element("li", "");
      item.style.setProperty("--warning-color", colors[alert.severity]);
      const shape = shapes.get(alert.id);
      const title = element(shape ? "button" : "strong", `${alert.is_demo ? "DEMONSTRAÇÃO · " : ""}${alert.title}`);
      if (shape) {
        title.type = "button";
        title.addEventListener("click", () => {
          $("#alert-layer").checked = true;
          alertLayer.addTo(map);
          map.fitBounds(shape.getBounds().pad(.2), { maxZoom: 10 });
          shape.openPopup();
          $("#weather-map").scrollIntoView({ block: "center" });
        });
      }
      item.append(element("span", PrevClima.severityName(alert.severity), "warning-level"), title, element("p", alert.area_name), element("p", `Fonte: ${alert.source_name}`), element("p", `Até ${new Date(alert.valid_until).toLocaleString("pt-BR")}`));
      if (!alert.polygon && !(alert.latitude != null && alert.longitude != null && Number(alert.radius_km) > 0)) item.append(element("p", "Área descrita em texto pela fonte, sem delimitação no mapa."));
      const link = sourceLink(alert.source_url);
      if (link) item.append(link);
      list.append(item);
    }
  }
  function draw(data, recenter) {
    if (!map) return;
    forecastLayer.clearLayers();
    alertLayer.clearLayers();
    shapes.clear();
    for (const point of data.forecast_points || []) {
      L.circleMarker([Number(point.latitude), Number(point.longitude)], { radius: 10, color: "#fff", fillColor: "#258cce", fillOpacity: 1, weight: 3 })
        .bindPopup(popup(`${point.city}, ${point.state}`, `${point.condition} · ${Math.round(Number(point.temperature_c))} °C${point.is_stale ? " · Último dado salvo" : ""}`, point.source_name, point.source_url, point.valid_until)).addTo(forecastLayer);
    }
    for (const area of data.forecast_areas || []) {
      L.geoJSON(area.polygon, { style: { color: "#258cce", fillOpacity: .1, dashArray: "5 6" } })
        .bindPopup(popup(`${area.city}, ${area.state}`, "Área de previsão cadastrada", area.source_name, null, area.valid_until)).addTo(forecastLayer);
    }
    let invalidGeometry = false;
    for (const alert of data.alerts || []) {
      try {
        const style = { color: colors[alert.severity], fillOpacity: .2, weight: 2 };
        const shape = alert.polygon ? L.geoJSON(alert.polygon, { style }) :
          alert.latitude != null && alert.longitude != null && Number(alert.radius_km) > 0 ?
            L.circle([Number(alert.latitude), Number(alert.longitude)], { ...style, radius: Number(alert.radius_km) * 1000 }) : null;
        if (shape) {
          shape.bindPopup(popup(`${alert.is_demo ? "DEMONSTRAÇÃO · " : ""}${alert.title}`, alert.area_name, alert.source_name, alert.source_url, alert.valid_until)).addTo(alertLayer);
          shapes.set(alert.id, shape);
        }
      } catch (_error) { invalidGeometry = true; }
    }
    if (invalidGeometry) visualNotice("Algumas áreas não puderam ser desenhadas. Todos os avisos continuam na lista.");
    if (recenter) {
      const point = data.forecast_points?.[0];
      if (point) map.setView([Number(point.latitude), Number(point.longitude)], 9);
      else fitAll();
    }
    map.invalidateSize();
  }
  function expireDisplayedData() {
    // Never keep an expired warning on screen just because a refresh failed.
    if (!lastData) return;
    lastData.alerts = (lastData.alerts || []).filter((a) => Date.parse(a.valid_until) > Date.now());
    lastData.forecast_areas = (lastData.forecast_areas || []).filter((f) => Date.parse(f.valid_until) > Date.now());
    lastData.forecast_points = (lastData.forecast_points || []).filter((p) => Date.now() - Date.parse(p.issued_at) <= 86400000).map((p) => ({ ...p, is_stale: true }));
    draw(lastData, false);
    renderForecast(lastData);
    renderWarnings(lastData);
  }
  async function load(params = currentParams, { recenter = true } = {}) {
    const id = ++requestId;
    currentParams = new URLSearchParams(params);
    status.textContent = "Consultando fontes meteorológicas…";
    refreshButton.disabled = true;
    form.querySelector("button").disabled = true;
    try {
      const data = await PrevClima.request(`/map-data${params.size ? `?${params}` : ""}`);
      if (id !== requestId) return;
      lastData = data;
      if (map && !tileError) visualNotice("");
      draw(data, recenter);
      renderForecast(data);
      renderWarnings(data);
      $("#feed-status").textContent = PrevClima.feedStatus(data.warning_feed);
      status.textContent = `Consulta ${new Date(data.generated_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })} · Atualização automática a cada 5 min`;
    } catch (error) {
      if (id !== requestId) return;
      // A failed city search must not relabel the previous city's data.
      expireDisplayedData();
      status.textContent = `${error.message}${lastData ? " Exibindo a última consulta, sem atualização confirmada." : " Tente atualizar."}`;
      $("#feed-status").textContent = "Não foi possível verificar o estado da sincronização.";
      if (!lastData) {
        $("#map-forecast").replaceChildren(element("h2", "Dados indisponíveis"), element("p", "Confira a conexão e tente novamente."));
        $("#map-warning-list").replaceChildren(element("li", "Os avisos não puderam ser consultados."));
      }
    } finally {
      if (id === requestId) {
        refreshButton.disabled = false;
        form.querySelector("button").disabled = false;
      }
    }
  }
  if (window.L) {
    map = L.map("weather-map", { zoomControl: false }).setView([-15.7, -51.5], 4);
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' })
      .on("tileerror", () => { tileError = true; visualNotice("Mapa-base indisponível. Consulte as previsões e os avisos na lista."); }).addTo(map);
    forecastLayer = L.layerGroup().addTo(map);
    alertLayer = L.layerGroup().addTo(map);
  } else {
    visualNotice("O mapa visual não carregou. A busca, as previsões e a lista de avisos continuam disponíveis abaixo ou ao lado.");
    $("#map-fit").disabled = true;
  }
  for (const [selector, layer] of [["#forecast-layer", forecastLayer], ["#alert-layer", alertLayer]]) {
    $(selector).disabled = !map;
    $(selector).addEventListener("change", (event) => { if (event.target.checked) layer.addTo(map); else layer.removeFrom(map); });
  }
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    load(new URLSearchParams({ city: form.elements.city.value.trim(), state: form.elements.state.value }));
  });
  refreshButton.addEventListener("click", () => load(currentParams, { recenter: false }));
  $("#map-fit").addEventListener("click", fitAll);
  locationButton.disabled = !navigator.geolocation;
  locationButton.addEventListener("click", async () => {
    locationButton.disabled = true;
    try {
      await PrevClima.request("/users/me");
      status.textContent = "Obtendo sua localização…";
      const position = await new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: false, timeout: 10000, maximumAge: 900000 }));
      await load(new URLSearchParams({ latitude: position.coords.latitude.toFixed(2), longitude: position.coords.longitude.toFixed(2) }));
    } catch (error) {
      status.textContent = error.status === 401 ? "Entre na sua conta para usar o GPS. A busca por cidade é pública. " : "Não foi possível obter sua localização. Use a busca por cidade.";
      if (error.status === 401) {
        const link = element("a", "Entrar");
        link.href = "/?next=/mapa.html";
        status.append(link);
      }
    } finally { locationButton.disabled = false; }
  });
  setInterval(() => { if (!document.hidden) load(currentParams, { recenter: false }); }, 300000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) load(currentParams, { recenter: false }); });
  const initial = new URLSearchParams(window.location.search);
  if (initial.has("city") && initial.has("state")) currentParams = new URLSearchParams({ city: initial.get("city"), state: initial.get("state") });
  load();
});
