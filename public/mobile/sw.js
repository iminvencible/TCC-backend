const CACHE = "prevclima-mobile-v8";
const SHELL = [
  "/mobile/",
  "/mobile/conta.html",
  "/mobile/mobile-shell.js",
  "/mobile/mobile-common.js",
  "/mobile/mobile-alerts.js",
  "/mobile/mobile-profile.js",
  "/assets/js/account.js",
  "/assets/js/map.js",
  "/assets/js/sao-paulo-map.js",
  "/assets/data/sao-paulo.geojson",
  "/assets/css/state-map.css",
  "/assets/css/weather-map.css",
  "/mobile/mobile.css?v=8",
  "/mobile/mobile.js",
  "/mobile/mobile-home.js",
  "/assets/img/prevclima-logo.jpg",
  "/assets/js/api.js",
  "/assets/js/notifications.js",
  "/assets/css/notifications.css"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith("prevclima-mobile-") && key !== CACHE).map((key) => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (new URL(event.request.url).origin !== self.location.origin) return;
  if (event.request.method !== "GET" || new URL(event.request.url).pathname.startsWith("/api/")) return;
  event.respondWith(fetch(event.request).then((response) => {
    const copy = response.clone();
    if (response.ok) event.waitUntil(caches.open(CACHE).then((cache) => cache.put(event.request, copy)));
    return response;
  }).catch(() => caches.match(event.request).then((cached) => cached || new Response("Sem conexão. Reconecte e tente novamente.", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } }))));
});
