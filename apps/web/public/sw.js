/*
 * Service worker — makes the app installable and opens instantly on a phone.
 *
 * Rules (control-system safety):
 *  - NEVER cache /api, /ws or /health: live state and commands always hit the network.
 *  - Map images, icons and fonts: cache-first (they never change for a given file name).
 *  - App shell (HTML/JS/CSS): network-first with cached fallback, so a deploy is
 *    picked up immediately but the shell still opens when the farm link is down
 *    (the app then shows OFFLINE instead of a browser error page).
 */
const VERSION = 'v1';
const SHELL = `shell-${VERSION}`;
const ASSETS = `assets-${VERSION}`;

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(['/', '/manifest.webmanifest'])));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => ![SHELL, ASSETS].includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/ws') || url.pathname.startsWith('/health')) return;

  const isAsset =
    url.pathname.startsWith('/map/') || url.pathname.startsWith('/icons/') || /\.(woff2?|webp|png|svg)$/.test(url.pathname);

  if (isAsset) {
    event.respondWith(
      caches.open(ASSETS).then(async (cache) => {
        const hit = await cache.match(req);
        if (hit) return hit;
        const res = await fetch(req);
        if (res.ok) cache.put(req, res.clone());
        return res;
      }),
    );
    return;
  }

  // shell: network first, fall back to cache (SPA routes fall back to "/")
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) caches.open(SHELL).then((c) => c.put(req, res.clone()));
        return res;
      })
      .catch(async () => (await caches.match(req)) || (req.mode === 'navigate' ? caches.match('/') : Response.error())),
  );
});
