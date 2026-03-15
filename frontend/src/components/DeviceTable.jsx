// 2026-03-12: Extracted from App.js — device table/grid rendering with search, filter, sort, inline rename
import React, { useState } from 'react';
import { buildUrl } from '../utils/apiConfig';
import DeviceCard from './DeviceCard';
import ViewModeToggle from './ViewModeToggle';

export default function DeviceTable({
  devices,
  deviceGroups,
  homeStatus,
  setHomeStatus,
  handleDeviceUpdate,
  formatDate,
  isNewDevice,
  banner,
  showBanner,
  pollingConfig,
  clientNodeMap,
  setClientNodeMap,
  decoNodeMacs,
  decoNodesMap,
  decoNodeDetails,
  chesterInfo,
  setDevices,
  onDeviceClick,
}) {
  const [deviceViewMode, setDeviceViewMode] = useState('list');
  const [deviceQuery, setDeviceQuery] = useState('');
  const [deviceStatusFilter, setDeviceStatusFilter] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: 'lastSeen', direction: 'desc' });
  const [inlineEditId, setInlineEditId] = useState(null);
  const [inlineEditValue, setInlineEditValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [optimizeLoading, setOptimizeLoading] = useState(false);

  // Set a display name for a device (stored in DB as friendly_name)
  const setCustomName = async (device, newName) => {
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
    if (sortConfig.key !== key) return '\u2195';
    return sortConfig.direction === 'asc' ? '\u25B2' : '\u25BC';
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

  return (
    <div className="devices-card">
      <div className="devices-header">
        <div className="devices-header-left">
          <h2>Network Devices ({displayedDevices.length})</h2>
        </div>
        <div className="devices-filter-row">
          <label htmlFor="device-search" className="sr-only">Search devices</label>
          <input
            id="device-search"
            type="text"
            className="devices-search-input"
            placeholder="Search devices..."
            value={deviceQuery}
            onChange={(e) => setDeviceQuery(e.target.value)}
          />
          <label htmlFor="device-status-filter" className="sr-only">Filter by status</label>
          <select
            id="device-status-filter"
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
                isNew={isNewDevice(device)}
                onClick={() => onDeviceClick(device)}
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

                return (
                <tr
                  key={device.device_id}
                  className={`device-row ${device.status === 'online' ? 'online' : 'offline'}${isNewDevice(device) ? ' device-row-new' : ''}`}
                  onClick={() => onDeviceClick(device)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      onDeviceClick(device);
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
                        }}
                      >
                        {device.friendly_name || decoName || device.mac_address}
                      </span>
                    )}
                    {/* 2026-03-12: "New" badge for devices first seen in last 24h */}
                    {isNewDevice(device) && <span className="device-new-badge">NEW</span>}
                  </td>
                  {/* 2026-03-11: Status + type badge column */}
                  {(() => {
                    const mac = (device.mac_address || '').toLowerCase();
                    const nodeInfo = clientNodeMap[mac];
                    const isDecoNode = decoNodeMacs.has(mac);
                    const meshValue = nodeInfo ? !!nodeInfo.client_mesh : false;
                    const normPref = device.preferred_deco_node
                      ? device.preferred_deco_node.toLowerCase().replace(/-/g, ':')
                      : null;
                    const isPinned = !!normPref;
                    const pinnedNodeName = isPinned ? (decoNodesMap[normPref] || normPref) : null;
                    const currentNodeName = nodeInfo ? nodeInfo.node_name : null;
                    const currentNodeMac = nodeInfo ? nodeInfo.node_mac.toLowerCase().replace(/-/g, ':') : null;
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
                    const chesterSigLabel = chesterRsrp == null ? 'Chester \u2014 no signal data'
                      : `Chester 5G \u2014 RSRP ${chesterRsrp} dBm`;
                    // Signal strength
                    let signalLevel = 'none';
                    let signalTitle = '';
                    if (nodeInfo && !isWired) {
                      const downSpeed = nodeInfo.down_speed || 0;
                      const upSpeed = nodeInfo.up_speed || 0;
                      const band = connType.toLowerCase();
                      if (band.includes('band5') || band.includes('band6')) {
                        signalLevel = 'strong';
                        signalTitle = `${band.includes('6') ? '6 GHz' : '5 GHz'} \u2014 ${downSpeed} kbps down, ${upSpeed} kbps up`;
                      } else if (band.includes('band2')) {
                        signalLevel = 'medium';
                        signalTitle = `2.4 GHz \u2014 ${downSpeed} kbps down, ${upSpeed} kbps up`;
                      } else {
                        signalLevel = 'medium';
                        signalTitle = `Wireless \u2014 ${downSpeed} kbps down, ${upSpeed} kbps up`;
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
                      backhaulWired = nd.backhaul === 'wired' || nd.role === 'primary';
                      const bands = nd.backhaul_bands || [];
                      if (backhaulWired) {
                        bhTitle = nd.role === 'primary' ? 'Primary node (WAN)' : 'Wired backhaul (Ethernet)';
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
                              <button
                                className={`pref-badge ${isPinned ? 'pinned' : 'auto'}`}
                                title={isPinned
                                  ? `Pinned to ${pinnedNodeName} \u2014 click to revert to Auto`
                                  : currentNodeMac
                                    ? `Auto \u2014 click to pin to ${currentNodeName}`
                                    : 'Auto \u2014 connects to nearest node'}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (isPinned) {
                                    setPreferredDecoNode(device.device_id, null);
                                  } else if (currentNodeMac) {
                                    setPreferredDecoNode(device.device_id, currentNodeMac);
                                  }
                                }}
                              >
                                {isPinned ? 'Pinned' : 'Auto'}
                              </button>
                            )}
                          </div>
                        </td>
                        <td className="deco-node-cell">
                          <div className="deco-node-info">
                            {/* Signal/backhaul icon */}
                            {isChester ? (
                              <svg className="conn-icon" viewBox="0 0 24 24">
                                <title>{chesterSigLabel}</title>
                                <ellipse cx="10" cy="10" rx="9" ry="5" transform="rotate(-45 10 10)" fill="none" stroke="#78909c" strokeWidth="1.8"/>
                                <line x1="10" y1="10" x2="19" y2="19" stroke="#78909c" strokeWidth="1.8" strokeLinecap="round"/>
                                <circle cx="19" cy="19" r="1.5" fill="#78909c"/>
                                <line x1="19" y1="19" x2="19" y2="23" stroke="#78909c" strokeWidth="1.8" strokeLinecap="round"/>
                                <line x1="16" y1="23" x2="22" y2="23" stroke="#78909c" strokeWidth="1.8" strokeLinecap="round"/>
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
                            ) : isOnline ? (
                              <svg className="conn-icon" viewBox="0 0 24 24" title="Wireless (no node info)">
                                <path d="M1.3 8.7a16 16 0 0 1 21.4 0" fill="none" stroke="#555" strokeWidth="2.5" strokeLinecap="round"/>
                                <path d="M5.3 12.7a10 10 0 0 1 13.4 0" fill="none" stroke="#555" strokeWidth="2.5" strokeLinecap="round"/>
                                <path d="M9.3 16.7a4 4 0 0 1 5.4 0" fill="none" stroke="#555" strokeWidth="2.5" strokeLinecap="round"/>
                                <circle cx="12" cy="20" r="1.5" fill="#555"/>
                              </svg>
                            ) : (
                              <span style={{ width: 22 }} />
                            )}
                            {/* Node dropdown */}
                            {isDecoNode ? (
                              <select
                                className="deco-pref-select"
                                value={normPref || ''}
                                title={isPinned ? `Uplink pinned to ${pinnedNodeName}` : 'Auto uplink'}
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) => {
                                  const val = e.target.value;
                                  setPreferredDecoNode(device.device_id, val === '' ? null : val);
                                }}
                              >
                                <option value="">{decoNodesMap[mac] || currentNodeName || '\u2014'}</option>
                                {Object.entries(decoNodesMap)
                                  .filter(([nodeMac]) => nodeMac !== mac)
                                  .map(([nodeMac, name]) => (
                                    <option key={nodeMac} value={nodeMac}>{name}</option>
                                  ))}
                              </select>
                            ) : isWired ? (
                              <span className="deco-node-name" title="Wired connection \u2014 cannot change node">
                                {currentNodeName || '\u2014'}
                              </span>
                            ) : (
                              <select
                                className="deco-pref-select"
                                value={normPref || ''}
                                title={isPinned ? `Pinned to ${pinnedNodeName}` : `Connected to ${currentNodeName || '\u2014'} (auto)`}
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) => {
                                  const val = e.target.value;
                                  setPreferredDecoNode(device.device_id, val === '' ? null : val);
                                }}
                              >
                                <option value="">{currentNodeName || '\u2014'}</option>
                                {Object.entries(decoNodesMap).map(([nodeMac, name]) => (
                                  <option key={nodeMac} value={nodeMac}>{name}</option>
                                ))}
                              </select>
                            )}
                            {/* Mesh steering oval button */}
                            {!isDecoNode && (
                              <button
                                className={`mesh-oval-btn ${meshValue ? 'mesh-on' : 'mesh-off'}`}
                                title={meshValue ? 'Mesh: ON \u2014 click to disable' : 'Mesh: OFF \u2014 click to enable'}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleClientMesh(device.mac_address, meshValue);
                                }}
                              >
                                {meshValue ? 'Mesh' : 'Off'}
                              </button>
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
  );
}
