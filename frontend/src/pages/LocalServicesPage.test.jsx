import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LocalServicesPage from './LocalServicesPage';

const payload = {
  services: [
    { id: 'api', name: 'HomeSentinel Backend', port: 8443, protocol: 'tcp', pid: 42, process_name: 'python', bind_address: '127.0.0.1', status: 'running', health_status: 'degraded', response_time_ms: 812, uptime_seconds: 3661, connections: 3, expected: true, controllable: true, last_changed: '2026-09-01T12:00:00Z', history: [{ timestamp: 'a', value: 100 }, { timestamp: 'b', value: 812 }] },
    { id: 'mystery', name: 'Unknown listener', port: 9000, protocol: 'tcp', status: 'running', health_status: 'unknown', expected: false, controllable: false, history: [] },
  ],
  summary: { total: 2, healthy: 0, degraded: 1, down: 0, unexpected: 1, conflicts: 0 },
  updated_at: '2026-09-01T12:01:00Z',
};

describe('LocalServicesPage', () => {
  beforeEach(() => {
    global.fetch = jest.fn((url) => Promise.resolve({
      ok: true,
      json: async () => url.endsWith('/events') ? { events: [{ id: 1, event_type: 'service_recovered', service_name: 'Frontend', timestamp: '2026-09-01T12:00:00Z' }] } : payload,
    }));
  });

  afterEach(() => jest.restoreAllMocks());

  test('shows service health separately from process state and summary', async () => {
    render(<LocalServicesPage />);
    expect(await screen.findByRole('heading', { name: 'Local Services' })).toBeInTheDocument();
    expect(screen.getByText('HomeSentinel Backend')).toBeInTheDocument();
    const row = screen.getByText('HomeSentinel Backend').closest('tr');
    expect(within(row).getByText('Running')).toBeInTheDocument();
    expect(within(row).getByText('Degraded')).toBeInTheDocument();
    expect(screen.getByText('Unexpected')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /response time trend/i })).toBeInTheDocument();
  });

  test('filters services by search and status', async () => {
    const user = userEvent.setup();
    render(<LocalServicesPage />);
    await screen.findByText('HomeSentinel Backend');
    await user.type(screen.getByRole('searchbox'), 'unknown');
    expect(screen.queryByText('HomeSentinel Backend')).not.toBeInTheDocument();
    expect(screen.getByText('Unknown listener')).toBeInTheDocument();
    await user.clear(screen.getByRole('searchbox'));
    await user.selectOptions(screen.getByLabelText('Filter by health'), 'degraded');
    expect(screen.getByText('HomeSentinel Backend')).toBeInTheDocument();
    expect(screen.queryByText('Unknown listener')).not.toBeInTheDocument();
  });

  test('confirms and requests an allowed restart', async () => {
    window.confirm = jest.fn(() => true);
    const user = userEvent.setup();
    render(<LocalServicesPage />);
    await user.click(await screen.findByRole('button', { name: 'Restart HomeSentinel Backend' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/local-services/api/restart', expect.objectContaining({ method: 'POST' })));
  });

  test('disables controls for read-only services', async () => {
    render(<LocalServicesPage />);
    expect(await screen.findByRole('button', { name: 'Restart Unknown listener' })).toBeDisabled();
  });
});
