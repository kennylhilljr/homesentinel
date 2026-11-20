import { render, screen, waitFor, within } from '@testing-library/react';
import App from './App';

// useDevicePolling opens an SSE stream; jsdom has no EventSource, so stub it.
class MockEventSource {
  static instances = [];
  constructor(url) {
    this.url = url;
    this.listeners = {};
    this.onerror = null;
    this.closed = false;
    MockEventSource.instances.push(this);
  }
  addEventListener(type, cb) {
    (this.listeners[type] ||= []).push(cb);
  }
  removeEventListener(type, cb) {
    this.listeners[type] = (this.listeners[type] || []).filter((l) => l !== cb);
  }
  close() {
    this.closed = true;
  }
}

const jsonResponse = (body, ok = true) => ({ ok, status: ok ? 200 : 500, json: async () => body });

/**
 * Route fetch calls by path. `overrides` maps an API path (e.g. '/health') to
 * a response object, an Error (rejects), or a function returning either.
 * Unlisted endpoints get a benign empty payload.
 */
const mockApi = (overrides = {}) => {
  const defaults = {
    '/health': jsonResponse({ status: 'healthy', service: 'HomeSentinel Backend' }),
    '/devices': jsonResponse({ devices: [], total: 0 }),
    '/device-groups': jsonResponse({ groups: [] }),
    '/events/alerts?limit=10': jsonResponse({ alerts: [] }),
    '/events/alerts/unseen': jsonResponse([]),
    '/speedtest/insights': jsonResponse([]),
  };
  global.fetch = vi.fn(async (url) => {
    const path = String(url).replace(/^.*?\/api(?=\/)/, '');
    let entry = path in overrides ? overrides[path] : defaults[path];
    if (typeof entry === 'function') entry = entry();
    if (entry instanceof Error) throw entry;
    return entry || jsonResponse({}, false);
  });
};

describe('App Component', () => {
  beforeEach(() => {
    localStorage.clear();
    MockEventSource.instances = [];
    vi.stubGlobal('EventSource', MockEventSource);
    mockApi();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  test('renders without crashing', async () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1, name: 'HomeSentinel' })).toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalled());
  });

  test('renders title and subtitle', async () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1, name: 'HomeSentinel' })).toBeInTheDocument();
    expect(screen.getByText('Network Monitor & Device Management')).toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalled());
  });

  test('calls API health endpoint on mount', async () => {
    render(<App />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/health',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
  });

  test('calls API devices endpoint on mount', async () => {
    render(<App />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/devices',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
  });

  test('opens an SSE stream for live device updates', async () => {
    render(<App />);
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    expect(MockEventSource.instances[0].url).toBe('/api/sse/events');
    expect(MockEventSource.instances[0].listeners.device_update).toHaveLength(1);
  });

  test('displays API status as "connected" when health check succeeds', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/connected/i)).toBeInTheDocument();
    });
  });

  test('displays API status as "disconnected" when health check fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    mockApi({ '/health': new Error('Network error'), '/devices': new Error('Network error') });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/disconnected/i)).toBeInTheDocument();
    });
  });

  test('displays empty devices list initially', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/No devices discovered yet/i)).toBeInTheDocument();
    });
  });

  test('handles API error gracefully', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    mockApi({ '/devices': new Error('Failed to fetch') });

    // Should not throw
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/No devices discovered yet/i)).toBeInTheDocument();
    });
  });

  test('handles malformed API response', async () => {
    mockApi({ '/devices': jsonResponse({}) }); // Missing devices field

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/No devices discovered yet/i)).toBeInTheDocument();
    });
  });

  test('renders device items when devices are returned', async () => {
    mockApi({
      '/devices': jsonResponse({
        devices: [
          { device_id: 'd1', friendly_name: 'Router', mac_address: '00:11:22:33:44:55', status: 'online' },
          { device_id: 'd2', friendly_name: 'Camera', mac_address: '00:11:22:33:44:66', status: 'online' },
        ],
        total: 2,
      }),
    });

    render(<App />);

    const table = await screen.findByRole('table');
    expect(await within(table).findByText('Router')).toBeInTheDocument();
    expect(within(table).getByText('Camera')).toBeInTheDocument();
    expect(screen.queryByText(/No devices discovered yet/i)).not.toBeInTheDocument();
  });

  test('displays backend URL information', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/https:\/\/localhost:8443/i)).toBeInTheDocument();
      expect(screen.getByText(/http:\/\/localhost:2026/i)).toBeInTheDocument();
    });
  });

  test('no console errors on initial render', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<App />);

    expect(screen.getByRole('heading', { level: 1, name: 'HomeSentinel' })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/No devices discovered yet/i)).toBeInTheDocument();
    });
    await waitFor(() => expect(screen.getByText('Connected')).toBeInTheDocument());

    expect(consoleSpy).not.toHaveBeenCalled();
  });
});
