import React, { useState, useEffect } from 'react';
import { buildUrl } from '../utils/apiConfig';
import './DecoWiFiConfigEditor.css';

export const WIFI_CHANGES_UNSUPPORTED_MESSAGE =
  "WiFi changes aren't supported yet; change them in the Deco app";

/**
 * DecoWiFiConfigEditor Component
 * Shows the current WiFi configuration (SSID, band steering) read-only.
 * WiFi changes are not supported yet (the backend PUT returns 501), so there
 * is no save action; users change these settings in the Deco app.
 */
function DecoWiFiConfigEditor() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCurrentConfig();
  }, []);

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

      setConfig(await response.json());
    } catch (err) {
      console.error('Error fetching WiFi config:', err);
      setError(`Failed to load current WiFi configuration: ${err.message}`);
    } finally {
      setLoading(false);
    }
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

  const bandSteering = Boolean(config?.band_steering_enabled);

  return (
    <div className="wifi-config-editor">
      <div className="editor-container">
        <h2>WiFi Configuration</h2>
        <p className="editor-description">
          Current network SSID and band steering settings (read-only)
        </p>

        <div className="editor-notice" role="status">
          <div className="notice-icon">i</div>
          <div className="notice-text">{WIFI_CHANGES_UNSUPPORTED_MESSAGE}</div>
        </div>

        {error && (
          <div className="editor-error">
            <div className="error-icon">!</div>
            <div className="error-text">{error}</div>
          </div>
        )}

        {config && (
          <div className="editor-readonly">
            <div className="form-group">
              <span className="form-label">Network Name (SSID)</span>
              <p className="readonly-value ssid-value">{config.ssid || 'Unknown'}</p>
            </div>

            <div className="form-group band-steering-group">
              <span className="form-label">Band Steering</span>
              <p className="readonly-value band-steering-value">
                {bandSteering ? 'Enabled' : 'Disabled'}
              </p>
              <div className="field-hint">
                Band steering automatically moves devices between 2.4 GHz and 5 GHz bands
              </div>
            </div>
          </div>
        )}

        <div className="form-actions">
          <button type="button" onClick={fetchCurrentConfig} className="btn btn-secondary">
            Refresh
          </button>
        </div>
      </div>
    </div>
  );
}

export default DecoWiFiConfigEditor;
