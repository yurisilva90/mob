const CACHE_NAME = 'smartmobi-v21-network-first';
const ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png',
  '/apple-touch-icon.png',
  '/screenshot-home.png',
  '/screenshot-wide.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  const isAppShell = event.request.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('/index.html');

  if (isAppShell) {
    // Network-first pro HTML: o app SEMPRE busca a versão mais nova primeiro.
    // Só cai pro cache se estiver de verdade offline (sem internet).
    // Isso evita o app ficar "preso" numa versão antiga mesmo depois de eu corrigir algo.
    event.respondWith(
      fetch(event.request).then(response => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        return response;
      }).catch(() => caches.match(event.request).then(cached => cached || caches.match('/index.html')))
    );
    return;
  }

  // Demais assets (ícones, manifest) — cache-first, ok serem mais "lentos" pra atualizar.
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
      return response;
    }).catch(() => caches.match('/index.html')))
  );
});

self.addEventListener('sync', event => {
  if (event.tag === 'smartmobi-v20-header-menu-fix') event.waitUntil(Promise.resolve());
});

self.addEventListener('push', event => {
  const data = event.data ? event.data.text() : 'SmartMobi';
  event.waitUntil(self.registration.showNotification('SmartMobi', {
    body: data,
    icon: '/icon-192.png',
    badge: '/icon-192.png'
  }));
});
