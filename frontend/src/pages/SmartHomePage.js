// 2026-03-10: Smart Home Control page — toggle plugs/lights on/off
// to identify which physical device is which, then link to network devices.
import React, { useState, useEffect, useCallback } from 'react';
import { buildUrl } from '../utils/apiConfig';
import './SmartHomePage.css';

function SmartHomePage() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all'); // 'all', 'light', 'plug'
  const [actionLoading, setActionLoading] = useState({}); // entity_id -> bool

  const fetchDevices = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(buildUrl('/alexa/smart-home/devices'));
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setDevices(data.devices || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  const sendCommand = async (entityId, action, params) => {
    setActionLoading(prev => ({ ...prev, [entityId]: true }));
    try {
      const resp = await fetch(buildUrl(`/alexa/smart-home/${entityId}/control`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, params }),
      });
      const data = await resp.json();
      if (!data.success) {
        const errMsg = data.errors?.map(e => e.message || e.code).join(', ') || 'Command failed';
        alert(`Failed: ${errMsg}`);
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setActionLoading(prev => ({ ...prev, [entityId]: false }));
    }
  };

  const filtered = filter === 'all' ? devices : devices.filter(d => d.kind === filter);

  const lightCount = devices.filter(d => d.kind === 'light').length;
  const plugCount = devices.filter(d => d.kind === 'plug').length;

  if (loading) {
    return <div className="smart-home-page"><div className="loading">Loading smart home devices...</div></div>;
  }

  if (error) {
    return (
      <div className="smart-home-page">
        <div className="error-banner">{error}</div>
        <button className="refresh-btn" onClick={fetchDevices}>Retry</button>
      </div>
    );
  }

  return (
    <div className="smart-home-page">
      <div className="page-header">
        <h2>Smart Home Control</h2>
        <p className="subtitle">
          {lightCount} lights, {plugCount} plugs — toggle on/off to identify devices
        </p>
        <div className="header-actions">
          <div className="filter-group">
            <button className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
              onClick={() => setFilter('all')}>All ({devices.length})</button>
            <button className={`filter-btn ${filter === 'light' ? 'active' : ''}`}
              onClick={() => setFilter('light')}>Lights ({lightCount})</button>
            <button className={`filter-btn ${filter === 'plug' ? 'active' : ''}`}
              onClick={() => setFilter('plug')}>Plugs ({plugCount})</button>
          </div>
          <button className="refresh-btn" onClick={fetchDevices}>Refresh</button>
        </div>
      </div>

      <div className="device-grid">
        {filtered.map(device => (
          <div key={device.entity_id} className={`device-card ${device.kind} ${device.available ? '' : 'unavailable'}`}>
            <div className="device-icon">
              {device.kind === 'light' ? '💡' : '🔌'}
            </div>
            <div className="device-info">
              <div className="device-name">{device.name}</div>
              <div className="device-desc">{device.description}</div>
              {!device.available && <div className="device-offline">Offline</div>}
            </div>
            <div className="device-controls">
              <button
                className="control-btn on"
                disabled={actionLoading[device.entity_id] || !device.available}
                onClick={() => sendCommand(device.entity_id, 'turnOn')}
                title="Turn On"
              >
                ON
              </button>
              <button
                className="control-btn off"
                disabled={actionLoading[device.entity_id] || !device.available}
                onClick={() => sendCommand(device.entity_id, 'turnOff')}
                title="Turn Off"
              >
                OFF
              </button>
              {device.has_brightness && (
                <div className="brightness-controls">
                  {[10, 50, 100].map(level => (
                    <button
                      key={level}
                      className="control-btn dim"
                      disabled={actionLoading[device.entity_id] || !device.available}
                      onClick={() => sendCommand(device.entity_id, 'setBrightness', { brightness: level })}
                      title={`${level}%`}
                    >
                      {level}%
                    </button>
                  ))}
                </div>
              )}
            </div>
            {actionLoading[device.entity_id] && <div className="action-spinner" />}
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="empty-state">
          No {filter === 'all' ? '' : filter} devices found.
          {filter !== 'all' && <button className="link-btn" onClick={() => setFilter('all')}>Show all</button>}
        </div>
      )}
    </div>
  );
}

export default SmartHomePage;
