import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import DecoTopologyView from '../DecoTopologyView';

// Mock the API
vi.mock('../../utils/apiConfig', () => ({
  buildUrl: (path) => `http://localhost:9000/api${path}`,
}));

describe('DecoTopologyView Component', () => {
  const mockTopologyData = {
    nodes: [
      {
        node_id: 'node_1',
        node_name: 'Main Node',
        mac_address: 'AA:BB:CC:DD:EE:01',
        status: 'online',
        signal_strength: 85,
        connected_clients: 3,
      },
      {
        node_id: 'node_2',
        node_name: 'Bedroom Node',
        mac_address: 'AA:BB:CC:DD:EE:02',
        status: 'online',
        signal_strength: 72,
        connected_clients: 2,
      },
    ],
    devices: [
      {
        device_id: 'device_1',
        mac_address: '11:22:33:44:55:66',
        device_name: 'iPhone',
        status: 'online',
        friendly_name: "John's iPhone",
        vendor_name: 'APPLE',
      },
      {
        device_id: 'device_2',
        mac_address: '11:22:33:44:55:77',
        device_name: 'Laptop',
        status: 'online',
        friendly_name: 'Work Laptop',
        vendor_name: 'DELL',
      },
      {
        device_id: 'device_3',
        mac_address: '11:22:33:44:55:88',
        device_name: 'Smart TV',
        status: 'online',
        friendly_name: 'Living Room TV',
        vendor_name: 'SAMSUNG',
      },
    ],
    relationships: [
      {
        device_id: 'device_1',
        device_mac: '11:22:33:44:55:66',
        node_id: 'node_1',
        node_mac: 'AA:BB:CC:DD:EE:01',
      },
      {
        device_id: 'device_2',
        device_mac: '11:22:33:44:55:77',
        node_id: 'node_1',
        node_mac: 'AA:BB:CC:DD:EE:01',
      },
      {
        device_id: 'device_3',
        device_mac: '11:22:33:44:55:88',
        node_id: 'node_2',
        node_mac: 'AA:BB:CC:DD:EE:02',
      },
    ],
    total_nodes: 2,
    total_devices: 3,
    total_relationships: 3,
    timestamp: new Date().toISOString(),
  };

  beforeEach(() => {
    fetch.resetMocks();
  });

  // stale, see #3
  test.skip('renders component with header', () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    expect(screen.getByText('Network Topology')).toBeInTheDocument();
    expect(
      screen.getByText('Visual map of Deco nodes and connected devices')
    ).toBeInTheDocument();
  });

  // stale, see #3
  test.skip('displays loading state initially', () => {
    fetch.mockResponseOnce(
      () => new Promise((resolve) => setTimeout(() => resolve(JSON.stringify(mockTopologyData)), 100))
    );

    render(<DecoTopologyView />);

    expect(screen.getByText('Loading topology...')).toBeInTheDocument();
  });

  // stale, see #3
  test.skip('fetches and displays topology data', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('Main Node')).toBeInTheDocument();
    });

    expect(screen.getByText('Bedroom Node')).toBeInTheDocument();
  });

  // stale, see #3
  test.skip('displays topology statistics', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument(); // Nodes count
      expect(screen.getByText('3')).toBeInTheDocument(); // Devices count
    });
  });

  // stale, see #3
  test.skip('renders legend with status indicators', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('Online Node')).toBeInTheDocument();
      expect(screen.getByText('Offline Node')).toBeInTheDocument();
      expect(screen.getByText('Online Device')).toBeInTheDocument();
      expect(screen.getByText('Offline Device')).toBeInTheDocument();
    });
  });

  // stale, see #3
  test.skip('renders nodes in details section', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('Main Node')).toBeInTheDocument();
      expect(screen.getByText('Bedroom Node')).toBeInTheDocument();
    });

    expect(screen.getByText('AA:BB:CC:DD:EE:01')).toBeInTheDocument();
  });

  // stale, see #3
  test.skip('renders devices in details section', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText("John's iPhone")).toBeInTheDocument();
    });

    expect(screen.getByText('Work Laptop')).toBeInTheDocument();
    expect(screen.getByText('Living Room TV')).toBeInTheDocument();
  });

  // stale, see #3
  test.skip('renders SVG canvas for topology visualization', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    const { container } = render(<DecoTopologyView />);

    await waitFor(() => {
      const svg = container.querySelector('svg.topology-svg');
      expect(svg).toBeInTheDocument();
    });
  });

  // stale, see #3
  test.skip('handles refresh button click', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('Main Node')).toBeInTheDocument();
    });

    const refreshButton = screen.getByRole('button', { name: /Refresh/i });
    fireEvent.click(refreshButton);

    expect(fetch).toHaveBeenCalledTimes(2);
  });

  // stale, see #3
  test.skip('toggles auto-refresh on checkbox change', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView autoRefreshInterval={5000} />);

    await waitFor(() => {
      expect(screen.getByText('Main Node')).toBeInTheDocument();
    });

    const autoRefreshCheckbox = screen.getByRole('checkbox', {
      name: /Auto-refresh/i,
    });

    // Uncheck auto-refresh
    fireEvent.click(autoRefreshCheckbox);
    expect(autoRefreshCheckbox).not.toBeChecked();

    // Check auto-refresh
    fireEvent.click(autoRefreshCheckbox);
    expect(autoRefreshCheckbox).toBeChecked();
  });

  // stale, see #3
  test.skip('displays error state on API failure', async () => {
    fetch.mockRejectOnce(new Error('Network error'));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('Error Loading Topology')).toBeInTheDocument();
    });
  });

  // stale, see #3
  test.skip('displays error message for unauthorized access', async () => {
    fetch.mockResponseOnce(
      JSON.stringify({ detail: 'Not authenticated with Deco API' }),
      { status: 401 }
    );

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(
        screen.getByText('Error Loading Topology')
      ).toBeInTheDocument();
    });
  });

  // stale, see #3
  test.skip('displays empty state when no nodes', async () => {
    fetch.mockResponseOnce(
      JSON.stringify({
        nodes: [],
        devices: [],
        relationships: [],
        total_nodes: 0,
        total_devices: 0,
        total_relationships: 0,
        timestamp: new Date().toISOString(),
      })
    );

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('No Topology Data Available')).toBeInTheDocument();
    });
  });

  // stale, see #3
  test.skip('displays device status indicators', async () => {
    const topologyWithOffline = {
      ...mockTopologyData,
      devices: [
        ...mockTopologyData.devices,
        {
          device_id: 'device_4',
          mac_address: '11:22:33:44:55:99',
          device_name: 'Old Device',
          status: 'offline',
          friendly_name: 'Old Device',
          vendor_name: 'UNKNOWN',
        },
      ],
    };

    fetch.mockResponseOnce(JSON.stringify(topologyWithOffline));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('Old Device')).toBeInTheDocument();
    });

    // Check that offline badge is displayed
    const offlineBadges = screen.getAllByText(/● Offline/);
    expect(offlineBadges.length).toBeGreaterThan(0);
  });

  // stale, see #3
  test.skip('updates last refresh time', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('Main Node')).toBeInTheDocument();
    });

    const lastRefresh = screen.getByText(/Last updated:/);
    expect(lastRefresh).toBeInTheDocument();
    expect(lastRefresh.textContent).toContain('ago');
  });

  // stale, see #3
  test.skip('renders retry button on error', async () => {
    fetch.mockRejectOnce(new Error('API Error'));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
    });
  });

  // stale, see #3
  test.skip('fetches from correct API endpoint', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:9000/api/deco/topology',
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });
  });

  // stale, see #3
  test.skip('displays all required information in node cards', async () => {
    fetch.mockResponseOnce(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('Main Node')).toBeInTheDocument();
    });

    // Check node information
    expect(screen.getByText(/AA:BB:CC:DD:EE:01/)).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument(); // Clients count
  });

  // stale, see #3
  test.skip('handles multiple refresh cycles', async () => {
    fetch.mockResponse(JSON.stringify(mockTopologyData));

    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(screen.getByText('Main Node')).toBeInTheDocument();
    });

    // Refresh multiple times
    const refreshButton = screen.getByRole('button', { name: /Refresh/i });
    fireEvent.click(refreshButton);
    fireEvent.click(refreshButton);

    expect(fetch).toHaveBeenCalledTimes(3); // Initial + 2 refreshes
  });
});
