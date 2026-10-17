import React, { useState, useEffect } from 'react';
import { buildUrl } from '../utils/apiConfig';
import './DeviceNamingPage.css';

function DeviceNamingPage() {
  const [suggestions, setSuggestions] = useState([]);
  const [unlinkedAlexa, setUnlinkedAlexa] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('unnamed'); // unnamed, all, linked
  const [saving, setSaving] = useState({});
  const [selectedAlexa, setSelectedAlexa] = useState({}); // networkDeviceId -> alexaEndpointId
  const [customNames, setCustomNames] = useState({}); // networkDeviceId -> custom name string
  const [importResult, setImportResult] = useState(null);

  useEffect(() => {
    fetchSuggestions();
  }, []);

  const fetchSuggestions = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(buildUrl('/alexa/suggest-matches'));
      if (response.ok) {
        const data = await response.json();
        setSuggestions(data.suggestions || []);
        setUnlinkedAlexa(data.unlinked_alexa_devices || []);
        setStats({
          totalNetwork: data.total_network,
          totalAlexa: data.total_alexa,
          totalLinked: data.total_linked,
        });
      } else {
        setError('Failed to load device suggestions');
      }
    } catch (err) {
      setError(`Failed to fetch: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const linkAndRename = async (networkDeviceId, alexaEndpointId, alexaName) => {
    setSaving(prev => ({ ...prev, [networkDeviceId]: true }));
    try {
      // Link the devices
      await fetch(buildUrl(`/alexa/devices/${alexaEndpointId}/link`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ network_device_id: networkDeviceId }),
      });

      // Apply the name
      await fetch(buildUrl(`/alexa/apply-name/${networkDeviceId}`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ friendly_name: alexaName }),
      });

      // Refresh
      await fetchSuggestions();
    } catch (err) {
      console.error('Failed to link/rename:', err);
    } finally {
      setSaving(prev => ({ ...prev, [networkDeviceId]: false }));
    }
  };

  const applyCustomName = async (networkDeviceId) => {
    const name = customNames[networkDeviceId];
    if (!name) return;

    setSaving(prev => ({ ...prev, [networkDeviceId]: true }));
    try {
      await fetch(buildUrl(`/alexa/apply-name/${networkDeviceId}`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ friendly_name: name }),
      });
      await fetchSuggestions();
      setCustomNames(prev => ({ ...prev, [networkDeviceId]: '' }));
    } catch (err) {
      console.error('Failed to rename:', err);
    } finally {
      setSaving(prev => ({ ...prev, [networkDeviceId]: false }));
    }
  };

  // Filter suggestions
  const filtered = suggestions.filter(s => {
    const net = s.network_device;
    if (filter === 'unnamed') return !net.friendly_name;
    if (filter === 'linked') return s.already_linked_to;
    return true;
  });

  const unnamedCount = suggestions.filter(s => !s.network_device.friendly_name).length;
  const linkedCount = suggestions.filter(s => s.already_linked_to).length;

  return (
    <div className="naming-page">
      <div className="page-header">
        <div className="header-title">
          <h1>Device Naming</h1>
          <p>Match network devices to Alexa names to identify everything on your network</p>
        </div>
        <div className="header-controls">
          <button
            className="refresh-btn"
            style={{ marginRight: '0.5rem' }}
            onClick={async () => {
              try {
                const res = await fetch(buildUrl('/deco/import-client-names'), { method: 'POST' });
                const data = await res.json();
                setImportResult(`Imported ${data.imported} names from ${data.total_clients} Deco clients`);
                setTimeout(() => setImportResult(null), 5000);
                fetchSuggestions();
              } catch (err) {
                setImportResult(`Import failed: ${err.message}`);
                setTimeout(() => setImportResult(null), 5000);
              }
            }}
            disabled={loading}
          >
            Import Deco Names
          </button>
          <button
            className="refresh-btn"
            style={{ marginRight: '0.5rem' }}
            onClick={async () => {
              await fetch(buildUrl('/deco/auto-name-nodes'), { method: 'POST' });
              fetchSuggestions();
            }}
            disabled={loading}
          >
            Auto-Name Deco Nodes
          </button>
          <button className="refresh-btn" onClick={fetchSuggestions} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {importResult && (
        <div className="naming-error" style={{ background: '#1a2e1a', borderColor: '#00ff88', color: '#00ff88' }}>
          <p>{importResult}</p>
        </div>
      )}

      {/* Stats */}
      <div className="naming-stats">
        <div className="naming-stat">
          <div className="stat-value">{stats.totalNetwork || 0}</div>
          <div className="stat-label">Network Devices</div>
        </div>
        <div className="naming-stat">
          <div className="stat-value">{stats.totalAlexa || 0}</div>
          <div className="stat-label">Alexa Devices</div>
        </div>
        <div className="naming-stat">
          <div className="stat-value">{stats.totalLinked || 0}</div>
          <div className="stat-label">Linked</div>
        </div>
        <div className="naming-stat">
          <div className="stat-value">{unnamedCount}</div>
          <div className="stat-label">Unnamed</div>
        </div>
      </div>

      {error && (
        <div className="naming-error">
          <p>{error}</p>
          <button className="refresh-btn" onClick={fetchSuggestions}>Retry</button>
        </div>
      )}

      {/* Filter tabs */}
      <div className="device-filters">
        <button
          className={`filter-btn ${filter === 'unnamed' ? 'active' : ''}`}
          onClick={() => setFilter('unnamed')}
        >
          Unnamed ({unnamedCount})
        </button>
        <button
          className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All ({suggestions.length})
        </button>
        <button
          className={`filter-btn ${filter === 'linked' ? 'active' : ''}`}
          onClick={() => setFilter('linked')}
        >
          Linked ({linkedCount})
        </button>
      </div>

      {loading && <div className="naming-loading"><p>Loading device data...</p></div>}

      {/* Device list */}
      {!loading && filtered.length > 0 && (
        <div className="naming-list">
          {filtered.map(item => {
            const net = item.network_device;
            const deviceId = net.device_id;
            const isSaving = saving[deviceId];
            const candidates = item.suggested_alexa_devices || [];
            const selected = selectedAlexa[deviceId];

            return (
              <div key={deviceId} className={`naming-row ${item.already_linked_to ? 'linked' : ''}`}>
                {/* Network device info */}
                <div className="net-device-info">
                  <div className="net-device-header">
                    <span className={`status-dot ${net.status === 'online' ? 'green' : 'gray'}`}></span>
                    <span className="net-name">
                      {net.friendly_name || net.hostname || '(unknown)'}
                    </span>
                    {net.friendly_name && <span className="named-badge">Named</span>}
                  </div>
                  <div className="net-device-details">
                    <span className="mac">{net.mac_address}</span>
                    <span className="ip">{net.current_ip || 'No IP'}</span>
                    <span className="vendor">{net.vendor_name || 'Unknown vendor'}</span>
                  </div>
                </div>

                {/* Linking controls */}
                <div className="link-controls">
                  {/* Suggested Alexa matches */}
                  {candidates.length > 0 && (
                    <div className="suggestions">
                      <select
                        value={selected || ''}
                        onChange={e => setSelectedAlexa(prev => ({ ...prev, [deviceId]: e.target.value }))}
                      >
                        <option value="">-- Select Alexa device --</option>
                        {candidates.map(c => (
                          <option key={c.endpoint_id} value={c.endpoint_id}>
                            {c.friendly_name} ({c.device_type})
                          </option>
                        ))}
                      </select>
                      <button
                        className="link-btn"
                        disabled={!selected || isSaving}
                        onClick={() => {
                          const match = candidates.find(c => c.endpoint_id === selected);
                          if (match) linkAndRename(deviceId, selected, match.friendly_name);
                        }}
                      >
                        {isSaving ? '...' : 'Link & Name'}
                      </button>
                    </div>
                  )}

                  {/* Or pick from all unlinked Alexa devices */}
                  {candidates.length === 0 && unlinkedAlexa.length > 0 && (
                    <div className="suggestions">
                      <select
                        value={selected || ''}
                        onChange={e => setSelectedAlexa(prev => ({ ...prev, [deviceId]: e.target.value }))}
                      >
                        <option value="">-- Pick any Alexa device --</option>
                        {unlinkedAlexa.map(c => (
                          <option key={c.endpoint_id} value={c.endpoint_id}>
                            {c.friendly_name} ({c.device_type})
                          </option>
                        ))}
                      </select>
                      <button
                        className="link-btn"
                        disabled={!selected || isSaving}
                        onClick={() => {
                          const match = unlinkedAlexa.find(c => c.endpoint_id === selected);
                          if (match) linkAndRename(deviceId, selected, match.friendly_name);
                        }}
                      >
                        {isSaving ? '...' : 'Link & Name'}
                      </button>
                    </div>
                  )}

                  {/* Manual name entry */}
                  <div className="manual-name">
                    <input
                      type="text"
                      placeholder="Or type a custom name..."
                      value={customNames[deviceId] || ''}
                      onChange={e => setCustomNames(prev => ({ ...prev, [deviceId]: e.target.value }))}
                    />
                    <button
                      className="name-btn"
                      disabled={!customNames[deviceId] || isSaving}
                      onClick={() => applyCustomName(deviceId)}
                    >
                      {isSaving ? '...' : 'Rename'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="naming-empty">
          <p>{filter === 'unnamed' ? 'All devices are named!' : 'No devices match this filter.'}</p>
        </div>
      )}
    </div>
  );
}

export default DeviceNamingPage;
