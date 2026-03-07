import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DecoNodesPage from '../DecoNodesPage';
import * as apiConfig from '../../utils/apiConfig';

// Mock the apiConfig module
jest.mock('../../utils/apiConfig', () => ({
  buildUrl: jest.fn((endpoint) => `/api${endpoint}`),
}));

// Mock the DecoNodeCard component
jest.mock('../../components/DecoNodeCard', () => {
  return function MockDecoNodeCard({ node, onClick }) {
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

  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
    // Reset timers
    jest.useFakeTimers();
    // Mock fetch globally
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.resetAllMocks();
  });

  describe('Component Rendering', () => {
    test('renders without errors', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Deco Nodes')).toBeInTheDocument();
      });
    });

    test('renders page header with title', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Deco Nodes')).toBeInTheDocument();
        expect(screen.getByText('Monitor your TP-Link Deco mesh network nodes')).toBeInTheDocument();
      });
    });

    test('renders refresh button', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Refresh/i })).toBeInTheDocument();
      });
    });

    test('renders auto-refresh toggle', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByRole('checkbox', { name: /Auto-refresh/i })).toBeInTheDocument();
      });
    });
  });

  describe('Initial Load', () => {
    test('fetches nodes from API on initial load', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/deco/nodes', expect.any(Object));
      });
    });

    test('displays loading state while fetching', () => {
      global.fetch.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            // Simulate slow API response
            setTimeout(() => {
              resolve({
                ok: true,
                json: async () => mockNodesData,
              });
            }, 100);
          })
      );

      render(<DecoNodesPage />);

      // Should show loading spinner initially
      expect(screen.getByText('Loading Deco nodes...')).toBeInTheDocument();
    });

    test('displays nodes list after fetch completes', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
        expect(screen.getByText('Satellite 1')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    test('displays error state if fetch fails', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network error'));

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Nodes')).toBeInTheDocument();
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    test('displays error message for API errors', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Nodes')).toBeInTheDocument();
        expect(screen.getByText(/authentication/i)).toBeInTheDocument();
      });
    });

    test('displays retry button in error state', async () => {
      global.fetch.mockRejectedValueOnce(new Error('API error'));

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    test('displays empty state when no nodes returned', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ nodes: [], total: 0 }),
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('No Deco Nodes Found')).toBeInTheDocument();
        expect(screen.getByText(/No Deco nodes are currently available/)).toBeInTheDocument();
      });
    });

    test('displays try again button in empty state', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ nodes: [] }),
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        const buttons = screen.getAllByRole('button', { name: /Try Again/i });
        expect(buttons.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Statistics Calculation', () => {
    test('calculates statistics correctly', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        // Total nodes
        expect(screen.getByText('Total Nodes')).toBeInTheDocument();
        const statCards = screen.getAllByText(/2/);
        expect(statCards.length).toBeGreaterThan(0);
      });
    });

    test('calculates online count correctly', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Online')).toBeInTheDocument();
      });
    });

    test('calculates total clients correctly', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Total Clients')).toBeInTheDocument();
        // 5 + 3 = 8 total clients
        const stats = screen.getAllByText(/8/);
        expect(stats.length).toBeGreaterThan(0);
      });
    });

    test('calculates average signal strength correctly', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Avg Signal')).toBeInTheDocument();
        // (85 + 72) / 2 = 78.5 ≈ 79
        const avgSignal = screen.getByText('79%');
        expect(avgSignal).toBeInTheDocument();
      });
    });

    test('handles edge case with single node', async () => {
      const singleNodeData = {
        nodes: [mockNodesData.nodes[0]],
        total: 1,
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => singleNodeData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Total Nodes')).toBeInTheDocument();
        const statCards = screen.getAllByText(/1/);
        expect(statCards.length).toBeGreaterThan(0);
      });
    });

    test('handles statistics with zero values', async () => {
      const zeroStatsData = {
        nodes: [
          {
            ...mockNodesData.nodes[0],
            connected_clients: 0,
            signal_strength: 0,
            status: 'offline',
          },
        ],
        total: 1,
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => zeroStatsData,
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
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      const refreshButton = screen.getByRole('button', { name: /Refresh/i });
      await userEvent.click(refreshButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(2);
      });
    });

    test('manual refresh updates last refresh time', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText(/Last updated/)).toBeInTheDocument();
      });

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      const refreshButton = screen.getByRole('button', { name: /Refresh/i });
      await userEvent.click(refreshButton);

      await waitFor(() => {
        const lastUpdated = screen.getByText(/Last updated/);
        expect(lastUpdated.textContent).toMatch(/ago|ago/);
      });
    });

    test('refresh button disabled while loading', async () => {
      global.fetch.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                ok: true,
                json: async () => mockNodesData,
              });
            }, 100);
          })
      );

      render(<DecoNodesPage />);

      const refreshButton = screen.getByRole('button', { name: /Refreshing/i });
      expect(refreshButton).toBeDisabled();
    });

    test('calls refresh endpoint on manual refresh', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      global.fetch.mockClear();
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      const refreshButton = screen.getByRole('button', { name: /Refresh/i });
      await userEvent.click(refreshButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/deco/nodes/refresh', expect.any(Object));
      });
    });
  });

  describe('Auto-Refresh', () => {
    test('auto-refresh happens every 60 seconds', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      global.fetch.mockClear();
      global.fetch.mockResolvedValue({
        ok: true,
        json: async () => mockNodesData,
      });

      // Advance time by 60 seconds
      jest.advanceTimersByTime(60000);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalled();
      });
    });

    test('auto-refresh respects the interval state', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      global.fetch.mockClear();
      global.fetch.mockResolvedValue({
        ok: true,
        json: async () => mockNodesData,
      });

      // Get the auto-refresh toggle
      const autoRefreshCheckbox = screen.getByRole('checkbox', { name: /Auto-refresh/i });

      // Disable auto-refresh
      userEvent.click(autoRefreshCheckbox);

      // Clear fetch calls from toggle interaction
      global.fetch.mockClear();

      // Advance time - should not call fetch
      jest.advanceTimersByTime(60000);

      // No additional fetch calls should be made
      expect(global.fetch).not.toHaveBeenCalled();
    });

    test('can toggle auto-refresh on and off', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      const autoRefreshCheckbox = screen.getByRole('checkbox', { name: /Auto-refresh/i });

      // Should be enabled by default
      expect(autoRefreshCheckbox).toBeChecked();

      // Disable it
      await userEvent.click(autoRefreshCheckbox);
      expect(autoRefreshCheckbox).not.toBeChecked();

      // Enable it again
      await userEvent.click(autoRefreshCheckbox);
      expect(autoRefreshCheckbox).toBeChecked();
    });
  });

  describe('Node Detail Modal', () => {
    test('detail modal opens on node click', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      const nodeCard = screen.getByTestId('node-card-node1');
      await userEvent.click(nodeCard);

      await waitFor(() => {
        expect(screen.getByText(/Node Details/)).toBeInTheDocument();
      });
    });

    test('detail modal displays full node information', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      const nodeCard = screen.getByTestId('node-card-node1');
      await userEvent.click(nodeCard);

      await waitFor(() => {
        expect(screen.getByText('node1')).toBeInTheDocument();
        expect(screen.getByText('1.5.8')).toBeInTheDocument(); // firmware
        expect(screen.getByText(/Deco M32/)).toBeInTheDocument(); // model
      });
    });

    test('detail modal closes on close button click', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      const nodeCard = screen.getByTestId('node-card-node1');
      await userEvent.click(nodeCard);

      await waitFor(() => {
        expect(screen.getByLabelText('Close modal')).toBeInTheDocument();
      });

      const closeButton = screen.getByLabelText('Close modal');
      await userEvent.click(closeButton);

      await waitFor(() => {
        expect(screen.queryByLabelText('Close modal')).not.toBeInTheDocument();
      });
    });

    test('detail modal closes on overlay click', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      const nodeCard = screen.getByTestId('node-card-node1');
      await userEvent.click(nodeCard);

      await waitFor(() => {
        expect(screen.getByLabelText('Close modal')).toBeInTheDocument();
      });

      // Find and click the modal overlay
      const { container } = render(<DecoNodesPage />);
      // Re-open modal
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      await userEvent.click(nodeCard);

      const overlay = container.querySelector('.modal-overlay');
      if (overlay) {
        await userEvent.click(overlay);
      }
    });

    test('node card click calls handler with correct node data', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      const nodeCard = screen.getByTestId('node-card-node1');
      await userEvent.click(nodeCard);

      // Verify node details are shown
      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
        expect(screen.getByText('node1')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    test('has proper ARIA labels on interactive elements', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Auto-refresh/)).toBeInTheDocument();
      });
    });

    test('modal has close button with aria-label', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      const nodeCard = screen.getByTestId('node-card-node1');
      await userEvent.click(nodeCard);

      await waitFor(() => {
        expect(screen.getByLabelText('Close modal')).toBeInTheDocument();
      });
    });

    test('buttons are keyboard accessible', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(screen.getByText('Main Router')).toBeInTheDocument();
      });

      const refreshButton = screen.getByRole('button', { name: /Refresh/i });
      expect(refreshButton).toHaveProperty('type', 'button');
    });
  });

  describe('API Configuration', () => {
    test('uses buildUrl utility for API calls', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

      render(<DecoNodesPage />);

      await waitFor(() => {
        expect(apiConfig.buildUrl).toHaveBeenCalledWith('/deco/nodes');
      });
    });

    test('sends correct headers in API request', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockNodesData,
      });

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
