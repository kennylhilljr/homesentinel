import React, { useState, useEffect } from 'react';
import './App.css';
import DeviceCard from './components/DeviceCard';
import DeviceDetailCard from './components/DeviceDetailCard';
import DecoTopologyPage from './pages/DecoTopologyPage';
import SettingsPage from './pages/SettingsPage';
import AlexaDevicesPage from './pages/AlexaDevicesPage';
import SmartHomePage from './pages/SmartHomePage';
import SpeedInsightsPage from './pages/SpeedInsightsPage';
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
  // 2026-03-12: Inline rename on double-click
  const [inlineEditId, setInlineEditId] = useState(null);
  const [inlineEditValue, setInlineEditValue] = useState('');
  const [formData, setFormData] = useState({
    friendly_name: '',
    device_type: '',
    notes: '',
  });
  // 2026-03-10: Deco node mapping — which Deco each client is connected to
  const [clientNodeMap, setClientNodeMap] = useState({});
  // 2026-03-11: Set of normalized Deco node MACs (for hiding mesh toggle on nodes)
  const [decoNodeMacs, setDecoNodeMacs] = useState(new Set());
  // 2026-03-11: Map of Deco node MAC → node name (for connection preference dropdown)
  const [decoNodesMap, setDecoNodesMap] = useState({});
  // 2026-03-11: Map of Deco node MAC → { name, role, backhaul, backhaul_bands }
  const [decoNodeDetails, setDecoNodeDetails] = useState({});
  // 2026-03-11: Optimize network state
  const [optimizeLoading, setOptimizeLoading] = useState(false);
  // 2026-03-11: Speed test state
  const [speedTestData, setSpeedTestData] = useState(null);
  const [speedTestRunning, setSpeedTestRunning] = useState(false);
  // 2026-03-11: Chester 5G cellular info for dashboard card
  const [chesterInfo, setChesterInfo] = useState(null);
  // 2026-03-12: Home/Away network detection state
  // 2026-03-12: Default to home=true until backend confirms, avoids flash of "Away"
  const [homeStatus, setHomeStatus] = useState({ is_home: true, method: 'init', detail: 'loading...', auto_scan_active: true, auto_scan_paused: false });
  // 2026-03-11: Banner notification state (replaces all alert() popups)
  const [banner, setBanner] = useState(null); // { message, type: 'success'|'error'|'info' }

  const showBanner = (message, type = 'info') => {
    setBanner({ message, type });
    setTimeout(() => setBanner(null), type === 'error' ? 6000 : 4000);
  };

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
          // 2026-03-11: Store normalized Deco node MACs for mesh toggle exclusion
          if (data.nodes) {
            const nodeMacs = new Set(
              Object.keys(data.nodes).map(m => m.toLowerCase().replace(/-/g, ':'))
            );
            setDecoNodeMacs(nodeMacs);
            setDecoNodesMap(data.nodes);
            // 2026-03-11: Store node details for backhaul signal icons
            if (data.node_details) {
              // Normalize keys to lowercase colon format
              const normalized = {};
              for (const [k, v] of Object.entries(data.node_details)) {
                const nk = k.toLowerCase().replace(/-/g, ':');
                normalized[nk] = v;
              }
              setDecoNodeDetails(normalized);
            }
          }
        }
      } catch (error) {
        // Silently fail — Deco may not be configured
      }
    };

    // 2026-03-11: Fetch latest speed test result with % change
    const getSpeedTestLatest = async () => {
      try {
        const response = await fetch(buildUrl('/speedtest/latest'));
        if (response.ok) {
          const data = await response.json();
          setSpeedTestData(data);
        }
      } catch (error) {
        // Silently fail — speed test may not have run yet
      }
    };

    // 2026-03-11: Fetch Chester 5G cellular info for dashboard card
    const getChesterInfo = async () => {
      try {
        const response = await fetch(buildUrl('/chester/system-info'));
        if (response.ok) {
          const data = await response.json();
          setChesterInfo(data);
        }
      } catch (error) {
        // Silently fail — Chester may not be reachable
      }
    };

    // 2026-03-12: Home/Away network detection
    const getHomeStatus = async () => {
      try {
        const response = await fetch(buildUrl('/network/home-status'));
        if (response.ok) {
          const data = await response.json();
          setHomeStatus(data);
        }
      } catch (error) {
        // Silently fail
      }
    };

    checkHealth();
    getDevices();
    getPollingConfig();
    getDeviceGroups();
    getClientNodeMap();
    getSpeedTestLatest();
    getChesterInfo();
    getHomeStatus();

    // 2026-03-11: Fast poll for devices/health (5s), slow poll for Deco map (30s)
    const fastInterval = setInterval(() => {
      checkHealth();
      getDevices();
      getPollingConfig();
      getDeviceGroups();
      getHomeStatus();
    }, 5000);

    const slowInterval = setInterval(() => {
      getClientNodeMap();
      getChesterInfo();
    }, 30000);

    // 2026-03-11: Speed test poll (60s) — updates after scheduled 30-min tests
    const speedInterval = setInterval(() => {
      getSpeedTestLatest();
    }, 60000);

    return () => {
      clearInterval(fastInterval);
      clearInterval(slowInterval);
      clearInterval(speedInterval);
    };
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

  // 2026-03-10: Toggle mesh steering per client device
  const toggleClientMesh = async (macAddress, currentMeshValue) => {
    const newValue = !currentMeshValue;
    try {
      const response = await fetch(buildUrl('/deco/client-mesh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mac_address: macAddress, mesh_enabled: newValue }),
      });
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          // Optimistically update local state
          setClientNodeMap(prev => {
            const mac = macAddress.toLowerCase();
            if (prev[mac]) {
              return { ...prev, [mac]: { ...prev[mac], client_mesh: newValue } };
            }
            return prev;
          });
        } else {
          console.warn('Mesh toggle returned error_code:', data.error_code);
        }
      }
    } catch (error) {
      console.error('Failed to toggle client mesh:', error);
    }
  };

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

  // 2026-03-11: Trigger Deco mesh network optimization
  const optimizeNetwork = async () => {
    setOptimizeLoading(true);
    try {
      const response = await fetch(buildUrl('/deco/optimize-network'), {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          showBanner(data.message, 'success');
        } else {
          showBanner(`Optimization failed: ${data.message}`, 'error');
        }
      } else {
        showBanner('Failed to start optimization. Deco may not be reachable.', 'error');
      }
    } catch (error) {
      console.error('Failed to optimize network:', error);
      showBanner('Failed to optimize network. Check Deco connectivity.', 'error');
    } finally {
      setOptimizeLoading(false);
    }
  };

  // 2026-03-11: Manual speed test trigger
  const runSpeedTest = async () => {
    setSpeedTestRunning(true);
    try {
      const response = await fetch(buildUrl('/speedtest/run'), { method: 'POST' });
      if (response.ok) {
        const result = await response.json();
        if (result.error) {
          showBanner(`Speed test error: ${result.error}`, 'error');
        } else {
          // Refresh latest data
          const latestResp = await fetch(buildUrl('/speedtest/latest'));
          if (latestResp.ok) {
            setSpeedTestData(await latestResp.json());
          }
          showBanner('Speed test completed', 'success');
        }
      } else {
        showBanner('Speed test failed. Check Chester connectivity.', 'error');
      }
    } catch (error) {
      console.error('Speed test failed:', error);
      showBanner('Speed test failed. Check Chester connectivity.', 'error');
    } finally {
      setSpeedTestRunning(false);
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
        showBanner('Device updated successfully', 'success');
      } else {
        showBanner('Failed to update device', 'error');
      }
    } catch (error) {
      console.error('Failed to save device:', error);
      showBanner('Error saving device', 'error');
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

  // 2026-03-11: Set preferred Deco node for a device (null = auto, MAC = pinned)
  const setPreferredDecoNode = async (deviceId, nodeMAC) => {
    try {
      const res = await fetch(buildUrl(`/devices/${deviceId}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preferred_deco_node: nodeMAC }),
      });
      if (res.ok) {
        const updated = await res.json();
        setDevices(prev => prev.map(d =>
          d.device_id === updated.device_id ? updated : d
        ));
      }
    } catch (e) {
      console.error('Failed to set preferred Deco node:', e);
    }
  };

  // 2026-03-11: All dates displayed in Eastern Time
  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString + (dateString.endsWith('Z') || dateString.includes('+') ? '' : 'Z'));
    return date.toLocaleString('en-US', { timeZone: 'America/New_York' });
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
      {/* 2026-03-12: aria-live for screen reader accessibility */}
      <div aria-live="polite" aria-atomic="true" role="status">
        {banner && (
          <div className={`app-banner app-banner-${banner.type}`}>
            {banner.message}
            <button className="banner-close" onClick={() => setBanner(null)} aria-label="Dismiss notification">&times;</button>
          </div>
        )}
      </div>
      <header className="App-header">
        <div className="header-content">
          <h1>HomeSentinel</h1>
          <p>Home Network Monitor & Device Management Platform</p>
        </div>
        {/* 2026-03-12: Nav consolidated into 3 groups — Network | Smart Home | Performance */}
        <nav className="main-nav">
          <div className="nav-group">
            <span className="nav-group-label">Network</span>
            <div className="nav-group-buttons">
              <button className={`nav-button ${currentPage === 'dashboard' ? 'active' : ''}`} onClick={() => setCurrentPage('dashboard')}>Dashboard</button>
              <button className={`nav-button ${currentPage === 'topology' ? 'active' : ''}`} onClick={() => setCurrentPage('topology')}>Topology</button>
            </div>
          </div>
          <div className="nav-group">
            <span className="nav-group-label">Smart Home</span>
            <div className="nav-group-buttons">
              <button className={`nav-button ${currentPage === 'alexa' ? 'active' : ''}`} onClick={() => setCurrentPage('alexa')}>Alexa</button>
              <button className={`nav-button ${currentPage === 'smart-home' ? 'active' : ''}`} onClick={() => setCurrentPage('smart-home')}>Controls</button>
            </div>
          </div>
          <div className="nav-group">
            <span className="nav-group-label">Performance</span>
            <div className="nav-group-buttons">
              <button className={`nav-button ${currentPage === 'speed-insights' ? 'active' : ''}`} onClick={() => setCurrentPage('speed-insights')}>Speed</button>
            </div>
          </div>
          <button className={`nav-button nav-settings ${currentPage === 'settings' ? 'active' : ''}`} onClick={() => setCurrentPage('settings')}>Settings</button>
        </nav>
      </header>
      <main className="App-main">
        {/* Network Topology Page */}
        {currentPage === 'topology' && <DecoTopologyPage />}

        {/* Alexa Devices Page */}
        {currentPage === 'alexa' && <AlexaDevicesPage />}

        {/* Smart Home Control Page */}
        {currentPage === 'smart-home' && <SmartHomePage />}

        {/* Speed Insights Page */}
        {currentPage === 'speed-insights' && <SpeedInsightsPage />}

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
          <div className={`summary-card ${homeStatus?.is_home ? 'home' : 'away'}`}>
            <div className="summary-label">{homeStatus?.is_home ? 'Home' : 'Away'}</div>
            <div className="summary-value home-icon">
              <svg viewBox="0 0 24 24" width="36" height="36">
                <path d="M3 12 L12 3 L21 12 V21 H15 V15 H9 V21 H3 Z"
                  fill={homeStatus?.is_home ? '#2e7d32' : '#e67e22'}
                  stroke={homeStatus?.is_home ? '#1b5e20' : '#d35400'}
                  strokeWidth="1.5" strokeLinejoin="round"/>
              </svg>
            </div>
          </div>
        </div>
        {/* 2026-03-11: Three-card layout — System + 5G Signal + Speed Test */}
        <div className="status-split status-split-3">
          <div className="status-card status-card-compact">
            <h2>System Status</h2>
            <p>API: <strong className={apiStatus === 'connected' ? 'status-ok' : 'status-error'}>{apiStatus}</strong></p>
            {pollingConfig && (
              <p>Scan: <strong>{pollingConfig.interval}s</strong> — {formatDate(pollingConfig.last_scan)}</p>
            )}
            <p>Vendors: <strong>{vendorNamesPresent}/{devices.length}</strong></p>
          </div>

          {/* 2026-03-11: 5G Cellular Signal card — live Chester router metrics */}
          <div className="status-card cellular-card">
            <h2>5G Signal</h2>
            {chesterInfo ? (
              <div className="cellular-info">
                <div className="cellular-type">
                  <span className={`cellular-badge ${chesterInfo.is_5g ? 'badge-5g' : 'badge-lte'}`}>
                    {chesterInfo.connection_type || 'Unknown'}
                  </span>
                  {chesterInfo.ca_band && chesterInfo.ca_band.length > 0 && (
                    <span className="cellular-ca-count">{chesterInfo.ca_band.length}x CA</span>
                  )}
                </div>
                <div className="cellular-metrics">
                  <div className="cellular-metric">
                    <span className="cellular-label">RSRP</span>
                    <span className={`cellular-value ${
                      chesterInfo.rsrp > -80 ? 'signal-excellent' :
                      chesterInfo.rsrp > -100 ? 'signal-good' :
                      chesterInfo.rsrp > -110 ? 'signal-fair' : 'signal-poor'
                    }`}>{chesterInfo.rsrp} <small>dBm</small></span>
                  </div>
                  <div className="cellular-metric">
                    <span className="cellular-label">SINR</span>
                    <span className={`cellular-value ${
                      chesterInfo.sinr > 20 ? 'signal-excellent' :
                      chesterInfo.sinr > 10 ? 'signal-good' :
                      chesterInfo.sinr > 0 ? 'signal-fair' : 'signal-poor'
                    }`}>{chesterInfo.sinr} <small>dB</small></span>
                  </div>
                  <div className="cellular-metric">
                    <span className="cellular-label">RSRQ</span>
                    <span className="cellular-value">{chesterInfo.rsrq} <small>dB</small></span>
                  </div>
                  <div className="cellular-metric">
                    <span className="cellular-label">Band</span>
                    <span className="cellular-value">n{chesterInfo.band}</span>
                  </div>
                </div>
                {chesterInfo.ca_band && chesterInfo.ca_band.length > 0 && (
                  <div className="cellular-ca-list">
                    {chesterInfo.ca_band.map((entry, i) => {
                      const parts = entry.replace(/"/g, '').split(',');
                      const role = parts[0]?.trim() || '';
                      const bandName = parts[3]?.trim().replace('NR5G BAND ', 'n').replace('LTE BAND ', 'B') || '';
                      const arfcn = parts[1]?.trim() || '';
                      return (
                        <span key={i} className={`ca-chip ${role === 'PCC' ? 'ca-pcc' : 'ca-scc'}`}
                              title={`${role} — ARFCN ${arfcn}`}>
                          {role === 'PCC' ? '\u2605 ' : ''}{bandName}
                        </span>
                      );
                    })}
                  </div>
                )}
                <div className="cellular-meta">
                  <span>Cell {chesterInfo.cell_id}</span>
                  <span>PCID {chesterInfo.pcid}</span>
                  <span>ARFCN {chesterInfo.arfcn}</span>
                </div>
              </div>
            ) : (
              <p className="text-muted">Chester not reachable</p>
            )}
          </div>

          <div className="status-card speedtest-card">
            <h2>Speed Test
              <button
                className="btn-speedtest-run"
                onClick={runSpeedTest}
                disabled={speedTestRunning}
                title="Run speed test on Chester router via SSH"
              >
                {speedTestRunning ? 'Testing...' : 'Run Now'}
              </button>
            </h2>
            {speedTestData && speedTestData.latest ? (() => {
              const st = speedTestData.latest;
              const ch = speedTestData.change;
              const renderChange = (pct, invertColor) => {
                if (pct == null) return null;
                // For ping, negative = good (invertColor=true)
                const isGood = invertColor ? pct < 0 : pct > 0;
                const arrow = pct > 0 ? '\u25B2' : pct < 0 ? '\u25BC' : '';
                const cls = isGood ? 'change-good' : 'change-bad';
                return <span className={`speed-change ${cls}`}>{arrow} {Math.abs(pct)}%</span>;
              };
              return (
                <div className="speedtest-results">
                  <div className="speedtest-metrics">
                    <div className="speed-metric download">
                      <span className="speed-label">Download</span>
                      <span className="speed-value">{st.download_mbps.toFixed(1)}</span>
                      <span className="speed-unit">Mbps</span>
                      {ch && renderChange(ch.download_pct, false)}
                    </div>
                    <div className="speed-metric upload">
                      <span className="speed-label">Upload</span>
                      <span className="speed-value">{st.upload_mbps.toFixed(1)}</span>
                      <span className="speed-unit">Mbps</span>
                      {ch && renderChange(ch.upload_pct, false)}
                    </div>
                    <div className="speed-metric ping">
                      <span className="speed-label">Ping</span>
                      <span className="speed-value">{st.ping_ms.toFixed(0)}</span>
                      <span className="speed-unit">ms</span>
                      {ch && renderChange(ch.ping_pct, true)}
                    </div>
                    {st.jitter_ms != null && (
                      <div className="speed-metric jitter">
                        <span className="speed-label">Jitter</span>
                        <span className="speed-value">{st.jitter_ms.toFixed(1)}</span>
                        <span className="speed-unit">ms</span>
                      </div>
                    )}
                  </div>
                  <div className="speedtest-meta">
                    <span>via {st.server_name || 'Unknown'}</span>
                    <span>{st.isp || ''}</span>
                    <span>{formatDate(st.timestamp)}</span>
                  </div>
                </div>
              );
            })() : (
              <div className="speedtest-empty">
                <p>No speed test results yet</p>
                <p className="text-muted">Tests run every 30 minutes on the Chester router</p>
              </div>
            )}
          </div>
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
                label=""
                value={deviceViewMode}
                onChange={setDeviceViewMode}
              />
              {/* 2026-03-12: Auto-scan toggle — Scan/Off, same style as Tiles/List */}
              <ViewModeToggle
                label=""
                value={homeStatus?.auto_scan_active ? 'scan' : 'off'}
                onChange={(val) => {
                  const enabled = val === 'scan';
                  fetch(buildUrl('/network/auto-scan?enabled=' + enabled), { method: 'POST' })
                    .then(r => r.json())
                    .then(() => {
                      setHomeStatus(prev => prev ? { ...prev, auto_scan_paused: !enabled, auto_scan_active: enabled && prev.is_home } : prev);
                    })
                    .catch(() => {});
                }}
                options={[
                  { value: 'scan', label: 'Scan' },
                  { value: 'off', label: 'Off' },
                ]}
              />
              <button
                onClick={triggerManualScan}
                disabled={loading}
                className="scan-button"
              >
                {loading ? 'Scanning...' : 'Scan Now'}
              </button>
              {/* 2026-03-11: Download dashboard device list as CSV */}
              <button
                onClick={() => {
                  const headers = ['Name', 'Deco Node', 'Status', 'IP Address', 'MAC Address', 'Vendor', 'Last Seen'];
                  const rows = displayedDevices.map(d => {
                    const mac = (d.mac_address || '').toLowerCase();
                    const nodeInfo = clientNodeMap[mac];
                    return [
                      d.friendly_name || d.deco_name || d.mac_address || '',
                      nodeInfo ? nodeInfo.node_name : '',
                      d.status || '',
                      d.current_ip || '',
                      d.mac_address || '',
                      d.vendor_name || '',
                      d.last_seen || '',
                    ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(',');
                  });
                  const csv = [headers.join(','), ...rows].join('\n');
                  const blob = new Blob([csv], { type: 'text/csv' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `homesentinel-devices-${new Date().toISOString().slice(0, 10)}.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="scan-button"
                title="Download device list as CSV"
              >
                Download CSV
              </button>
              <button
                className="btn-optimize"
                onClick={optimizeNetwork}
                disabled={optimizeLoading}
                title="Optimize Deco mesh — re-evaluate channels, band steering, and client connections"
              >
                {optimizeLoading ? 'Optimizing...' : 'Optimize Network'}
              </button>
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
                      <button className="sort-button" onClick={() => requestSort('status')}>
                        Status <span className="sort-indicator">{getSortIndicator('status')}</span>
                      </button>
                    </th>
                    <th>
                      <button className="sort-button" onClick={() => requestSort('decoNode')}>
                        Deco Mesh Configuration <span className="sort-indicator">{getSortIndicator('decoNode')}</span>
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
                      {/* 2026-03-11: Name column — inline edit on double-click, dropdown for suggestions */}
                      <td className="device-name alexa-name-cell">
                        {inlineEditId === device.device_id ? (
                          <input
                            className="inline-rename-input"
                            type="text"
                            value={inlineEditValue}
                            autoFocus
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => setInlineEditValue(e.target.value)}
                            onKeyDown={(e) => {
                              e.stopPropagation();
                              if (e.key === 'Enter' && inlineEditValue.trim()) {
                                setCustomName(device, inlineEditValue.trim());
                                setInlineEditId(null);
                              } else if (e.key === 'Escape') {
                                setInlineEditId(null);
                              }
                            }}
                            onBlur={() => {
                              if (inlineEditValue.trim() && inlineEditValue.trim() !== (device.friendly_name || decoName || device.mac_address)) {
                                setCustomName(device, inlineEditValue.trim());
                              }
                              setInlineEditId(null);
                            }}
                          />
                        ) : (
                          <span
                            className="device-name-text"
                            title="Double-click to rename"
                            onDoubleClick={(e) => {
                              e.stopPropagation();
                              setInlineEditId(device.device_id);
                              setInlineEditValue(device.friendly_name || decoName || '');
                              setNameDropdownDevice(null);
                            }}
                          >
                            {device.friendly_name || decoName || device.mac_address}
                          </span>
                        )}
                        {/* 2026-03-12: "New" badge for devices first seen in last 24h */}
                        {device.first_seen && (Date.now() - new Date(device.first_seen + (device.first_seen.includes('Z') ? '' : 'Z')).getTime()) < 86400000 && (
                          <span className="device-new-badge">NEW</span>
                        )}
                        {inlineEditId !== device.device_id && (
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
                      {/* 2026-03-11: Status + type badge column */}
                      {(() => {
                        const mac = (device.mac_address || '').toLowerCase();
                        const nodeInfo = clientNodeMap[mac];
                        const isDecoNode = decoNodeMacs.has(mac);
                        const meshValue = nodeInfo ? !!nodeInfo.client_mesh : false;
                        const isPinned = !!device.preferred_deco_node;
                        const pinnedNodeName = isPinned
                          ? (decoNodesMap[device.preferred_deco_node] || device.preferred_deco_node)
                          : null;
                        const currentNodeName = nodeInfo ? nodeInfo.node_name : null;
                        const isOnline = device.status === 'online';
                        const wireType = nodeInfo ? (nodeInfo.wire_type || '') : '';
                        const connType = nodeInfo ? (nodeInfo.connection_type || '') : '';
                        const isWired = wireType === 'wired' || connType === 'wired';
                        // 2026-03-12: Chester 5G router gets a satellite dish icon
                        const displayName = (device.friendly_name || device.deco_name || device.mac_address || '').toLowerCase();
                        const isChester = displayName.includes('chester');
                        const chesterRsrp = chesterInfo ? chesterInfo.rsrp : null;
                        const chesterSigColor = chesterRsrp == null ? '#bbb'
                          : chesterRsrp > -80 ? '#2e7d32'
                          : chesterRsrp > -100 ? '#f9a825'
                          : '#e53935';
                        const chesterSigLabel = chesterRsrp == null ? 'Chester — no signal data'
                          : `Chester 5G — RSRP ${chesterRsrp} dBm`;
                        // Signal strength
                        // 2026-03-12: Signal level based on Wi-Fi band, not throughput.
                        // Deco local API only reports instantaneous kbps (down_speed/up_speed),
                        // NOT actual RSSI. Idle devices show ~1 kbps despite strong signal.
                        // Band is a reliable proxy: 5/6 GHz = strong, 2.4 GHz = medium.
                        let signalLevel = 'none';
                        let signalTitle = '';
                        if (nodeInfo && !isWired) {
                          const downSpeed = nodeInfo.down_speed || 0;
                          const upSpeed = nodeInfo.up_speed || 0;
                          const band = connType.toLowerCase();
                          if (band.includes('band5') || band.includes('band6')) {
                            signalLevel = 'strong';
                            signalTitle = `${band.includes('6') ? '6 GHz' : '5 GHz'} — ${downSpeed} kbps down, ${upSpeed} kbps up`;
                          } else if (band.includes('band2')) {
                            signalLevel = 'medium';
                            signalTitle = `2.4 GHz — ${downSpeed} kbps down, ${upSpeed} kbps up`;
                          } else {
                            signalLevel = 'medium';
                            signalTitle = `Wireless — ${downSpeed} kbps down, ${upSpeed} kbps up`;
                          }
                        } else if (isWired) {
                          signalTitle = 'Wired (Ethernet)';
                        }
                        // Deco node backhaul info
                        let backhaulWired = false;
                        let bhSignalLevel = 'medium';
                        let bhTitle = '';
                        if (isDecoNode) {
                          const nd = decoNodeDetails[mac] || {};
                          backhaulWired = nd.backhaul === 'wired' || nd.role === 'master';
                          const bands = nd.backhaul_bands || [];
                          if (backhaulWired) {
                            bhTitle = nd.role === 'master' ? 'Master node (WAN)' : 'Wired backhaul (Ethernet)';
                          } else {
                            const has5g = bands.some(b => b.includes('band5') || b.includes('band6'));
                            const has24g = bands.some(b => b.includes('band2'));
                            if (has5g) { bhSignalLevel = 'strong'; bhTitle = `Wireless backhaul (${bands.join(', ')})`; }
                            else if (has24g) { bhSignalLevel = 'low'; bhTitle = `Wireless backhaul (2.4 GHz)`; }
                            else { bhSignalLevel = 'medium'; bhTitle = `Wireless backhaul`; }
                          }
                        }
                        return (
                          <>
                            <td className="status">
                              <div className="status-badges">
                                <span className={`status-badge ${isOnline ? 'online' : 'offline'}`}>
                                  {isOnline ? 'Online' : 'Offline'}
                                </span>
                                {isDecoNode ? (
                                  <span className="pref-badge mesh-node" title="This device is a Deco mesh node">Mesh Node</span>
                                ) : isWired ? (
                                  <span className="pref-badge wired" title="Wired (Ethernet) connection">Wired</span>
                                ) : (
                                  <span
                                    className={`pref-badge ${isPinned ? 'pinned' : 'auto'}`}
                                    title={isPinned ? `Pinned to ${pinnedNodeName} — click to revert to Auto` : 'Auto — connects to nearest node'}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      if (isPinned) setPreferredDecoNode(device.device_id, null);
                                    }}
                                    style={{ cursor: isPinned ? 'pointer' : 'default' }}
                                  >
                                    {isPinned ? 'Pinned' : 'Auto'}
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="deco-node-cell">
                              <div className="deco-node-info">
                                {/* Signal/backhaul icon — far left of column */}
                                {isChester ? (
                                  <svg className="conn-icon" viewBox="0 0 24 24">
                                    <title>{chesterSigLabel}</title>
                                    {/* Dish bowl — parabolic, tilted upper-left */}
                                    <ellipse cx="10" cy="10" rx="9" ry="5" transform="rotate(-45 10 10)" fill="none" stroke="#78909c" strokeWidth="1.8"/>
                                    {/* Feed arm from dish center to lower-right */}
                                    <line x1="10" y1="10" x2="19" y2="19" stroke="#78909c" strokeWidth="1.8" strokeLinecap="round"/>
                                    {/* Feed base */}
                                    <circle cx="19" cy="19" r="1.5" fill="#78909c"/>
                                    {/* Stand/base */}
                                    <line x1="19" y1="19" x2="19" y2="23" stroke="#78909c" strokeWidth="1.8" strokeLinecap="round"/>
                                    <line x1="16" y1="23" x2="22" y2="23" stroke="#78909c" strokeWidth="1.8" strokeLinecap="round"/>
                                    {/* Signal arcs — upper-left, colored by RSRP */}
                                    <path d="M7 3 a4 4 0 0 0 -4 4" fill="none" stroke={chesterSigColor} strokeWidth="1.8" strokeLinecap="round"/>
                                    <path d="M8.5 0.5 a7 7 0 0 0 -8 7" fill="none" stroke={chesterSigColor} strokeWidth="1.5" strokeLinecap="round" opacity="0.6"/>
                                  </svg>
                                ) : isDecoNode ? (
                                  backhaulWired ? (
                                    <svg className="conn-icon" viewBox="0 0 24 24">
                                      <title>{bhTitle}</title>
                                      <path d="M4 4h16v2H4zm0 4h16v2H4zm0 4h16v2H4zm0 4h16v2H4z" fill="#546e7a"/>
                                    </svg>
                                  ) : (
                                    <svg className="conn-icon" viewBox="0 0 24 24">
                                      <title>{bhTitle}</title>
                                      <path d="M1.3 8.7a16 16 0 0 1 21.4 0" fill="none"
                                        stroke={bhSignalLevel === 'strong' ? '#2e7d32' : '#ccc'} strokeWidth="2.5" strokeLinecap="round"/>
                                      <path d="M5.3 12.7a10 10 0 0 1 13.4 0" fill="none"
                                        stroke={bhSignalLevel === 'strong' || bhSignalLevel === 'medium' ? (bhSignalLevel === 'strong' ? '#2e7d32' : '#f9a825') : '#ccc'} strokeWidth="2.5" strokeLinecap="round"/>
                                      <path d="M9.3 16.7a4 4 0 0 1 5.4 0" fill="none"
                                        stroke={bhSignalLevel !== 'none' ? (bhSignalLevel === 'low' ? '#e53935' : bhSignalLevel === 'medium' ? '#f9a825' : '#2e7d32') : '#ccc'} strokeWidth="2.5" strokeLinecap="round"/>
                                      <circle cx="12" cy="20" r="1.5" fill={bhSignalLevel !== 'none' ? (bhSignalLevel === 'low' ? '#e53935' : bhSignalLevel === 'medium' ? '#f9a825' : '#2e7d32') : '#ccc'}/>
                                    </svg>
                                  )
                                ) : nodeInfo ? (
                                  isWired ? (
                                    <svg className="conn-icon" viewBox="0 0 24 24">
                                      <title>{signalTitle}</title>
                                      <path d="M4 4h16v2H4zm0 4h16v2H4zm0 4h16v2H4zm0 4h16v2H4z" fill="#546e7a"/>
                                    </svg>
                                  ) : (
                                    <svg className="conn-icon" viewBox="0 0 24 24">
                                      <title>{signalTitle}</title>
                                      <path d="M1.3 8.7a16 16 0 0 1 21.4 0" fill="none"
                                        stroke={signalLevel === 'strong' ? '#2e7d32' : '#ccc'} strokeWidth="2.5" strokeLinecap="round"/>
                                      <path d="M5.3 12.7a10 10 0 0 1 13.4 0" fill="none"
                                        stroke={signalLevel === 'strong' || signalLevel === 'medium' ? (signalLevel === 'strong' ? '#2e7d32' : '#f9a825') : '#ccc'} strokeWidth="2.5" strokeLinecap="round"/>
                                      <path d="M9.3 16.7a4 4 0 0 1 5.4 0" fill="none"
                                        stroke={signalLevel !== 'none' ? (signalLevel === 'low' ? '#e53935' : signalLevel === 'medium' ? '#f9a825' : '#2e7d32') : '#ccc'} strokeWidth="2.5" strokeLinecap="round"/>
                                      <circle cx="12" cy="20" r="1.5" fill={signalLevel !== 'none' ? (signalLevel === 'low' ? '#e53935' : signalLevel === 'medium' ? '#f9a825' : '#2e7d32') : '#ccc'}/>
                                    </svg>
                                  )
                                ) : (
                                  <span style={{ width: 18 }} />
                                )}
                                {/* Node dropdown */}
                                {isDecoNode ? (
                                  <select
                                    className={`deco-pref-select ${isOnline ? 'row-online' : 'row-offline'}`}
                                    value={isPinned ? device.preferred_deco_node : ''}
                                    title={isPinned ? `Uplink pinned to ${pinnedNodeName}` : 'Auto uplink'}
                                    onClick={(e) => e.stopPropagation()}
                                    onChange={(e) => {
                                      const val = e.target.value;
                                      setPreferredDecoNode(device.device_id, val === '' ? null : val);
                                    }}
                                  >
                                    <option value="">{currentNodeName ? `${currentNodeName} (Auto)` : 'Auto'}</option>
                                    {Object.entries(decoNodesMap)
                                      .filter(([nodeMac]) => nodeMac.toLowerCase().replace(/-/g, ':') !== mac)
                                      .map(([nodeMac, name]) => (
                                        <option key={nodeMac} value={nodeMac}>{name}</option>
                                      ))}
                                  </select>
                                ) : isWired ? (
                                  <span className="deco-node-name" title="Wired connection — cannot change node">
                                    {currentNodeName || '—'}
                                  </span>
                                ) : (
                                  <select
                                    className={`deco-pref-select ${isOnline ? 'row-online' : 'row-offline'}`}
                                    value={isPinned ? device.preferred_deco_node : ''}
                                    title={isPinned ? `Pinned to ${pinnedNodeName}` : `Connected to ${currentNodeName} (auto)`}
                                    onClick={(e) => e.stopPropagation()}
                                    onChange={(e) => {
                                      const val = e.target.value;
                                      setPreferredDecoNode(device.device_id, val === '' ? null : val);
                                    }}
                                  >
                                    <option value="">{currentNodeName ? `${currentNodeName} (Auto)` : 'Auto'}</option>
                                    {Object.entries(decoNodesMap).map(([nodeMac, name]) => (
                                      <option key={nodeMac} value={nodeMac}>{name}</option>
                                    ))}
                                  </select>
                                )}
                                {/* Mesh steering toggle at end (non-Deco nodes only) */}
                                {!isDecoNode && (
                                  <label
                                    className="mesh-toggle"
                                    title={meshValue ? 'Mesh: ON — click to disable' : 'Mesh: OFF — click to enable'}
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={meshValue}
                                      onChange={() => toggleClientMesh(device.mac_address, meshValue)}
                                    />
                                    <span className="mesh-slider"></span>
                                  </label>
                                )}
                              </div>
                            </td>
                          </>
                        );
                      })()}
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
