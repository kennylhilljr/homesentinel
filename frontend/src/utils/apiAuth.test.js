import { vi } from 'vitest';
import {
  AUTH_REQUIRED_EVENT, clearApiKey, getApiKey, installApiAuth, isApiRequest, setApiKey,
} from './apiAuth';

function fakeWindow(status = 200) {
  const target = new EventTarget();
  target.fetch = vi.fn(() => Promise.resolve({ ok: status < 400, status }));
  return target;
}

describe('apiAuth', () => {
  afterEach(() => clearApiKey());

  test('stores, trims and clears the key', () => {
    expect(getApiKey()).toBe('');
    setApiKey('  abc  ');
    expect(getApiKey()).toBe('abc');
    setApiKey('   ');
    expect(getApiKey()).toBe('');
  });

  test('isApiRequest matches only the same-origin /api prefix', () => {
    expect(isApiRequest('/api/devices')).toBe(true);
    expect(isApiRequest('/api')).toBe(true);
    expect(isApiRequest(`${window.location.origin}/api/health`)).toBe(true);
    expect(isApiRequest('/apix/devices')).toBe(false);
    expect(isApiRequest('/assets/app.js')).toBe(false);
    expect(isApiRequest('https://evil.example/api/devices')).toBe(false);
    expect(isApiRequest(undefined)).toBe(false);
  });

  test('without a stored key, requests pass through unchanged (loopback dev)', async () => {
    const target = fakeWindow();
    const original = target.fetch;
    installApiAuth(target);
    const init = { method: 'POST' };
    await target.fetch('/api/devices', init);
    expect(original).toHaveBeenCalledWith('/api/devices', init);
  });

  test('adds X-API-Key to API requests and keeps existing headers', async () => {
    setApiKey('secret-value');
    const target = fakeWindow();
    const original = target.fetch;
    installApiAuth(target);
    await target.fetch('/api/events/alerts/mark-seen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const [url, init] = original.mock.calls[0];
    expect(url).toBe('/api/events/alerts/mark-seen');
    expect(url).not.toContain('secret-value');
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{}');
    const headers = new Headers(init.headers);
    expect(headers.get('X-API-Key')).toBe('secret-value');
    expect(headers.get('Content-Type')).toBe('application/json');
  });

  test('handles Request and URL inputs', async () => {
    setApiKey('k1');
    const target = fakeWindow();
    const original = target.fetch;
    installApiAuth(target);
    await target.fetch(new Request(`${window.location.origin}/api/devices`, { headers: { Accept: 'application/json' } }));
    await target.fetch(new URL('/api/health', window.location.origin));
    const first = new Headers(original.mock.calls[0][1].headers);
    expect(first.get('X-API-Key')).toBe('k1');
    expect(first.get('Accept')).toBe('application/json');
    expect(new Headers(original.mock.calls[1][1].headers).get('X-API-Key')).toBe('k1');
  });

  test('never sends the key to other origins or non-API paths', async () => {
    setApiKey('k2');
    const target = fakeWindow();
    const original = target.fetch;
    installApiAuth(target);
    await target.fetch('https://evil.example/api/devices', {});
    await target.fetch('/favicon.ico');
    expect(original.mock.calls[0][1]).toEqual({});
    expect(original.mock.calls[1][1]).toBeUndefined();
  });

  test('does not override an explicit X-API-Key header', async () => {
    setApiKey('stored');
    const target = fakeWindow();
    const original = target.fetch;
    installApiAuth(target);
    await target.fetch('/api/x', { headers: { 'X-API-Key': 'explicit' } });
    expect(new Headers(original.mock.calls[0][1].headers).get('X-API-Key')).toBe('explicit');
  });

  test('a 401 on an API request raises the auth-required event', async () => {
    setApiKey('bad');
    const target = fakeWindow(401);
    installApiAuth(target);
    const seen = [];
    target.addEventListener(AUTH_REQUIRED_EVENT, (event) => seen.push(event.detail));
    const response = await target.fetch('/api/devices');
    expect(response.status).toBe(401);
    expect(seen).toEqual([{ hadKey: true }]);
  });

  test('installing twice does not double-wrap', () => {
    const target = fakeWindow();
    installApiAuth(target);
    const wrapped = target.fetch;
    installApiAuth(target);
    expect(target.fetch).toBe(wrapped);
  });
});
