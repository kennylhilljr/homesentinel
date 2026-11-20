/**
 * Dashboard API-key auth.
 *
 * When the backend has HOMESENTINEL_API_KEY set, every /api request needs an
 * X-API-Key header. The key is entered once in the dashboard (ApiKeyPrompt) and
 * kept in this browser's localStorage. installApiAuth() wraps window.fetch so
 * existing call sites send the header without each one being changed. The key is
 * only attached to requests for the API base, and never put in a URL.
 *
 * With no key stored (loopback dev with auth off) requests are sent unchanged.
 */
import { getApiUrl } from './apiConfig';

const STORAGE_KEY = 'hs_api_key';
export const AUTH_REQUIRED_EVENT = 'homesentinel:auth-required';

export function getApiKey() {
  try {
    return localStorage.getItem(STORAGE_KEY) || '';
  } catch (e) {
    return '';
  }
}

export function setApiKey(key) {
  const value = (key || '').trim();
  if (value) localStorage.setItem(STORAGE_KEY, value);
  else localStorage.removeItem(STORAGE_KEY);
}

export function clearApiKey() {
  localStorage.removeItem(STORAGE_KEY);
}

function requestUrl(input) {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.href;
  return input && input.url;
}

/** True when url points at the HomeSentinel API (same origin + path prefix as getApiUrl()). */
export function isApiRequest(url) {
  if (!url) return false;
  try {
    const base = new URL(getApiUrl(), window.location.href);
    const target = new URL(url, window.location.href);
    const prefix = base.pathname.replace(/\/+$/, '');
    return target.origin === base.origin
      && (target.pathname === prefix || target.pathname.startsWith(`${prefix}/`));
  } catch (e) {
    return false;
  }
}

/** Wrap target.fetch so API requests carry X-API-Key and 401s raise AUTH_REQUIRED_EVENT. */
export function installApiAuth(target = window) {
  if (!target.fetch || target.fetch.hsApiAuth) return;
  const originalFetch = target.fetch.bind(target);

  const authFetch = async (input, init) => {
    if (!isApiRequest(requestUrl(input))) return originalFetch(input, init);

    const key = getApiKey();
    let nextInit = init;
    if (key) {
      const isRequest = typeof Request !== 'undefined' && input instanceof Request;
      const headers = new Headers((init && init.headers) || (isRequest ? input.headers : undefined));
      if (!headers.has('X-API-Key')) headers.set('X-API-Key', key);
      nextInit = { ...(init || {}), headers };
    }

    const response = await originalFetch(input, nextInit);
    if (response && response.status === 401) {
      target.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT, { detail: { hadKey: Boolean(key) } }));
    }
    return response;
  };

  authFetch.hsApiAuth = true;
  target.fetch = authFetch;
}
