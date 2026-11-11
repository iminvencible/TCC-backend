const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('public/assets/js/notifications.js', 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
function harness(pathname = '/inicio.html') {
  const events = {}, nodes = {}, saved = new Map();
  const banner = { hidden: true, dataset: {}, setAttribute() {}, querySelector(s) { return nodes[s] ||= {}; } };
  let tick, requests = 0, sounds = 0;
  const document = { hidden: false, body: { append() {} }, createElement: () => banner, addEventListener: (e, fn) => { events[e] = fn; } };
  const user = { id: 1, weather_notifications: true, alert_sound: true };
  const rows = [{ id: 7, title: 'Tempestade severa', valid_until: new Date(Date.now()+60000).toISOString() }];
  class AudioContext {
    state = 'running'; currentTime = 0;
    createOscillator() { sounds++; return { connect() {}, frequency: {}, start() {}, stop() {} }; }
    createGain() { return { connect() {}, gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} } }; }
  }
  vm.runInNewContext(source, {
    document, window: { AudioContext, location: { pathname }, addEventListener() {} },
    PrevClima: { request: async path => { requests++; return path === '/users/me' ? user : rows; } },
    sessionStorage: { getItem: k => saved.get(k), setItem: (k,v) => saved.set(k,v) },
    setInterval: fn => { tick = fn; return 1; }, clearInterval() {}, Date, Set, JSON,
  });
  return { user, rows, document, banner, events, get requests() { return requests; }, get sounds() { return sounds; }, async start() { events.DOMContentLoaded(); await settle(); }, async poll() { await tick(); await settle(); } };
}
test('notifications deduplicate alerts and respect sound preference', async () => {
  const h = harness(); await h.start();
  assert.equal(h.banner.hidden, false);
  h.events.pointerdown(); await h.poll(); assert.equal(h.sounds, 0);
  h.rows.push({ ...h.rows[0], id: 8 }); await h.poll(); assert.equal(h.sounds, 1);
  h.user.alert_sound = false; h.rows.push({ ...h.rows[0], id: 9 }); await h.poll(); assert.equal(h.sounds, 1);
});
test('hidden pages do not poll and disabled notifications hide the banner', async () => {
  const h = harness(); await h.start(); const before = h.requests;
  h.document.hidden = true; await h.poll(); assert.equal(h.requests, before);
  h.document.hidden = false; h.user.weather_notifications = false; await h.poll(); assert.equal(h.banner.hidden, true);
});
test('expired alerts are not announced and missing local alerts remove old banner', async () => {
  const h = harness(); h.rows[0].valid_until = new Date(Date.now()-1000).toISOString(); await h.start();
  assert.equal(h.banner.hidden, true);
  h.rows[0].valid_until = new Date(Date.now()+60000).toISOString(); await h.poll(); assert.equal(h.banner.hidden, false);
  h.rows.length = 0; await h.poll(); assert.equal(h.banner.hidden, true);
});


test('mobile notification opens the mobile advisory page', async () => {
  const h = harness('/mobile/inicio.html'); await h.start();
  assert.equal(h.banner.querySelector('a').href, '/mobile/alertas.html');
});
