// 2026-03-12: Refactored — extracted polling hook, status strip, insights panel,
// system/cellular/speed cards, and device table into separate files.
// 2026-05-10: Migrated nav + theme toggle to Material Symbols SVGs (per-icon, tree-shaken)
import React, { useState, useEffect } from 'react';
import {
  IconMonitorHeart, IconHub, IconSpeaker, IconLightGroup,
  IconSpeed, IconCellTower, IconSettings,
  IconLightMode, IconDarkMode,
  IconLan, IconCottage, IconMonitoring,
} from './icons';
import './App.css';
import DeviceDetailCard from './components/DeviceDetailCard';
import DecoTopologyPage from './pages/DecoTopologyPage';
import SettingsPage from './pages/SettingsPage';
import AlexaDevicesPage from './pages/AlexaDevicesPage';
import SmartHomePage from './pages/SmartHomePage';
import SpeedInsightsPage from './pages/SpeedInsightsPage';
import HiBoostPage from './pages/HiBoostPage';
import LocalServicesPage from './pages/LocalServicesPage';
import ErrorBoundary from './components/ErrorBoundary';
// 2026-03-12: Extracted components
import useDevicePolling from './hooks/useDevicePolling';
import StatusStrip from './components/StatusStrip';
import InsightsPanel from './components/InsightsPanel';
import SystemStatusCard from './components/SystemStatusCard';
import CellularCard from './components/CellularCard';
import SpeedTestCard from './components/SpeedTestCard';
import DeviceTable from './components/DeviceTable';

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('hs_theme') || 'deep-slate');
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [showDetailCard, setShowDetailCard] = useState(false);
  const [currentPage, setCurrentPage] = useState('dashboard');
  // Lazy-mount: track which pages have ever been visited so they stay in DOM once loaded
  const [mountedPages, setMountedPages] = useState(new Set(['dashboard']));
  const navigateTo = (page) => {
    setCurrentPage(page);
    setMountedPages(prev => { const s = new Set(prev); s.add(page); return s; });
  };
  // 2026-03-12: Collapsible insights panel on dashboard
  const [showInsights, setShowInsights] = useState(false);
  // 2026-05-07: Lifted scan state so SystemStatusCard can show spinner alongside the Scan button
  const [scanning, setScanning] = useState(false);

  // 2026-03-12: All data fetching and polling extracted to custom hook
  const {
    devices, setDevices,
    apiStatus,
    pollingConfig,
    chesterInfo,
    speedTestData, speedTestRunning,
    deviceGroups,
    clientNodeMap, setClientNodeMap,
    decoNodeMacs,
    decoNodesMap,
    decoNodeDetails,
    activeAlerts,
    anomalyInsights,
    dailyDigest,
    healthScore,
    homeStatus, setHomeStatus,
    unseenCount,
    showBanner, banner, setBanner,
    runSpeedTest,
    dismissAlert,
    handleDeviceUpdate: hookHandleDeviceUpdate,
    pollingCallbacksRef,
  } = useDevicePolling();

  // 2026-03-12: Helper — is this device new (first seen within last 24h)?
  const isNewDevice = (device) => {
    if (!device.first_seen) return false;
    const ts = device.first_seen + (device.first_seen.includes('Z') ? '' : 'Z');
    return (Date.now() - new Date(ts).getTime()) < 86400000;
  };
  const newDeviceCount = devices.filter(isNewDevice).length;

  const handleDeviceClick = (device) => {
    setSelectedDevice(device);
    setShowDetailCard(true);
  };

  const handleDetailCardClose = () => {
    setShowDetailCard(false);
    setSelectedDevice(null);
  };

  const handleDeviceUpdate = (updatedDevice) => {
    hookHandleDeviceUpdate(updatedDevice);
    setSelectedDevice(updatedDevice);
  };

  const handleDeviceDelete = (deviceId) => {
    setDevices(prev => prev.filter(d => d.device_id !== deviceId));
  };

  // Handle Escape key to close detail card
  useEffect(() => {
    const handleEscapeKey = (e) => {
      if (e.key === 'Escape') {
        if (showDetailCard) {
          handleDetailCardClose();
        }
      }
    };

    window.addEventListener('keydown', handleEscapeKey);
    return () => {
      window.removeEventListener('keydown', handleEscapeKey);
    };
  }, [showDetailCard]);

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

  // 2026-03-12: Use browser's local timezone instead of hardcoded America/New_York
  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString + (dateString.endsWith('Z') || dateString.includes('+') ? '' : 'Z'));
    return date.toLocaleString('en-US');
  };

  const vendorNamesPresent = devices.filter(d => d.vendor_name).length;

  // Calculate status summary
  const onlineCount = devices.filter(d => d.status === 'online').length;
  const offlineCount = devices.filter(d => d.status === 'offline').length;

  return (
    <ErrorBoundary>
    <div className={`App theme-${theme}`}>
      {/* 2026-03-12: skip-to-content for keyboard users */}
      <a href="#main-content" className="skip-to-content">Skip to main content</a>
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
          {/* 2026-03-12: SVG shield logo + wordmark for brand identity */}
          <div className="brand-lockup">
            <svg className="brand-logo" viewBox="0 0 32 36" width="32" height="36" fill="none">
              <path d="M16 1L2 8v10c0 9.5 6 16.5 14 18 8-1.5 14-8.5 14-18V8L16 1z" fill="rgba(255,255,255,0.15)" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5"/>
              <circle cx="16" cy="17" r="5" fill="none" stroke="#fff" strokeWidth="1.5"/>
              <path d="M16 12v-3M16 22v3M11 17H8M24 17h-3" stroke="rgba(255,255,255,0.5)" strokeWidth="1" strokeLinecap="round"/>
            </svg>
            <div>
              <h1>HomeSentinel</h1>
              <p>Network Monitor & Device Management</p>
            </div>
          </div>
        </div>
        {/* 2026-03-12: Nav consolidated into 3 groups — Network | Smart Home | Performance */}
        {/* 2026-05-07: Group labels gain SVG icon + descriptive title for clearer category identity */}
        <nav className="main-nav" aria-label="Primary navigation">
          <div className="nav-group" role="group" aria-label="Network monitoring">
            <span className="nav-group-label">
              <IconLan className="nav-group-label-icon" width={12} height={12} aria-hidden />
              Network
            </span>
            <div className="nav-group-buttons">
              <button className={`nav-button ${currentPage === 'dashboard' ? 'active' : ''}`} onClick={() => navigateTo('dashboard')} title="Network monitoring dashboard">
                <IconMonitorHeart className="nav-icon" width={16} height={16} aria-hidden />
                Dashboard{newDeviceCount > 0 && <span className="nav-count-badge" aria-label={`${newDeviceCount} new devices`}>{newDeviceCount}</span>}
              </button>
              <button className={`nav-button ${currentPage === 'topology' ? 'active' : ''}`} onClick={() => navigateTo('topology')} title="Mesh topology view">
                <IconHub className="nav-icon" width={16} height={16} aria-hidden />
                Topology
              </button>
              <button className={`nav-button ${currentPage === 'local-services' ? 'active' : ''}`} onClick={() => navigateTo('local-services')} title="Local service health and port monitoring">
                <IconMonitoring className="nav-icon" width={16} height={16} aria-hidden />
                Services
              </button>
            </div>
          </div>
          <div className="nav-group" role="group" aria-label="Smart home devices">
            <span className="nav-group-label">
              <IconCottage className="nav-group-label-icon" width={12} height={12} aria-hidden />
              Smart Home
            </span>
            <div className="nav-group-buttons">
              <button className={`nav-button ${currentPage === 'alexa' ? 'active' : ''}`} onClick={() => navigateTo('alexa')} title="Alexa devices">
                <IconSpeaker className="nav-icon" width={16} height={16} aria-hidden />
                Alexa
              </button>
              <button className={`nav-button ${currentPage === 'smart-home' ? 'active' : ''}`} onClick={() => navigateTo('smart-home')} title="Smart home controls">
                <IconLightGroup className="nav-icon" width={16} height={16} aria-hidden />
                Controls
              </button>
            </div>
          </div>
          <div className="nav-group" role="group" aria-label="Connection performance">
            <span className="nav-group-label">
              <IconMonitoring className="nav-group-label-icon" width={12} height={12} aria-hidden />
              Performance
            </span>
            <div className="nav-group-buttons">
              <button className={`nav-button ${currentPage === 'speed-insights' ? 'active' : ''}`} onClick={() => navigateTo('speed-insights')} title="Internet speed history">
                <IconSpeed className="nav-icon" width={16} height={16} aria-hidden />
                Speed
              </button>
              <button className={`nav-button ${currentPage === 'hiboost' ? 'active' : ''}`} onClick={() => navigateTo('hiboost')} title="HiBoost cellular signal booster">
                <IconCellTower className="nav-icon" width={16} height={16} aria-hidden />
                HiBoost
              </button>
            </div>
          </div>
          {/* 2026-05-07: Theme toggle — visible affordance so users discover light/dark variants */}
          <button
            type="button"
            className="theme-toggle-btn"
            onClick={() => setTheme(t => t === 'deep-slate' ? 'blue-steel' : 'deep-slate')}
            title={theme === 'deep-slate' ? 'Switch to Blue Steel theme' : 'Switch to Deep Slate theme'}
            aria-label={theme === 'deep-slate' ? 'Switch to Blue Steel theme' : 'Switch to Deep Slate theme'}
          >
            {theme === 'deep-slate'
              ? <IconLightMode width={18} height={18} aria-hidden />
              : <IconDarkMode width={18} height={18} aria-hidden />
            }
          </button>
          <button className={`nav-button nav-settings ${currentPage === 'settings' ? 'active' : ''}`} onClick={() => navigateTo('settings')} title="Settings">
            <IconSettings className="nav-icon" width={16} height={16} aria-hidden />
            Settings
          </button>
        </nav>
      </header>
      <main className="App-main" id="main-content">
        {/* Pages: lazy-mount on first visit, then stay in DOM hidden to avoid refetch on tab switch */}
        {mountedPages.has('topology') && <div style={{ display: currentPage === 'topology' ? '' : 'none' }}><DecoTopologyPage /></div>}
        {mountedPages.has('alexa') && <div style={{ display: currentPage === 'alexa' ? '' : 'none' }}><AlexaDevicesPage /></div>}
        {mountedPages.has('smart-home') && <div style={{ display: currentPage === 'smart-home' ? '' : 'none' }}><SmartHomePage /></div>}
        {mountedPages.has('speed-insights') && <div style={{ display: currentPage === 'speed-insights' ? '' : 'none' }}><SpeedInsightsPage /></div>}
        {mountedPages.has('hiboost') && <div style={{ display: currentPage === 'hiboost' ? '' : 'none' }}><HiBoostPage /></div>}
        {mountedPages.has('local-services') && <div style={{ display: currentPage === 'local-services' ? '' : 'none' }}><LocalServicesPage /></div>}
        {mountedPages.has('settings') && <div style={{ display: currentPage === 'settings' ? '' : 'none' }}><SettingsPage theme={theme} onThemeChange={setTheme} /></div>}

        {/* Dashboard Page */}
        {currentPage === 'dashboard' && (
          <>
        {/* 2026-03-12: Compact status strip */}
        <StatusStrip
          devices={devices}
          onlineCount={onlineCount}
          offlineCount={offlineCount}
          homeStatus={homeStatus}
          activeAlerts={activeAlerts}
          anomalyInsights={anomalyInsights}
          newDeviceCount={newDeviceCount}
          pollingConfig={pollingConfig}
          formatDate={formatDate}
        />

        {/* 2026-03-12: Collapsible insights panel */}
        <InsightsPanel
          showInsights={showInsights}
          setShowInsights={setShowInsights}
          activeAlerts={activeAlerts}
          dailyDigest={dailyDigest}
          healthScore={healthScore}
        />

        {/* 2026-03-11: Three-card layout — System + 5G Signal + Speed Test */}
        <div className="status-split status-split-3">
          <SystemStatusCard
            apiStatus={apiStatus}
            pollingConfig={pollingConfig}
            formatDate={formatDate}
            vendorNamesPresent={vendorNamesPresent}
            deviceCount={devices.length}
            scanning={scanning}
          />
          <CellularCard chesterInfo={chesterInfo} />
          <SpeedTestCard
            speedTestData={speedTestData}
            speedTestRunning={speedTestRunning}
            runSpeedTest={runSpeedTest}
            formatDate={formatDate}
          />
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

        {/* 2026-03-12: Device table extracted to its own component */}
        <DeviceTable
          devices={devices}
          deviceGroups={deviceGroups}
          homeStatus={homeStatus}
          setHomeStatus={setHomeStatus}
          handleDeviceUpdate={handleDeviceUpdate}
          formatDate={formatDate}
          isNewDevice={isNewDevice}
          banner={banner}
          showBanner={showBanner}
          pollingConfig={pollingConfig}
          clientNodeMap={clientNodeMap}
          setClientNodeMap={setClientNodeMap}
          decoNodeMacs={decoNodeMacs}
          decoNodesMap={decoNodesMap}
          decoNodeDetails={decoNodeDetails}
          chesterInfo={chesterInfo}
          setDevices={setDevices}
          onDeviceClick={handleDeviceClick}
          onScanningChange={setScanning}
        />

        {/* Detail Card */}
        {showDetailCard && selectedDevice && (
          <DeviceDetailCard
            device={selectedDevice}
            groups={deviceGroups}
            onClose={handleDetailCardClose}
            onUpdate={handleDeviceUpdate}
            onDelete={handleDeviceDelete}
          />
        )}

        <div className="info-card">
          <h3>Welcome to HomeSentinel</h3>
          <p>This is the home network monitoring dashboard. The system is currently discovering devices on your network.</p>
          <p><strong>Backend:</strong> https://localhost:8443</p>
          <p><strong>Frontend:</strong> http://localhost:2026</p>
          <p><strong>Features:</strong> OUI vendor lookup, device metadata, device grouping, and Deco mesh monitoring</p>
        </div>
          </>
        )}
      </main>
    </div>
    </ErrorBoundary>
  );
}

export default App;
