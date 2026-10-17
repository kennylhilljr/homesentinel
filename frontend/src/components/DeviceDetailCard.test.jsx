import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import DeviceDetailCard from './DeviceDetailCard';

// Mock fetch
global.fetch = jest.fn();

describe('DeviceDetailCard Component', () => {
  const mockDevice = {
    device_id: 'test-device-1',
    mac_address: '00:11:22:33:44:55',
    current_ip: '192.168.1.100',
    ip_history: ['192.168.1.50', '192.168.1.100'],
    friendly_name: 'Living Room TV',
    vendor_name: 'Samsung Electronics',
    device_type: 'tv',
    hostname: 'samsung-tv.local',
    status: 'online',
    first_seen: '2024-01-01T10:00:00Z',
    last_seen: '2024-01-06T15:30:00Z',
    device_group_ids: ['group-1'],
    notes: 'Main entertainment device',
  };

  const mockGroups = [
    { group_id: 'group-1', name: 'Living Room', color: '#3498db' },
  ];

  const mockOnClose = jest.fn();
  const mockOnUpdate = jest.fn();

  beforeEach(() => {
    fetch.mockClear();
    mockOnClose.mockClear();
    mockOnUpdate.mockClear();
  });

  test('test_detail_card_renders', () => {
    render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    expect(screen.getByText('Device Details')).toBeInTheDocument();
  });

  test('test_detail_card_shows_all_fields', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    // Core Information - check they're in the document with getAllByText or container queries
    const allText = container.textContent;
    expect(allText).toContain('test-device-1');
    expect(allText).toContain('00:11:22:33:44:55');
    expect(allText).toContain('192.168.1.100');
    expect(allText).toContain('samsung-tv.local');

    // Classification
    expect(allText).toContain('Samsung Electronics');
    expect(container.querySelector('.detail-card-subtitle')).toHaveTextContent('Living Room TV');
    const typeBadge = container.querySelector('.type-badge');
    expect(typeBadge).toHaveTextContent('tv');

    // Status - check the header status indicator
    const statusElement = container.querySelector('.detail-card-status.status-online');
    expect(statusElement).toBeInTheDocument();
  });

  test('test_detail_card_shows_device_id', () => {
    render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    expect(screen.getByText('test-device-1')).toBeInTheDocument();
  });

  test('test_detail_card_shows_mac_address', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    // Find all monospace values and check one contains MAC
    const monospaceValues = container.querySelectorAll('.detail-value.monospace');
    const macFound = Array.from(monospaceValues).some(el => el.textContent === '00:11:22:33:44:55');
    expect(macFound).toBe(true);
  });

  test('test_detail_card_shows_current_ip', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    // Find the current IP in the core information section
    const monospaceValues = container.querySelectorAll('.detail-value.monospace');
    const ipFound = Array.from(monospaceValues).some(el => el.textContent === '192.168.1.100');
    expect(ipFound).toBe(true);
  });

  test('test_detail_card_shows_ip_history', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const ipHistory = container.querySelector('.ip-history-list');
    expect(ipHistory).toBeInTheDocument();
    expect(ipHistory).toHaveTextContent('192.168.1.50');
  });

  test('test_detail_card_shows_hostname', () => {
    render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    expect(screen.getByText('samsung-tv.local')).toBeInTheDocument();
  });

  test('test_detail_card_shows_vendor', () => {
    render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    expect(screen.getByText('Samsung Electronics')).toBeInTheDocument();
  });

  test('test_detail_card_shows_friendly_name', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const subtitle = container.querySelector('.detail-card-subtitle');
    expect(subtitle).toHaveTextContent('Living Room TV');
  });

  test('test_detail_card_shows_device_type', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const typeBadge = container.querySelector('.type-badge');
    expect(typeBadge).toHaveTextContent('tv');
  });

  test('test_detail_card_shows_status', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const statusBadge = container.querySelector('.status-badge.status-online');
    expect(statusBadge).toBeInTheDocument();
  });

  test('test_detail_card_shows_groups', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const groupName = container.querySelector('.group-name');
    expect(groupName).toHaveTextContent('Living Room');
  });

  test('test_detail_card_shows_first_seen', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    // Check that first_seen is displayed
    const firstSeenLabel = Array.from(container.querySelectorAll('.detail-label')).find(
      el => el.textContent === 'First Seen'
    );
    expect(firstSeenLabel).toBeInTheDocument();
  });

  test('test_detail_card_shows_notes', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const notesDisplay = container.querySelector('.notes-display');
    expect(notesDisplay).toHaveTextContent('Main entertainment device');
  });

  test('test_detail_card_close_button_works', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const closeButton = container.querySelector('.btn-close');
    fireEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  test('test_detail_card_x_button_works', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const xButton = container.querySelector('.detail-card-close');
    fireEvent.click(xButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  test('test_overlay_click_closes_card', () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const overlay = container.querySelector('.detail-card-overlay');
    fireEvent.click(overlay);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  test('test_edit_friendly_name_inline', async () => {
    render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]); // First edit button is for friendly name

    const input = screen.getByDisplayValue('Living Room TV');
    expect(input).toBeInTheDocument();
  });

  test('test_edit_friendly_name_saves', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...mockDevice, friendly_name: 'New Name' }),
    });

    render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    const input = screen.getByDisplayValue('Living Room TV');
    fireEvent.change(input, { target: { value: 'New Name' } });

    const saveButton = screen.getByText('Save');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        `https://localhost:8443/api/devices/${mockDevice.device_id}`,
        expect.any(Object)
      );
    });
  });

  test('test_edit_device_type_inline', async () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[1]); // Second edit button is for device type

    const select = container.querySelector('select');
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue('tv');
  });

  test('test_edit_device_type_saves', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...mockDevice, device_type: 'camera' }),
    });

    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[1]);

    const select = container.querySelector('select');
    fireEvent.change(select, { target: { value: 'camera' } });

    const saveButtons = screen.getAllByText('Save');
    fireEvent.click(saveButtons[0]);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });
  });

  test('test_edit_notes_inline', async () => {
    render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[2]); // Third edit button is for notes

    const textarea = screen.getByDisplayValue('Main entertainment device');
    expect(textarea).toBeInTheDocument();
  });

  test('test_cancel_edit_reverts_changes', async () => {
    const { container } = render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    const input = screen.getByDisplayValue('Living Room TV');
    fireEvent.change(input, { target: { value: 'Changed Name' } });

    const cancelButtons = screen.getAllByText('Cancel');
    fireEvent.click(cancelButtons[0]);

    // Check that the input is gone and normal view is back
    const subtitle = container.querySelector('.detail-card-subtitle');
    expect(subtitle).toHaveTextContent('Living Room TV');
  });

  test('test_api_call_on_update', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...mockDevice, friendly_name: 'Updated Name' }),
    });

    render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    const input = screen.getByDisplayValue('Living Room TV');
    fireEvent.change(input, { target: { value: 'Updated Name' } });

    const saveButton = screen.getByText('Save');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/devices/'),
        expect.objectContaining({
          method: 'PUT',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });
  });

  test('test_update_callback_called_after_save', async () => {
    const updatedDevice = { ...mockDevice, friendly_name: 'Updated Name' };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => updatedDevice,
    });

    render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    const input = screen.getByDisplayValue('Living Room TV');
    fireEvent.change(input, { target: { value: 'Updated Name' } });

    const saveButton = screen.getByText('Save');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockOnUpdate).toHaveBeenCalledWith(updatedDevice);
    });
  });

  test('test_offline_status_display', () => {
    const offlineDevice = { ...mockDevice, status: 'offline' };
    const { container } = render(
      <DeviceDetailCard
        device={offlineDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    // Check that status badge shows Offline
    const statusBadge = container.querySelector('.status-badge.status-offline');
    expect(statusBadge).toBeInTheDocument();
  });

  test('test_no_console_errors', () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    render(
      <DeviceDetailCard
        device={mockDevice}
        groups={mockGroups}
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    );

    expect(consoleSpy).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
