import { render, screen, waitFor } from '@testing-library/react';
import App from './App';

// Mock fetch globally
global.fetch = jest.fn();

describe('App Component', () => {
  beforeEach(() => {
    fetch.mockClear();
  });

  test('renders without crashing', () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [], total: 0 })
    });

    render(<App />);
    const heading = screen.getByText(/HomeSentinel/i);
    expect(heading).toBeInTheDocument();
  });

  test('renders title and subtitle', () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [], total: 0 })
    });

    render(<App />);
    expect(screen.getByText(/HomeSentinel/i)).toBeInTheDocument();
    expect(screen.getByText(/Home Network Monitor/i)).toBeInTheDocument();
  });

  test('calls API health endpoint on mount', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [], total: 0 })
    });

    render(<App />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        'https://localhost:8443/api/health',
        expect.any(Object)
      );
    });
  });

  test('calls API devices endpoint on mount', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [], total: 0 })
    });

    render(<App />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        'https://localhost:8443/api/devices',
        expect.any(Object)
      );
    });
  });

  test('displays API status as "connected" when health check succeeds', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [], total: 0 })
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/connected/i)).toBeInTheDocument();
    });
  });

  test('displays API status as "disconnected" when health check fails', async () => {
    fetch.mockRejectedValueOnce(new Error('Network error'));
    fetch.mockRejectedValueOnce(new Error('Network error'));

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/disconnected/i)).toBeInTheDocument();
    });
  });

  test('displays empty devices list initially', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [], total: 0 })
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/No devices discovered yet/i)).toBeInTheDocument();
    });
  });

  test('handles API error gracefully', async () => {
    // First fetch succeeds (health)
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    // Second fetch fails (devices)
    fetch.mockRejectedValueOnce(new Error('Failed to fetch'));

    // Should not throw
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/No devices discovered yet/i)).toBeInTheDocument();
    });
  });

  test('handles malformed API response', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}) // Missing devices field
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/No devices discovered yet/i)).toBeInTheDocument();
    });
  });

  test('renders device items when devices are returned', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        devices: [
          { name: 'Router', mac_address: '00:11:22:33:44:55' },
          { name: 'Camera', mac_address: '00:11:22:33:44:66' }
        ],
        total: 2
      })
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Router/i)).toBeInTheDocument();
      expect(screen.getByText(/Camera/i)).toBeInTheDocument();
    });
  });

  test('displays backend URL information', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [], total: 0 })
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/https:\/\/localhost:8443/i)).toBeInTheDocument();
      expect(screen.getByText(/http:\/\/localhost:2026/i)).toBeInTheDocument();
    });
  });

  test('no console errors on initial render', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'HomeSentinel Backend' })
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [], total: 0 })
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/HomeSentinel/i)).toBeInTheDocument();
    });

    expect(consoleSpy).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
