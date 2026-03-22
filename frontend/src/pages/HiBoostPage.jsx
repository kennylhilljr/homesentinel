import React, { useState, useEffect, useCallback } from 'react';
import { buildUrl } from '../utils/apiConfig';
import './HiBoostPage.css';

const BANDS = ['LTE700', 'CELL800', 'PCS1900', 'AWS2100'];

function HiBoostPage() {
  const [rfData, setRfData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeBand, setActiveBand] = useState('LTE700');
  const [refreshing, setRefreshing] = useState(false);
  const [mgcSaving, setMgcSaving] = useState(false);
  const [switchSaving, setSwitchSaving] = useState(null);
  // Track pending MGC edits per band
  const [pendingMgc, setPendingMgc] = useState({});

  const fetchData = useCallback(async (forceRefresh = false) => {
    try {
      // First get device list to find the device ID
      const statusResp = await fetch(buildUrl('/hiboost/status'));
      if (!statusResp.ok) throw new Error('HiBoost not connected');
      const status = await statusResp.json();
      if (!status.connected || !status.devices?.length) {
        setError('No HiBoost devices found. Check Settings.');
        setLoading(false);
        return;
      }

      const deviceId = status.devices[0].id;
      const endpoint = forceRefresh
        ? `/hiboost/devices/${deviceId}/refresh`
        : `/hiboost/devices/${deviceId}/rf-params`;
      const method = forceRefresh ? 'POST' : 'GET';

      const resp = await fetch(buildUrl(endpoint), { method });
      if (!resp.ok) throw new Error(`Failed to fetch RF params: ${resp.status}`);
      const data = await resp.json();
      setRfData(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(), 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData(true);
  };

  const handleMgcChange = (bandName, direction, value) => {
    const key = `${bandName}_${direction}`;
    setPendingMgc(prev => ({ ...prev, [key]: parseInt(value) }));
  };

  const handleMgcSave = async (bandName) => {
    if (!rfData) return;
    const ulKey = `${bandName}_ul`;
    const dlKey = `${bandName}_dl`;
    const mgcUl = pendingMgc[ulKey];
    const mgcDl = pendingMgc[dlKey];
    if (mgcUl === undefined && mgcDl === undefined) return;

    setMgcSaving(true);
    try {
      const deviceId = rfData.device_id;
      const body = { band: bandName };
      if (mgcUl !== undefined) body.mgc_ul = mgcUl;
      if (mgcDl !== undefined) body.mgc_dl = mgcDl;

      const resp = await fetch(buildUrl(`/hiboost/devices/${deviceId}/mgc`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error('Failed to update MGC');
      // Clear pending and refresh
      setPendingMgc(prev => {
        const next = { ...prev };
        delete next[ulKey];
        delete next[dlKey];
        return next;
      });
      await fetchData(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setMgcSaving(false);
    }
  };

  const handleRfSwitch = async (bandName, enabled) => {
    if (!rfData) return;
    setSwitchSaving(bandName);
    try {
      const resp = await fetch(buildUrl(`/hiboost/devices/${rfData.device_id}/rf-switch`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ band: bandName, enabled }),
      });
      if (!resp.ok) throw new Error('Failed to toggle RF switch');
      await fetchData(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSwitchSaving(null);
    }
  };

  const getBand = (name) => rfData?.bands?.find(b => b.name === name);
  const currentBand = getBand(activeBand);

  if (loading) {
    return (
      <div className="hiboost-page">
        <div className="hiboost-loading">Loading HiBoost data...</div>
      </div>
    );
  }

  if (error && !rfData) {
    return (
      <div className="hiboost-page">
        <div className="hiboost-error">
          <h3>HiBoost Signal Booster</h3>
          <p>{error}</p>
          <button className="hiboost-btn" onClick={() => { setLoading(true); fetchData(); }}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="hiboost-page">
      {/* Header */}
      <div className="hiboost-header">
        <div className="hiboost-header-info">
          <h2>HiBoost {rfData?.product || '10K'}</h2>
          <div className="hiboost-meta">
            <span className={`hiboost-state ${rfData?.state === 'NORMAL' ? 'state-online' : 'state-offline'}`}>
              {rfData?.state === 'NORMAL' ? 'Online' : 'Offline'}
            </span>
            <span className="hiboost-model">{rfData?.model}</span>
            <span className="hiboost-serial">SN: {rfData?.serial_number}</span>
            <span className="hiboost-fw">FW: {rfData?.firmware}</span>
            {rfData?.temperature != null && (
              <span className="hiboost-temp">{rfData.temperature}°C</span>
            )}
          </div>
        </div>
      </div>

      {error && <div className="hiboost-banner hiboost-banner-error">{error}</div>}

      {/* Overview Gauges */}
      <div className="hiboost-overview">
        {BANDS.map(name => {
          const band = getBand(name);
          if (!band) return null;
          const power = band.output_power_dl;
          const gain = band.gain_dl;
          const isActive = band.rf_switch;
          return (
            <div
              key={name}
              className={`hiboost-gauge-card ${activeBand === name ? 'active' : ''} ${!isActive ? 'disabled' : ''}`}
              onClick={() => setActiveBand(name)}
            >
              <div className="gauge-ring">
                <svg viewBox="0 0 120 120" className="gauge-svg">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="#e8ecf1" strokeWidth="8" />
                  <circle
                    cx="60" cy="60" r="50" fill="none"
                    stroke={isActive ? (power >= 0 ? '#1e8b52' : power >= -5 ? '#b26b00' : '#bf2f4b') : '#ccc'}
                    strokeWidth="8"
                    strokeDasharray={`${Math.max(0, Math.min(1, (power + 13) / 25)) * 220} 314`}
                    strokeLinecap="round"
                    transform="rotate(-135 60 60)"
                  />
                </svg>
                <div className="gauge-value">
                  <span className="gauge-number">{isActive ? power : '—'}</span>
                  <span className="gauge-unit">dBm</span>
                </div>
              </div>
              <div className="gauge-label">{name}</div>
              <div className="gauge-meta">
                <span>Gain: {gain} dB</span>
                <span className={`gauge-status ${band.rf_status ? 'ok' : 'alert'}`}>
                  {band.rf_status ? 'Normal' : 'Alert'}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Band Tabs */}
      <div className="hiboost-band-tabs">
        {BANDS.map(name => (
          <button
            key={name}
            className={`band-tab ${activeBand === name ? 'active' : ''}`}
            onClick={() => setActiveBand(name)}
          >
            {name}
          </button>
        ))}
      </div>

      {/* Band Detail */}
      {currentBand && (
        <div className="hiboost-band-detail">
          {/* RF Status & Switch */}
          <div className="band-row band-row-header">
            <span className="band-label">RF Status</span>
            <span className={`band-indicator ${currentBand.rf_status ? 'indicator-ok' : 'indicator-alert'}`} />
          </div>
          <div className="band-row band-row-header">
            <span className="band-label">RF Switch</span>
            <label className="hiboost-switch">
              <input
                type="checkbox"
                checked={currentBand.rf_switch}
                disabled={switchSaving === activeBand}
                onChange={(e) => handleRfSwitch(activeBand, e.target.checked)}
              />
              <span className="switch-slider" />
            </label>
          </div>

          {/* Data Table */}
          <div className="band-table">
            <div className="band-table-header">
              <span />
              <span>Uplink</span>
              <span>Downlink</span>
            </div>

            <div className="band-table-row">
              <span className="band-label">Frequency</span>
              <span className="band-value">{currentBand.freq_uplink}</span>
              <span className="band-value">{currentBand.freq_downlink}</span>
            </div>

            <div className="band-table-row">
              <span className="band-label">Output Power</span>
              <span className="band-value">{currentBand.output_power_ul === 0 ? '–' : `${currentBand.output_power_ul} dBm`}</span>
              <span className="band-value">{currentBand.output_power_dl} dBm</span>
            </div>

            <div className="band-table-row band-table-row-editable">
              <span className="band-label">MGC</span>
              <span className="band-value band-value-edit">
                <input
                  type="number"
                  min="0"
                  max="20"
                  value={pendingMgc[`${activeBand}_ul`] ?? currentBand.mgc_ul}
                  onChange={(e) => handleMgcChange(activeBand, 'ul', e.target.value)}
                  className="mgc-input"
                />
                <span className="mgc-unit">dB</span>
              </span>
              <span className="band-value band-value-edit">
                <input
                  type="number"
                  min="0"
                  max="20"
                  value={pendingMgc[`${activeBand}_dl`] ?? currentBand.mgc_dl}
                  onChange={(e) => handleMgcChange(activeBand, 'dl', e.target.value)}
                  className="mgc-input"
                />
                <span className="mgc-unit">dB</span>
              </span>
            </div>
            {(pendingMgc[`${activeBand}_ul`] !== undefined || pendingMgc[`${activeBand}_dl`] !== undefined) && (
              <div className="band-table-row mgc-save-row">
                <span />
                <span colSpan="2">
                  <button
                    className="hiboost-btn hiboost-btn-primary mgc-save-btn"
                    onClick={() => handleMgcSave(activeBand)}
                    disabled={mgcSaving}
                  >
                    {mgcSaving ? 'Saving...' : 'Apply MGC'}
                  </button>
                </span>
              </div>
            )}

            <div className="band-table-row">
              <span className="band-label">Gain</span>
              <span className="band-value">{currentBand.gain_ul} dB</span>
              <span className="band-value">{currentBand.gain_dl} dB</span>
            </div>

            <div className="band-table-row">
              <span className="band-label">ISO</span>
              <span className="band-value">
                <span className={`band-indicator ${currentBand.iso_ul ? 'indicator-ok' : 'indicator-alert'}`} />
              </span>
              <span className="band-value">
                <span className={`band-indicator ${currentBand.iso_dl ? 'indicator-ok' : 'indicator-alert'}`} />
              </span>
            </div>

            <div className="band-table-row">
              <span className="band-label">Overload</span>
              <span className="band-value">
                <span className={`band-indicator ${currentBand.overload_ul ? 'indicator-ok' : 'indicator-alert'}`} />
              </span>
              <span className="band-value">
                <span className={`band-indicator ${currentBand.overload_dl ? 'indicator-ok' : 'indicator-alert'}`} />
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Connection Info */}
      {rfData?.connection && (
        <div className="hiboost-connection">
          <h3>Connection</h3>
          <div className="connection-grid">
            <div className="connection-item">
              <span className="connection-label">Network Type</span>
              <span className="connection-value">{rfData.connection.mode}</span>
            </div>
            <div className="connection-item">
              <span className="connection-label">WiFi SSID</span>
              <span className="connection-value">{rfData.connection.wifi_ssid || '–'}</span>
            </div>
            <div className="connection-item">
              <span className="connection-label">IP Address</span>
              <span className="connection-value">{rfData.connection.ip || '–'}</span>
            </div>
            <div className="connection-item">
              <span className="connection-label">Status</span>
              <span className={`connection-value ${rfData.connection.online ? 'text-green' : 'text-red'}`}>
                {rfData.connection.online ? 'Online' : 'Offline'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Refresh Button */}
      <button
        className="hiboost-btn hiboost-btn-refresh"
        onClick={handleRefresh}
        disabled={refreshing}
      >
        {refreshing ? 'Refreshing...' : 'Refresh'}
      </button>
    </div>
  );
}

export default HiBoostPage;
