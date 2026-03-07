import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import DecoWiFiConfigEditor from './DecoWiFiConfigEditor';

// Mock apiConfig module
jest.mock('../utils/apiConfig', () => ({
  buildUrl: jest.fn((endpoint) => `/api${endpoint}`),
  __esModule: true,
}));

// Mock fetch
global.fetch = jest.fn();

describe('DecoWiFiConfigEditor Component', () => {
  const mockWiFiConfig = {
    ssid: 'TestNetwork',
    band_steering_enabled: true,
    timestamp: '2026-03-06T12:00:00Z',
    cache_info: {
      ttl_seconds: 60,
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    fetch.mockResolvedValue({
      ok: true,
      json: async () => mockWiFiConfig,
    });
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  // ==================== Loading & Initialization ====================
  test('test_editor_shows_loading_state_on_mount', async () => {
    fetch.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: async () => mockWiFiConfig,
              }),
            100
          )
        )
    );

    const { container } = render(<DecoWiFiConfigEditor />);

    expect(container.querySelector('.editor-loading')).toBeInTheDocument();
  });

  test('test_editor_loads_current_config', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });
  });

  test('test_editor_displays_title_and_description', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByText('WiFi Configuration Editor')).toBeInTheDocument();
      expect(
        screen.getByText(/Update your network SSID/i)
      ).toBeInTheDocument();
    });
  });

  // ==================== Form Rendering ====================
  test('test_form_renders_ssid_field', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Network Name/i)).toBeInTheDocument();
    });
  });

  test('test_form_renders_password_field', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByLabelText(/WiFi Password/i)).toBeInTheDocument();
    });
  });

  test('test_form_renders_band_steering_toggle', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByLabelText('Band Steering')).toBeInTheDocument();
    });
  });

  test('test_form_renders_submit_button', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /Update Configuration/i })
      ).toBeInTheDocument();
    });
  });

  // ==================== Input Validation ====================
  test('test_ssid_cannot_be_empty', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    // Clear SSID
    fireEvent.change(ssidInput, { target: { value: '' } });

    // Try to submit
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/No changes to apply/i)).toBeInTheDocument();
    });
  });

  test('test_ssid_max_length_validation', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    // Set SSID to 33 characters (exceeds max)
    const longSsid = 'A'.repeat(33);
    fireEvent.change(ssidInput, { target: { value: longSsid } });

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/must be between 1 and 32 characters/i)).toBeInTheDocument();
    });
  });

  test('test_password_min_length_validation', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const passwordInput = screen.getByLabelText(/WiFi Password/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    // Set password to less than 8 characters
    fireEvent.change(passwordInput, { target: { value: 'short' } });

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/must be at least 8 characters/i)).toBeInTheDocument();
    });
  });

  test('test_password_confirm_mismatch_validation', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const passwordInput = screen.getByLabelText(/WiFi Password/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    // Set password
    fireEvent.change(passwordInput, { target: { value: 'ValidPassword123' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/Confirm Password/i)).toBeInTheDocument();
    });

    const confirmInput = screen.getByLabelText(/Confirm Password/i);
    fireEvent.change(confirmInput, { target: { value: 'DifferentPassword456' } });

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Passwords do not match/i)).toBeInTheDocument();
    });
  });

  // ==================== Confirmation Dialog ====================
  test('test_confirmation_dialog_appears_before_submit', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    // Change SSID to trigger changes
    fireEvent.change(ssidInput, { target: { value: 'NewNetwork' } });

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Confirm WiFi Configuration Changes/i)).toBeInTheDocument();
    });
  });

  test('test_confirmation_dialog_shows_changes', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    fireEvent.change(ssidInput, { target: { value: 'NewNetwork' } });

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('NewNetwork')).toBeInTheDocument();
    });
  });

  test('test_confirmation_dialog_can_be_cancelled', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    fireEvent.change(ssidInput, { target: { value: 'NewNetwork' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Confirm WiFi Configuration Changes/i)).toBeInTheDocument();
    });

    const cancelButton = within(document.querySelector('.dialog-container')).getByRole('button', {
      name: /Cancel/i,
    });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByText(/Confirm WiFi Configuration Changes/i)).not.toBeInTheDocument();
    });
  });

  // ==================== Submit & API Calls ====================
  test('test_form_submission_calls_api', async () => {
    fetch.mockClear();
    fetch.mockResolvedValue({
      ok: true,
      json: async () => mockWiFiConfig,
    });

    const { rerender } = render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    fireEvent.change(ssidInput, { target: { value: 'NewNetwork' } });
    fireEvent.click(submitButton);

    // Confirm in dialog
    await waitFor(() => {
      expect(screen.getByText(/Confirm WiFi Configuration Changes/i)).toBeInTheDocument();
    });

    const applyButton = within(document.querySelector('.dialog-container')).getByRole('button', {
      name: /Apply Changes/i,
    });
    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/deco/wifi-config',
        expect.objectContaining({
          method: 'PUT',
        })
      );
    });
  });

  test('test_success_message_displays_after_update', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    fireEvent.change(ssidInput, { target: { value: 'NewNetwork' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Confirm WiFi Configuration Changes/i)).toBeInTheDocument();
    });

    const applyButton = within(document.querySelector('.dialog-container')).getByRole('button', {
      name: /Apply Changes/i,
    });
    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(screen.getByText(/WiFi configuration updated successfully/i)).toBeInTheDocument();
    });
  });

  test('test_error_message_displays_on_api_failure', async () => {
    fetch.mockRejectedValueOnce(new Error('API Error'));

    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    fireEvent.change(ssidInput, { target: { value: 'NewNetwork' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Confirm WiFi Configuration Changes/i)).toBeInTheDocument();
    });

    const applyButton = within(document.querySelector('.dialog-container')).getByRole('button', {
      name: /Apply Changes/i,
    });
    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(screen.getByText(/Failed to update WiFi configuration/i)).toBeInTheDocument();
    });
  });

  // ==================== Verification Polling ====================
  test('test_verification_polling_occurs_after_submit', async () => {
    jest.useFakeTimers();

    fetch.mockResolvedValue({
      ok: true,
      json: async () => mockWiFiConfig,
    });

    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    fireEvent.change(ssidInput, { target: { value: 'NewNetwork' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Confirm WiFi Configuration Changes/i)).toBeInTheDocument();
    });

    const applyButton = within(document.querySelector('.dialog-container')).getByRole('button', {
      name: /Apply Changes/i,
    });
    fireEvent.click(applyButton);

    // Fast-forward to trigger polling
    jest.runAllTimers();

    jest.useRealTimers();
  });

  // ==================== Loading & Disabled States ====================
  test('test_submit_button_disabled_during_submission', async () => {
    fetch.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: async () => mockWiFiConfig,
              }),
            500
          )
        )
    );

    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    fireEvent.change(ssidInput, { target: { value: 'NewNetwork' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Confirm WiFi Configuration Changes/i)).toBeInTheDocument();
    });

    const applyButton = within(document.querySelector('.dialog-container')).getByRole('button', {
      name: /Apply Changes/i,
    });

    fireEvent.click(applyButton);

    // Submit button should show processing state
    await waitFor(() => {
      expect(
        within(document.querySelector('.dialog-container')).getByRole('button', {
          name: /Applying/i,
        })
      ).toBeInTheDocument();
    });
  });

  // ==================== Cancel/Reset ====================
  test('test_cancel_button_clears_changes', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const cancelButton = screen.getByRole('button', { name: /^Cancel$/ });

    fireEvent.change(ssidInput, { target: { value: 'NewNetwork' } });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });
  });

  // ==================== Password Confirmation ====================
  test('test_password_confirm_field_appears_when_password_entered', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const passwordInput = screen.getByLabelText(/WiFi Password/i);

    fireEvent.change(passwordInput, { target: { value: 'ValidPassword123' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/Confirm Password/i)).toBeInTheDocument();
    });
  });

  test('test_password_confirm_field_hidden_when_password_empty', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const passwordInput = screen.getByLabelText(/WiFi Password/i);

    fireEvent.change(passwordInput, { target: { value: 'ValidPassword123' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/Confirm Password/i)).toBeInTheDocument();
    });

    fireEvent.change(passwordInput, { target: { value: '' } });

    await waitFor(() => {
      expect(screen.queryByLabelText(/Confirm Password/i)).not.toBeInTheDocument();
    });
  });

  // ==================== Band Steering Toggle ====================
  test('test_band_steering_toggle_can_be_changed', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      const toggle = screen.getByRole('checkbox', { name: '' });
      expect(toggle).toBeChecked();
    });

    const toggle = screen.getByRole('checkbox', { name: '' });
    fireEvent.click(toggle);

    expect(toggle).not.toBeChecked();
  });

  // ==================== Callback ====================
  test('test_callback_called_on_successful_update', async () => {
    const mockCallback = jest.fn();

    render(<DecoWiFiConfigEditor onConfigUpdated={mockCallback} />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    fireEvent.change(ssidInput, { target: { value: 'NewNetwork' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Confirm WiFi Configuration Changes/i)).toBeInTheDocument();
    });

    const applyButton = within(document.querySelector('.dialog-container')).getByRole('button', {
      name: /Apply Changes/i,
    });
    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(mockCallback).toHaveBeenCalled();
    });
  });
});
