/**
 * Authenticated SSE connection.
 *
 * EventSource can't send headers, so when the backend requires an API key the
 * stream is opened with a short-lived, single-use token from POST /api/sse/token
 * (that request carries X-API-Key via the fetch wrapper). The long-lived key is
 * never placed in the URL. Tokens are single-use, so instead of EventSource's
 * built-in retry (which would reuse a spent token) every error closes the stream
 * and reconnects with a fresh token, backing off up to maxRetryMs.
 */
import { buildUrl } from './apiConfig';

/** Resolve the URL to open, or null when the server rejects our credentials. */
export async function getEventStreamUrl(path = '/sse/events') {
  const url = buildUrl(path);
  try {
    const response = await fetch(buildUrl('/sse/token'), { method: 'POST' });
    if (response.status === 401) return null;
    // Older backend without the token route (auth off): connect directly.
    if (!response.ok) return url;
    const { token } = await response.json();
    return token ? `${url}?token=${encodeURIComponent(token)}` : url;
  } catch (e) {
    return null; // backend unreachable; caller retries
  }
}

/**
 * Open the SSE stream and keep it open. listeners maps event names to handlers.
 * Returns a function that closes the stream and stops reconnecting.
 */
export function openEventStream(listeners, {
  path = '/sse/events',
  EventSourceImpl = typeof EventSource !== 'undefined' ? EventSource : undefined,
  initialRetryMs = 2000,
  maxRetryMs = 60000,
} = {}) {
  if (!EventSourceImpl) return () => {};

  let closed = false;
  let source = null;
  let timer = null;
  let retryMs = initialRetryMs;

  const scheduleReconnect = () => {
    if (closed) return;
    timer = setTimeout(connect, retryMs);
    retryMs = Math.min(retryMs * 2, maxRetryMs);
  };

  async function connect() {
    timer = null;
    const url = await getEventStreamUrl(path);
    if (closed) return;
    if (!url) {
      scheduleReconnect();
      return;
    }
    source = new EventSourceImpl(url);
    source.addEventListener('connected', () => { retryMs = initialRetryMs; });
    for (const [name, handler] of Object.entries(listeners)) {
      source.addEventListener(name, handler);
    }
    source.onerror = () => {
      console.warn('SSE: connection lost, relying on polling fallback');
      if (source) source.close();
      source = null;
      scheduleReconnect();
    };
  }

  connect();

  return () => {
    closed = true;
    if (timer) clearTimeout(timer);
    if (source) source.close();
    source = null;
  };
}
