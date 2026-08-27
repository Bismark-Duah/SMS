// eduManage360 Offline-First Service Worker
const CACHE_NAME = 'edumanage360-v7.7';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/auth.html',
  '/dashboard.html',
  '/bulk-entry.html',
  '/programs.html',
  '/users.html',
  '/assignments.html',
  '/report-card.html',
  '/super-admin.html',
  '/css/styles.css',
  '/js/theme.js',
  '/js/auth.js',
  '/js/guard.js',
  '/js/users.js',
  '/js/assignments.js',
  '/js/super-admin.js',
  '/js/offline-store.js',
  '/js/bulk-entry.js',
  '/js/programs.js',
  '/js/report-card.js',
  '/assets/logo_primary.png',
  '/assets/logo_compact.png',
  '/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('Some assets could not be cached immediately:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  // Skip API network requests so live database changes are never stale
  if (event.request.url.includes('/api/')) return;

  const isHtmlNavigation = event.request.mode === 'navigate' ||
    (event.request.headers.get('accept') && event.request.headers.get('accept').includes('text/html'));

  if (isHtmlNavigation) {
    // Network-First for HTML pages: Always fetch latest from server, fallback to cache offline
    event.respondWith(
      fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
          }
          return networkResponse;
        })
        .catch(() => {
          return caches.match(event.request).then((cached) => cached || caches.match('/index.html') || caches.match('/auth.html'));
        })
    );
    return;
  }

  // Stale-While-Revalidate for CSS, JS, and image assets
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
          }
          return networkResponse;
        })
        .catch(() => {});

      return cachedResponse || fetchPromise;
    })
  );
});
