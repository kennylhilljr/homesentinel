import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import DecoWiFiConfigEditor, { WIFI_CHANGES_UNSUPPORTED_MESSAGE } from './DecoWiFiConfigEditor';

// Mock apiConfig module
vi.mock('../utils/apiConfig', () => ({
  buildUrl: vi.fn((endpoint) => `/api${endpoint}`),
  __esModule: true,
}));

// Mock fetch
global.fetch = vi.fn();

const UNSUPPORTED_MESSAGE = "WiFi changes aren't supported yet; change them in the Deco app";

describe('DecoWiFiConfigEditor Component (read-only)', () => {
  const mockWiFiConfig = {
    ssid: 'TestNetwork',
    band_steering_enabled: true,
    timestamp: '2026-03-06T12:00:00Z',
    cache_info: {
      ttl_seconds: 60,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    fetch.mockResolvedValue({
      ok: true,
      json: async () => mockWiFiConfig,
    });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  const expectOnlyGetRequests = () => {
    expect(fetch).toHaveBeenCalled();
    for (const [url, opts] of fetch.mock.calls) {
      expect(url).toBe('/api/deco/wifi-config');
      expect(opts?.method ?? 'GET').toBe('GET');
    }
  };

  test('test_editor_shows_loading_state_on_mount', () => {
    fetch.mockImplementation(() => new Promise(() => {}));

    const { container } = render(<DecoWiFiConfigEditor />);

    expect(container.querySelector('.editor-loading')).toBeInTheDocument();
  });

  test('test_message_constant_matches_backend_message', () => {
    expect(WIFI_CHANGES_UNSUPPORTED_MESSAGE).toBe(UNSUPPORTED_MESSAGE);
  });

  test('test_editor_shows_current_ssid_read_only', async () => {
    render(<DecoWiFiConfigEditor />);

    expect(await screen.findByText('TestNetwork')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('TestNetwork')).not.toBeInTheDocument();
  });

  test('test_editor_shows_band_steering_read_only', async () => {
    render(<DecoWiFiConfigEditor />);

    expect(await screen.findByText('Enabled')).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  test('test_editor_shows_disabled_band_steering', async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ...mockWiFiConfig, band_steering_enabled: false }),
    });

    render(<DecoWiFiConfigEditor />);

    expect(await screen.findByText('Disabled')).toBeInTheDocument();
  });

  test('test_editor_shows_unknown_when_ssid_missing', async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({}) });

    render(<DecoWiFiConfigEditor />);

    expect(await screen.findByText('Unknown')).toBeInTheDocument();
  });

  test('test_editor_shows_unsupported_message', async () => {
    render(<DecoWiFiConfigEditor />);

    expect(await screen.findByText(UNSUPPORTED_MESSAGE)).toBeInTheDocument();
  });

  test('test_editor_has_no_save_action_or_password_field', async () => {
    const { container } = render(<DecoWiFiConfigEditor />);
    await screen.findByText('TestNetwork');

    expect(
      screen.queryByRole('button', { name: /update|save|apply/i })
    ).not.toBeInTheDocument();
    expect(container.querySelector('form')).not.toBeInTheDocument();
    expect(container.querySelector('input')).not.toBeInTheDocument();
    expect(container.querySelector('.dialog-overlay')).not.toBeInTheDocument();
  });

  test('test_editor_never_sends_put', async () => {
    render(<DecoWiFiConfigEditor />);
    await screen.findByText('TestNetwork');

    fireEvent.click(screen.getByRole('button', { name: /Refresh/i }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));

    expectOnlyGetRequests();
  });

  test('test_refresh_reloads_config', async () => {
    render(<DecoWiFiConfigEditor />);
    await screen.findByText('TestNetwork');

    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ...mockWiFiConfig, ssid: 'RenamedInDecoApp' }),
    });
    fireEvent.click(screen.getByRole('button', { name: /Refresh/i }));

    expect(await screen.findByText('RenamedInDecoApp')).toBeInTheDocument();
  });

  test('test_error_message_displays_on_load_failure', async () => {
    fetch.mockResolvedValue({ ok: false, statusText: 'Internal Server Error' });

    render(<DecoWiFiConfigEditor />);

    expect(
      await screen.findByText(/Failed to load current WiFi configuration: .*Internal Server Error/)
    ).toBeInTheDocument();
    expect(screen.getByText(UNSUPPORTED_MESSAGE)).toBeInTheDocument();
  });
});
