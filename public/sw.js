// Service worker — minimal app-shell cache.
//
// Keeping this deliberately small: we cache only the static shell
// (HTML, manifest, icon, config). All data calls go straight to
// Supabase over the network, which means the app works offline only
// in the very narrow sense of "loads the shell and tells you you're
// offline" — that's intentional. A more ambitious version would
// queue mutations in IndexedDB and replay them, but that's a real
// design exercise of its own (conflict resolution, auth refresh,
// expired requests, ...) — not v1.

const SHELL = 'tasukete-shell-v1';
const ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icon.svg',
  '/config.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Never intercept Supabase API calls — they need fresh data.
  if (url.host.endsWith('.supabase.co') || url.host.endsWith('.supabase.in')) {
    return;
  }
  // Network-first for HTML so we always pick up new shell versions
  // when the user has connectivity.
  if (event.request.mode === 'navigate' || url.pathname.endsWith('.html')) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(SHELL).then((c) => c.put(event.request, copy));
          return res;
        })
        .catch(() => caches.match(event.request).then((r) => r || caches.match('/index.html')))
    );
    return;
  }
  // Cache-first for static assets.
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
