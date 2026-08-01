const CACHE = 'mycodexai-static-v2';
const STATIC = ['/static/app-icon.svg', '/static/style.css', '/static/remote.css', '/static/login.css'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(STATIC)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (event) => event.waitUntil(
  caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key.startsWith('mycodexai-static-') && key !== CACHE).map((key) => caches.delete(key))
  )).then(() => self.clients.claim())
));
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith('/static/') || event.request.method !== 'GET') return;
  if (url.pathname.endsWith('.js')) return;
  event.respondWith(fetch(event.request).then((response) => {
    const copy = response.clone();
    caches.open(CACHE).then((cache) => cache.put(event.request, copy));
    return response;
  }).catch(() => caches.match(event.request)));
});
