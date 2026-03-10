// 2026-03-10: Smart Home Control page — toggle plugs/lights on/off,
// manual two-step identify flow to find MAC/IP of physical devices.
import React, { useState, useEffect, useCallback } from 'react';
import { buildUrl } from '../utils/apiConfig';
import './SmartHomePage.css';

// Identify flow states per device:
//   null        — idle
//   "snapshot"  — taking before snapshot
//   "waiting"   — snapshot taken, waiting for user to cut power
//   "scanning"  — user clicked "I cut the power", taking after snapshot
//   "done"      — results ready

function SmartHomePage() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const [actionLoading, setActionLoading] = useState({});
  const [identifyState, setIdentifyState] = useState({}); // entity_id -> flow state
  const [identifyResults, setIdentifyResults] = useState({}); // entity_id -> result
  const [candidates, setCandidates] = useState({});
  const [showCandidates, setShowCandidates] = useState({});

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

  // Step 1: Start identify — take "before" snapshot
  const identifyStart = async (entityId) => {
    setIdentifyState(prev => ({ ...prev, [entityId]: 'snapshot' }));
    setIdentifyResults(prev => ({ ...prev, [entityId]: null }));
    try {
      const resp = await fetch(buildUrl(`/alexa/smart-home/${entityId}/identify/start`), {
        method: 'POST',
      });
      const data = await resp.json();
      if (resp.ok) {
        setIdentifyState(prev => ({ ...prev, [entityId]: 'waiting' }));
      } else {
        alert(`Snapshot failed: ${data.detail || 'Unknown error'}`);
        setIdentifyState(prev => ({ ...prev, [entityId]: null }));
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
      setIdentifyState(prev => ({ ...prev, [entityId]: null }));
    }
  };

  // Step 2: Complete identify — take "after" snapshot and diff
  const identifyComplete = async (entityId) => {
    setIdentifyState(prev => ({ ...prev, [entityId]: 'scanning' }));
    try {
      const resp = await fetch(buildUrl(`/alexa/smart-home/${entityId}/identify/complete`), {
        method: 'POST',
      });
      const data = await resp.json();
      if (resp.ok) {
        setIdentifyResults(prev => ({ ...prev, [entityId]: data }));
        setIdentifyState(prev => ({ ...prev, [entityId]: 'done' }));
      } else {
        alert(`Scan failed: ${data.detail || 'Unknown error'}`);
        setIdentifyState(prev => ({ ...prev, [entityId]: null }));
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
      setIdentifyState(prev => ({ ...prev, [entityId]: null }));
    }
  };

  // Step 3: Associate a dropped MAC with this entity
  const associateDevice = async (entityId, macAddress, deviceName) => {
    try {
      const resp = await fetch(buildUrl(`/alexa/smart-home/${entityId}/identify/associate`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mac_address: macAddress, alexa_name: deviceName }),
      });
      const data = await resp.json();
      if (data.success) {
        alert(`Associated ${macAddress} with "${deviceName}"`);
        // Clear identify state
        setIdentifyState(prev => ({ ...prev, [entityId]: null }));
        setIdentifyResults(prev => ({ ...prev, [entityId]: null }));
      } else {
        alert(`Association failed: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  // Cancel identify flow
  const identifyCancel = (entityId) => {
    setIdentifyState(prev => ({ ...prev, [entityId]: null }));
    setIdentifyResults(prev => ({ ...prev, [entityId]: null }));
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
          const idState = identifyState[device.entity_id];
          const result = identifyResults[device.entity_id];
          const isBusy = actionLoading[device.entity_id] || idState === 'snapshot' || idState === 'scanning';
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
                >ON</button>
                <button
                  className="control-btn off"
                  disabled={isBusy || !device.available}
                  onClick={() => sendCommand(device.entity_id, 'turnOff')}
                  title="Turn Off"
                >OFF</button>

                {/* Identify button — starts the two-step flow */}
                {!idState && (
                  <button
                    className="control-btn identify"
                    disabled={isBusy}
                    onClick={() => identifyStart(device.entity_id)}
                    title="Identify this device by cutting its power"
                  >Identify</button>
                )}

                {devCandidates && devCandidates.candidates.length > 0 && (
                  <button
                    className="control-btn candidates"
                    onClick={() => setShowCandidates(prev => ({
                      ...prev, [device.entity_id]: !prev[device.entity_id]
                    }))}
                    title="Show candidate MACs by manufacturer"
                  >MACs ({devCandidates.candidates.length})</button>
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
                      >{level}%</button>
                    ))}
                  </div>
                )}
              </div>

              {/* Identify flow: taking snapshot */}
              {idState === 'snapshot' && (
                <div className="identify-progress">
                  Taking network snapshot...
                </div>
              )}

              {/* Identify flow: waiting for user to cut power */}
              {idState === 'waiting' && (
                <div className="identify-prompt">
                  <div className="prompt-icon">⚡</div>
                  <div className="prompt-text">
                    <strong>Network snapshot taken.</strong><br />
                    Now physically cut power to this device (unplug it or flip the breaker).
                    Wait a few seconds for it to drop off WiFi, then click below.
                  </div>
                  <div className="prompt-actions">
                    <button
                      className="control-btn confirm-cut"
                      onClick={() => identifyComplete(device.entity_id)}
                    >
                      I've Cut the Power
                    </button>
                    <button
                      className="control-btn cancel-identify"
                      onClick={() => identifyCancel(device.entity_id)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Identify flow: scanning after power cut */}
              {idState === 'scanning' && (
                <div className="identify-progress">
                  Scanning network for dropped devices...
                </div>
              )}

              {/* Identify flow: results */}
              {idState === 'done' && result && (
                <div className={`identify-result ${result.dropped_count > 0 ? 'found' : 'none'}`}>
                  {result.dropped_count === 0 && (
                    <div className="identify-none">
                      <strong>No devices dropped offline.</strong><br />
                      Make sure the device is fully unplugged and wait longer before clicking
                      "I've Cut the Power". Some devices take 10-15 seconds to drop.
                      <div className="prompt-actions" style={{ marginTop: 8 }}>
                        <button className="control-btn identify" onClick={() => identifyStart(device.entity_id)}>
                          Try Again
                        </button>
                        <button className="control-btn cancel-identify" onClick={() => identifyCancel(device.entity_id)}>
                          Close
                        </button>
                      </div>
                    </div>
                  )}

                  {result.dropped_count === 1 && (
                    <div className="identify-match">
                      <div className="match-label">Match found — 1 device dropped:</div>
                      <div className="match-mac">{result.dropped[0].mac}</div>
                      <div className="match-detail">
                        IP: {result.dropped[0].ip}
                        {result.dropped[0].name && ` — Deco: ${result.dropped[0].name}`}
                        {result.dropped[0].friendly_name && ` — DB: ${result.dropped[0].friendly_name}`}
                        {result.dropped[0].vendor && ` — ${result.dropped[0].vendor}`}
                      </div>
                      <div className="prompt-actions" style={{ marginTop: 8 }}>
                        <button
                          className="control-btn confirm-cut"
                          onClick={() => associateDevice(device.entity_id, result.dropped[0].mac, device.name)}
                        >
                          Associate This MAC
                        </button>
                        <button className="control-btn cancel-identify" onClick={() => identifyCancel(device.entity_id)}>
                          Dismiss
                        </button>
                      </div>
                      <div className="power-reminder">
                        Turn the device back on now.
                      </div>
                    </div>
                  )}

                  {result.dropped_count > 1 && (
                    <div className="identify-multi">
                      <div className="match-label">{result.dropped_count} devices dropped — select the correct one:</div>
                      {result.dropped.map(d => (
                        <div key={d.mac} className="dropped-row">
                          <div className="dropped-info">
                            <span className="match-mac">{d.mac}</span>
                            <span className="match-detail">
                              {d.ip} — {d.name || d.friendly_name || '?'}
                              {d.vendor && ` (${d.vendor})`}
                            </span>
                          </div>
                          <button
                            className="control-btn confirm-cut small"
                            onClick={() => associateDevice(device.entity_id, d.mac, device.name)}
                          >
                            This One
                          </button>
                        </div>
                      ))}
                      <div className="prompt-actions" style={{ marginTop: 8 }}>
                        <button className="control-btn identify" onClick={() => identifyStart(device.entity_id)}>
                          Try Again
                        </button>
                        <button className="control-btn cancel-identify" onClick={() => identifyCancel(device.entity_id)}>
                          Cancel
                        </button>
                      </div>
                      <div className="power-reminder">
                        Turn the device back on now.
                      </div>
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
