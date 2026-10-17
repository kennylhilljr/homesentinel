import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DecoNodeCard from '../DecoNodeCard';

describe('DecoNodeCard Component', () => {
  const mockNode = {
    node_id: 'node1',
    node_name: 'Main Router',
    firmware_version: '1.5.8',
    uptime_seconds: 432000, // 5 days
    connected_clients: 5,
    signal_strength: 75,
    model: 'Deco M32',
    status: 'online',
    last_updated: '2024-01-15T10:30:00Z',
  };

  describe('Rendering', () => {
    test('renders node card with node data', () => {
      render(<DecoNodeCard node={mockNode} onClick={jest.fn()} />);

      expect(screen.getByText('Main Router')).toBeInTheDocument();
      expect(screen.getByText('node1')).toBeInTheDocument();
    });

    test('displays firmware version', () => {
      render(<DecoNodeCard node={mockNode} onClick={jest.fn()} />);

      expect(screen.getByText('1.5.8')).toBeInTheDocument();
    });

    test('displays connected clients count', () => {
      render(<DecoNodeCard node={mockNode} onClick={jest.fn()} />);

      expect(screen.getByText(/5/)).toBeInTheDocument();
      expect(screen.getByText(/connected/)).toBeInTheDocument();
    });

    test('displays model name', () => {
      render(<DecoNodeCard node={mockNode} onClick={jest.fn()} />);

      expect(screen.getByText('Deco M32')).toBeInTheDocument();
    });

    test('displays online status badge', () => {
      render(<DecoNodeCard node={mockNode} onClick={jest.fn()} />);

      const statusBadge = screen.getByText('Online');
      expect(statusBadge).toBeInTheDocument();
    });

    test('displays offline status badge for offline nodes', () => {
      const offlineNode = { ...mockNode, status: 'offline' };
      render(<DecoNodeCard node={offlineNode} onClick={jest.fn()} />);

      expect(screen.getByText('Offline')).toBeInTheDocument();
    });

    test('renders with null node shows loading state', () => {
      render(<DecoNodeCard node={null} onClick={jest.fn()} />);

      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  describe('Uptime Formatting', () => {
    test('formats uptime in days and hours', () => {
      render(<DecoNodeCard node={mockNode} onClick={jest.fn()} />);

      // 432000 seconds = 5 days exactly
      expect(screen.getByText(/5 day/)).toBeInTheDocument();
    });

    test('formats uptime with multiple units', () => {
      const nodeWithUptime = {
        ...mockNode,
        uptime_seconds: 90061, // 1 day, 1 hour, 1 minute
      };
      render(<DecoNodeCard node={nodeWithUptime} onClick={jest.fn()} />);

      expect(screen.getByText(/1 day/)).toBeInTheDocument();
      expect(screen.getByText(/1 hour/)).toBeInTheDocument();
    });

    test('handles zero uptime', () => {
      const newNode = { ...mockNode, uptime_seconds: 0 };
      render(<DecoNodeCard node={newNode} onClick={jest.fn()} />);

      expect(screen.getByText(/Just started/)).toBeInTheDocument();
    });

    test('handles negative uptime gracefully', () => {
      const badNode = { ...mockNode, uptime_seconds: -1000 };
      render(<DecoNodeCard node={badNode} onClick={jest.fn()} />);

      expect(screen.getByText(/Unknown/)).toBeInTheDocument();
    });
  });

  describe('Signal Strength Indicator', () => {
    test('renders signal strength percentage', () => {
      render(<DecoNodeCard node={mockNode} onClick={jest.fn()} />);

      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    test('shows excellent signal quality for 70+ strength', () => {
      const node = { ...mockNode, signal_strength: 85 };
      render(<DecoNodeCard node={node} onClick={jest.fn()} />);

      expect(screen.getByText('Excellent')).toBeInTheDocument();
    });

    test('shows good signal quality for 40-70 strength', () => {
      const node = { ...mockNode, signal_strength: 60 };
      render(<DecoNodeCard node={node} onClick={jest.fn()} />);

      expect(screen.getByText('Good')).toBeInTheDocument();
    });

    test('shows good signal quality at boundary (40%)', () => {
      const node = { ...mockNode, signal_strength: 40 };
      render(<DecoNodeCard node={node} onClick={jest.fn()} />);

      expect(screen.getByText('Good')).toBeInTheDocument();
    });

    test('shows poor signal quality for < 40 strength', () => {
      const node = { ...mockNode, signal_strength: 30 };
      render(<DecoNodeCard node={node} onClick={jest.fn()} />);

      expect(screen.getByText('Poor')).toBeInTheDocument();
    });

    test('handles missing signal strength', () => {
      const node = { ...mockNode, signal_strength: undefined };
      render(<DecoNodeCard node={node} onClick={jest.fn()} />);

      expect(screen.getByText('0%')).toBeInTheDocument();
    });
  });

  describe('Click Handler', () => {
    test('calls onClick when card is clicked', async () => {
      const onClick = jest.fn();
      const user = userEvent.setup();
      const { container } = render(<DecoNodeCard node={mockNode} onClick={onClick} />);

      const card = container.querySelector('.deco-node-card');
      await user.click(card);

      expect(onClick).toHaveBeenCalled();
    });

    test('calls onClick when Enter key is pressed', async () => {
      const onClick = jest.fn();
      const user = userEvent.setup();
      const { container } = render(<DecoNodeCard node={mockNode} onClick={onClick} />);

      const card = container.querySelector('.deco-node-card');
      card.focus();
      await user.keyboard('{Enter}');

      expect(onClick).toHaveBeenCalled();
    });

    test('calls onClick when Space key is pressed', async () => {
      const onClick = jest.fn();
      const user = userEvent.setup();
      const { container } = render(<DecoNodeCard node={mockNode} onClick={onClick} />);

      const card = container.querySelector('.deco-node-card');
      card.focus();
      await user.keyboard(' ');

      expect(onClick).toHaveBeenCalled();
    });
  });

  describe('Missing/Null Data Handling', () => {
    test('handles missing node_name', () => {
      const node = { ...mockNode, node_name: undefined };
      render(<DecoNodeCard node={node} onClick={jest.fn()} />);

      expect(screen.getByText('Unknown Node')).toBeInTheDocument();
    });

    test('handles missing firmware_version', () => {
      const node = { ...mockNode, firmware_version: undefined };
      render(<DecoNodeCard node={node} onClick={jest.fn()} />);

      expect(screen.getByText('Unknown')).toBeInTheDocument();
    });

    test('handles missing model', () => {
      const node = { ...mockNode, model: undefined };
      render(<DecoNodeCard node={node} onClick={jest.fn()} />);

      // Model should not be displayed if undefined
      expect(screen.queryByText('Model')).not.toBeInTheDocument();
    });

    test('handles all fields undefined', () => {
      const node = {
        node_id: 'node1',
        node_name: undefined,
        firmware_version: undefined,
        uptime_seconds: undefined,
        connected_clients: undefined,
        signal_strength: undefined,
        model: undefined,
        status: 'online',
        last_updated: undefined,
      };
      render(<DecoNodeCard node={node} onClick={jest.fn()} />);

      // Should still render without crashing
      expect(screen.getByText('Unknown Node')).toBeInTheDocument();
    });
  });

  describe('CSS Classes', () => {
    test('applies online class for online status', () => {
      const { container } = render(<DecoNodeCard node={mockNode} onClick={jest.fn()} />);

      const card = container.querySelector('.deco-node-card.online');
      expect(card).toBeInTheDocument();
    });

    test('applies offline class for offline status', () => {
      const node = { ...mockNode, status: 'offline' };
      const { container } = render(<DecoNodeCard node={node} onClick={jest.fn()} />);

      const card = container.querySelector('.deco-node-card.offline');
      expect(card).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    test('has proper ARIA label', () => {
      const { container } = render(<DecoNodeCard node={mockNode} onClick={jest.fn()} />);

      const card = container.querySelector('.deco-node-card');
      expect(card).toHaveAttribute('aria-label', 'Deco Node Main Router');
    });

    test('card is keyboard accessible', () => {
      const { container } = render(<DecoNodeCard node={mockNode} onClick={jest.fn()} />);

      const card = container.querySelector('.deco-node-card');
      expect(card).toHaveAttribute('tabIndex', '0');
      expect(card).toHaveAttribute('role', 'button');
    });
  });
});
