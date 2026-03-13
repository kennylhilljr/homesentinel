import React, { useState, useEffect } from 'react';
import { buildUrl } from '../utils/apiConfig';
import AlexaDeviceCard from '../components/AlexaDeviceCard';
import ViewModeToggle from '../components/ViewModeToggle';
import './AlexaDevicesPage.css';

function AlexaDevicesPage() {
  const [devices, setDevices] = useState([]);
  const [echoDevices, setEchoDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(null);
  const [filter, setFilter] = useState('all');
  const [refreshing, setRefreshing] = useState(false);
  const [viewMode, setViewMode] = useState('grid');
  const [expandedListDevice, setExpandedListDevice] = useState(null);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const response = await fetch(buildUrl('/alexa/status'));
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
        if (data.authenticated) {
          fetchDevices();
          fetchEchoDevices();
        } else {
          setLoading(false);
        }
      }
    } catch (err) {
      setError('Failed to check Alexa status');
      setLoading(false);
    }
  };

  const fetchDevices = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(buildUrl('/alexa/devices'));
      if (response.ok) {
        const data = await response.json();
        setDevices(data.devices || []);
      } else if (response.status === 401) {
        setError('Not authenticated. Please connect your Alexa account in Settings.');
      } else {
        setError('Failed to load Alexa devices');
      }
    } catch (err) {
      setError(`Failed to fetch devices: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchEchoDevices = async () => {
    try {
      const response = await fetch(buildUrl('/alexa/echo-devices'));
      if (response.ok) {
        const data = await response.json();
        setEchoDevices(data.devices || []);
      }
    } catch (err) {
      console.error('Failed to fetch Echo devices:', err);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchDevices();
    await fetchEchoDevices();
    setRefreshing(false);
  };

  const handleStateChange = async (endpointId) => {
    // Refresh single device state after command
    setTimeout(() => fetchDevices(), 2000);
  };

  // Filter devices (exclude echo devices from smart home list)
  const smartDevices = devices.filter(d => !d.is_echo_device);
  const filteredDevices = filter === 'all'
    ? smartDevices
    : smartDevices.filter(d => d.device_type === filter);

  // Stats
  const deviceTypes = [...new Set(smartDevices.map(d => d.device_type))];
  const onlineCount = smartDevices.filter(d => d.is_online).length;

  // Not authenticated
  if (!loading && status && !status.authenticated) {
    return (
      <div className="alexa-page">
        <div className="alexa-not-auth">
          <h2>Connect Your Alexa Account</h2>
          <p>Go to Settings to configure your Amazon Alexa integration.</p>
          <p style={{ color: '#888', fontSize: '0.85rem' }}>
            You'll need a Login with Amazon (LWA) Client ID and Secret.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="alexa-page">
      <div className="page-header">
        <div className="header-title">
          <h1>Alexa Smart Home</h1>
          <p>View and control your Alexa-connected devices</p>
        </div>
        <div className="header-controls">
          <ViewModeToggle
            label="Devices"
            value={viewMode}
            onChange={setViewMode}
          />
          <button className="refresh-btn" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Stats */}
      {smartDevices.length > 0 && (
        <div className="alexa-stats">
          <div className="alexa-stat">
            <div className="stat-value">{smartDevices.length}</div>
            <div className="stat-label">Smart Devices</div>
          </div>
          <div className="alexa-stat">
            <div className="stat-value">{onlineCount}</div>
            <div className="stat-label">Online</div>
          </div>
          <div className="alexa-stat">
            <div className="stat-value">{echoDevices.length}</div>
            <div className="stat-label">Echo Devices</div>
          </div>
          <div className="alexa-stat">
            <div className="stat-value">{deviceTypes.length}</div>
            <div className="stat-label">Device Types</div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="alexa-error">
          <p>{error}</p>
          <button className="refresh-btn" onClick={handleRefresh}>Retry</button>
        </div>
      )}

      {/* Loading */}
      {loading && <div className="alexa-loading"><p>Loading Alexa devices...</p></div>}

      {/* Devices */}
      {!loading && !error && smartDevices.length > 0 && (
        <>
          {/* Filter tabs */}
          <div className="device-filters">
            <button
              className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
              onClick={() => setFilter('all')}
            >
              All ({smartDevices.length})
            </button>
            {deviceTypes.map(type => (
              <button
                key={type}
                className={`filter-btn ${filter === type ? 'active' : ''}`}
                onClick={() => setFilter(type)}
              >
                {type.charAt(0).toUpperCase() + type.slice(1)} ({smartDevices.filter(d => d.device_type === type).length})
              </button>
            ))}
          </div>

          {viewMode === 'grid' ? (
            <div className="alexa-devices-grid">
              {filteredDevices.map(device => (
                <AlexaDeviceCard
                  key={device.endpoint_id}
                  device={device}
                  onStateChange={handleStateChange}
                />
              ))}
            </div>
          ) : (
            <div className="alexa-device-list">
              {filteredDevices.map((device) => {
                const isExpanded = expandedListDevice === device.endpoint_id;
                const isOnline = !!device.is_online;
                return (
                  <div key={device.endpoint_id} className={`alexa-list-row ${isExpanded ? 'expanded' : ''}`}>
                    <div className="alexa-list-summary">
                      <div className="summary-main">
                        <p className="summary-name">{device.friendly_name}</p>
                        <p className="summary-meta">
                          {device.device_type} • {device.manufacturer || 'Unknown Vendor'}
                        </p>
                      </div>
                      <div className="summary-side">
                        <span className={`power-chip ${isOnline ? 'on' : 'off'}`}>
                          {isOnline ? 'Online' : 'Offline'}
                        </span>
                        <button
                          type="button"
                          className="list-controls-btn"
                          onClick={() => setExpandedListDevice(isExpanded ? null : device.endpoint_id)}
                        >
                          {isExpanded ? 'Hide Controls' : 'Show Controls'}
                        </button>
                      </div>
                    </div>
                    {isExpanded && (
                      <div className="alexa-list-controls">
                        <AlexaDeviceCard
                          device={device}
                          onStateChange={handleStateChange}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Empty */}
      {!loading && !error && smartDevices.length === 0 && status?.authenticated && (
        <div className="alexa-empty">
          <h2>No Smart Home Devices Found</h2>
          <p>No Alexa-compatible smart home devices were discovered.</p>
          <button className="refresh-btn" onClick={handleRefresh}>Try Again</button>
        </div>
      )}

      {/* Echo Devices */}
      {echoDevices.length > 0 && (
        <div className="echo-section">
          <h2>Echo Devices ({echoDevices.length})</h2>
          <div className="echo-grid">
            {echoDevices.map(device => (
              <div key={device.endpoint_id} className="echo-card">
                <span className="echo-icon">{'\u{1F4E2}'}</span>
                <div>
                  <div className="echo-name">{device.friendly_name}</div>
                  <div className="echo-model">
                    {device.manufacturer} {device.model ? `\u2022 ${device.model}` : ''}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default AlexaDevicesPage;
