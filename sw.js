const TILE_CACHE = "travel-map-tile-cache-v1";
const WEATHER_CACHE = "travel-map-weather-api-cache-v1";
const TILE_HOSTS = new Set(["tile.openstreetmap.jp"]);
const WEATHER_HOSTS = new Set(["api.open-meteo.com"]);

self.addEventListener("install", event => {
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (TILE_HOSTS.has(url.hostname)) {
    event.respondWith(cacheFirst(event.request, TILE_CACHE));
    return;
  }
  if (WEATHER_HOSTS.has(url.hostname)) {
    event.respondWith(networkFirst(event.request, WEATHER_CACHE));
  }
});

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  cache.put(request, response.clone());
  return response;
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}
