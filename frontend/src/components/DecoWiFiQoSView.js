import React, { useState, useEffect } from 'react';
import './DecoWiFiQoSView.css';

/**
 * DecoWiFiQoSView Component
 * Displays WiFi configuration and QoS settings in read-only view
 * Shows SSID, bands, channels, and per-device bandwidth allocation
 */
function DecoWiFiQoSView({ refreshInterval = 10000 }) {
  const [wifiConfig, setWifiConfig] = useState(null);
  const [qosSettings, setQosSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch WiFi config
        const wifiResponse = await fetch('http://localhost:9000/api/deco/wifi-config', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!wifiResponse.ok) {
          throw new Error(`Failed to fetch WiFi config: ${wifiResponse.statusText}`);
        }

        const wifiData = await wifiResponse.json();
        setWifiConfig(wifiData);

        // Fetch QoS settings
        const qosResponse = await fetch('http://localhost:9000/api/deco/qos', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!qosResponse.ok) {
          throw new Error(`Failed to fetch QoS settings: ${qosResponse.statusText}`);
        }

        const qosData = await qosResponse.json();
        setQosSettings(qosData);
        setLastUpdated(new Date());
      } catch (err) {
        console.error('Error fetching WiFi/QoS data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    // Fetch on component mount
    fetchData();

    // Set up polling
    const interval = setInterval(fetchData, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval]);

  const formatTimestamp = (date) => {
    if (!date) return 'N/A';
    return date.toLocaleString();
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'High':
        return '#ef4444';
      case 'Low':
        return '#8b5cf6';
      default:
        return '#3b82f6';
    }
  };

  if (loading) {
    return (
      <div className="wifi-qos-view">
        <div className="view-loading">
          <div className="spinner"></div>
          <p>Loading WiFi and QoS settings...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="wifi-qos-view">
        <div className="view-error">
          <div className="error-icon">!</div>
          <h3>Error Loading Data</h3>
          <p>{error}</p>
          <button onClick={() => window.location.reload()} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="wifi-qos-view">
      {/* WiFi Configuration Section */}
      <div className="section wifi-section">
        <div className="section-header">
          <h2 className="section-title">WiFi Configuration</h2>
          {lastUpdated && (
            <span className="last-updated">
              Updated: {formatTimestamp(lastUpdated)}
            </span>
          )}
        </div>

        {wifiConfig && (
          <div className="wifi-content">
            {/* SSID Card */}
            <div className="config-card ssid-card">
              <h3 className="card-label">Network Name (SSID)</h3>
              <p className="card-value ssid-value">{wifiConfig.ssid || 'Unknown'}</p>
            </div>

            {/* Bands Card */}
            <div className="config-card bands-card">
              <h3 className="card-label">Supported Bands</h3>
              <div className="bands-container">
                {wifiConfig.bands && wifiConfig.bands.length > 0 ? (
                  wifiConfig.bands.map((band, idx) => (
                    <span key={idx} className="band-badge">
                      {band}
                    </span>
                  ))
                ) : (
                  <span className="no-data">Not available</span>
                )}
              </div>
            </div>

            {/* Channels Card */}
            <div className="config-card channels-card">
              <h3 className="card-label">Channel Configuration</h3>
              <div className="channels-grid">
                <div className="channel-item">
                  <span className="channel-label">2.4 GHz</span>
                  <span className="channel-value">
                    {wifiConfig.channel_2_4ghz || 'Auto'}
                  </span>
                </div>
                <div className="channel-item">
                  <span className="channel-label">5 GHz</span>
                  <span className="channel-value">
                    {wifiConfig.channel_5ghz || 'Auto'}
                  </span>
                </div>
                {wifiConfig.channel_6ghz && (
                  <div className="channel-item">
                    <span className="channel-label">6 GHz</span>
                    <span className="channel-value">{wifiConfig.channel_6ghz}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Band Steering Card */}
            <div className="config-card band-steering-card">
              <h3 className="card-label">Band Steering</h3>
              <div className="band-steering-status">
                <span
                  className={`status-badge ${
                    wifiConfig.band_steering_enabled ? 'enabled' : 'disabled'
                  }`}
                >
                  {wifiConfig.band_steering_enabled ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* QoS Settings Section */}
      <div className="section qos-section">
        <div className="section-header">
          <h2 className="section-title">QoS Settings & Device Bandwidth</h2>
          {qosSettings && (
            <span className="device-count">
              {qosSettings.total_devices || 0} device{qosSettings.total_devices !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {qosSettings && (
          <div className="qos-content">
            {qosSettings.total_devices && qosSettings.total_devices > 0 ? (
              <div className="qos-table-container">
                <table className="qos-table">
                  <thead>
                    <tr>
                      <th className="col-device">Device Name</th>
                      <th className="col-mac">MAC Address</th>
                      <th className="col-ip">IP Address</th>
                      <th className="col-priority">Priority</th>
                      <th className="col-bandwidth">Bandwidth Limit</th>
                      <th className="col-type">Connection Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {qosSettings.devices.map((device, idx) => (
                      <tr key={idx} className="qos-row">
                        <td className="col-device">
                          <span className="device-name">{device.device_name}</span>
                        </td>
                        <td className="col-mac">
                          <code className="mac-address">{device.mac_address}</code>
                        </td>
                        <td className="col-ip">
                          <code className="ip-address">{device.ip_address}</code>
                        </td>
                        <td className="col-priority">
                          <span
                            className="priority-badge"
                            style={{
                              backgroundColor: getPriorityColor(device.priority),
                            }}
                          >
                            {device.priority}
                          </span>
                        </td>
                        <td className="col-bandwidth">
                          {device.bandwidth_limit_mbps ? (
                            <span className="bandwidth-value">
                              {device.bandwidth_limit_mbps} Mbps
                            </span>
                          ) : (
                            <span className="no-limit">No limit</span>
                          )}
                        </td>
                        <td className="col-type">
                          <span
                            className={`connection-type ${device.connection_type.toLowerCase()}`}
                          >
                            {device.connection_type}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="no-devices">
                <p>No connected devices</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Info Footer */}
      <div className="view-footer">
        <p className="footer-text">
          WiFi and QoS settings are displayed in read-only mode
        </p>
        {wifiConfig && qosSettings && (
          <p className="footer-text">
            Data cached for {wifiConfig.cache_info?.ttl_seconds || 60} seconds
          </p>
        )}
      </div>
    </div>
  );
}

export default DecoWiFiQoSView;
