import React, { useState, useEffect } from 'react';
import './App.css';
import DeviceCard from './components/DeviceCard';
import DeviceDetailCard from './components/DeviceDetailCard';
import DecoTopologyPage from './pages/DecoTopologyPage';
import SettingsPage from './pages/SettingsPage';
import AlexaDevicesPage from './pages/AlexaDevicesPage';
import SmartHomePage from './pages/SmartHomePage';
import { buildUrl } from './utils/apiConfig';
import ViewModeToggle from './components/ViewModeToggle';

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('hs_theme') || 'deep-slate');
  const [apiStatus, setApiStatus] = useState('connecting...');
  const [devices, setDevices] = useState([]);
  const [pollingConfig, setPollingConfig] = useState(null);
  const [lastScanTime, setLastScanTime] = useState(null);
  const [loading, setLoading] = useState(false);
  const [deviceGroups, setDeviceGroups] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [showDetailCard, setShowDetailCard] = useState(false);
  const [editingDevice, setEditingDevice] = useState(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [deviceViewMode, setDeviceViewMode] = useState('list');
  const [deviceQuery, setDeviceQuery] = useState('');
  const [deviceStatusFilter, setDeviceStatusFilter] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: 'lastSeen', direction: 'desc' });
  const [nameDropdownDevice, setNameDropdownDevice] = useState(null); // device_id of open dropdown
  const [customNameInput, setCustomNameInput] = useState('');
  const [nameActionLoading, setNameActionLoading] = useState(false);
  const [formData, setFormData] = useState({
    friendly_name: '',
    device_type: '',
    notes: '',
  });
  // 2026-03-10: Deco node mapping — which Deco each client is connected to
  const [clientNodeMap, setClientNodeMap] = useState({});

  useEffect(() => {
    // Check backend API health
    const checkHealth = async () => {
      try {
        const response = await fetch(buildUrl('/health'));
        if (response.ok) {
          await response.json();
          setApiStatus('connected');
        } else {
          setApiStatus('error');
        }
      } catch (error) {
        console.error('Health check failed:', error);
        setApiStatus('disconnected');
      }
    };

    const getDevices = async () => {
      try {
        const response = await fetch(buildUrl('/devices'));
        if (response.ok) {
          const data = await response.json();
          setDevices(data.devices || []);
          setLastScanTime(data.timestamp);
        }
      } catch (error) {
        console.error('Failed to fetch devices:', error);
      }
    };

    const getPollingConfig = async () => {
      try {
        const response = await fetch(buildUrl('/config/polling'));
        if (response.ok) {
          const data = await response.json();
          setPollingConfig(data);
        }
      } catch (error) {
        console.error('Failed to fetch polling config:', error);
      }
    };

    const getDeviceGroups = async () => {
      try {
        const response = await fetch(buildUrl('/device-groups'));
        if (response.ok) {
          const data = await response.json();
          setDeviceGroups(data.groups || []);
        }
      } catch (error) {
        console.error('Failed to fetch device groups:', error);
      }
    };

    // 2026-03-10: Fetch Deco client-to-node mapping for dashboard "Deco" column
    const getClientNodeMap = async () => {
      try {
        const response = await fetch(buildUrl('/deco/client-node-map'));
        if (response.ok) {
          const data = await response.json();
          setClientNodeMap(data.client_node_map || {});
        }
      } catch (error) {
        // Silently fail — Deco may not be configured
      }
    };

    checkHealth();
    getDevices();
    getPollingConfig();
    getDeviceGroups();
    getClientNodeMap();

    const interval = setInterval(() => {
      checkHealth();
      getDevices();
      getPollingConfig();
      getDeviceGroups();
      getClientNodeMap();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // One-time migration: switch old default users to Deep Slate.
    const migrated = localStorage.getItem('hs_theme_default_migrated');
    if (migrated) return;

    const storedTheme = localStorage.getItem('hs_theme');
    if (!storedTheme || storedTheme === 'blue-steel') {
      setTheme('deep-slate');
      localStorage.setItem('hs_theme', 'deep-slate');
    }
    localStorage.setItem('hs_theme_default_migrated', '1');
  }, []);

  useEffect(() => {
    localStorage.setItem('hs_theme', theme);
  }, [theme]);

  const triggerManualScan = async () => {
    setLoading(true);
    try {
      const response = await fetch(buildUrl('/devices/scan-now'), {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        console.log('Manual scan completed:', data);
        // Refresh devices after scan
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      }
    } catch (error) {
      console.error('Failed to trigger manual scan:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeviceClick = (device) => {
    setSelectedDevice(device);
    setShowDetailCard(true);
  };

  const handleDetailCardClose = () => {
    setShowDetailCard(false);
    setSelectedDevice(null);
  };

  const handleDeviceUpdate = (updatedDevice) => {
    setDevices(devices.map(d => d.device_id === updatedDevice.device_id ? updatedDevice : d));
    setSelectedDevice(updatedDevice);
  };

  // Handle Escape key to close detail card and name dropdown
  useEffect(() => {
    const handleEscapeKey = (e) => {
      if (e.key === 'Escape') {
        if (nameDropdownDevice) {
          setNameDropdownDevice(null);
        } else if (showDetailCard) {
          handleDetailCardClose();
        }
      }
    };

    const handleClickOutside = () => {
      if (nameDropdownDevice) setNameDropdownDevice(null);
    };

    window.addEventListener('keydown', handleEscapeKey);
    window.addEventListener('click', handleClickOutside);
    return () => {
      window.removeEventListener('keydown', handleEscapeKey);
      window.removeEventListener('click', handleClickOutside);
    };
  }, [showDetailCard, nameDropdownDevice]);

  const openEditModal = (device) => {
    setEditingDevice(device);
    setFormData({
      friendly_name: device.friendly_name || '',
      device_type: device.device_type || '',
      notes: device.notes || '',
    });
    setShowEditModal(true);
  };

  const closeEditModal = () => {
    setShowEditModal(false);
    setEditingDevice(null);
    setFormData({
      friendly_name: '',
      device_type: '',
      notes: '',
    });
  };

  const saveDeviceChanges = async () => {
    if (!editingDevice) return;

    try {
      const response = await fetch(
        buildUrl(`/devices/${editingDevice.device_id}`),
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData),
        }
      );

      if (response.ok) {
        const updatedDevice = await response.json();
        setDevices(devices.map(d => d.device_id === updatedDevice.device_id ? updatedDevice : d));
        closeEditModal();
        alert('Device updated successfully');
      } else {
        alert('Failed to update device');
      }
    } catch (error) {
      console.error('Failed to save device:', error);
      alert('Error saving device');
    }
  };

  // Set a display name for a device (stored in DB as friendly_name).
  // Note: Deco client names are read-only (auto-detected by router fingerprinting).
  // The Deco local API has no endpoint for renaming clients — names on the Deco app
  // are stored in the TP-Link cloud, not on the router.
  const setCustomName = async (device, newName) => {
    setNameActionLoading(true);
    try {
      const res = await fetch(buildUrl(`/devices/${device.device_id}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ friendly_name: newName }),
      });
      if (res.ok) {
        const updated = await res.json();
        setDevices(prev => prev.map(d =>
          d.device_id === updated.device_id ? updated : d
        ));
      }
    } catch (e) {
      console.error('Failed to set custom name:', e);
    } finally {
      setNameActionLoading(false);
      setNameDropdownDevice(null);
      setCustomNameInput('');
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getSortableValue = (device, key) => {
    switch (key) {
      case 'decoName':
        return (device.friendly_name || device.deco_name || device.mac_address || '').toLowerCase();
      case 'alexaName':
        return (device.alexa_name || '').toLowerCase();
      case 'decoNode': {
        const mac = (device.mac_address || '').toLowerCase();
        const nodeInfo = clientNodeMap[mac];
        return (nodeInfo ? nodeInfo.node_name : '').toLowerCase();
      }
      case 'status':
        return (device.status || '').toLowerCase();
      case 'ip':
        return (device.current_ip || '').toLowerCase();
      case 'mac':
        return (device.mac_address || '').toLowerCase();
      case 'vendor':
        return (device.vendor_name || '').toLowerCase();
      case 'lastSeen':
        return device.last_seen ? new Date(device.last_seen).getTime() : 0;
      default:
        return '';
    }
  };

  const requestSort = (key) => {
    setSortConfig((prev) => {
      if (prev.key === key) {
        return { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { key, direction: 'asc' };
    });
  };

  const getSortIndicator = (key) => {
    if (sortConfig.key !== key) return '↕';
    return sortConfig.direction === 'asc' ? '▲' : '▼';
  };

  const filteredDevices = devices.filter((device) => {
    if (deviceStatusFilter && device.status !== deviceStatusFilter) {
      return false;
    }

    const q = deviceQuery.trim().toLowerCase();
    if (!q) return true;

    const mac = (device.mac_address || '').toLowerCase();
    const nodeInfo = clientNodeMap[mac];
    const searchableFields = [
      device.deco_name,
      device.alexa_name,
      nodeInfo ? nodeInfo.node_name : '',
      device.friendly_name,
      device.hostname,
      device.mac_address,
      device.current_ip,
      device.vendor_name,
      device.status,
    ];

    return searchableFields.some((field) => String(field || '').toLowerCase().includes(q));
  });

  const displayedDevices = [...filteredDevices].sort((a, b) => {
    const aValue = getSortableValue(a, sortConfig.key);
    const bValue = getSortableValue(b, sortConfig.key);

    let comparison = 0;
    if (typeof aValue === 'number' && typeof bValue === 'number') {
      comparison = aValue - bValue;
    } else {
      comparison = String(aValue).localeCompare(String(bValue), undefined, { numeric: true, sensitivity: 'base' });
    }

    return sortConfig.direction === 'asc' ? comparison : -comparison;
  });

  const getDeviceDisplayName = (device) => {
    return device.friendly_name || device.deco_name || device.mac_address;
  };

  const vendorNamesPresent = devices.filter(d => d.vendor_name).length;

  // Calculate status summary
  const onlineCount = devices.filter(d => d.status === 'online').length;
  const offlineCount = devices.filter(d => d.status === 'offline').length;

  return (
    <div className={`App theme-${theme}`}>
      <header className="App-header">
        <div className="header-content">
          <h1>HomeSentinel</h1>
          <p>Home Network Monitor & Device Management Platform</p>
        </div>
        <nav className="main-nav">
          <button
            className={`nav-button ${currentPage === 'dashboard' ? 'active' : ''}`}
            onClick={() => setCurrentPage('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={`nav-button ${currentPage === 'topology' ? 'active' : ''}`}
            onClick={() => setCurrentPage('topology')}
          >
            Network Topology
          </button>
          <button
            className={`nav-button ${currentPage === 'alexa' ? 'active' : ''}`}
            onClick={() => setCurrentPage('alexa')}
          >
            Alexa
          </button>
          <button
            className={`nav-button ${currentPage === 'smart-home' ? 'active' : ''}`}
            onClick={() => setCurrentPage('smart-home')}
          >
            Smart Home
          </button>
          <button
            className={`nav-button ${currentPage === 'settings' ? 'active' : ''}`}
            onClick={() => setCurrentPage('settings')}
          >
            Settings
          </button>
        </nav>
      </header>
      <main className="App-main">
        {/* Network Topology Page */}
        {currentPage === 'topology' && <DecoTopologyPage />}

        {/* Alexa Devices Page */}
        {currentPage === 'alexa' && <AlexaDevicesPage />}

        {/* Smart Home Control Page */}
        {currentPage === 'smart-home' && <SmartHomePage />}

        {/* Settings Page */}
        {currentPage === 'settings' && (
          <SettingsPage
            theme={theme}
            onThemeChange={setTheme}
          />
        )}

        {/* Dashboard Page */}
        {currentPage === 'dashboard' && (
          <>
        {/* Status Summary */}
        <div className="status-summary">
          <div className="summary-card">
            <div className="summary-label">Total Devices</div>
            <div className="summary-value">{devices.length}</div>
          </div>
          <div className="summary-card online">
            <div className="summary-label">Online</div>
            <div className="summary-value">{onlineCount}</div>
          </div>
          <div className="summary-card offline">
            <div className="summary-label">Offline</div>
            <div className="summary-value">{offlineCount}</div>
          </div>
          <div className="summary-card">
            <div className="summary-label">Last Refreshed</div>
            <div className="summary-value timestamp-small">
              {lastScanTime ? new Date(lastScanTime).toLocaleTimeString() : 'Never'}
            </div>
          </div>
        </div>
        <div className="status-card">
          <h2>System Status</h2>
          <p>API Connection: <strong className={apiStatus === 'connected' ? 'status-ok' : 'status-error'}>{apiStatus}</strong></p>
          {pollingConfig && (
            <>
              <p>Polling Interval: <strong>{pollingConfig.interval}s</strong></p>
              <p>Last Scanned: <strong>{formatDate(pollingConfig.last_scan)}</strong></p>
            </>
          )}
          <p>Devices with Vendor Info: <strong>{vendorNamesPresent}/{devices.length}</strong></p>
        </div>

        {deviceGroups.length > 0 && (
          <div className="groups-card">
            <h2>Device Groups ({deviceGroups.length})</h2>
            <div className="groups-container">
              {deviceGroups.map((group) => (
                <div key={group.group_id} className="group-item" style={{ borderLeftColor: group.color }}>
                  <h3>{group.name}</h3>
                  <p className="group-color" style={{ backgroundColor: group.color }}>Color: {group.color}</p>
                  <p className="group-timestamp">Created: {formatDate(group.created_at)}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="devices-card">
          <div className="devices-header">
            <div className="devices-header-left">
              <h2>Network Devices ({displayedDevices.length})</h2>
            </div>
            <div className="devices-filter-row">
              <input
                type="text"
                className="devices-search-input"
                placeholder="Search devices..."
                value={deviceQuery}
                onChange={(e) => setDeviceQuery(e.target.value)}
              />
              <select
                className="devices-status-filter"
                value={deviceStatusFilter}
                onChange={(e) => setDeviceStatusFilter(e.target.value)}
              >
                <option value="">All Status</option>
                <option value="online">Online</option>
                <option value="offline">Offline</option>
              </select>
            </div>
            <div className="devices-actions">
              <ViewModeToggle
                label="Devices"
                value={deviceViewMode}
                onChange={setDeviceViewMode}
              />
              <button
                onClick={triggerManualScan}
                disabled={loading}
                className="scan-button"
              >
                {loading ? 'Scanning...' : 'Scan Now'}
              </button>
              {lastScanTime && (
                <span className="device-info">
                  Updated: {new Date(lastScanTime).toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>
          {displayedDevices.length > 0 ? (
            deviceViewMode === 'grid' ? (
              <div className="devices-grid">
                {displayedDevices.map((device) => (
                  <DeviceCard
                    key={device.device_id}
                    device={device}
                    groups={deviceGroups}
                    onClick={() => handleDeviceClick(device)}
                  />
                ))}
              </div>
            ) : (
              <table className="devices-table">
                <thead>
                  <tr>
                    <th>
                      <button className="sort-button" onClick={() => requestSort('decoName')}>
                        Name <span className="sort-indicator">{getSortIndicator('decoName')}</span>
                      </button>
                    </th>
                    <th>
                      <button className="sort-button" onClick={() => requestSort('alexaName')}>
                        Alexa Name <span className="sort-indicator">{getSortIndicator('alexaName')}</span>
                      </button>
                    </th>
                    <th>
                      <button className="sort-button" onClick={() => requestSort('decoNode')}>
                        Deco <span className="sort-indicator">{getSortIndicator('decoNode')}</span>
                      </button>
                    </th>
                    <th>
                      <button className="sort-button" onClick={() => requestSort('status')}>
                        Status <span className="sort-indicator">{getSortIndicator('status')}</span>
                      </button>
                    </th>
                    <th>
                      <button className="sort-button" onClick={() => requestSort('ip')}>
                        IP Address <span className="sort-indicator">{getSortIndicator('ip')}</span>
                      </button>
                    </th>
                    <th>
                      <button className="sort-button" onClick={() => requestSort('mac')}>
                        MAC Address <span className="sort-indicator">{getSortIndicator('mac')}</span>
                      </button>
                    </th>
                    <th>
                      <button className="sort-button" onClick={() => requestSort('vendor')}>
                        Vendor <span className="sort-indicator">{getSortIndicator('vendor')}</span>
                      </button>
                    </th>
                    <th>
                      <button className="sort-button" onClick={() => requestSort('lastSeen')}>
                        Last Seen <span className="sort-indicator">{getSortIndicator('lastSeen')}</span>
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {displayedDevices.map((device) => {
                    const decoName = device.deco_name || '';
                    const alexaName = device.alexa_name || '';
                    const hasMismatch = decoName && alexaName && decoName !== alexaName;
                    const isDropdownOpen = nameDropdownDevice === device.device_id;

                    return (
                    <tr
                      key={device.device_id}
                      className={`device-row ${device.status === 'online' ? 'online' : 'offline'}`}
                      onClick={() => !isDropdownOpen && handleDeviceClick(device)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          handleDeviceClick(device);
                        }
                      }}
                    >
                      <td className="device-name">
                        {device.friendly_name || decoName || device.mac_address}
                      </td>
                      <td className="alexa-name-cell">
                        {alexaName || <span className="na-text">N/A</span>}
                        {/* 2026-03-10: Always show rename dropdown, not just when alexa/deco names exist */}
                        {(
                          <div className="name-action-wrapper">
                            <button
                              className="name-action-btn"
                              title="Name actions"
                              onClick={(e) => {
                                e.stopPropagation();
                                setNameDropdownDevice(isDropdownOpen ? null : device.device_id);
                                setCustomNameInput('');
                              }}
                            >
                              &#9662;
                            </button>
                            {isDropdownOpen && (
                              <div className="name-dropdown" onClick={(e) => e.stopPropagation()}>
                                {alexaName && alexaName !== device.friendly_name && (
                                  <button
                                    className="dropdown-item"
                                    disabled={nameActionLoading}
                                    onClick={() => setCustomName(device, alexaName)}
                                  >
                                    Use Alexa name "{alexaName}"
                                  </button>
                                )}
                                {decoName && decoName !== device.friendly_name && decoName !== alexaName && (
                                  <button
                                    className="dropdown-item"
                                    disabled={nameActionLoading}
                                    onClick={() => setCustomName(device, decoName)}
                                  >
                                    Use Deco name "{decoName}"
                                  </button>
                                )}
                                <div className="dropdown-custom">
                                  <input
                                    type="text"
                                    placeholder="Custom name..."
                                    value={customNameInput}
                                    onChange={(e) => setCustomNameInput(e.target.value)}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter' && customNameInput.trim()) {
                                        setCustomName(device, customNameInput.trim());
                                      }
                                    }}
                                  />
                                  <button
                                    className="dropdown-item custom-save"
                                    disabled={nameActionLoading || !customNameInput.trim()}
                                    onClick={() => setCustomName(device, customNameInput.trim())}
                                  >
                                    Set Name
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="deco-node-cell">
                        {(() => {
                          const mac = (device.mac_address || '').toLowerCase();
                          const nodeInfo = clientNodeMap[mac];
                          if (nodeInfo) {
                            return (
                              <span className="deco-node-name" title={`Connected via ${nodeInfo.connection_type || 'unknown'}`}>
                                {nodeInfo.node_name}
                              </span>
                            );
                          }
                          return <span className="na-text">—</span>;
                        })()}
                      </td>
                      <td className="status">
                        <span className={`status-badge ${device.status === 'online' ? 'online' : 'offline'}`}>
                          {device.status === 'online' ? 'Online' : 'Offline'}
                        </span>
                      </td>
                      <td className="ip-address">{device.current_ip || 'N/A'}</td>
                      <td className="mac-address">{device.mac_address}</td>
                      <td className="vendor-name">{device.vendor_name || 'Unknown'}</td>
                      <td className="timestamp">{formatDate(device.last_seen)}</td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            )
          ) : (
            <p className="no-devices">
              {devices.length > 0
                ? 'No devices match the current search or status filter.'
                : 'No devices discovered yet. Click "Scan Now" to start discovery.'}
            </p>
          )}
        </div>

        {/* Detail Card - New Component */}
        {showDetailCard && selectedDevice && (
          <DeviceDetailCard
            device={selectedDevice}
            groups={deviceGroups}
            onClose={handleDetailCardClose}
            onUpdate={handleDeviceUpdate}
          />
        )}

        {/* Legacy Edit Modal - Keeping for backwards compatibility */}
        {showEditModal && editingDevice && (
          <div className="modal-overlay">
            <div className="modal-content">
              <h2>Edit Device: {editingDevice.mac_address}</h2>
              <form>
                <div className="form-group">
                  <label htmlFor="friendly_name">Friendly Name:</label>
                  <input
                    type="text"
                    id="friendly_name"
                    value={formData.friendly_name}
                    onChange={(e) =>
                      setFormData({ ...formData, friendly_name: e.target.value })
                    }
                    placeholder="e.g., Living Room TV"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="device_type">Device Type:</label>
                  <select
                    id="device_type"
                    value={formData.device_type}
                    onChange={(e) =>
                      setFormData({ ...formData, device_type: e.target.value })
                    }
                  >
                    <option value="">Select type...</option>
                    <option value="mobile">Mobile</option>
                    <option value="computer">Computer</option>
                    <option value="iot">IoT</option>
                    <option value="printer">Printer</option>
                    <option value="router">Router</option>
                    <option value="tv">Smart TV</option>
                    <option value="camera">Camera</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="notes">Notes:</label>
                  <textarea
                    id="notes"
                    value={formData.notes}
                    onChange={(e) =>
                      setFormData({ ...formData, notes: e.target.value })
                    }
                    placeholder="Add any notes about this device..."
                    rows="4"
                  />
                </div>
                <div className="modal-buttons">
                  <button
                    type="button"
                    className="btn-save"
                    onClick={saveDeviceChanges}
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    className="btn-cancel"
                    onClick={closeEditModal}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        <div className="info-card">
          <h3>Welcome to HomeSentinel</h3>
          <p>This is the home network monitoring dashboard. The system is currently discovering devices on your network.</p>
          <p><strong>Backend:</strong> https://localhost:8443</p>
          <p><strong>Frontend:</strong> http://localhost:3000</p>
          <p><strong>Features:</strong> OUI vendor lookup, device metadata, device grouping, and Deco mesh monitoring</p>
        </div>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
