import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolveDevServerHost } from '../devServerHost.mjs';

test('defaults to 127.0.0.1', () => {
  assert.equal(resolveDevServerHost({}), '127.0.0.1');
});

test('accepts loopback hosts', () => {
  assert.equal(resolveDevServerHost({ HOMESENTINEL_FRONTEND_HOST: 'localhost' }), 'localhost');
  assert.equal(resolveDevServerHost({ HOMESENTINEL_FRONTEND_HOST: '::1' }), '::1');
});

test('refuses non-loopback hosts without the override', () => {
  assert.throws(() => resolveDevServerHost({ HOMESENTINEL_FRONTEND_HOST: '0.0.0.0' }));
  assert.throws(() => resolveDevServerHost({ HOMESENTINEL_FRONTEND_HOST: '192.168.12.5' }));
  assert.throws(() => resolveDevServerHost({ HOMESENTINEL_FRONTEND_HOST: '0.0.0.0', HOMESENTINEL_ALLOW_INSECURE_BIND: '0' }));
});

test('allows a non-loopback host with the explicit override', () => {
  assert.equal(
    resolveDevServerHost({ HOMESENTINEL_FRONTEND_HOST: '0.0.0.0', HOMESENTINEL_ALLOW_INSECURE_BIND: '1' }),
    '0.0.0.0',
  );
});

test('vite.config.js uses the resolver and no wildcard host', () => {
  const config = readFileSync(new URL('../vite.config.js', import.meta.url), 'utf8');
  assert.ok(config.includes('resolveDevServerHost(process.env)'));
  assert.ok(!config.includes("'0.0.0.0'"));
});

test('npm test runs this file', () => {
  const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
  assert.ok(pkg.scripts.test.includes('node --test tests/devServerHost.test.mjs'));
});
