import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import DecoTopologyView from '../DecoTopologyView';

// Mock the API
vi.mock('../../utils/apiConfig', () => ({
  buildUrl: (path) => `http://localhost:9000/api${path}`,
}));

const TOPOLOGY_URL = 'http://localhost:9000/api/deco/topology';
const GRAPH_URL = 'http://localhost:9000/api/deco/topology-graph';
const MOCK_GRAPH_SVG =
  '<svg class="topology-svg" xmlns="http://www.w3.org/2000/svg"><circle r="5" /></svg>';

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

  const jsonResponse = (body, init = {}) => ({
    ok: (init.status || 200) < 400,
    status: init.status || 200,
    statusText: init.statusText || 'OK',
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
  const textResponse = (text) => ({ ok: true, status: 200, statusText: 'OK', text: async () => text });
  const never = () => new Promise(() => {});

  /**
   * The component fetches JSON from /deco/topology and a backend-rendered SVG
   * from /deco/topology-graph on mount, on refresh, and on each auto-refresh tick.
   * Each route may be a response, an Error (rejects), or a function returning either.
   */
  const mockApi = ({
    topology = jsonResponse(mockTopologyData),
    graph = textResponse(MOCK_GRAPH_SVG),
  } = {}) => {
    global.fetch = vi.fn(async (url) => {
      let entry = url === TOPOLOGY_URL ? topology : url === GRAPH_URL ? graph : null;
      if (typeof entry === 'function') entry = entry();
      if (entry instanceof Error) throw entry;
      return entry || { ok: false, status: 404, statusText: 'Not Found' };
    });
  };

  const callsTo = (url) => global.fetch.mock.calls.filter(([u]) => u === url);
  const refreshButton = () => screen.getByRole('button', { name: /Refresh/i });

  // Wait until both topology and graph requests have settled
  const waitForIdle = () =>
    waitFor(() => {
      expect(refreshButton()).toHaveTextContent(/^\W*Refresh$/);
      expect(refreshButton()).not.toBeDisabled();
    });

  // Node/device details are only rendered in the "Cards" view
  const renderCards = async (props = {}) => {
    const utils = render(<DecoTopologyView {...props} />);
    await screen.findByText('Nodes:');
    fireEvent.click(screen.getByRole('button', { name: 'Cards' }));
    return utils;
  };

  const nodeGroup = (name) => screen.getByRole('heading', { name }).closest('.node-group');

  beforeEach(() => {
    mockApi();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('renders component with header', async () => {
    render(<DecoTopologyView />);

    expect(screen.getByRole('heading', { name: 'Network Topology' })).toBeInTheDocument();
    expect(screen.getByText('Deco mesh nodes and connected devices')).toBeInTheDocument();
    await waitForIdle();
  });

  test('displays loading state initially', () => {
    mockApi({ topology: never, graph: never });

    render(<DecoTopologyView />);

    expect(screen.getByText('Loading topology...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Refreshing/i })).toBeDisabled();
  });

  test('fetches and displays topology data', async () => {
    await renderCards();

    expect(await screen.findByRole('heading', { name: 'Main Node' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Bedroom Node' })).toBeInTheDocument();
  });

  test('displays topology statistics', async () => {
    const { container } = render(<DecoTopologyView />);

    await screen.findByText('Nodes:');
    const stat = (label) => screen.getByText(label).closest('.stat-item');
    expect(stat('Nodes:')).toHaveTextContent('Nodes:2');
    expect(stat('Devices:')).toHaveTextContent('Devices:3');
    expect(stat('Connections:')).toHaveTextContent('Connections:3');
    expect(container.querySelectorAll('.topology-stats .stat-item')).toHaveLength(3);
  });

  test('renders nodes in details section', async () => {
    await renderCards();

    await screen.findByRole('heading', { name: 'Main Node' });
    expect(screen.getByRole('heading', { name: 'Bedroom Node' })).toBeInTheDocument();
    expect(within(nodeGroup('Main Node')).getByText('AA:BB:CC:DD:EE:01')).toBeInTheDocument();
    expect(within(nodeGroup('Bedroom Node')).getByText('AA:BB:CC:DD:EE:02')).toBeInTheDocument();
  });

  test('renders devices in details section', async () => {
    await renderCards();

    await screen.findByText("John's iPhone");
    // Devices are grouped under the node they are connected to
    const main = within(nodeGroup('Main Node'));
    expect(main.getByText("John's iPhone")).toBeInTheDocument();
    expect(main.getByText('Work Laptop')).toBeInTheDocument();
    expect(within(nodeGroup('Bedroom Node')).getByText('Living Room TV')).toBeInTheDocument();
  });

  test('renders SVG canvas for topology visualization', async () => {
    const { container } = render(<DecoTopologyView />);

    // Graph view (default) injects the backend-rendered NetworkX SVG
    await waitFor(() => {
      const svg = container.querySelector('.networkx-svg-wrapper svg.topology-svg');
      expect(svg).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /Download Diagram/i })).toBeInTheDocument();
  });

  test('handles refresh button click', async () => {
    render(<DecoTopologyView />);
    await waitForIdle();
    expect(callsTo(TOPOLOGY_URL)).toHaveLength(1);
    expect(callsTo(GRAPH_URL)).toHaveLength(1);

    fireEvent.click(refreshButton());

    expect(callsTo(TOPOLOGY_URL)).toHaveLength(2);
    expect(callsTo(GRAPH_URL)).toHaveLength(2);
    await waitForIdle();
  });

  test('toggles auto-refresh on checkbox change', async () => {
    render(<DecoTopologyView autoRefreshInterval={5000} />);
    await waitForIdle();

    const autoRefreshCheckbox = screen.getByRole('checkbox', {
      name: /Auto-refresh/i,
    });
    // Enabled by default
    expect(autoRefreshCheckbox).toBeChecked();

    // Uncheck auto-refresh
    fireEvent.click(autoRefreshCheckbox);
    expect(autoRefreshCheckbox).not.toBeChecked();

    // Check auto-refresh
    fireEvent.click(autoRefreshCheckbox);
    expect(autoRefreshCheckbox).toBeChecked();
    await waitForIdle();
  });

  test('displays error state on API failure', async () => {
    mockApi({ topology: new Error('Network error') });

    render(<DecoTopologyView />);

    const errorBox = await waitFor(() => {
      const el = document.querySelector('.error-container');
      expect(el).toBeInTheDocument();
      return el;
    });
    expect(within(errorBox).getByRole('heading', { name: 'Error' })).toBeInTheDocument();
    expect(within(errorBox).getByText('Network error')).toBeInTheDocument();
  });

  test('displays error message for unauthorized access', async () => {
    mockApi({
      topology: jsonResponse({ detail: 'Not authenticated with Deco API' }, { status: 401, statusText: 'Unauthorized' }),
    });

    render(<DecoTopologyView />);

    expect(await screen.findByText('Not authenticated with Deco API.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Error' })).toBeInTheDocument();
  });

  test('displays empty state when no nodes', async () => {
    mockApi({
      topology: jsonResponse({
        nodes: [],
        devices: [],
        relationships: [],
        total_nodes: 0,
        total_devices: 0,
        total_relationships: 0,
        timestamp: new Date().toISOString(),
      }),
    });

    render(<DecoTopologyView />);

    expect(await screen.findByRole('heading', { name: 'No Topology Data' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument();
  });

  test('displays device status indicators', async () => {
    const topologyWithOffline = {
      ...mockTopologyData,
      nodes: [...mockTopologyData.nodes, {
        node_id: 'node_3',
        node_name: 'Garage Node',
        mac_address: 'AA:BB:CC:DD:EE:03',
        status: 'offline',
        signal_strength: 0,
        connected_clients: 0,
      }],
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
    mockApi({ topology: jsonResponse(topologyWithOffline) });

    await renderCards();
    await screen.findByRole('heading', { name: 'Garage Node' });

    // Node status badges
    expect(within(nodeGroup('Main Node')).getByText('Online')).toHaveClass('status-badge', 'online');
    expect(within(nodeGroup('Garage Node')).getByText('Offline')).toHaveClass('status-badge', 'offline');

    // Unassigned devices are collapsed by default; expand everything to see them
    fireEvent.click(screen.getByRole('button', { name: 'Expand All' }));
    const oldDevice = await screen.findByText('Old Device');
    expect(within(nodeGroup('Unassigned')).getByText('Old Device')).toBeInTheDocument();
    expect(oldDevice.closest('.topo-device-card')).toHaveClass('offline');
    expect(screen.getByText("John's iPhone").closest('.topo-device-card')).toHaveClass('online');
  });

  test('updates last refresh time', async () => {
    render(<DecoTopologyView />);

    // Nothing loaded yet
    expect(screen.getByText('Updated: Never')).toBeInTheDocument();

    await screen.findByText('Nodes:');

    const lastRefresh = screen.getByText(/Updated:/);
    expect(lastRefresh).toBeInTheDocument();
    expect(lastRefresh.textContent).toMatch(/Updated: \d+s ago/);
  });

  test('renders retry button on error', async () => {
    mockApi({ topology: new Error('API Error') });

    render(<DecoTopologyView />);

    const retry = await screen.findByRole('button', { name: /Retry/i });
    await waitForIdle();
    mockApi();
    fireEvent.click(retry);

    // Retry re-fetches and recovers
    expect(await screen.findByText('Nodes:')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Retry/i })).not.toBeInTheDocument();
  });

  test('fetches from correct API endpoint', async () => {
    render(<DecoTopologyView />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(TOPOLOGY_URL);
      expect(fetch).toHaveBeenCalledWith(GRAPH_URL);
    });
    await waitForIdle();
  });

  test('displays all required information in node cards', async () => {
    await renderCards();

    await screen.findByRole('heading', { name: 'Main Node' });

    // Check node information
    const main = within(nodeGroup('Main Node'));
    expect(main.getByText(/AA:BB:CC:DD:EE:01/)).toBeInTheDocument();
    expect(main.getByText('2 devices')).toBeInTheDocument(); // devices connected to this node
    expect(main.getByText('Online')).toBeInTheDocument();
    expect(within(nodeGroup('Bedroom Node')).getByText('1 device')).toBeInTheDocument();
  });

  test('handles multiple refresh cycles', async () => {
    render(<DecoTopologyView />);
    await waitForIdle();

    // Refresh multiple times (button is disabled while a refresh is in flight)
    fireEvent.click(refreshButton());
    await waitForIdle();
    fireEvent.click(refreshButton());
    await waitForIdle();

    expect(callsTo(TOPOLOGY_URL)).toHaveLength(3); // Initial + 2 refreshes
    expect(callsTo(GRAPH_URL)).toHaveLength(3);
  });
});
