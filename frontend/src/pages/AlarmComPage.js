// 2026-03-10: Alarm.com integration page — partitions, sensors, locks, cameras
import React, { useState, useEffect, useCallback } from 'react';
import { buildUrl } from '../utils/apiConfig';
import './AlarmComPage.css';

function AlarmComPage() {
  const [status, setStatus] = useState(null);
  const [devices, setDevices] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState({});
  const [loginLoading, setLoginLoading] = useState(false);
  const [otpRequired, setOtpRequired] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [creds, setCreds] = useState({ username: '', password: '', two_factor_cookie: '' });
  const [showCredForm, setShowCredForm] = useState(false);
  const [activeTab, setActiveTab] = useState('partitions');

  const fetchStatus = useCallback(async () => {
    try {
      const resp = await fetch(buildUrl('/alarm-com/status'));
      if (resp.ok) {
        const data = await resp.json();
        setStatus(data);
        return data;
      }
    } catch (err) {
      console.warn('Failed to fetch Alarm.com status:', err);
    }
    return null;
  }, []);

  const fetchDevices = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(buildUrl('/alarm-com/devices'));
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setDevices(data.devices || {});
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      const s = await fetchStatus();
      if (s && s.logged_in) {
        await fetchDevices();
      } else {
        setLoading(false);
      }
    };
    init();
  }, [fetchStatus, fetchDevices]);

  const handleLogin = async () => {
    setLoginLoading(true);
    setError(null);
    try {
      const resp = await fetch(buildUrl('/alarm-com/login'), { method: 'POST' });
      const data = await resp.json();
      if (data.otp_required) {
        setOtpRequired(true);
      } else if (data.success) {
        await fetchStatus();
        await fetchDevices();
      } else {
        setError(data.detail || data.message || 'Login failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoginLoading(false);
    }
  };

  const handleOtpSubmit = async () => {
    if (!otpCode.trim()) return;
    setLoginLoading(true);
    try {
      const resp = await fetch(buildUrl('/alarm-com/otp/submit'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: otpCode.trim() }),
      });
      const data = await resp.json();
      if (data.success) {
        setOtpRequired(false);
        setOtpCode('');
        await fetchStatus();
        await fetchDevices();
      } else {
        setError(data.detail || 'OTP failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoginLoading(false);
    }
  };

  const handleSaveCreds = async () => {
    try {
      const resp = await fetch(buildUrl('/alarm-com/credentials'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds),
      });
      const data = await resp.json();
      if (data.success) {
        setShowCredForm(false);
        await fetchStatus();
      } else {
        setError(data.detail || 'Failed to save credentials');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const sendPartitionCommand = async (partitionId, command) => {
    const label = command.replace('_', ' ');
    if (command === 'disarm' && !window.confirm(`Disarm this partition?`)) return;

    setActionLoading(prev => ({ ...prev, [partitionId]: true }));
    try {
      const resp = await fetch(buildUrl(`/alarm-com/partitions/${partitionId}/command`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command }),
      });
      const data = await resp.json();
      if (!data.success) {
        alert(`${label} failed: ${data.detail || 'Unknown error'}`);
      }
      await fetchDevices();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setActionLoading(prev => ({ ...prev, [partitionId]: false }));
    }
  };

  const sendLockCommand = async (lockId, command) => {
    if (command === 'unlock' && !window.confirm('Unlock this lock?')) return;

    setActionLoading(prev => ({ ...prev, [lockId]: true }));
    try {
      const resp = await fetch(buildUrl(`/alarm-com/locks/${lockId}/command`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command }),
      });
      const data = await resp.json();
      if (!data.success) {
        alert(`${command} failed: ${data.detail || 'Unknown error'}`);
      }
      await fetchDevices();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setActionLoading(prev => ({ ...prev, [lockId]: false }));
    }
  };

  const getStateColor = (state) => {
    if (!state) return '#999';
    const s = state.toUpperCase();
    if (s.includes('ARMED')) return '#e74c3c';
    if (s === 'DISARMED') return '#27ae60';
    if (s === 'OPEN' || s === 'UNLOCKED') return '#f39c12';
    if (s === 'CLOSED' || s === 'LOCKED') return '#27ae60';
    if (s === 'ONLINE' || s === 'ON') return '#27ae60';
    if (s === 'IDLE') return '#999';
    return '#4a9eff';
  };

  const getStateIcon = (deviceType, state) => {
    const s = (state || '').toUpperCase();
    switch (deviceType) {
      case 'Partition':
        if (s.includes('ARMED')) return '🛡️';
        return '🏠';
      case 'Sensor':
        if (s === 'OPEN') return '🚪';
        if (s === 'CLOSED') return '✅';
        return '📡';
      case 'Lock':
        return s === 'LOCKED' ? '🔒' : '🔓';
      case 'Light':
        return '💡';
      case 'Thermostat':
        return '🌡️';
      case 'Camera':
        return '📷';
      case 'GarageDoor':
        return s === 'OPEN' ? '🚗' : '🏗️';
      case 'WaterSensor':
        return '💧';
      default:
        return '📟';
    }
  };

  // Not configured
  if (!status?.configured && !loading) {
    return (
      <div className="alarm-com-page">
        <div className="page-header">
          <h2>Alarm.com</h2>
          <p className="subtitle">Security system integration</p>
        </div>
        <div className="setup-card">
          <h3>Setup Required</h3>
          <p>Enter your Alarm.com credentials to connect your security system.</p>
          <div className="cred-form">
            <input
              type="text" placeholder="Email / Username"
              value={creds.username}
              onChange={e => setCreds({ ...creds, username: e.target.value })}
            />
            <input
              type="password" placeholder="Password"
              value={creds.password}
              onChange={e => setCreds({ ...creds, password: e.target.value })}
            />
            <input
              type="text" placeholder="2FA Cookie (optional)"
              value={creds.two_factor_cookie}
              onChange={e => setCreds({ ...creds, two_factor_cookie: e.target.value })}
            />
            <button className="save-btn" onClick={handleSaveCreds}>Save Credentials</button>
          </div>
          {error && <div className="error-banner">{error}</div>}
        </div>
      </div>
    );
  }

  // OTP required
  if (otpRequired) {
    return (
      <div className="alarm-com-page">
        <div className="page-header">
          <h2>Alarm.com — Two-Factor Authentication</h2>
        </div>
        <div className="setup-card">
          <p>Enter the verification code from your authenticator app:</p>
          <div className="otp-form">
            <input
              type="text" placeholder="6-digit code"
              value={otpCode}
              onChange={e => setOtpCode(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleOtpSubmit()}
              maxLength={6}
              autoFocus
            />
            <button className="save-btn" onClick={handleOtpSubmit} disabled={loginLoading}>
              {loginLoading ? 'Verifying...' : 'Verify'}
            </button>
          </div>
          {error && <div className="error-banner">{error}</div>}
        </div>
      </div>
    );
  }

  const tabs = [
    { key: 'partitions', label: 'Partitions', count: devices?.partitions?.length },
    { key: 'sensors', label: 'Sensors', count: devices?.sensors?.length },
    { key: 'locks', label: 'Locks', count: devices?.locks?.length },
    { key: 'cameras', label: 'Cameras', count: devices?.cameras?.length },
    { key: 'lights', label: 'Lights', count: devices?.lights?.length },
    { key: 'thermostats', label: 'Thermostats', count: devices?.thermostats?.length },
    { key: 'garage_doors', label: 'Garage', count: devices?.garage_doors?.length },
    { key: 'water_sensors', label: 'Water', count: devices?.water_sensors?.length },
  ];

  const currentDevices = devices?.[activeTab] || [];

  return (
    <div className="alarm-com-page">
      <div className="page-header">
        <h2>Alarm.com</h2>
        <p className="subtitle">
          {status?.logged_in ? 'Connected' : 'Not connected'}
          {status?.username && ` — ${status.username}`}
        </p>
        <div className="header-actions">
          {!status?.logged_in && (
            <button className="login-btn" onClick={handleLogin} disabled={loginLoading}>
              {loginLoading ? 'Logging in...' : 'Login'}
            </button>
          )}
          <button className="refresh-btn" onClick={fetchDevices} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </button>
          <button className="settings-btn" onClick={() => setShowCredForm(!showCredForm)}>
            Settings
          </button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {showCredForm && (
        <div className="cred-form-inline">
          <input type="text" placeholder="Email / Username"
            value={creds.username}
            onChange={e => setCreds({ ...creds, username: e.target.value })} />
          <input type="password" placeholder="Password"
            value={creds.password}
            onChange={e => setCreds({ ...creds, password: e.target.value })} />
          <input type="text" placeholder="2FA Cookie"
            value={creds.two_factor_cookie}
            onChange={e => setCreds({ ...creds, two_factor_cookie: e.target.value })} />
          <button className="save-btn" onClick={handleSaveCreds}>Save</button>
        </div>
      )}

      {/* Tabs */}
      <div className="alarm-tabs">
        {tabs.filter(t => (t.count || 0) > 0 || t.key === 'partitions' || t.key === 'sensors').map(tab => (
          <button
            key={tab.key}
            className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label} {tab.count != null ? `(${tab.count})` : ''}
          </button>
        ))}
      </div>

      {/* Device grid */}
      {loading ? (
        <div className="loading">Loading Alarm.com devices...</div>
      ) : (
        <div className="device-grid">
          {currentDevices.map(device => {
            const isBusy = actionLoading[device.id];
            return (
              <div key={device.id} className="device-card">
                <div className="device-header">
                  <span className="device-icon">
                    {getStateIcon(device.device_type, device.state)}
                  </span>
                  <div className="device-info">
                    <div className="device-name">{device.name}</div>
                    <div className="device-type">{device.device_type}</div>
                  </div>
                  <span
                    className="state-badge"
                    style={{ background: getStateColor(device.state) }}
                  >
                    {device.state || 'Unknown'}
                  </span>
                </div>

                {device.malfunction && (
                  <div className="malfunction-badge">Malfunction</div>
                )}
                {device.battery && (
                  <div className="battery-info">Battery: {device.battery}</div>
                )}
                {device.mac_address && (
                  <div className="mac-info">MAC: {device.mac_address}</div>
                )}

                {/* Partition controls */}
                {device.device_type === 'Partition' && (
                  <div className="device-controls">
                    <button
                      className="ctrl-btn arm-away"
                      disabled={isBusy}
                      onClick={() => sendPartitionCommand(device.id, 'arm_away')}
                    >Arm Away</button>
                    <button
                      className="ctrl-btn arm-stay"
                      disabled={isBusy}
                      onClick={() => sendPartitionCommand(device.id, 'arm_stay')}
                    >Arm Stay</button>
                    <button
                      className="ctrl-btn arm-night"
                      disabled={isBusy}
                      onClick={() => sendPartitionCommand(device.id, 'arm_night')}
                    >Arm Night</button>
                    <button
                      className="ctrl-btn disarm"
                      disabled={isBusy}
                      onClick={() => sendPartitionCommand(device.id, 'disarm')}
                    >Disarm</button>
                  </div>
                )}

                {/* Lock controls */}
                {device.device_type === 'Lock' && (
                  <div className="device-controls">
                    <button
                      className="ctrl-btn lock"
                      disabled={isBusy}
                      onClick={() => sendLockCommand(device.id, 'lock')}
                    >Lock</button>
                    <button
                      className="ctrl-btn unlock"
                      disabled={isBusy}
                      onClick={() => sendLockCommand(device.id, 'unlock')}
                    >Unlock</button>
                  </div>
                )}

                {isBusy && <div className="action-spinner" />}
              </div>
            );
          })}
          {currentDevices.length === 0 && (
            <div className="empty-state">
              No {activeTab.replace('_', ' ')} found.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AlarmComPage;
