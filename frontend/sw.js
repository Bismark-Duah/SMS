// eduManage360 Offline-First Service Worker
const CACHE_NAME = 'edumanage360-v10.2';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/auth.html',
  '/login.html',
  '/dashboard.html',
  '/students.html',
  '/classes.html',
  '/fees.html',
  '/attendance.html',
  '/exeat.html',
  '/discipline.html',
  '/clearance.html',
  '/bulk-entry.html',
  '/programs.html',
  '/users.html',
  '/assignments.html',
  '/report-card.html',
  '/reports.html',
  '/results.html',
  '/super-admin.html',
  '/settings.html',
  '/parent-view.html',
  '/academic.html',
  '/announcements.html',
  '/assets.html',
  '/broadsheet.html',
  '/cumulative-record.html',
  '/data-tools.html',
  '/departments.html',
  '/enrollment.html',
  '/houses.html',
  '/messaging.html',
  '/promotions.html',
  '/rollover.html',
  '/subjects.html',
  '/timetable.html',
  '/css/styles.css',
  '/js/academic.js',
  '/js/announcements.js',
  '/js/app.js',
  '/js/assets.js',
  '/js/assignments.js',
  '/js/attendance.js',
  '/js/auth.js',
  '/js/branding.js',
  '/js/broadsheet.js',
  '/js/bulk-entry.js',
  '/js/charts.js',
  '/js/classes.js',
  '/js/clearance.js',
  '/js/config.js',
  '/js/cumulative-record.js',
  '/js/dashboard.js',
  '/js/data-tools.js',
  '/js/departments.js',
  '/js/discipline.js',
  '/js/enrollment.js',
  '/js/exeat.js',
  '/js/featureGate.js',
  '/js/fees.js',
  '/js/guard.js',
  '/js/houses.js',
  '/js/messaging.js',
  '/js/offline-store.js',
  '/js/parent-view.js',
  '/js/programs.js',
  '/js/promotions.js',
  '/js/qrcode.min.js',
  '/js/report-card.js',
  '/js/reports.js',
  '/js/results.js',
  '/js/rollover.js',
  '/js/settings.js',
  '/js/stateBus.js',
  '/js/students.js',
  '/js/subjects.js',
  '/js/super-admin.js',
  '/js/syncManager.js',
  '/js/theme.js',
  '/js/timetable.js',
  '/js/users.js',
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
