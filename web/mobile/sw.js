'use strict';
// scripts/build_site.py replaces these values with the build digest and relative asset URLs.
const VERSION = __CACHE_VERSION__;
const PRECACHE = __PRECACHE_URLS__;
const SCOPE = new URL(self.registration.scope);
const PREFIX = `zhixing-mobile:${SCOPE.pathname}:`;
const CACHE_NAME = `${PREFIX}${VERSION}`;
const ownURL = path => new URL(path, SCOPE).href;
const allowed = new Set(PRECACHE.map(ownURL));
const withinScope = url => url.origin === SCOPE.origin && url.pathname.startsWith(SCOPE.pathname);

self.addEventListener('install', event => event.waitUntil((async () => {
  const cache = await caches.open(CACHE_NAME);
  // Sequential requests avoid loading every video and lesson audio into memory together.
  for (const asset of PRECACHE) {
    const url = ownURL(asset);
    if (!withinScope(new URL(url))) throw new Error('Asset outside app scope');
    const response = await fetch(url, { cache: 'reload' });
    if (!response.ok || response.status === 206) throw new Error(`Unable to cache ${asset}`);
    await cache.put(url, response);
  }
  // Updates remain waiting until the learner saves their work and requests a reload.
})()));
self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') event.waitUntil(self.skipWaiting());
});
self.addEventListener('activate', event => event.waitUntil((async () => {
  for (const name of await caches.keys()) if (name.startsWith(PREFIX) && name !== CACHE_NAME) await caches.delete(name);
  await self.clients.claim();
})()));
async function rangedResponse(request, cached) {
  const header = request.headers.get('Range');
  if (!header) return cached;
  const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  const bytes = await cached.arrayBuffer(); const length = bytes.byteLength;
  const badRange = () => new Response(null, { status: 416, headers: { 'Content-Range': `bytes */${length}`, 'Accept-Ranges': 'bytes' } });
  if (!match || (!match[1] && !match[2]) || length === 0) return badRange();
  let start; let end;
  if (!match[1]) { const suffix = Number(match[2]); if (!Number.isSafeInteger(suffix) || suffix <= 0) return badRange(); start = Math.max(0, length - suffix); end = length - 1; }
  else { start = Number(match[1]); end = match[2] ? Number(match[2]) : length - 1; }
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || start >= length || end < start) return badRange();
  end = Math.min(end, length - 1);
  const headers = new Headers(cached.headers); headers.set('Content-Range', `bytes ${start}-${end}/${length}`); headers.set('Content-Length', String(end - start + 1)); headers.set('Accept-Ranges', 'bytes'); headers.delete('Content-Encoding');
  return new Response(bytes.slice(start, end + 1), { status: 206, statusText: 'Partial Content', headers });
}
self.addEventListener('fetch', event => {
  const request = event.request; const url = new URL(request.url);
  if (request.method !== 'GET' || !withinScope(url)) return;
  const key = new URL(url); key.search = ''; key.hash = '';
  const navigation = request.mode === 'navigate';
  if (!navigation && !allowed.has(key.href)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    // The complete build is one unit: never mix a new course JSON with old audio.
    const cached = await cache.match(key.href) || (navigation ? await cache.match(ownURL('index.html')) : null);
    if (cached) return rangedResponse(request, cached);
    try { const response = await fetch(request); if (response.ok && response.status !== 206 && allowed.has(key.href)) await cache.put(key.href, response.clone()); return response; }
    catch { return new Response('此内容尚未保存到设备。请联网打开一次，再离线学习。', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } }); }
  })());
});
