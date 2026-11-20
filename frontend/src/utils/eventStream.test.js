import { vi } from 'vitest';
import { getEventStreamUrl, openEventStream } from './eventStream';

class FakeEventSource {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.listeners = {};
    this.closed = false;
    FakeEventSource.instances.push(this);
  }

  addEventListener(name, handler) {
    (this.listeners[name] ||= []).push(handler);
  }

  emit(name) {
    (this.listeners[name] || []).forEach((handler) => handler({ data: '{}' }));
  }

  close() {
    this.closed = true;
  }
}

const json = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('eventStream', () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  test('auth off: connects to the plain stream URL', async () => {
    global.fetch = vi.fn(() => json(200, { token: null, expires_in: null }));
    expect(await getEventStreamUrl()).toBe('/api/sse/events');
    expect(global.fetch).toHaveBeenCalledWith('/api/sse/token', { method: 'POST' });
  });

  test('auth on: appends the one-time token, never the API key', async () => {
    global.fetch = vi.fn(() => json(200, { token: '123.n o.sig', expires_in: 60 }));
    expect(await getEventStreamUrl()).toBe('/api/sse/events?token=123.n%20o.sig');
  });

  test('rejected credentials or an unreachable backend give no URL', async () => {
    global.fetch = vi.fn(() => json(401, {}));
    expect(await getEventStreamUrl()).toBeNull();
    global.fetch = vi.fn(() => Promise.reject(new TypeError('network')));
    expect(await getEventStreamUrl()).toBeNull();
  });

  test('backend without the token route: falls back to the plain URL', async () => {
    global.fetch = vi.fn(() => json(404, {}));
    expect(await getEventStreamUrl()).toBe('/api/sse/events');
  });

  test('wires listeners and reconnects with a fresh token after an error', async () => {
    vi.useFakeTimers();
    let n = 0;
    global.fetch = vi.fn(() => json(200, { token: `t${++n}`, expires_in: 60 }));
    const onUpdate = vi.fn();
    const close = openEventStream({ device_update: onUpdate }, { EventSourceImpl: FakeEventSource, initialRetryMs: 1000 });
    await vi.advanceTimersByTimeAsync(0);

    expect(FakeEventSource.instances).toHaveLength(1);
    const first = FakeEventSource.instances[0];
    expect(first.url).toBe('/api/sse/events?token=t1');
    first.emit('device_update');
    expect(onUpdate).toHaveBeenCalledTimes(1);

    first.onerror();
    expect(first.closed).toBe(true);
    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(FakeEventSource.instances[1].url).toBe('/api/sse/events?token=t2');

    close();
    expect(FakeEventSource.instances[1].closed).toBe(true);
  });

  test('backs off while unauthorized and stops after close', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn(() => json(401, {}));
    const close = openEventStream({}, { EventSourceImpl: FakeEventSource, initialRetryMs: 1000, maxRetryMs: 4000 });
    await vi.advanceTimersByTimeAsync(0);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(global.fetch).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1999);
    expect(global.fetch).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(global.fetch).toHaveBeenCalledTimes(3);
    close();
    await vi.advanceTimersByTimeAsync(60000);
    expect(global.fetch).toHaveBeenCalledTimes(3);
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  test('close before the token arrives opens nothing', async () => {
    global.fetch = vi.fn(() => json(200, { token: 't', expires_in: 60 }));
    const close = openEventStream({}, { EventSourceImpl: FakeEventSource });
    close();
    await flush();
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  test('no EventSource support is a no-op', () => {
    global.fetch = vi.fn();
    const close = openEventStream({}, { EventSourceImpl: undefined });
    close();
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
