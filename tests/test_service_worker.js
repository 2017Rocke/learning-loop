'use strict';
// Execute the real service worker against an in-memory Cache/Fetch interface.
// This checks offline routing; installation on real phone browsers is separate QA.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

(async () => {
  const scope = 'https://example.test/learning-loop/';
  const listeners = {};
  const stores = new Map();
  let online = true;
  const caches = {
    async open(name) {
      if (!stores.has(name)) stores.set(name, new Map());
      const entries = stores.get(name);
      return {
        async put(key, response) { entries.set(String(key), response.clone()); },
        async match(key) { return entries.get(String(key))?.clone(); }
      };
    },
    async keys() { return [...stores.keys()]; },
    async delete(name) { return stores.delete(name); }
  };
  const source = fs.readFileSync(path.join(__dirname, '../web/mobile/sw.js'), 'utf8')
    .replace('__CACHE_VERSION__', '"test-v1"')
    .replace('__PRECACHE_URLS__', JSON.stringify(['./', './index.html', './courses.json', './media/test.m4a']));
  const sandbox = {
    URL, Response, Headers, caches,
    fetch: async resource => {
      if (!online) throw new Error('offline');
      const url = typeof resource === 'string' ? resource : resource.url;
      assert.ok(url.startsWith(scope), 'never fetch outside deployment subpath');
      if (url.endsWith('.m4a')) return new Response(Uint8Array.from([0, 1, 2, 3, 4, 5]), {headers:{'Content-Type':'audio/mp4'}});
      return new Response(url.endsWith('courses.json') ? '{"courses":[]}' : '<main>Learning Loop</main>');
    },
    self: {registration:{scope}, addEventListener:(type, callback)=>{listeners[type]=callback;},
      skipWaiting: async()=>{}, clients:{claim:async()=>{}}}
  };
  vm.runInNewContext(source, sandbox);
  const life = async type => { let work; listeners[type]({waitUntil(promise){work=promise;}}); await work; };
  const request = async (pathname, headers={}, mode='cors') => {
    let work;
    listeners.fetch({request:{url:new URL(pathname, scope).href, method:'GET', mode, headers:new Headers(headers)},
      respondWith(promise){work=promise;}});
    return work ? await work : null;
  };
  await caches.open('zhixing-mobile:/other/:old');
  await caches.open('zhixing-mobile:/learning-loop/:old');
  await life('install');
  await life('activate');
  assert.ok(stores.has('zhixing-mobile:/other/:old'), 'other sites keep their offline caches');
  assert.ok(!stores.has('zhixing-mobile:/learning-loop/:old'), 'this site removes stale caches');
  online = false;
  assert.equal(await (await request('courses.json')).text(), '{"courses":[]}');
  assert.match(await (await request('', {}, 'navigate')).text(), /Learning Loop/);
  const range = await request('media/test.m4a', {Range:'bytes=2-4'});
  assert.equal(range.status, 206);
  assert.equal(range.headers.get('Content-Range'), 'bytes 2-4/6');
  assert.deepEqual([...new Uint8Array(await range.arrayBuffer())], [2, 3, 4]);
  const suffix = await request('media/test.m4a', {Range:'bytes=-2'});
  assert.deepEqual([...new Uint8Array(await suffix.arrayBuffer())], [4, 5]);
  assert.equal((await request('media/test.m4a', {Range:'bytes=100-'})).status, 416);
  assert.equal(await request('/api/state'), null, 'never intercept the private authoring API');
  assert.equal(await request('/other/index.html'), null);
  assert.equal(await request('unknown.json'), null);
  console.log('Service worker checks passed: offline subpath, audio seek, invalid range, cache isolation.');
})().catch(error => { console.error(error); process.exitCode = 1; });
