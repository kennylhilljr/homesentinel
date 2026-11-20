import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import DecoWiFiConfigEditor from './DecoWiFiConfigEditor';

// Mock apiConfig module
vi.mock('../utils/apiConfig', () => ({
  buildUrl: vi.fn((endpoint) => `/api${endpoint}`),
  __esModule: true,
}));

// Mock fetch
global.fetch = vi.fn();

describe('DecoWiFiConfigEditor Component', () => {
  const mockWiFiConfig = {
    ssid: 'TestNetwork',
    band_steering_enabled: true,
    timestamp: '2026-03-06T12:00:00Z',
    cache_info: {
      ttl_seconds: 60,
    },
  };

  /**
   * Stateful WiFi API mock: GET returns the current config, a successful PUT
   * applies the change so the component's verification poll succeeds on the
   * first check. `onPut` may return a custom response (or a promise of one).
   */
  const mockWiFiApi = ({ onPut } = {}) => {
    let current = { ...mockWiFiConfig };
    fetch.mockImplementation(async (url, opts = {}) => {
      if (opts.method === 'PUT') {
        if (onPut) return onPut(opts);
        const body = JSON.parse(opts.body);
        current = {
          ...current,
          ...(body.ssid ? { ssid: body.ssid } : {}),
          band_steering_enabled: body.band_steering,
        };
        return { ok: true, json: async () => ({ success: true, updated_config: current }) };
      }
      return { ok: true, json: async () => current };
    });
    return () => current;
  };

  const submitSsidChange = async (newSsid = 'NewNetwork') => {
    await screen.findByDisplayValue('TestNetwork');
    fireEvent.change(screen.getByLabelText(/Network Name/i), { target: { value: newSsid } });
    fireEvent.click(screen.getByRole('button', { name: /Update Configuration/i }));
    await screen.findByText(/Confirm WiFi Configuration Changes/i);
    fireEvent.click(
      within(document.querySelector('.dialog-container')).getByRole('button', {
        name: /Apply Changes/i,
      })
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();
    fetch.mockResolvedValue({
      ok: true,
      json: async () => mockWiFiConfig,
    });
  });

  afterEach(() => {
    vi.resetAllMocks();
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

    // The "Band Steering" label is a visual heading; the checkbox lives in the toggle group
    expect(await screen.findByText('Band Steering')).toBeInTheDocument();
    const group = document.querySelector('.band-steering-group');
    const toggle = within(group).getByRole('checkbox');
    expect(toggle).toBeChecked();
    expect(within(group).getByText('Enabled')).toBeInTheDocument();
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

  test('test_ssid_with_trailing_spaces_within_32_chars_should_pass', async () => {
    render(<DecoWiFiConfigEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('TestNetwork')).toBeInTheDocument();
    });

    const ssidInput = screen.getByLabelText(/Network Name/i);
    const submitButton = screen.getByRole('button', { name: /Update Configuration/i });

    // Set SSID with trailing spaces: "TestNet     " (7 chars + 5 spaces = 12 total, 7 trimmed)
    fireEvent.change(ssidInput, { target: { value: 'TestNet     ' } });

    fireEvent.click(submitButton);

    // Should show confirmation dialog (validation passes)
    await waitFor(() => {
      expect(screen.getByText(/Confirm WiFi Configuration Changes/i)).toBeInTheDocument();
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

    // Inline field error shows as soon as the values differ
    expect(document.querySelector('.field-error')).toHaveTextContent('Passwords do not match');

    fireEvent.click(submitButton);

    // Submitting also surfaces the form-level validation error and no confirm dialog
    await waitFor(() => {
      expect(document.querySelector('.editor-error')).toHaveTextContent('Passwords do not match');
    });
    expect(screen.queryByText(/Confirm WiFi Configuration Changes/i)).not.toBeInTheDocument();
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
    mockWiFiApi();
    render(<DecoWiFiConfigEditor />);

    await submitSsidChange('NewNetwork');

    // Verification resolves ~1s after the first successful poll
    expect(
      await screen.findByText(/WiFi configuration updated successfully/i, {}, { timeout: 4000 })
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue('NewNetwork')).toBeInTheDocument();
  });

  test('test_error_message_displays_on_api_failure', async () => {
    mockWiFiApi({ onPut: () => Promise.reject(new Error('API Error')) });
    render(<DecoWiFiConfigEditor />);

    await submitSsidChange('NewNetwork');

    expect(
      await screen.findByText(/Failed to update WiFi configuration: API Error/i)
    ).toBeInTheDocument();
    expect(screen.queryByText(/WiFi configuration updated successfully/i)).not.toBeInTheDocument();
  });

  // ==================== Verification Polling ====================
  test('test_verification_polling_occurs_after_submit', async () => {
    vi.useFakeTimers();

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
    vi.runAllTimers();

    vi.useRealTimers();
  });

  // ==================== Loading & Disabled States ====================
  test('test_submit_button_disabled_during_submission', async () => {
    let resolvePut;
    mockWiFiApi({
      onPut: () =>
        new Promise((resolve) => {
          resolvePut = resolve;
        }),
    });
    render(<DecoWiFiConfigEditor />);

    await submitSsidChange('NewNetwork');

    // Dialog closes on apply; the main submit button shows a disabled processing state
    const processingButton = await screen.findByRole('button', { name: /Processing/i });
    expect(processingButton).toBeDisabled();
    expect(screen.getByLabelText(/Network Name/i)).toBeDisabled();
    expect(screen.queryByText(/Confirm WiFi Configuration Changes/i)).not.toBeInTheDocument();

    // Finish the request so the component settles before teardown
    resolvePut({ ok: false, statusText: 'Bad Request', json: async () => ({ detail: 'nope' }) });
    expect(await screen.findByText(/Failed to update WiFi configuration: nope/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Update Configuration/i })).not.toBeDisabled();
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
    const mockCallback = vi.fn();
    mockWiFiApi();

    render(<DecoWiFiConfigEditor onConfigUpdated={mockCallback} />);

    await submitSsidChange('NewNetwork');

    await waitFor(
      () => {
        expect(mockCallback).toHaveBeenCalledWith(
          expect.objectContaining({ ssid: 'NewNetwork', band_steering_enabled: true })
        );
      },
      { timeout: 4000 }
    );
  });
});
