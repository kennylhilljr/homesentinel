import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import DecoWiFiQoSView from './DecoWiFiQoSView';
import * as apiConfig from '../utils/apiConfig';

// Mock apiConfig module
jest.mock('../utils/apiConfig', () => ({
  buildUrl: jest.fn((endpoint) => `/api${endpoint}`),
}));

// Mock fetch
global.fetch = jest.fn();

describe('DecoWiFiQoSView Component', () => {
  const mockWiFiConfig = {
    ssid: 'TestNetwork',
    bands: ['2.4 GHz', '5 GHz'],
    channel_2_4ghz: '6',
    channel_5ghz: '36',
    channel_6ghz: null,
    band_steering_enabled: true,
    timestamp: '2026-03-06T12:00:00Z',
    cache_info: {
      ttl_seconds: 60,
    },
  };

  const mockQoSSettings = {
    qos_enabled: true,
    devices: [
      {
        device_name: 'iPhone',
        mac_address: '00:11:22:33:44:55',
        ip_address: '192.168.1.100',
        priority: 'Normal',
        bandwidth_limit_mbps: null,
        connection_type: 'WiFi',
      },
      {
        device_name: 'Desktop PC',
        mac_address: '00:11:22:33:44:66',
        ip_address: '192.168.1.101',
        priority: 'High',
        bandwidth_limit_mbps: 100,
        connection_type: 'Wired',
      },
    ],
    total_devices: 2,
    timestamp: '2026-03-06T12:00:00Z',
    cache_info: {
      ttl_seconds: 60,
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  test('test_wifi_qos_view_renders', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView refreshInterval={60000} />);

    await waitFor(() => {
      expect(screen.getByText('WiFi Configuration')).toBeInTheDocument();
      expect(screen.getByText('QoS Settings & Device Bandwidth')).toBeInTheDocument();
    });
  });

  test('test_wifi_config_displays_ssid', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('TestNetwork')).toBeInTheDocument();
    });
  });

  test('test_wifi_config_displays_bands', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('2.4 GHz')).toBeInTheDocument();
      expect(screen.getByText('5 GHz')).toBeInTheDocument();
    });
  });

  test('test_wifi_config_displays_channels', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('6')).toBeInTheDocument();
      expect(screen.getByText('36')).toBeInTheDocument();
    });
  });

  test('test_qos_table_displays_devices', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('iPhone')).toBeInTheDocument();
      expect(screen.getByText('Desktop PC')).toBeInTheDocument();
    });
  });

  test('test_qos_table_displays_mac_addresses', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('00:11:22:33:44:55')).toBeInTheDocument();
      expect(screen.getByText('00:11:22:33:44:66')).toBeInTheDocument();
    });
  });

  test('test_qos_table_displays_ip_addresses', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('192.168.1.100')).toBeInTheDocument();
      expect(screen.getByText('192.168.1.101')).toBeInTheDocument();
    });
  });

  test('test_qos_table_displays_priority', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('Normal')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
    });
  });

  test('test_qos_table_displays_bandwidth', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('100 Mbps')).toBeInTheDocument();
      expect(screen.getByText('No limit')).toBeInTheDocument();
    });
  });

  test('test_qos_table_displays_connection_type', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      const wifiElements = screen.getAllByText('WiFi');
      expect(wifiElements.length).toBeGreaterThan(0);
      expect(screen.getByText('Wired')).toBeInTheDocument();
    });
  });

  test('test_band_steering_status_displayed', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('Enabled')).toBeInTheDocument();
    });
  });

  test('test_device_count_displayed', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('2 devices')).toBeInTheDocument();
    });
  });

  test('test_handles_api_error', async () => {
    fetch.mockRejectedValueOnce(new Error('API unavailable'));

    const { container } = render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('Error Loading Data')).toBeInTheDocument();
      expect(screen.getByText(/API unavailable/i)).toBeInTheDocument();
    });
  });

  test('test_handles_empty_devices', async () => {
    const emptyQoS = { ...mockQoSSettings, devices: [], total_devices: 0 };

    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => emptyQoS,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(screen.getByText('0 devices')).toBeInTheDocument();
      expect(screen.getByText('No connected devices')).toBeInTheDocument();
    });
  });

  test('test_displays_loading_state', () => {
    fetch.mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              ok: true,
              json: async () => mockWiFiConfig,
            });
          }, 1000);
        })
    );

    render(<DecoWiFiQoSView />);

    expect(screen.getByText('Loading WiFi and QoS settings...')).toBeInTheDocument();
  });

  test('test_makes_correct_api_calls', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockWiFiConfig,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockQoSSettings,
      });

    render(<DecoWiFiQoSView />);

    await waitFor(() => {
      expect(apiConfig.buildUrl).toHaveBeenCalledWith('/deco/wifi-config');
      expect(apiConfig.buildUrl).toHaveBeenCalledWith('/deco/qos');
      expect(fetch).toHaveBeenCalledWith('/api/deco/wifi-config', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      expect(fetch).toHaveBeenCalledWith('/api/deco/qos', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });
});
