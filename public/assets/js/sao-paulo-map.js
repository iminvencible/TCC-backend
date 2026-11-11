// Shared public and professional map viewport. Boundary: IBGE, state code 35.
export const SP_BOUNDS = [[-25.32, -53.12], [-19.77, -44.15]];
let boundaryRequest;
export function loadStateBoundary() {
  return boundaryRequest ||= fetch('/assets/data/sao-paulo.geojson').then((response) => {
    if (!response.ok) throw new Error('Limite de São Paulo indisponível');
    return response.json();
  }).catch((error) => { boundaryRequest = null; throw error; });
}

export function containsPoint(geometry, latitude, longitude) {
  function inRing(ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [x, y] = ring[i], [px, py] = ring[j];
      const cross = (longitude - px) * (y - py) - (latitude - py) * (x - px);
      if (Math.abs(cross) < 1e-9 && longitude >= Math.min(x, px) && longitude <= Math.max(x, px) && latitude >= Math.min(y, py) && latitude <= Math.max(y, py)) return true;
      if ((y > latitude) !== (py > latitude) && longitude < (px - x) * (latitude - y) / (py - y) + x) inside = !inside;
    }
    return inside;
  }
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  return polygons.some((rings) => inRing(rings[0]) && !rings.slice(1).some(inRing));
}

export async function configureStateMap(map, onTileError = () => {}, isActive = () => true) {
  const boundary = await loadStateBoundary();
  if (!isActive()) throw new Error('Mapa fechado');
  const geometry = boundary.features[0].geometry;
  const stateLayer = L.geoJSON(boundary);
  const bounds = stateLayer.getBounds();
  map.getContainer().classList.add('sp-dark-map');
  map.options.zoomSnap = 0.25;
  map.options.maxBoundsViscosity = 1;
  map.setMaxBounds(bounds);
  const updateMinimum = () => {
    // Fractional zoom preserves the complete state on both narrow and wide maps.
    const minimum = map.getBoundsZoom(bounds, false, L.point(24, 24));
    map.setMinZoom(minimum);
    if (map.getZoom() < minimum) map.setZoom(minimum);
  };
  updateMinimum();
  map.fitBounds(bounds, { padding: [12, 12], animate: false });
  map.on('resize', updateMinimum);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, bounds, noWrap: true, className: 'sp-dark-tiles', opacity: 0.78,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · Limite: <a href="https://servicodados.ibge.gov.br/api/docs/malhas?versao=3">IBGE</a>',
  }).on('tileerror', onTileError).addTo(map);
  const pane = map.createPane('stateMask');
  pane.style.zIndex = '650';
  pane.style.pointerEvents = 'none';
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  const world = [[-85, -180], [-85, 180], [85, 180], [85, -180]];
  const holes = polygons.map((rings) => rings[0].map(([lng, lat]) => [lat, lng]));
  L.polygon([world, ...holes], { pane: 'stateMask', stroke: false, fillColor: '#080f1a', fillOpacity: 1, fillRule: 'evenodd', interactive: false }).addTo(map);
  L.geoJSON(boundary, { pane: 'stateMask', interactive: false, style: { color: '#6daac1', opacity: 0.8, weight: 1.3, fillOpacity: 0 } }).addTo(map);
  return {
    bounds,
    contains: (lat, lng) => containsPoint(geometry, lat, lng),
    fit: () => map.fitBounds(bounds, { padding: [12, 12], animate: false }),
    fitArea: (areaBounds) => {
      const south = Math.max(bounds.getSouth(), areaBounds.getSouth()), north = Math.min(bounds.getNorth(), areaBounds.getNorth());
      const west = Math.max(bounds.getWest(), areaBounds.getWest()), east = Math.min(bounds.getEast(), areaBounds.getEast());
      if (south > north || west > east) return false;
      map.fitBounds([[south, west], [north, east]], { maxZoom: 10, padding: [16, 16] });
      return true;
    },
  };
}
