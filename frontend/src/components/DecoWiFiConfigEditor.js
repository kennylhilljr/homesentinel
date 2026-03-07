import React, { useState, useEffect } from 'react';
import { buildUrl } from '../utils/apiConfig';
import './DecoWiFiConfigEditor.css';

/**
 * DecoWiFiConfigEditor Component
 * Provides a form to edit WiFi configuration (SSID, password, band steering)
 * Includes confirmation dialog and verification polling
 */
function DecoWiFiConfigEditor({ onConfigUpdated = null }) {
  // Form state
  const [ssid, setSsid] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [bandSteering, setBandSteering] = useState(false);

  // UI state
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationMessage, setVerificationMessage] = useState(null);

  // Pending changes (stored when confirmation is triggered)
  const [pendingChanges, setPendingChanges] = useState(null);

  // Load current WiFi config on mount
  useEffect(() => {
    fetchCurrentConfig();
  }, []);

  // Clear success message after 5 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  const fetchCurrentConfig = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(buildUrl('/deco/wifi-config'), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch WiFi config: ${response.statusText}`);
      }

      const data = await response.json();
      setSsid(data.ssid || '');
      setBandSteering(data.band_steering_enabled || false);
      // Don't load password (security - it's not returned by API)
      setPassword('');
      setConfirmPassword('');
    } catch (err) {
      console.error('Error fetching WiFi config:', err);
      setError(`Failed to load current WiFi configuration: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const validateInputs = () => {
    // At least one field must be changed
    const hasChanges =
      ssid.trim().length > 0 ||
      password.length > 0 ||
      confirmPassword.length > 0;

    if (!hasChanges) {
      setError('No changes to apply. Please modify at least one setting.');
      return false;
    }

    // Validate SSID if provided
    if (ssid.trim().length > 0) {
      if (ssid.length < 1 || ssid.length > 32) {
        setError('SSID must be between 1 and 32 characters');
        return false;
      }
    }

    // Validate password if provided
    if (password.length > 0) {
      if (password.length < 8) {
        setError('Password must be at least 8 characters');
        return false;
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match');
        return false;
      }
    }

    return true;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError(null);

    if (!validateInputs()) {
      return;
    }

    // Show confirmation dialog
    setPendingChanges({
      ssid: ssid.trim().length > 0 ? ssid.trim() : null,
      password: password.length > 0 ? password : null,
      band_steering: bandSteering,
    });
    setShowConfirmDialog(true);
  };

  const confirmAndSubmit = async () => {
    setShowConfirmDialog(false);

    if (!pendingChanges) return;

    try {
      setSubmitting(true);
      setError(null);
      setSuccessMessage(null);
      setVerificationMessage('Submitting configuration...');
      setIsVerifying(true);

      // Submit the update
      const response = await fetch(buildUrl('/deco/wifi-config'), {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ssid: pendingChanges.ssid,
          password: pendingChanges.password,
          band_steering: pendingChanges.band_steering,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `Failed to update WiFi config: ${response.statusText}`
        );
      }

      const result = await response.json();
      setVerificationMessage('Configuration submitted. Verifying changes...');

      // Poll to verify changes were applied (every 5 seconds for up to 30 seconds)
      await verifyConfigChanges(pendingChanges, 30000);

      // Update form with new values
      if (pendingChanges.ssid) setSsid(pendingChanges.ssid);
      setPassword('');
      setConfirmPassword('');
      if (pendingChanges.band_steering !== null) {
        setBandSteering(pendingChanges.band_steering);
      }

      setSuccessMessage('WiFi configuration updated successfully!');
      setIsVerifying(false);
      setVerificationMessage(null);

      // Call callback if provided
      if (onConfigUpdated) {
        onConfigUpdated(result.updated_config);
      }
    } catch (err) {
      console.error('Error updating WiFi config:', err);
      setError(`Failed to update WiFi configuration: ${err.message}`);
      setIsVerifying(false);
      setVerificationMessage(null);
    } finally {
      setSubmitting(false);
      setPendingChanges(null);
    }
  };

  const verifyConfigChanges = async (changes, maxWaitMs) => {
    const pollInterval = 5000; // 5 seconds
    const startTime = Date.now();

    return new Promise((resolve, reject) => {
      const pollChanges = async () => {
        try {
          const response = await fetch(buildUrl('/deco/wifi-config'), {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
            },
          });

          if (!response.ok) {
            throw new Error(`Failed to verify: ${response.statusText}`);
          }

          const currentConfig = await response.json();
          const elapsed = Date.now() - startTime;

          // Check if changes were applied
          let allChangesApplied = true;

          if (changes.ssid && currentConfig.ssid !== changes.ssid) {
            allChangesApplied = false;
            setVerificationMessage(
              `Verifying SSID change... (${Math.round(elapsed / 1000)}s elapsed)`
            );
          }

          if (
            changes.band_steering !== null &&
            currentConfig.band_steering_enabled !== changes.band_steering
          ) {
            allChangesApplied = false;
            setVerificationMessage(
              `Verifying band steering change... (${Math.round(elapsed / 1000)}s elapsed)`
            );
          }

          if (allChangesApplied) {
            setVerificationMessage('Configuration verified successfully!');
            setTimeout(() => {
              setVerificationMessage(null);
              resolve();
            }, 1000);
            return;
          }

          // Check timeout
          if (elapsed >= maxWaitMs) {
            setVerificationMessage(
              'Verification timed out. Changes may still be applying.'
            );
            setTimeout(() => {
              setVerificationMessage(null);
              resolve();
            }, 2000);
            return;
          }

          // Poll again
          setTimeout(pollChanges, pollInterval);
        } catch (err) {
          console.error('Error during verification:', err);
          setVerificationMessage(null);
          // Don't reject on verification error, just proceed
          resolve();
        }
      };

      pollChanges();
    });
  };

  const cancelConfirm = () => {
    setShowConfirmDialog(false);
    setPendingChanges(null);
  };

  const handleReset = () => {
    setError(null);
    setSuccessMessage(null);
    setVerificationMessage(null);
    setShowConfirmDialog(false);
    setPendingChanges(null);
    fetchCurrentConfig();
  };

  if (loading) {
    return (
      <div className="wifi-config-editor">
        <div className="editor-loading">
          <div className="spinner"></div>
          <p>Loading WiFi configuration...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="wifi-config-editor">
      <div className="editor-container">
        <h2>WiFi Configuration Editor</h2>
        <p className="editor-description">
          Update your network SSID, password, and band steering settings
        </p>

        {error && (
          <div className="editor-error">
            <div className="error-icon">!</div>
            <div className="error-text">{error}</div>
          </div>
        )}

        {successMessage && (
          <div className="editor-success">
            <div className="success-icon">✓</div>
            <div className="success-text">{successMessage}</div>
          </div>
        )}

        {isVerifying && verificationMessage && (
          <div className="editor-verifying">
            <div className="verifying-icon">⟳</div>
            <div className="verifying-text">{verificationMessage}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="editor-form">
          {/* SSID Field */}
          <div className="form-group">
            <label htmlFor="ssid" className="form-label">
              Network Name (SSID) *
              <span className="field-optional"> (optional to change)</span>
            </label>
            <input
              id="ssid"
              type="text"
              placeholder="Leave blank to keep current SSID"
              value={ssid}
              onChange={(e) => {
                setSsid(e.target.value);
                setError(null);
              }}
              disabled={submitting || isVerifying}
              className="form-input"
              maxLength="32"
            />
            <div className="field-hint">
              Current SSID shown above. 1-32 characters.
            </div>
          </div>

          {/* Password Field */}
          <div className="form-group">
            <label htmlFor="password" className="form-label">
              WiFi Password
              <span className="field-optional"> (optional to change)</span>
            </label>
            <input
              id="password"
              type="password"
              placeholder="Leave blank to keep current password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setError(null);
              }}
              disabled={submitting || isVerifying}
              className="form-input"
            />
            <div className="field-hint">
              Minimum 8 characters. Only set if changing password.
            </div>
          </div>

          {/* Confirm Password Field */}
          {password.length > 0 && (
            <div className="form-group">
              <label htmlFor="confirmPassword" className="form-label">
                Confirm Password *
              </label>
              <input
                id="confirmPassword"
                type="password"
                placeholder="Confirm new password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value);
                  setError(null);
                }}
                disabled={submitting || isVerifying}
                className="form-input"
              />
              {confirmPassword && password !== confirmPassword && (
                <div className="field-error">Passwords do not match</div>
              )}
            </div>
          )}

          {/* Band Steering Toggle */}
          <div className="form-group band-steering-group">
            <label className="form-label">Band Steering</label>
            <div className="toggle-container">
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={bandSteering}
                  onChange={(e) => setBandSteering(e.target.checked)}
                  disabled={submitting || isVerifying}
                />
                <span className="toggle-slider"></span>
              </label>
              <span className="toggle-label">
                {bandSteering ? 'Enabled' : 'Disabled'}
              </span>
            </div>
            <div className="field-hint">
              Band steering automatically moves devices between 2.4 GHz and 5 GHz bands
            </div>
          </div>

          {/* Form Actions */}
          <div className="form-actions">
            <button
              type="submit"
              disabled={submitting || isVerifying || loading}
              className="btn btn-primary"
            >
              {submitting || isVerifying ? 'Processing...' : 'Update Configuration'}
            </button>
            <button
              type="button"
              onClick={handleReset}
              disabled={submitting || isVerifying || loading}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>

      {/* Confirmation Dialog */}
      {showConfirmDialog && (
        <div className="dialog-overlay">
          <div className="dialog-container">
            <div className="dialog-header">
              <h3>Confirm WiFi Configuration Changes</h3>
            </div>

            <div className="dialog-body">
              <p>You are about to apply the following changes:</p>

              <div className="changes-list">
                {pendingChanges.ssid && (
                  <div className="change-item">
                    <span className="change-label">SSID:</span>
                    <span className="change-value">{pendingChanges.ssid}</span>
                  </div>
                )}

                {pendingChanges.password && (
                  <div className="change-item">
                    <span className="change-label">Password:</span>
                    <span className="change-value">
                      {'●'.repeat(pendingChanges.password.length)}
                    </span>
                  </div>
                )}

                <div className="change-item">
                  <span className="change-label">Band Steering:</span>
                  <span className="change-value">
                    {pendingChanges.band_steering ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              </div>

              <p className="dialog-warning">
                <strong>Note:</strong> Changes will take effect within 30 seconds.
                Connected devices may experience a brief disconnection.
              </p>
            </div>

            <div className="dialog-actions">
              <button
                onClick={confirmAndSubmit}
                className="btn btn-primary"
                disabled={submitting}
              >
                {submitting ? 'Applying...' : 'Apply Changes'}
              </button>
              <button
                onClick={cancelConfirm}
                className="btn btn-secondary"
                disabled={submitting}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DecoWiFiConfigEditor;
