import React, { useState, useEffect, useCallback, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { buildUrl } from '../utils/apiConfig';
import {
  FaLaptop, FaMobileAlt, FaTv, FaCamera, FaPrint,
  FaGamepad, FaDesktop, FaServer, FaQuestion,
  FaNetworkWired, FaMicrophone, FaLightbulb, FaLock, FaPlug,
  FaHome, FaThermometerHalf, FaAmazon, FaGoogle, FaApple
} from 'react-icons/fa';
import { SiSamsung, SiSonos, SiRoku } from 'react-icons/si';
import './DecoTopologyView.css';

// 2026-03-10: Vendor-to-icon mapping for topology node rendering.
// Maps lowercase vendor name fragments to react-icon components.
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

/**
 * Get the best icon for a device based on vendor name, device name, and type.
 */
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

  // Fallback by connection type
  const conn = (device.connection_type || '').toLowerCase();
  if (conn === 'wired') return { Icon: FaDesktop, color: '#78909C' };
  if (conn.includes('band5') || conn.includes('band6')) return { Icon: FaLaptop, color: '#42A5F5' };
  if (conn.includes('band2')) return { Icon: FaMobileAlt, color: '#66BB6A' };

  return { Icon: FaQuestion, color: '#9E9E9E' };
}

/**
 * DecoTopologyView — force-directed graph visualization of Deco mesh network
 */
function DecoTopologyView({ autoRefreshInterval = 30000 }) {
  const [topology, setTopology] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [hoveredNode, setHoveredNode] = useState(null);
  const graphRef = useRef();
  const containerRef = useRef();
  const [dimensions, setDimensions] = useState({ width: 1200, height: 700 });

  // Track container size
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({ width: rect.width - 20, height: 700 });
      }
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

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
    } catch (err) {
      console.error('Failed to fetch topology:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTopology();
    if (autoRefreshEnabled) {
      const interval = setInterval(fetchTopology, autoRefreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefreshEnabled, autoRefreshInterval, fetchTopology]);

  // Build force-graph data from topology
  const graphData = React.useMemo(() => {
    if (!topology) return { nodes: [], links: [] };

    const nodes = [];
    const links = [];

    // Build relationship lookup: device_id -> { node_id, connection_type }
    const relMap = {};
    for (const rel of (topology.relationships || [])) {
      relMap[rel.device_id] = { node_id: rel.node_id, connection_type: rel.connection_type || '' };
    }

    // Add Deco nodes
    for (const node of (topology.nodes || [])) {
      nodes.push({
        id: `node_${node.node_id}`,
        label: node.node_name || node.node_id,
        type: 'deco',
        status: node.status,
        mac: node.mac_address,
        clients: node.connected_clients || 0,
        signal: node.signal_strength || 0,
      });
    }

    // Add devices and links
    for (const device of (topology.devices || [])) {
      const rel = relMap[device.device_id];
      const iconInfo = getDeviceIcon(device);

      nodes.push({
        id: `device_${device.device_id}`,
        label: device.friendly_name || device.device_name || 'Unknown',
        type: 'device',
        status: device.status,
        mac: device.mac_address,
        ip: device.current_ip || '',
        vendor: device.vendor_name || '',
        connection_type: rel ? rel.connection_type : (device.connection_type || ''),
        iconColor: iconInfo.color,
        IconComponent: iconInfo.Icon,
      });

      if (rel) {
        links.push({
          source: `node_${rel.node_id}`,
          target: `device_${device.device_id}`,
          connection_type: rel.connection_type || '',
        });
      }
    }

    return { nodes, links };
  }, [topology]);

  // Custom node renderer on canvas
  const drawNode = useCallback((node, ctx, globalScale) => {
    const isHovered = hoveredNode === node.id;
    const size = node.type === 'deco' ? 24 : 14;
    const fontSize = Math.max(10 / globalScale, 3);

    if (node.type === 'deco') {
      // Deco node — rounded rectangle with router icon
      const w = size * 2.5;
      const h = size * 1.6;
      const r = 6;
      const x = node.x - w / 2;
      const y = node.y - h / 2;

      // Shadow
      if (isHovered) {
        ctx.shadowColor = 'rgba(0,0,0,0.3)';
        ctx.shadowBlur = 12;
      }

      // Background
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
      ctx.fillStyle = node.status === 'online' ? '#1e8b52' : '#78909C';
      ctx.fill();
      ctx.strokeStyle = isHovered ? '#fff' : 'rgba(255,255,255,0.3)';
      ctx.lineWidth = isHovered ? 2 : 1;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // WiFi icon (simple arcs)
      const cx = node.x;
      const cy = node.y - 4;
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.lineWidth = 1.5;
      for (let i = 1; i <= 3; i++) {
        ctx.beginPath();
        ctx.arc(cx, cy + 4, i * 4, -Math.PI * 0.75, -Math.PI * 0.25);
        ctx.stroke();
      }
      // Dot
      ctx.beginPath();
      ctx.arc(cx, cy + 4, 1.5, 0, Math.PI * 2);
      ctx.fillStyle = 'white';
      ctx.fill();

      // Label below
      ctx.font = `bold ${fontSize * 1.2}px -apple-system, BlinkMacSystemFont, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillStyle = node.status === 'online' ? '#1e8b52' : '#78909C';
      ctx.fillText(node.label, node.x, node.y + h / 2 + 4);

      // Client count
      ctx.font = `${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
      ctx.fillStyle = '#888';
      ctx.fillText(`${node.clients} clients`, node.x, node.y + h / 2 + 4 + fontSize * 1.4);

    } else {
      // Device node — circle with brand color
      const radius = isHovered ? size * 1.3 : size;

      if (isHovered) {
        ctx.shadowColor = 'rgba(0,0,0,0.25)';
        ctx.shadowBlur = 10;
      }

      // Circle background
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = node.status === 'online'
        ? (node.iconColor || '#42A5F5')
        : '#BDBDBD';
      ctx.fill();
      ctx.strokeStyle = isHovered ? '#fff' : 'rgba(255,255,255,0.2)';
      ctx.lineWidth = isHovered ? 2 : 0.5;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Icon letter (first letter of vendor or name as fallback)
      const iconLetter = (node.vendor || node.label || '?').charAt(0).toUpperCase();
      ctx.font = `bold ${radius * 0.9}px -apple-system, BlinkMacSystemFont, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = 'white';
      ctx.fillText(iconLetter, node.x, node.y);

      // Labels below: Name, IP, MAC (no titles, just values)
      if (globalScale > 0.6 || isHovered) {
        const lineHeight = fontSize * 1.2;
        let yOffset = node.y + radius + 4;

        // Name
        ctx.font = `bold ${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
        ctx.fillStyle = '#333';
        const displayName = node.label.length > 20 ? node.label.substring(0, 19) + '...' : node.label;
        ctx.fillText(displayName, node.x, yOffset);
        yOffset += lineHeight;

        // IP
        if (node.ip) {
          ctx.font = `${fontSize * 0.9}px -apple-system, BlinkMacSystemFont, sans-serif`;
          ctx.fillStyle = '#666';
          ctx.fillText(node.ip, node.x, yOffset);
          yOffset += lineHeight;
        }

        // MAC
        ctx.font = `${fontSize * 0.85}px monospace`;
        ctx.fillStyle = '#999';
        ctx.fillText(node.mac || '', node.x, yOffset);
      }
    }
  }, [hoveredNode]);

  // Link color based on connection type
  const getLinkColor = useCallback((link) => {
    const ct = (link.connection_type || '').toLowerCase();
    if (ct.includes('band6')) return 'rgba(156, 39, 176, 0.25)';   // purple for 6GHz
    if (ct.includes('band5')) return 'rgba(33, 150, 243, 0.25)';    // blue for 5GHz
    if (ct.includes('band2')) return 'rgba(76, 175, 80, 0.25)';     // green for 2.4GHz
    if (ct === 'wired') return 'rgba(255, 152, 0, 0.35)';           // orange for wired
    return 'rgba(200, 200, 200, 0.2)';
  }, []);

  const formatLastRefresh = () => {
    if (!lastRefresh) return 'Never';
    const diff = Math.floor((new Date() - lastRefresh) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return lastRefresh.toLocaleTimeString();
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
          <button onClick={fetchTopology} disabled={loading} className="btn btn-primary">
            {loading ? (<><span className="spinner"></span>Refreshing...</>) : (<><span className="refresh-icon">&#10227;</span>Refresh</>)}
          </button>
          <div className="auto-refresh-toggle">
            <input type="checkbox" id="autoRefreshTopology" checked={autoRefreshEnabled} onChange={(e) => setAutoRefreshEnabled(e.target.checked)} />
            <label htmlFor="autoRefreshTopology">Auto-refresh</label>
          </div>
          <div className="last-refresh">Updated: {formatLastRefresh()}</div>
        </div>
      </div>

      {/* Legend */}
      <div className="topology-legend">
        <div className="legend-item"><div className="legend-color" style={{background:'#1e8b52'}}></div><span>Deco Node</span></div>
        <div className="legend-item"><div className="legend-line" style={{background:'rgba(76,175,80,0.5)', height:3}}></div><span>2.4 GHz</span></div>
        <div className="legend-item"><div className="legend-line" style={{background:'rgba(33,150,243,0.5)', height:3}}></div><span>5 GHz</span></div>
        <div className="legend-item"><div className="legend-line" style={{background:'rgba(156,39,176,0.5)', height:3}}></div><span>6 GHz</span></div>
        <div className="legend-item"><div className="legend-line" style={{background:'rgba(255,152,0,0.5)', height:3}}></div><span>Wired</span></div>
      </div>

      {/* Error State */}
      {error && (
        <div className="error-container">
          <div className="error-message">
            <span className="error-icon">&#9888;</span>
            <div className="error-text"><h3>Error</h3><p>{error}</p></div>
            <button onClick={fetchTopology} className="btn btn-secondary">Retry</button>
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
          <button onClick={fetchTopology} className="btn btn-primary">Try Again</button>
        </div>
      )}

      {/* Graph */}
      {topology && (topology.nodes || []).length > 0 && (
        <>
          <div className="topology-stats">
            <div className="stat-item"><span className="stat-label">Nodes:</span><span className="stat-value">{topology.total_nodes}</span></div>
            <div className="stat-item"><span className="stat-label">Devices:</span><span className="stat-value">{topology.total_devices}</span></div>
            <div className="stat-item"><span className="stat-label">Connections:</span><span className="stat-value">{topology.total_relationships}</span></div>
          </div>

          <div className="graph-container" ref={containerRef}>
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              width={dimensions.width}
              height={dimensions.height}
              nodeCanvasObject={drawNode}
              nodePointerAreaPaint={(node, color, ctx) => {
                const r = node.type === 'deco' ? 30 : 16;
                ctx.beginPath();
                ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.fill();
              }}
              linkColor={getLinkColor}
              linkWidth={(link) => link.connection_type === 'wired' ? 2.5 : 1.5}
              linkLineDash={(link) => link.connection_type === 'wired' ? [] : [4, 2]}
              onNodeHover={(node) => setHoveredNode(node ? node.id : null)}
              d3AlphaDecay={0.03}
              d3VelocityDecay={0.3}
              cooldownTicks={100}
              backgroundColor="rgba(0,0,0,0)"
              // Deco nodes are heavier (more links pull toward them)
              d3Force="charge"
              d3ForceStrength={-200}
            />
          </div>

          {/* Hover tooltip */}
          {hoveredNode && (() => {
            const node = graphData.nodes.find(n => n.id === hoveredNode);
            if (!node) return null;
            return (
              <div className="topology-tooltip">
                {node.type === 'deco' ? (
                  <>
                    <strong>{node.label}</strong>
                    <span>{node.mac}</span>
                    <span>{node.clients} clients connected</span>
                    <span>Signal: {node.signal}%</span>
                  </>
                ) : (
                  <>
                    <strong>{node.label}</strong>
                    {node.ip && <span>{node.ip}</span>}
                    <span>{node.mac}</span>
                    {node.vendor && <span>{node.vendor}</span>}
                    {node.connection_type && <span>{node.connection_type}</span>}
                  </>
                )}
              </div>
            );
          })()}
        </>
      )}
    </div>
  );
}

export default DecoTopologyView;
