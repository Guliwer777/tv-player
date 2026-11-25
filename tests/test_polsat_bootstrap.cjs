const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const vm = require('node:vm');

const generator = `
import json, sys
sys.path.insert(0, "tests")
from test_polsat import account, record
print(json.dumps([account.bootstrap(record(), reuse_live_session=True), account.bootstrap(record())]))
`;
const [firstOpen, fallback] = JSON.parse(execFileSync(process.env.PYTHON || 'python', ['-B', '-c', generator], {
  cwd: path.resolve(__dirname, '..'), encoding: 'utf8'
}));

function load(script, cookies, options = {}) {
  let reloads = 0;
  const writes = new Map();
  const listeners = new Map();
  const storage = options.storage || new Map();
  const location = {
    origin: options.origin || 'https://polsatboxgo.pl',
    pathname: options.path || '/kanaly-tv/test/1/ogladaj',
    search: options.search || '',
    reload() { reloads++; }
  };
  const document = {
    readyState: options.loading ? 'loading' : 'complete',
    addEventListener: (event, listener) => listeners.set(event, listener),
    get cookie() { return cookies.join('; '); },
    set cookie(line) {
      const pair = line.split(';')[0];
      writes.set(pair.slice(0, pair.indexOf('=')), pair);
    }
  };
  const window = {};
  window.top = options.inFrame ? {} : window;
  vm.runInNewContext(script, {
    location, document, window, URLSearchParams, setTimeout: fn => fn(),
    sessionStorage: {getItem: key => storage.get(key), setItem: (key, val) => storage.set(key, val)}
  });
  return {get reloads() { return reloads; }, writes, listeners};
}

const initial = load(firstOpen, []);
assert.equal(initial.reloads, 1);
const matching = [...initial.writes.values()].filter(pair => !pair.startsWith('profile-selected-at='));
assert.equal(matching.length, 3);
assert.equal(load(firstOpen, matching).reloads, 0);
for (const name of ['user-session', 'profile-id', 'user-recognition']) {
  const without = matching.filter(pair => !pair.startsWith(name + '='));
  assert.equal(load(firstOpen, without).reloads, 1);
  assert.equal(load(firstOpen, [...without, name + '=changed']).reloads, 1);
  assert.equal(load(firstOpen, [...matching, name + '=duplicate']).reloads, 1);
}
// The normal retry still reloads an authenticated page once, even when cookies match.
const storage = new Map();
assert.equal(load(fallback, matching, {storage}).reloads, 1);
assert.equal(load(fallback, matching, {storage}).reloads, 0);
const cold = load(firstOpen, [], {loading: true});
assert.equal(cold.reloads, 1);
assert.equal(cold.writes.size, 4);
const retry = load(fallback, matching, {loading: true});
assert.equal(retry.reloads, 0);
retry.listeners.get('DOMContentLoaded')();
assert.equal(retry.reloads, 1);
assert.equal(load(firstOpen, matching, {path: '/wideo/serial'}).reloads, 1);
assert.equal(load(firstOpen, matching, {search: '?tvpStartOver='}).reloads, 1);
assert.equal(load(firstOpen, matching, {inFrame: true}).reloads, 1);
const foreign = load(firstOpen, [], {origin: 'https://example.org'});
assert.equal(foreign.writes.size, 0);
assert.equal(foreign.reloads, 0);
console.log('Polsat first-open and fallback bootstrap: OK');
