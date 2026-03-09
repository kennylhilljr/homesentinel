import React, { useState, useEffect, useRef } from 'react';
import { buildUrl } from '../utils/apiConfig';
import ViewModeToggle from './ViewModeToggle';
import './DecoTopologyView.css';

/**
 * DecoTopologyView Component
 * Displays network topology showing Deco nodes and their connected devices
 * with visual relationship lines
 */
function DecoTopologyView({ autoRefreshInterval = 30000 }) {
  const [topology, setTopology] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [detailsViewMode, setDetailsViewMode] = useState('grid');
  const svgRef = useRef(null);

  /**
   * Fetch topology data from API
   */
  const fetchTopology = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(buildUrl('/deco/topology'), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Not authenticated with Deco API. Please configure credentials.');
        } else if (response.status === 404) {
          throw new Error('Topology endpoint not available.');
        } else {
          throw new Error(`API error: ${response.statusText}`);
        }
      }

      const data = await response.json();
      setTopology(data);
      setLastRefresh(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to fetch topology:', err);
      setError(err.message);
      setTopology(null);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Initial load and auto-refresh setup
   */
  useEffect(() => {
    fetchTopology();

    if (autoRefreshEnabled) {
      const interval = setInterval(fetchTopology, autoRefreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefreshEnabled, autoRefreshInterval]);

  /**
   * Draw topology visualization using SVG
   */
  useEffect(() => {
    if (!topology || !svgRef.current) return;

    const nodes = topology.nodes || [];
    const devices = topology.devices || [];
    const relationships = topology.relationships || [];

    if (nodes.length === 0) return;

    // Calculate canvas dimensions
    const nodeRadius = 45;
    const deviceRadius = 25;
    const width = 1200;
    const height = 600;

    // Clear previous SVG content
    const svg = svgRef.current;
    while (svg.firstChild) {
      svg.removeChild(svg.firstChild);
    }

    // Set SVG dimensions
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

    // Calculate node positions in a horizontal line
    const nodeSpacing = width / (nodes.length + 1);
    const nodePositions = {};
    nodes.forEach((node, index) => {
      nodePositions[node.node_id] = {
        x: nodeSpacing * (index + 1),
        y: 150,
      };
    });

    // Calculate device positions around nodes
    const devicePositions = {};
    nodes.forEach((node) => {
      const nodeRelationships = relationships.filter((r) => r.node_id === node.node_id);
      const nodePos = nodePositions[node.node_id];

      // Distribute devices around the node in a circle
      const angleStep = nodeRelationships.length > 0 ? (Math.PI * 2) / nodeRelationships.length : 0;
      const radius = 120;

      nodeRelationships.forEach((rel, index) => {
        const angle = angleStep * index - Math.PI / 2;
        devicePositions[rel.device_id] = {
          x: nodePos.x + Math.cos(angle) * radius,
          y: nodePos.y + Math.sin(angle) * radius + 200,
        };
      });
    });

    // Create SVG elements
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');

    // Define arrowhead marker for relationship lines
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'arrowhead');
    marker.setAttribute('markerWidth', '10');
    marker.setAttribute('markerHeight', '10');
    marker.setAttribute('refX', '9');
    marker.setAttribute('refY', '3');
    marker.setAttribute('orient', 'auto');
    const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    polygon.setAttribute('points', '0 0, 10 3, 0 6');
    polygon.setAttribute('fill', '#999');
    marker.appendChild(polygon);
    defs.appendChild(marker);
    svg.appendChild(defs);

    // Draw relationship lines first (so they appear behind nodes)
    relationships.forEach((rel) => {
      const startPos = nodePositions[rel.node_id];
      const endPos = devicePositions[rel.device_id];

      if (startPos && endPos) {
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', startPos.x);
        line.setAttribute('y1', startPos.y);
        line.setAttribute('x2', endPos.x);
        line.setAttribute('y2', endPos.y);
        line.setAttribute('class', 'topology-line');
        line.setAttribute('stroke', '#ccc');
        line.setAttribute('stroke-width', '2');
        line.setAttribute('marker-end', 'url(#arrowhead)');
        svg.appendChild(line);
      }
    });

    // Draw nodes
    nodes.forEach((node) => {
      const pos = nodePositions[node.node_id];
      const isOnline = node.status === 'online';

      // Node circle
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', pos.x);
      circle.setAttribute('cy', pos.y);
      circle.setAttribute('r', nodeRadius);
      circle.setAttribute('class', `node-circle ${isOnline ? 'online' : 'offline'}`);
      circle.setAttribute('fill', isOnline ? '#4CAF50' : '#999');
      circle.setAttribute('stroke', '#333');
      circle.setAttribute('stroke-width', '2');
      svg.appendChild(circle);

      // Node label
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', pos.x);
      label.setAttribute('y', pos.y - 10);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('class', 'node-label');
      label.setAttribute('font-size', '14');
      label.setAttribute('font-weight', 'bold');
      label.setAttribute('fill', 'white');
      label.textContent = node.node_name || node.node_id;
      svg.appendChild(label);

      // Node status
      const statusText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      statusText.setAttribute('x', pos.x);
      statusText.setAttribute('y', pos.y + 12);
      statusText.setAttribute('text-anchor', 'middle');
      statusText.setAttribute('class', 'node-status');
      statusText.setAttribute('font-size', '10');
      statusText.setAttribute('fill', 'white');
      statusText.textContent = node.connected_clients
        ? `${node.connected_clients} clients`
        : 'No clients';
      svg.appendChild(statusText);
    });

    // Draw devices
    devices.forEach((device) => {
      const pos = devicePositions[device.device_id];
      if (!pos) return;

      const isOnline = device.status === 'online';

      // Device circle
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', pos.x);
      circle.setAttribute('cy', pos.y);
      circle.setAttribute('r', deviceRadius);
      circle.setAttribute('class', `device-circle ${isOnline ? 'online' : 'offline'}`);
      circle.setAttribute('fill', isOnline ? '#2196F3' : '#ccc');
      circle.setAttribute('stroke', '#333');
      circle.setAttribute('stroke-width', '1');
      svg.appendChild(circle);

      // Status indicator
      const statusDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      statusDot.setAttribute('cx', pos.x + deviceRadius - 5);
      statusDot.setAttribute('cy', pos.y - deviceRadius + 5);
      statusDot.setAttribute('r', '4');
      statusDot.setAttribute('fill', isOnline ? '#4CAF50' : '#999');
      statusDot.setAttribute('stroke', 'white');
      statusDot.setAttribute('stroke-width', '1');
      svg.appendChild(statusDot);

      // Device label (truncated)
      const deviceName = device.friendly_name || device.device_name || device.mac_address;
      const labelText = deviceName.length > 12 ? deviceName.substring(0, 11) + '…' : deviceName;
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', pos.x);
      label.setAttribute('y', pos.y + 4);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('class', 'device-label');
      label.setAttribute('font-size', '10');
      label.setAttribute('fill', 'white');
      label.setAttribute('pointer-events', 'none');
      label.textContent = labelText;
      svg.appendChild(label);

      // Add tooltip on hover
      circle.setAttribute('title', `${device.device_name}\n${device.mac_address}\nStatus: ${device.status}`);
    });
  }, [topology]);

  /**
   * Format last refresh time
   */
  const formatLastRefresh = () => {
    if (!lastRefresh) return 'Never';
    const now = new Date();
    const diff = Math.floor((now - lastRefresh) / 1000);

    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return lastRefresh.toLocaleTimeString();
  };

  return (
    <div className="deco-topology-view">
      {/* Header Section */}
      <div className="topology-header">
        <div className="header-info">
          <h2>Network Topology</h2>
          <p>Visual map of Deco nodes and connected devices</p>
        </div>

        <div className="header-controls">
          <button
            onClick={fetchTopology}
            disabled={loading}
            className="btn btn-primary"
            title="Manually refresh topology"
          >
            {loading ? (
              <>
                <span className="spinner"></span>
                Refreshing...
              </>
            ) : (
              <>
                <span className="refresh-icon">⟲</span>
                Refresh
              </>
            )}
          </button>

          <div className="auto-refresh-toggle">
            <input
              type="checkbox"
              id="autoRefreshTopology"
              checked={autoRefreshEnabled}
              onChange={(e) => setAutoRefreshEnabled(e.target.checked)}
            />
            <label htmlFor="autoRefreshTopology">Auto-refresh every {autoRefreshInterval / 1000}s</label>
          </div>

          <div className="last-refresh">Last updated: {formatLastRefresh()}</div>
        </div>
      </div>

      {/* Legend */}
      <div className="topology-legend">
        <div className="legend-item">
          <div className="legend-color online-node"></div>
          <span>Online Node</span>
        </div>
        <div className="legend-item">
          <div className="legend-color offline-node"></div>
          <span>Offline Node</span>
        </div>
        <div className="legend-item">
          <div className="legend-color online-device"></div>
          <span>Online Device</span>
        </div>
        <div className="legend-item">
          <div className="legend-color offline-device"></div>
          <span>Offline Device</span>
        </div>
        <div className="legend-item">
          <div className="legend-line"></div>
          <span>Device-to-Node Connection</span>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="error-container">
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <div className="error-text">
              <h3>Error Loading Topology</h3>
              <p>{error}</p>
            </div>
            <button onClick={fetchTopology} className="btn btn-secondary" title="Try again">
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && !topology && !error && (
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading topology...</p>
        </div>
      )}

      {/* Empty State */}
      {!loading && (!topology || topology.nodes.length === 0) && !error && (
        <div className="empty-state">
          <div className="empty-icon">🌐</div>
          <h2>No Topology Data Available</h2>
          <p>No Deco nodes or devices are currently available. Please check your Deco configuration.</p>
          <button onClick={fetchTopology} className="btn btn-primary">
            Try Again
          </button>
        </div>
      )}

      {/* Topology Visualization */}
      {topology && topology.nodes && topology.nodes.length > 0 && (
        <>
          <div className="topology-stats">
            <div className="stat-item">
              <span className="stat-label">Nodes:</span>
              <span className="stat-value">{topology.total_nodes}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Devices:</span>
              <span className="stat-value">{topology.total_devices}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Connections:</span>
              <span className="stat-value">{topology.total_relationships}</span>
            </div>
          </div>

          <div className="svg-container">
            <svg ref={svgRef} className="topology-svg"></svg>
          </div>

          {/* Detailed List Section */}
          <div className="topology-details">
            <div className="topology-details-toolbar">
              <ViewModeToggle
                label="Detail Layout"
                value={detailsViewMode}
                onChange={setDetailsViewMode}
              />
            </div>
            <div className="details-section">
              <h3>Nodes ({topology.total_nodes})</h3>
              {detailsViewMode === 'grid' ? (
                <div className="details-grid">
                  {topology.nodes.map((node) => (
                    <div key={node.node_id} className={`detail-card node-card ${node.status}`}>
                      <div className="card-header">
                        <h4>{node.node_name}</h4>
                        <span className={`status-badge ${node.status}`}>
                          {node.status === 'online' ? '● Online' : '● Offline'}
                        </span>
                      </div>
                      <div className="card-body">
                        <div className="info-row">
                          <span className="info-label">ID:</span>
                          <code>{node.node_id}</code>
                        </div>
                        <div className="info-row">
                          <span className="info-label">MAC:</span>
                          <code>{node.mac_address}</code>
                        </div>
                        <div className="info-row">
                          <span className="info-label">Clients:</span>
                          <span>{node.connected_clients}</span>
                        </div>
                        <div className="info-row">
                          <span className="info-label">Signal:</span>
                          <div className="signal-bar-small">
                            <div
                              className="signal-fill-small"
                              style={{ width: `${node.signal_strength}%` }}
                            ></div>
                            <span>{node.signal_strength}%</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <table className="topology-list-table">
                  <thead>
                    <tr>
                      <th>Node</th>
                      <th>Status</th>
                      <th>Clients</th>
                      <th>Signal</th>
                      <th>MAC</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topology.nodes.map((node) => (
                      <tr key={node.node_id}>
                        <td>{node.node_name}</td>
                        <td>
                          <span className={`status-badge ${node.status}`}>
                            {node.status === 'online' ? 'Online' : 'Offline'}
                          </span>
                        </td>
                        <td>{node.connected_clients}</td>
                        <td>{node.signal_strength}%</td>
                        <td><code>{node.mac_address}</code></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="details-section">
              <h3>Devices ({topology.total_devices})</h3>
              {detailsViewMode === 'grid' ? (
                <div className="details-grid">
                  {topology.devices.map((device) => (
                    <div key={device.device_id} className={`detail-card device-card ${device.status}`}>
                      <div className="card-header">
                        <h4>{device.friendly_name || device.device_name}</h4>
                        <span className={`status-badge ${device.status}`}>
                          {device.status === 'online' ? '● Online' : '● Offline'}
                        </span>
                      </div>
                      <div className="card-body">
                        <div className="info-row">
                          <span className="info-label">MAC:</span>
                          <code>{device.mac_address}</code>
                        </div>
                        {device.vendor_name && (
                          <div className="info-row">
                            <span className="info-label">Vendor:</span>
                            <span>{device.vendor_name}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <table className="topology-list-table">
                  <thead>
                    <tr>
                      <th>Device</th>
                      <th>Status</th>
                      <th>Vendor</th>
                      <th>MAC</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topology.devices.map((device) => (
                      <tr key={device.device_id}>
                        <td>{device.friendly_name || device.device_name}</td>
                        <td>
                          <span className={`status-badge ${device.status}`}>
                            {device.status === 'online' ? 'Online' : 'Offline'}
                          </span>
                        </td>
                        <td>{device.vendor_name || 'Unknown'}</td>
                        <td><code>{device.mac_address}</code></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default DecoTopologyView;
