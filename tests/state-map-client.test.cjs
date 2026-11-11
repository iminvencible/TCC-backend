const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const moduleUrl = 'data:text/javascript;base64,' + Buffer.from(fs.readFileSync('public/assets/js/sao-paulo-map.js', 'utf8')).toString('base64');
const boundary = JSON.parse(fs.readFileSync('public/assets/data/sao-paulo.geojson', 'utf8'));

test('official state boundary includes São Paulo cities and excludes nearby other states', async () => {
  const { containsPoint } = await import(moduleUrl);
  const geometry = boundary.features[0].geometry;
  for (const point of [[-23.55, -46.63], [-23.96, -46.33], [-21.17, -47.81], [-22.12, -51.39]]) assert.equal(containsPoint(geometry, ...point), true);
  for (const point of [[-25.43, -49.27], [-22.91, -43.17], [-22.23, -45.93], [-19.92, -43.94]]) assert.equal(containsPoint(geometry, ...point), false);
});

test('viewport fits state, adapts minimum zoom, masks outside, and refuses outside bounds', async () => {
  const { configureStateMap } = await import(moduleUrl);
  const bounds = { getSouth: () => -25.32, getNorth: () => -19.77, getWest: () => -53.12, getEast: () => -44.15 };
  const masks = [], tileOptions = [];
  global.fetch = async () => ({ ok: true, json: async () => boundary });
  global.L = {
    geoJSON: () => ({ getBounds: () => bounds, addTo() { return this; } }),
    point: (x, y) => ({ x, y }),
    tileLayer: (_url, options) => { tileOptions.push(options); return { on() { return this; }, addTo() { return this; } }; },
    polygon: (rings, options) => { masks.push({ rings, options }); return { addTo() {} }; },
  };
  let minimum = 5.75, appliedMinimum, fitCalls = 0;
  const events = {};
  const map = {
    options: {}, getContainer: () => ({ classList: { add() {} } }),
    setMaxBounds: (value) => assert.equal(value, bounds),
    getBoundsZoom: () => minimum, setMinZoom: (value) => { appliedMinimum = value; },
    getZoom: () => 6, setZoom() {}, fitBounds: () => { fitCalls++; },
    on: (name, handler) => { events[name] = handler; }, createPane: () => ({ style: {} }),
  };
  const view = await configureStateMap(map);
  assert.equal(appliedMinimum, 5.75);
  assert.equal(tileOptions[0].noWrap, true);
  assert.equal(tileOptions[0].opacity, .78);
  assert.equal(masks[0].options.fillOpacity, 1);
  assert.equal(masks[0].options.fillRule, 'evenodd');
  assert.ok(masks[0].rings.length > 1);
  minimum = 7; events.resize(); assert.equal(appliedMinimum, 7);
  const before = fitCalls;
  assert.equal(view.fitArea({ getSouth: () => 0, getNorth: () => 1, getWest: () => 0, getEast: () => 1 }), false);
  assert.equal(fitCalls, before);
  view.fit(); assert.equal(fitCalls, before + 1);
});
