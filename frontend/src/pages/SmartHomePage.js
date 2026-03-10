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
  const [identifyResults, setIdentifyResults] = useState({}); // entity_id -> result
  const [identifying, setIdentifying] = useState({}); // entity_id -> bool
  const [candidates, setCandidates] = useState({}); // entity_id -> {candidates, hw_type}
  const [showCandidates, setShowCandidates] = useState({}); // entity_id -> bool

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

  useEffect(() => { fetchDevices(); fetchCandidates(); }, [fetchDevices]);

  const fetchCandidates = async () => {
    try {
      const resp = await fetch(buildUrl('/alexa/smart-home/candidates'));
      if (resp.ok) {
        const data = await resp.json();
        const map = {};
        for (const d of (data.devices || [])) {
          map[d.entity_id] = {
            candidates: d.candidates || [],
            hw_type: d.hw_type,
            serial: d.serial,
          };
        }
        setCandidates(map);
      }
    } catch (err) {
      console.warn('Failed to fetch candidates:', err);
    }
  };

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

  const identifyDevice = async (entityId, deviceName) => {
    if (!window.confirm(
      `Identify "${deviceName}"?\n\nThis will turn it OFF for ~10 seconds, then back ON, ` +
      `while watching the Deco client list to find its MAC address.`
    )) return;

    setIdentifying(prev => ({ ...prev, [entityId]: true }));
    setIdentifyResults(prev => ({ ...prev, [entityId]: null }));
    try {
      const resp = await fetch(buildUrl(`/alexa/smart-home/${entityId}/identify`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await resp.json();
      if (resp.ok) {
        setIdentifyResults(prev => ({ ...prev, [entityId]: data }));
      } else {
        alert(`Identify failed: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setIdentifying(prev => ({ ...prev, [entityId]: false }));
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
          {lightCount} lights, {plugCount} plugs — toggle on/off or use Identify to find MAC/IP
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
        {filtered.map(device => {
          const result = identifyResults[device.entity_id];
          const isIdentifying = identifying[device.entity_id];
          const isBusy = actionLoading[device.entity_id] || isIdentifying;
          const devCandidates = candidates[device.entity_id];
          const showingCandidates = showCandidates[device.entity_id];

          return (
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
                  disabled={isBusy || !device.available}
                  onClick={() => sendCommand(device.entity_id, 'turnOn')}
                  title="Turn On"
                >
                  ON
                </button>
                <button
                  className="control-btn off"
                  disabled={isBusy || !device.available}
                  onClick={() => sendCommand(device.entity_id, 'turnOff')}
                  title="Turn Off"
                >
                  OFF
                </button>
                <button
                  className="control-btn identify"
                  disabled={isBusy || !device.available}
                  onClick={() => identifyDevice(device.entity_id, device.name)}
                  title="Turn off for 10s and watch Deco to find MAC"
                >
                  {isIdentifying ? 'Identifying...' : 'Identify'}
                </button>
                {devCandidates && devCandidates.candidates.length > 0 && (
                  <button
                    className="control-btn candidates"
                    onClick={() => setShowCandidates(prev => ({
                      ...prev, [device.entity_id]: !prev[device.entity_id]
                    }))}
                    title="Show candidate MACs by manufacturer"
                  >
                    MACs ({devCandidates.candidates.length})
                  </button>
                )}
                {device.has_brightness && (
                  <div className="brightness-controls">
                    {[10, 50, 100].map(level => (
                      <button
                        key={level}
                        className="control-btn dim"
                        disabled={isBusy || !device.available}
                        onClick={() => sendCommand(device.entity_id, 'setBrightness', { brightness: level })}
                        title={`${level}%`}
                      >
                        {level}%
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Identify results */}
              {result && (
                <div className={`identify-result ${result.dropped_count > 0 ? 'found' : 'none'}`}>
                  {result.dropped_count === 0 && (
                    <div className="identify-none">
                      No MAC dropped offline. Device may not disconnect when powered off
                      (some lights keep WiFi via the fixture), or try again with a longer wait.
                    </div>
                  )}
                  {result.dropped_count === 1 && (
                    <div className="identify-match">
                      <div className="match-label">Match found:</div>
                      <div className="match-mac">{result.dropped[0].mac}</div>
                      <div className="match-detail">
                        IP: {result.dropped[0].ip}
                        {result.dropped[0].name && ` — Deco name: ${result.dropped[0].name}`}
                        {result.dropped[0].friendly_name && ` — DB name: ${result.dropped[0].friendly_name}`}
                        {result.dropped[0].vendor && ` — ${result.dropped[0].vendor}`}
                      </div>
                    </div>
                  )}
                  {result.dropped_count > 1 && (
                    <div className="identify-multi">
                      <div className="match-label">{result.dropped_count} MACs dropped (ambiguous):</div>
                      {result.dropped.map(d => (
                        <div key={d.mac} className="match-detail">
                          {d.mac} — {d.ip} — {d.name || '?'}
                          {d.vendor && ` (${d.vendor})`}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* OUI-based MAC candidates */}
              {showingCandidates && devCandidates && (
                <div className="candidates-list">
                  <div className="match-label">
                    Candidate MACs ({devCandidates.hw_type}):
                  </div>
                  {devCandidates.candidates.map(c => (
                    <div key={c.mac} className="candidate-row">
                      <span className="candidate-mac">{c.mac}</span>
                      <span className="candidate-ip">{c.ip}</span>
                      <span className="candidate-name">
                        {c.friendly_name || c.deco_name || c.hostname || '?'}
                      </span>
                      <span className={`candidate-status ${c.status}`}>
                        {c.status === 'online' ? 'ON' : 'OFF'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {isIdentifying && (
                <div className="identify-progress">
                  Turning off, waiting 10s, checking Deco...
                </div>
              )}
              {isBusy && <div className="action-spinner" />}
            </div>
          );
        })}
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
