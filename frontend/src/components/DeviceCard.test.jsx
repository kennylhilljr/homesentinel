import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import DeviceCard from './DeviceCard';

describe('DeviceCard Component', () => {
  const mockDevice = {
    device_id: 'test-device-1',
    mac_address: '00:11:22:33:44:55',
    current_ip: '192.168.1.100',
    friendly_name: 'Living Room TV',
    vendor_name: 'Samsung Electronics',
    device_type: 'tv',
    status: 'online',
    device_group_ids: ['group-1', 'group-2'],
  };

  const mockGroups = [
    { group_id: 'group-1', name: 'Living Room', color: '#3498db' },
    { group_id: 'group-2', name: 'Smart Devices', color: '#2ecc71' },
  ];

  const mockOnClick = jest.fn();

  beforeEach(() => {
    mockOnClick.mockClear();
  });

  test('test_device_card_renders', () => {
    render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    expect(screen.getByText('Living Room TV')).toBeInTheDocument();
    expect(screen.getByText('192.168.1.100')).toBeInTheDocument();
  });

  test('test_device_card_displays_mac_address', () => {
    render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    expect(screen.getByText('00:11:22:33:44:55')).toBeInTheDocument();
  });

  test('test_device_card_displays_vendor_name', () => {
    render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    expect(screen.getByText('Samsung Electronics')).toBeInTheDocument();
  });

  test('test_device_card_displays_device_type', () => {
    render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    expect(screen.getByText('tv')).toBeInTheDocument();
  });

  test('test_online_offline_indicator', () => {
    const { container } = render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    expect(screen.getByText('Online')).toBeInTheDocument();
    const deviceCard = container.querySelector('.device-card-online');
    expect(deviceCard).toBeInTheDocument();
  });

  test('test_offline_status_indicator', () => {
    const offlineDevice = { ...mockDevice, status: 'offline' };
    const { container } = render(
      <DeviceCard
        device={offlineDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    expect(screen.getByText('Offline')).toBeInTheDocument();
    const deviceCard = container.querySelector('.device-card-offline');
    expect(deviceCard).toBeInTheDocument();
  });

  test('test_device_card_click_opens_detail', () => {
    render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    const card = screen.getByRole('button');
    fireEvent.click(card);

    expect(mockOnClick).toHaveBeenCalledTimes(1);
  });

  test('test_device_card_keyboard_enter_triggers_click', () => {
    render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    const card = screen.getByRole('button');
    fireEvent.keyDown(card, { key: 'Enter' });

    expect(mockOnClick).toHaveBeenCalledTimes(1);
  });

  test('test_device_card_keyboard_space_triggers_click', () => {
    render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    const card = screen.getByRole('button');
    fireEvent.keyDown(card, { key: ' ' });

    expect(mockOnClick).toHaveBeenCalledTimes(1);
  });

  test('test_group_badges_display', () => {
    const { container } = render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    const groupBadges = container.querySelectorAll('.group-badge');
    expect(groupBadges).toHaveLength(2);
  });

  test('test_device_card_uses_mac_as_fallback_name', () => {
    const deviceNoFriendlyName = { ...mockDevice, friendly_name: '' };
    const { container } = render(
      <DeviceCard
        device={deviceNoFriendlyName}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    const nameCard = container.querySelector('.device-name-card');
    expect(nameCard).toHaveTextContent('00:11:22:33:44:55');
  });

  test('test_device_card_handles_missing_vendor', () => {
    const deviceNoVendor = { ...mockDevice, vendor_name: null };
    const { container } = render(
      <DeviceCard
        device={deviceNoVendor}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    const vendorBadge = container.querySelector('.vendor-badge');
    expect(vendorBadge).not.toBeInTheDocument();
  });

  test('test_device_card_handles_missing_device_type', () => {
    const deviceNoType = { ...mockDevice, device_type: null };
    const { container } = render(
      <DeviceCard
        device={deviceNoType}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    const typeBadge = container.querySelector('.type-badge');
    expect(typeBadge).not.toBeInTheDocument();
  });

  test('test_device_card_handles_empty_groups', () => {
    const deviceNoGroups = { ...mockDevice, device_group_ids: [] };
    const { container } = render(
      <DeviceCard
        device={deviceNoGroups}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    const groupBadges = container.querySelectorAll('.group-badge');
    expect(groupBadges).toHaveLength(0);
  });

  test('test_device_card_missing_ip_shows_na', () => {
    const deviceNoIP = { ...mockDevice, current_ip: null };
    render(
      <DeviceCard
        device={deviceNoIP}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  test('test_device_card_has_correct_aria_label', () => {
    render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    const card = screen.getByRole('button');
    expect(card).toHaveAttribute('aria-label', 'Device Living Room TV');
  });

  test('test_device_card_hover_effects_present', () => {
    const { container } = render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    const card = container.querySelector('.device-card');
    expect(card).toHaveClass('device-card-online');
  });

  test('test_no_console_errors', () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    render(
      <DeviceCard
        device={mockDevice}
        groups={mockGroups}
        onClick={mockOnClick}
      />
    );

    expect(consoleSpy).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
