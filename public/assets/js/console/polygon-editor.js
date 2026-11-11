import { configureStateMap } from "../sao-paulo-map.js";
// One editable polygon, usable by map clicks or keyboard coordinate entry.
export function polygonEditor(host, initial = null) {
  host.innerHTML = `<div class="polygon-map console-map" aria-label="Área do aviso"></div>
    <p>Clique no mapa para adicionar vértices. Arraste os pontos para ajustar a área, ou use as coordenadas abaixo.</p>
    <div class="row"><label>Latitude<input class="field" data-lat type="number" min="-90" max="90" step="any"></label>
    <label>Longitude<input class="field" data-lon type="number" min="-180" max="180" step="any"></label>
    <button class="btn" type="button" data-add>Adicionar ponto</button><button class="btn" type="button" data-undo>Desfazer ponto</button><button class="btn" type="button" data-clear>Limpar área</button></div>
    <p data-count role="status"></p>`;
  let rings = initial ? structuredClone(initial.coordinates) : [[]];
  let points = rings[0].slice(0, initial ? -1 : undefined).map(([lon, lat]) => [lat, lon]);
  let map = null, layer = null;
  let destroyed = false;
  if (window.L) {
    map = L.map(host.querySelector(".polygon-map"), { zoomAnimation: false, fadeAnimation: false, markerZoomAnimation: false }).setView([-23.8, -46.5], 7);
    configureStateMap(map, () => {}, () => !destroyed).then((view) => {
      if (!destroyed && points.length >= 3) view.fitArea(L.polygon(points).getBounds());
    }).catch(() => {
      if (!destroyed) host.querySelector("[data-count]").textContent = "O limite de São Paulo não carregou. Use as coordenadas para editar.";
    });
    layer = L.layerGroup().addTo(map);
    map.on("click", (event) => { points.push([event.latlng.lat, event.latlng.lng]); render(); });
  } else host.querySelector(".polygon-map").textContent = "Mapa indisponível. Informe os pontos usando latitude e longitude.";
  function geometry() {
    if (points.length < 3) throw new Error("Desenhe uma área com pelo menos três pontos.");
    const ring = points.map(([lat, lon]) => [lon, lat]);
    return { type: "Polygon", coordinates: [[...ring, [...ring[0]]], ...rings.slice(1)] };
  }
  function render() {
    host.querySelector("[data-count]").textContent = `${points.length} pontos. ${points.length >= 3 ? "Área pronta para conferência." : "Adicione pelo menos três pontos."}`;
    if (!layer) return;
    layer.clearLayers();
    if (points.length >= 3) L.geoJSON(geometry(), { style: { color: "#f4c64c", fillOpacity: 0.2 } }).addTo(layer);
    else if (points.length) L.polyline(points, { color: "#f4c64c" }).addTo(layer);
    points.forEach((point, i) => {
      const marker = L.marker(point, { draggable: true, title: `Ponto ${i + 1}` }).addTo(layer);
      marker.on("dragend", () => { const pos = marker.getLatLng(); points[i] = [pos.lat, pos.lng]; render(); });
    });
  }
  host.querySelector("[data-add]").onclick = () => {
    const lat = host.querySelector("[data-lat]"), lon = host.querySelector("[data-lon]");
    if (!lat.value || !lon.value || !lat.reportValidity() || !lon.reportValidity()) return;
    points.push([Number(lat.value), Number(lon.value)]); render();
    if (map) map.panTo(points.at(-1), { animate: false });
  };
  host.querySelector("[data-undo]").onclick = () => { points.pop(); render(); };
  host.querySelector("[data-clear]").onclick = () => { points = []; rings = [[]]; render(); };
  render();
  if (map && points.length >= 3) map.fitBounds(L.polygon(points).getBounds().pad(0.15), { animate: false });
  requestAnimationFrame(() => map?.invalidateSize());
  return { geometry, destroy: () => { destroyed = true; map?.stop(); map?.remove(); map = null; } };
}
