import React, { useState, useEffect, useCallback, useRef } from 'react';
import { buildUrl } from '../utils/apiConfig';
import {
  FaLaptop, FaMobileAlt, FaTv, FaCamera, FaPrint,
  FaGamepad, FaDesktop, FaServer, FaQuestion,
  FaNetworkWired, FaMicrophone, FaLightbulb, FaLock, FaPlug,
  FaHome, FaThermometerHalf, FaAmazon, FaGoogle, FaApple, FaWifi
} from 'react-icons/fa';
import { SiSamsung, SiSonos, SiRoku } from 'react-icons/si';
import './DecoTopologyView.css';

// 2026-03-10: Vendor-to-icon mapping for topology node rendering.
const VENDOR_ICON_MAP = [
  { match: ['amazon', 'echo', 'fire', 'kindle', 'ring', 'blink'], Icon: FaAmazon, color: '#FF9900' },
  { match: ['google', 'nest', 'chromecast'], Icon: FaGoogle, color: '#4285F4' },
  { match: ['apple', 'iphone', 'ipad', 'macbook', 'airpod', 'homepod'], Icon: FaApple, color: '#A2AAAD' },
  { match: ['samsung', 'galaxy'], Icon: SiSamsung, color: '#1428A0' },
  { match: ['sonos'], Icon: SiSonos, color: '#000000' },
  { match: ['roku'], Icon: SiRoku, color: '#6C3C97' },
  { match: ['tp-link', 'tplink', 'deco', 'tapo', 'kasa'], Icon: FaNetworkWired, color: '#4CAF50' },
  { match: ['camera', 'cam', 'wyze', 'arlo', 'reolink'], Icon: FaCamera, color: '#E91E63' },
  { match: ['printer', 'hp inc', 'canon', 'epson', 'brother'], Icon: FaPrint, color: '#795548' },
  { match: ['television', 'tv', 'vizio', 'lg electronics', 'hisense'], Icon: FaTv, color: '#607D8B' },
  { match: ['xbox', 'playstation', 'nintendo', 'gaming'], Icon: FaGamepad, color: '#8BC34A' },
  { match: ['thermostat', 'ecobee', 'honeywell'], Icon: FaThermometerHalf, color: '#FF5722' },
  { match: ['lock', 'yale', 'schlage', 'kwikset', 'chester'], Icon: FaLock, color: '#FFC107' },
  { match: ['light', 'hue', 'lifx', 'wiz', 'bulb'], Icon: FaLightbulb, color: '#FFEB3B' },
  { match: ['plug', 'outlet', 'switch', 'wemo'], Icon: FaPlug, color: '#00BCD4' },
  { match: ['alarm', 'security', 'sensor'], Icon: FaHome, color: '#F44336' },
  { match: ['alexa', 'echo'], Icon: FaMicrophone, color: '#00CAFF' },
  { match: ['server', 'synology', 'qnap', 'nas'], Icon: FaServer, color: '#9E9E9E' },
];

function getDeviceIcon(device) {
  const searchStr = [
    device.vendor_name || '',
    device.device_name || '',
    device.friendly_name || '',
  ].join(' ').toLowerCase();

  for (const entry of VENDOR_ICON_MAP) {
    if (entry.match.some(m => searchStr.includes(m))) {
      return { Icon: entry.Icon, color: entry.color };
    }
  }

  const conn = (device.connection_type || '').toLowerCase();
  if (conn === 'wired') return { Icon: FaDesktop, color: '#78909C' };
  if (conn.includes('band5') || conn.includes('band6')) return { Icon: FaLaptop, color: '#42A5F5' };
  if (conn.includes('band2')) return { Icon: FaMobileAlt, color: '#66BB6A' };

  return { Icon: FaQuestion, color: '#9E9E9E' };
}

function getConnectionBadge(connType) {
  const ct = (connType || '').toLowerCase();
  if (ct.includes('band6')) return { label: '6 GHz', className: 'conn-6ghz' };
  if (ct.includes('band5')) return { label: '5 GHz', className: 'conn-5ghz' };
  if (ct.includes('band2')) return { label: '2.4 GHz', className: 'conn-24ghz' };
  if (ct === 'wired') return { label: 'Wired', className: 'conn-wired' };
  return null;
}

/**
 * DecoTopologyView — NetworkX graph visualization + card-based detail view
 * 2026-03-11: Uses backend-rendered NetworkX SVG for graph, with card details below.
 */
function DecoTopologyView({ autoRefreshInterval = 30000 }) {
  const [topology, setTopology] = useState(null);
  const [graphSvg, setGraphSvg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [graphLoading, setGraphLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  // 2026-03-14: Default auto-refresh on — backend caches 60s so requests are cheap
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  const [viewMode, setViewMode] = useState('graph'); // 'graph' or 'cards'
  const [downloadMenuOpen, setDownloadMenuOpen] = useState(false);
  const downloadRef = useRef(null);

  // Close download menu when clicking outside
  useEffect(() => {
    if (!downloadMenuOpen) return;
    const handleClickOutside = (e) => {
      if (downloadRef.current && !downloadRef.current.contains(e.target)) {
        setDownloadMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [downloadMenuOpen]);

  const fetchTopology = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(buildUrl('/deco/topology'));
      if (!response.ok) {
        if (response.status === 401) throw new Error('Not authenticated with Deco API.');
        throw new Error(`API error: ${response.statusText}`);
      }
      const data = await response.json();
      setTopology(data);
      setLastRefresh(new Date());
      if (data.nodes) {
        setExpandedNodes(new Set(data.nodes.map(n => n.node_id)));
      }
    } catch (err) {
      console.error('Failed to fetch topology:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // 2026-03-11: Fetch NetworkX SVG graph from backend
  const fetchGraph = useCallback(async () => {
    setGraphLoading(true);
    try {
      const response = await fetch(buildUrl('/deco/topology-graph'));
      if (response.ok) {
        const svgText = await response.text();
        setGraphSvg(svgText);
      } else {
        console.warn('Graph SVG fetch failed:', response.status);
      }
    } catch (err) {
      console.error('Failed to fetch topology graph:', err);
    } finally {
      setGraphLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTopology();
    fetchGraph();
    if (autoRefreshEnabled) {
      const interval = setInterval(() => {
        fetchTopology();
        fetchGraph();
      }, autoRefreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefreshEnabled, autoRefreshInterval, fetchTopology, fetchGraph]);

  // Group devices by their connected Deco node
  const nodeGroups = React.useMemo(() => {
    if (!topology) return [];

    const relMap = {};
    for (const rel of (topology.relationships || [])) {
      relMap[rel.device_id] = rel;
    }

    const groups = {};
    const unconnected = [];

    for (const device of (topology.devices || [])) {
      const rel = relMap[device.device_id];
      if (rel) {
        const nodeId = rel.node_id;
        if (!groups[nodeId]) groups[nodeId] = [];
        groups[nodeId].push({ ...device, connection_type: rel.connection_type || device.connection_type || '' });
      } else {
        unconnected.push(device);
      }
    }

    const result = (topology.nodes || []).map(node => ({
      node,
      devices: groups[node.node_id] || [],
    }));

    if (unconnected.length > 0) {
      result.push({
        node: { node_id: '_unconnected', node_name: 'Unassigned', status: 'unknown', connected_clients: unconnected.length },
        devices: unconnected,
      });
    }

    return result;
  }, [topology]);

  const toggleNode = (nodeId) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  };

  const expandAll = () => {
    if (topology && topology.nodes) {
      setExpandedNodes(new Set(topology.nodes.map(n => n.node_id).concat(['_unconnected'])));
    }
  };

  const collapseAll = () => setExpandedNodes(new Set());

  const formatLastRefresh = () => {
    if (!lastRefresh) return 'Never';
    const diff = Math.floor((new Date() - lastRefresh) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return lastRefresh.toLocaleTimeString();
  };

  const handleRefresh = () => {
    fetchTopology();
    fetchGraph();
  };

  // 2026-03-11: Download topology as SVG
  const downloadSvg = () => {
    if (!graphSvg) return;
    const blob = new Blob([graphSvg], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `homesentinel-topology-${new Date().toISOString().slice(0, 10)}.svg`;
    a.click();
    URL.revokeObjectURL(url);
    setDownloadMenuOpen(false);
  };

  // 2026-03-11: Download topology as PNG (render SVG to canvas)
  const downloadPng = () => {
    if (!graphSvg) return;
    const svgBlob = new Blob([graphSvg], { type: 'image/svg+xml;charset=utf-8' });
    const svgUrl = URL.createObjectURL(svgBlob);
    const img = new Image();
    img.onload = () => {
      const scale = 2; // 2x resolution for crisp output
      const canvas = document.createElement('canvas');
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      const ctx = canvas.getContext('2d');
      ctx.scale(scale, scale);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, img.width, img.height);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(svgUrl);
      canvas.toBlob((blob) => {
        const pngUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = pngUrl;
        a.download = `homesentinel-topology-${new Date().toISOString().slice(0, 10)}.png`;
        a.click();
        URL.revokeObjectURL(pngUrl);
      }, 'image/png');
    };
    img.src = svgUrl;
    setDownloadMenuOpen(false);
  };

  // 2026-03-11: Generate and download Mermaid diagram from topology data
  const downloadMermaid = () => {
    if (!topology) return;
    const lines = ['graph LR'];
    const safeId = (s) => s.replace(/[^a-zA-Z0-9_]/g, '_');

    // Add Deco nodes
    for (const node of (topology.nodes || [])) {
      const id = safeId(node.node_id);
      const label = node.node_name || node.node_id;
      const role = node.role ? ` (${node.role})` : '';
      lines.push(`    ${id}["${label}${role}"]`);
    }

    // Build relationship map
    const relMap = {};
    for (const rel of (topology.relationships || [])) {
      relMap[rel.device_id] = rel;
    }

    // Add devices grouped by node
    for (const node of (topology.nodes || [])) {
      const nodeId = safeId(node.node_id);
      const nodeDevices = (topology.devices || []).filter(d => {
        const rel = relMap[d.device_id];
        return rel && rel.node_id === node.node_id;
      });
      for (const dev of nodeDevices) {
        const devId = safeId(dev.device_id);
        const name = dev.friendly_name || dev.device_name || dev.mac_address || 'Unknown';
        const rel = relMap[dev.device_id];
        const conn = rel ? rel.connection_type || '' : '';
        let connLabel = '';
        if (conn.includes('band5')) connLabel = '5 GHz';
        else if (conn.includes('band2')) connLabel = '2.4 GHz';
        else if (conn.includes('band6')) connLabel = '6 GHz';
        else if (conn === 'wired') connLabel = 'Wired';
        const arrow = connLabel ? `-- "${connLabel}" ---` : '---';
        lines.push(`    ${nodeId} ${arrow} ${devId}("${name}")`);
      }
    }

    const mermaidText = lines.join('\n');
    const blob = new Blob([mermaidText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `homesentinel-topology-${new Date().toISOString().slice(0, 10)}.mmd`;
    a.click();
    URL.revokeObjectURL(url);
    setDownloadMenuOpen(false);
  };

  return (
    <div className="deco-topology-view">
      {/* Header */}
      <div className="topology-header">
        <div className="header-info">
          <h2>Network Topology</h2>
          <p>Deco mesh nodes and connected devices</p>
        </div>
        <div className="header-controls">
          {/* View mode toggle */}
          <div className="view-mode-toggle">
            <button
              className={`view-mode-btn ${viewMode === 'graph' ? 'active' : ''}`}
              onClick={() => setViewMode('graph')}
            >
              Graph
            </button>
            <button
              className={`view-mode-btn ${viewMode === 'cards' ? 'active' : ''}`}
              onClick={() => setViewMode('cards')}
            >
              Cards
            </button>
          </div>
          <button onClick={handleRefresh} disabled={loading || graphLoading} className="btn btn-primary">
            {(loading || graphLoading) ? (<><span className="spinner"></span>Refreshing...</>) : (<><span className="refresh-icon">&#10227;</span>Refresh</>)}
          </button>
          {/* 2026-03-11: Download topology diagram — SVG, PNG, or Mermaid */}
          {graphSvg && viewMode === 'graph' && (
            <div ref={downloadRef} className="download-dropdown" style={{ position: 'relative', display: 'inline-block' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setDownloadMenuOpen(prev => !prev)}
                title="Download topology diagram"
              >
                Download Diagram &#9662;
              </button>
              {downloadMenuOpen && (
                <div className="download-menu" style={{
                  position: 'absolute', top: '100%', left: 0, marginTop: 4,
                  background: '#fff', border: '1px solid #ccc', borderRadius: 6,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.15)', zIndex: 100, minWidth: 160,
                  overflow: 'hidden'
                }}>
                  <button className="download-menu-item" onClick={downloadSvg}
                    style={{ display: 'block', width: '100%', padding: '10px 16px', border: 'none',
                      background: 'none', textAlign: 'left', cursor: 'pointer', fontSize: 14 }}
                    onMouseEnter={e => e.target.style.background = '#f0f0f0'}
                    onMouseLeave={e => e.target.style.background = 'none'}
                  >SVG (Vector)</button>
                  <button className="download-menu-item" onClick={downloadPng}
                    style={{ display: 'block', width: '100%', padding: '10px 16px', border: 'none',
                      background: 'none', textAlign: 'left', cursor: 'pointer', fontSize: 14 }}
                    onMouseEnter={e => e.target.style.background = '#f0f0f0'}
                    onMouseLeave={e => e.target.style.background = 'none'}
                  >PNG (Image)</button>
                  <button className="download-menu-item" onClick={downloadMermaid}
                    style={{ display: 'block', width: '100%', padding: '10px 16px', border: 'none',
                      background: 'none', textAlign: 'left', cursor: 'pointer', fontSize: 14 }}
                    onMouseEnter={e => e.target.style.background = '#f0f0f0'}
                    onMouseLeave={e => e.target.style.background = 'none'}
                  >Mermaid (.mmd)</button>
                </div>
              )}
            </div>
          )}
          <div className="auto-refresh-toggle">
            <input type="checkbox" id="autoRefreshTopology" checked={autoRefreshEnabled} onChange={(e) => setAutoRefreshEnabled(e.target.checked)} />
            <label htmlFor="autoRefreshTopology">Auto-refresh</label>
          </div>
          <div className="last-refresh">Updated: {formatLastRefresh()}</div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="error-container">
          <div className="error-message">
            <span className="error-icon">&#9888;</span>
            <div className="error-text"><h3>Error</h3><p>{error}</p></div>
            <button onClick={handleRefresh} className="btn btn-secondary">Retry</button>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && !topology && !error && (
        <div className="loading-container"><div className="loading-spinner"></div><p>Loading topology...</p></div>
      )}

      {/* Empty */}
      {!loading && (!topology || (topology.nodes || []).length === 0) && !error && (
        <div className="empty-state">
          <div className="empty-icon">&#127760;</div>
          <h2>No Topology Data</h2>
          <p>No Deco nodes found. Check your Deco credentials in Settings.</p>
          <button onClick={handleRefresh} className="btn btn-primary">Try Again</button>
        </div>
      )}

      {/* Topology Content */}
      {topology && (topology.nodes || []).length > 0 && (
        <>
          {/* Stats bar */}
          <div className="topology-stats">
            <div className="stat-item"><span className="stat-label">Nodes:</span><span className="stat-value">{topology.total_nodes}</span></div>
            <div className="stat-item"><span className="stat-label">Devices:</span><span className="stat-value">{topology.total_devices}</span></div>
            <div className="stat-item"><span className="stat-label">Connections:</span><span className="stat-value">{topology.total_relationships}</span></div>
            {viewMode === 'cards' && (
              <div className="stat-actions">
                <button className="btn-text" onClick={expandAll}>Expand All</button>
                <button className="btn-text" onClick={collapseAll}>Collapse All</button>
              </div>
            )}
          </div>

          {/* NetworkX Graph View */}
          {viewMode === 'graph' && (
            <div className="networkx-graph-container">
              {graphLoading && !graphSvg && (
                <div className="loading-container"><div className="loading-spinner"></div><p>Generating network graph...</p></div>
              )}
              {graphSvg && (
                <div
                  className="networkx-svg-wrapper"
                  dangerouslySetInnerHTML={{ __html: graphSvg }}
                />
              )}
              {!graphLoading && !graphSvg && (
                <div className="empty-state">
                  <p>Failed to generate graph. Try refreshing.</p>
                </div>
              )}
            </div>
          )}

          {/* Card-based detail view */}
          {viewMode === 'cards' && (
            <div className="node-groups">
              {nodeGroups.map(({ node, devices }) => {
                const isExpanded = expandedNodes.has(node.node_id);
                const isOnline = node.status === 'online';

                return (
                  <div key={node.node_id} className={`node-group ${isOnline ? 'online' : 'offline'}`}>
                    <div className="node-group-header" onClick={() => toggleNode(node.node_id)}>
                      <div className="node-header-left">
                        <div className={`node-icon ${isOnline ? 'online' : 'offline'}`}>
                          <FaWifi size={18} />
                        </div>
                        <div className="node-header-info">
                          <h3>{node.node_name}</h3>
                          <span className="node-meta">
                            {node.mac_address}
                            {node.role && <span className="node-role">{node.role}</span>}
                          </span>
                        </div>
                      </div>
                      <div className="node-header-right">
                        <span className="device-count">{devices.length} device{devices.length !== 1 ? 's' : ''}</span>
                        <span className={`status-badge ${isOnline ? 'online' : 'offline'}`}>
                          {isOnline ? 'Online' : 'Offline'}
                        </span>
                        <span className={`expand-arrow ${isExpanded ? 'expanded' : ''}`}>&#9660;</span>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="node-devices-grid">
                        {devices.map((device) => {
                          const { Icon, color } = getDeviceIcon(device);
                          const connBadge = getConnectionBadge(device.connection_type);
                          const isDevOnline = device.status === 'online';

                          return (
                            <div key={device.device_id} className={`topo-device-card ${isDevOnline ? 'online' : 'offline'}`}>
                              <div className="topo-device-icon" style={{ backgroundColor: isDevOnline ? color : '#BDBDBD' }}>
                                <Icon size={16} color="white" />
                              </div>
                              <div className="topo-device-info">
                                <div className="topo-device-name">
                                  {device.friendly_name || device.device_name || 'Unknown'}
                                </div>
                                {device.current_ip && (
                                  <div className="topo-device-ip">{device.current_ip}</div>
                                )}
                                <div className="topo-device-mac">{device.mac_address}</div>
                              </div>
                              <div className="topo-device-badges">
                                {connBadge && (
                                  <span className={`conn-badge ${connBadge.className}`}>{connBadge.label}</span>
                                )}
                                {/* 2026-03-13: Show Pinned badge if device has a preferred node */}
                                {device.preferred_deco_node && (
                                  <span className="conn-badge conn-pinned">Pinned</span>
                                )}
                                {device.vendor_name && (
                                  <span className="vendor-badge">{device.vendor_name}</span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                        {devices.length === 0 && (
                          <div className="no-devices-msg">No devices connected to this node</div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default DecoTopologyView;
