import React from 'react';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DecoNodesPage from '../DecoNodesPage';
import * as apiConfig from '../../utils/apiConfig';

// Mock the apiConfig module
vi.mock('../../utils/apiConfig', () => ({
  buildUrl: vi.fn((endpoint) => `/api${endpoint}`),
}));

// Mock the DecoNodeCard component
vi.mock('../../components/DecoNodeCard', () => {
  const MockDecoNodeCard = function MockDecoNodeCard({ node, onClick }) {
    return (
      <div
        data-testid={`node-card-${node.node_id}`}
        onClick={onClick}
        className="deco-node-card"
      >
        <h3>{node.node_name}</h3>
        <p>{node.node_id}</p>
        <span>{node.status}</span>
        <span>{node.signal_strength}%</span>
      </div>
    );
  };
  return { default: MockDecoNodeCard };
});

describe('DecoNodesPage Component', () => {
  const mockNodesData = {
    nodes: [
      {
        node_id: 'node1',
        node_name: 'Main Router',
        firmware_version: '1.5.8',
        uptime_seconds: 432000,
        connected_clients: 5,
        signal_strength: 85,
        model: 'Deco M32',
        status: 'online',
        last_updated: '2024-03-06T10:30:00Z',
      },
      {
        node_id: 'node2',
        node_name: 'Satellite 1',
        firmware_version: '1.5.8',
        uptime_seconds: 400000,
        connected_clients: 3,
        signal_strength: 72,
        model: 'Deco M32',
        status: 'online',
        last_updated: '2024-03-06T10:30:00Z',
      },
    ],
    total: 2,
    timestamp: '2024-03-06T10:30:00Z',
    cache_info: { ttl_seconds: 60, cached: false },
  };

  const ok = (body) => ({ ok: true, status: 200, json: async () => body });

  /**
   * Route fetch by URL. The page fetches /deco/nodes on load and on every
   * auto-refresh tick, POSTs /deco/nodes/refresh on manual refresh, and also
   * loads /devices for the fallback client list whenever node state changes.
   * Each route may be a response, an Error (rejects), or a function returning either.
   */
  const mockApi = ({
    nodes = ok(mockNodesData),
    refresh = ok(mockNodesData),
    devices = ok({ devices: [] }),
  } = {}) => {
    const routes = {
      '/api/deco/nodes': nodes,
      '/api/deco/nodes/refresh': refresh,
      '/api/devices': devices,
      '/api/deco/import-client-names': ok({ imported: 0, total_clients: 0 }),
    };
    global.fetch.mockImplementation(async (url) => {
      let entry = routes[url];
      if (typeof entry === 'function') entry = entry();
      if (entry instanceof Error) throw entry;
      return entry || { ok: false, status: 404, statusText: 'Not Found', json: async () => ({}) };
    });
  };

  const callsTo = (url) => global.fetch.mock.calls.filter(([u]) => u === url);
  const never = () => new Promise(() => {});

  const renderLoaded = async () => {
    const user = userEvent.setup();
    const utils = render(<DecoNodesPage />);
    expect(await screen.findByText('Main Router')).toBeInTheDocument();
    return { user, ...utils };
  };

  const openNodeModal = async (nodeId = 'node1') => {
    const { user, ...utils } = await renderLoaded();
    await user.click(screen.getByTestId(`node-card-${nodeId}`));
    const modal = await waitFor(() => {
      const el = document.querySelector('.node-detail-modal');
      expect(el).toBeInTheDocument();
      return el;
    });
    return { user, modal, ...utils };
  };

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    mockApi();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('Component Rendering', () => {
    test('renders without errors', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Deco Nodes')).toBeInTheDocument();
      });
    });

    test('renders page header with title', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Deco Nodes')).toBeInTheDocument();
        expect(screen.getByText('Monitor your TP-Link Deco mesh network nodes')).toBeInTheDocument();
      });
    });

    test('renders refresh button', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Refresh/i })).toBeInTheDocument();
      });
    });

    test('renders auto-refresh toggle', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByRole('checkbox', { name: /Auto-refresh/i })).toBeInTheDocument();
      });
    });
  });

  describe('Initial Load', () => {
    test('fetches nodes from API on initial load', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/deco/nodes', expect.any(Object));
      });
    });

    test('displays loading state while fetching', () => {
      mockApi({ nodes: never });

      render(<DecoNodesPage />);

      // Should show loading spinner initially
      expect(screen.getByText('Loading Deco nodes...')).toBeInTheDocument();
    });

    test('displays nodes list after fetch completes', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
        expect(screen.getByText('Satellite 1')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    test('displays error state if fetch fails', async () => {
      mockApi({ nodes: new Error('Network error') });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Nodes')).toBeInTheDocument();
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    test('displays error message for API errors', async () => {
      mockApi({ nodes: { ok: false, status: 401, statusText: 'Unauthorized' } });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Nodes')).toBeInTheDocument();
        expect(
          screen.getByText('Not authenticated with Deco API. Please configure credentials.')
        ).toBeInTheDocument();
      });
    });

    test('displays retry button in error state', async () => {
      mockApi({ nodes: new Error('API error') });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    test('displays empty state when no nodes returned', async () => {
      mockApi({ nodes: ok({ nodes: [], total: 0 }) });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('No Deco Nodes Found')).toBeInTheDocument();
        expect(screen.getByText(/No Deco nodes are currently available/)).toBeInTheDocument();
      });
    });

    test('displays try again button in empty state', async () => {
      mockApi({ nodes: ok({ nodes: [] }) });

      render(<DecoNodesPage />);

      await waitFor(() => {
        const buttons = screen.getAllByRole('button', { name: /Try Again/i });
        expect(buttons.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Statistics Calculation', () => {
    test('calculates statistics correctly', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        // Total nodes
        expect(screen.getByText('Total Nodes')).toBeInTheDocument();
        const statCards = screen.getAllByText(/2/);
        expect(statCards.length).toBeGreaterThan(0);
      });
    });

    test('calculates online count correctly', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Online')).toBeInTheDocument();
      });
    });

    test('calculates total clients correctly', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Total Clients')).toBeInTheDocument();
        // 5 + 3 = 8 total clients
        const stats = screen.getAllByText(/8/);
        expect(stats.length).toBeGreaterThan(0);
      });
    });

    test('calculates average signal strength correctly', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Avg Signal')).toBeInTheDocument();
        // (85 + 72) / 2 = 78.5 ≈ 79
        const avgSignal = screen.getByText('79%');
        expect(avgSignal).toBeInTheDocument();
      });
    });

    test('handles edge case with single node', async () => {
      mockApi({ nodes: ok({ nodes: [mockNodesData.nodes[0]], total: 1 }) });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Total Nodes')).toBeInTheDocument();
        const statCards = screen.getAllByText(/1/);
        expect(statCards.length).toBeGreaterThan(0);
      });
    });

    test('handles statistics with zero values', async () => {
      mockApi({
        nodes: ok({
          nodes: [
            {
              ...mockNodesData.nodes[0],
              connected_clients: 0,
              signal_strength: 0,
              status: 'offline',
            },
          ],
          total: 1,
        }),
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        // Should handle zero stats gracefully
        expect(screen.getByText('Total Clients')).toBeInTheDocument();
      });
    });
  });

  describe('Manual Refresh', () => {
    test('manual refresh button calls API', async () => {
      const { user } = await renderLoaded();
      expect(callsTo('/api/deco/nodes/refresh')).toHaveLength(0);

      await user.click(screen.getByRole('button', { name: /Refresh/i }));

      await waitFor(() => {
        expect(callsTo('/api/deco/nodes/refresh')).toHaveLength(1);
      });
      // Initial GET only; manual refresh does not re-issue the cached GET
      expect(callsTo('/api/deco/nodes')).toHaveLength(1);
      expect(await screen.findByRole('button', { name: /^⟲\s*Refresh$/ })).not.toBeDisabled();
    });

    test('manual refresh updates last refresh time', async () => {
      // Fake only Date so the "last updated" age is deterministic while
      // timers (and userEvent) stay real.
      vi.useFakeTimers({ toFake: ['Date'] });
      vi.setSystemTime(new Date('2026-01-01T00:00:00Z'));
      const user = userEvent.setup();
      const { rerender } = render(<DecoNodesPage />);

      // Before the first response lands nothing has been refreshed
      expect(screen.getByText('Last updated: Never')).toBeInTheDocument();

      await screen.findByText('Main Router');
      expect(screen.getByText('Last updated: 0s ago')).toBeInTheDocument();

      // Time passes: the timestamp ages
      vi.setSystemTime(new Date('2026-01-01T00:00:30Z'));
      rerender(<DecoNodesPage />);
      expect(screen.getByText('Last updated: 30s ago')).toBeInTheDocument();

      // A manual refresh resets it
      await user.click(screen.getByRole('button', { name: /Refresh/i }));

      await waitFor(() => {
        expect(callsTo('/api/deco/nodes/refresh')).toHaveLength(1);
        expect(screen.getByText('Last updated: 0s ago')).toBeInTheDocument();
      });
    });

    test('refresh button disabled while loading', async () => {
      mockApi({ nodes: never });

      render(<DecoNodesPage />);

      const refreshButton = screen.getByRole('button', { name: /Refreshing/i });
      expect(refreshButton).toBeDisabled();
    });

    test('calls refresh endpoint on manual refresh', async () => {
      const { user } = await renderLoaded();

      global.fetch.mockClear();

      await user.click(screen.getByRole('button', { name: /Refresh/i }));

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/deco/nodes/refresh',
          expect.objectContaining({ method: 'POST' })
        );
      });
    });
  });

  describe('Auto-Refresh', () => {
    test('auto-refresh happens every 60 seconds', async () => {
      vi.useFakeTimers();

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      global.fetch.mockClear();

      // Advance time by 60 seconds
      vi.advanceTimersByTime(60000);

      await waitFor(() => {
        expect(callsTo('/api/deco/nodes')).toHaveLength(1);
      });
    });

    test('auto-refresh respects the interval state', async () => {
      vi.useFakeTimers();

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      // Disable auto-refresh (toggling re-runs the effect, which does one immediate fetch)
      const autoRefreshCheckbox = screen.getByRole('checkbox', { name: /Auto-refresh/i });
      fireEvent.click(autoRefreshCheckbox);
      expect(autoRefreshCheckbox).not.toBeChecked();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^⟲\s*Refresh$/ })).not.toBeDisabled();
      });

      // Clear fetch calls from toggle interaction
      global.fetch.mockClear();

      // Advance well past the interval - no node polling should happen
      vi.advanceTimersByTime(180000);

      expect(callsTo('/api/deco/nodes')).toHaveLength(0);
    });

    test('can toggle auto-refresh on and off', async () => {
      const { user } = await renderLoaded();

      const autoRefreshCheckbox = screen.getByRole('checkbox', { name: /Auto-refresh/i });

      // Should be enabled by default
      expect(autoRefreshCheckbox).toBeChecked();
      expect(screen.getByText('Auto-refresh every 60s')).toBeInTheDocument();

      // Disable it
      await user.click(autoRefreshCheckbox);
      expect(autoRefreshCheckbox).not.toBeChecked();

      // Enable it again
      await user.click(autoRefreshCheckbox);
      expect(autoRefreshCheckbox).toBeChecked();
    });
  });

  describe('Node Detail Modal', () => {
    test('detail modal opens on node click', async () => {
      const { modal } = await openNodeModal('node1');

      // Modal header shows the node name and status
      expect(within(modal).getByRole('heading', { name: 'Main Router' })).toBeInTheDocument();
      expect(within(modal).getByText('● Online')).toBeInTheDocument();
    });

    test('detail modal displays full node information', async () => {
      const { modal } = await openNodeModal('node1');

      expect(within(modal).getByText('node1')).toBeInTheDocument();
      expect(within(modal).getByText('1.5.8')).toBeInTheDocument(); // firmware
      expect(within(modal).getByText('Deco M32')).toBeInTheDocument(); // model
      expect(within(modal).getByText('432000')).toBeInTheDocument(); // uptime seconds
      expect(within(modal).getByText('Connected Clients').nextSibling).toHaveTextContent('5');
      expect(within(modal).getByText('85%')).toBeInTheDocument(); // signal
    });

    test('detail modal closes on close button click', async () => {
      const { user } = await openNodeModal('node1');

      await user.click(screen.getByLabelText('Close modal'));

      await waitFor(() => {
        expect(screen.queryByLabelText('Close modal')).not.toBeInTheDocument();
      });
      expect(document.querySelector('.node-detail-modal')).not.toBeInTheDocument();
    });

    test('detail modal closes on overlay click', async () => {
      const { user, modal } = await openNodeModal('node1');

      await user.click(modal.querySelector('.modal-overlay'));

      await waitFor(() => {
        expect(document.querySelector('.node-detail-modal')).not.toBeInTheDocument();
      });
    });

    test('node card click calls handler with correct node data', async () => {
      const { modal } = await openNodeModal('node2');

      // Modal shows the clicked node, not the first one
      expect(within(modal).getByRole('heading', { name: 'Satellite 1' })).toBeInTheDocument();
      expect(within(modal).getByText('node2')).toBeInTheDocument();
      expect(within(modal).queryByText('node1')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    test('has proper ARIA labels on interactive elements', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Auto-refresh/)).toBeInTheDocument();
      });
    });

    test('modal has close button with aria-label', async () => {
      await openNodeModal('node1');

      expect(screen.getByRole('button', { name: 'Close modal' })).toBeInTheDocument();
    });

    test('buttons are keyboard accessible', async () => {
      const { user } = await renderLoaded();

      const refreshButton = screen.getByRole('button', { name: /Refresh/i });
      refreshButton.focus();
      expect(refreshButton).toHaveFocus();

      await user.keyboard('{Enter}');

      await waitFor(() => {
        expect(callsTo('/api/deco/nodes/refresh')).toHaveLength(1);
      });
    });
  });

  describe('API Configuration', () => {
    test('uses buildUrl utility for API calls', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(apiConfig.buildUrl).toHaveBeenCalledWith('/deco/nodes');
      });
    });

    test('sends correct headers in API request', async () => {
      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
            },
          })
        );
      });
    });
  });
});
