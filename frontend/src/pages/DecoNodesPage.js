import React, { useState, useEffect } from 'react';
import DecoNodeCard from '../components/DecoNodeCard';
import '../pages/DecoNodesPage.css';

/**
 * DecoNodesPage Component
 * Displays list of all Deco nodes with auto-refresh
 */
function DecoNodesPage() {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(60000); // 60 seconds

  /**
   * Fetch Deco nodes from API
   */
  const fetchNodes = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:9000/api/deco/nodes', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Not authenticated with Deco API. Please configure credentials.');
        } else if (response.status === 404) {
          throw new Error('Deco API endpoint not available.');
        } else {
          throw new Error(`API error: ${response.statusText}`);
        }
      }

      const data = await response.json();
      setNodes(data.nodes || []);
      setLastRefresh(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to fetch Deco nodes:', err);
      setError(err.message);
      setNodes([]);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Manually refresh nodes (bypass cache)
   */
  const handleManualRefresh = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:9000/api/deco/nodes/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Refresh failed: ${response.statusText}`);
      }

      const data = await response.json();
      setNodes(data.nodes || []);
      setLastRefresh(new Date());
      setError(null);
    } catch (err) {
      console.error('Manual refresh failed:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Initial load and auto-refresh setup
   */
  useEffect(() => {
    fetchNodes();

    if (autoRefreshEnabled) {
      const interval = setInterval(() => {
        fetchNodes();
      }, refreshInterval);

      return () => clearInterval(interval);
    }
  }, [autoRefreshEnabled, refreshInterval]);

  /**
   * Get statistics about nodes
   */
  const getNodeStats = () => {
    const onlineCount = nodes.filter((n) => n.status === 'online').length;
    const totalClients = nodes.reduce((sum, n) => sum + (n.connected_clients || 0), 0);
    const avgSignal =
      nodes.length > 0
        ? Math.round(nodes.reduce((sum, n) => sum + (n.signal_strength || 0), 0) / nodes.length)
        : 0;

    return { onlineCount, totalClients, avgSignal };
  };

  const stats = getNodeStats();

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
    <div className="deco-nodes-page">
      {/* Header Section */}
      <div className="page-header">
        <div className="header-title">
          <h1>Deco Nodes</h1>
          <p>Monitor your TP-Link Deco mesh network nodes</p>
        </div>

        <div className="header-controls">
          <button
            onClick={handleManualRefresh}
            disabled={loading}
            className="btn btn-primary"
            title="Manually refresh node list"
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
              id="autoRefresh"
              checked={autoRefreshEnabled}
              onChange={(e) => setAutoRefreshEnabled(e.target.checked)}
            />
            <label htmlFor="autoRefresh">Auto-refresh every {refreshInterval / 1000}s</label>
          </div>

          <div className="last-refresh">Last updated: {formatLastRefresh()}</div>
        </div>
      </div>

      {/* Statistics Summary */}
      {nodes.length > 0 && (
        <div className="stats-summary">
          <div className="stat-card">
            <div className="stat-label">Total Nodes</div>
            <div className="stat-value">{nodes.length}</div>
          </div>
          <div className="stat-card online">
            <div className="stat-label">Online</div>
            <div className="stat-value">{stats.onlineCount}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Clients</div>
            <div className="stat-value">{stats.totalClients}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Avg Signal</div>
            <div className="stat-value">{stats.avgSignal}%</div>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="error-container">
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <div className="error-text">
              <h3>Error Loading Nodes</h3>
              <p>{error}</p>
            </div>
            <button
              onClick={handleManualRefresh}
              className="btn btn-secondary"
              title="Try again"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && nodes.length === 0 && !error && (
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading Deco nodes...</p>
        </div>
      )}

      {/* Empty State */}
      {!loading && nodes.length === 0 && !error && (
        <div className="empty-state">
          <div className="empty-icon">🌐</div>
          <h2>No Deco Nodes Found</h2>
          <p>No Deco nodes are currently available. Please check your Deco configuration.</p>
          <button onClick={handleManualRefresh} className="btn btn-primary">
            Try Again
          </button>
        </div>
      )}

      {/* Nodes Grid */}
      {nodes.length > 0 && (
        <div className="nodes-section">
          <h2 className="section-title">Nodes ({nodes.length})</h2>
          <div className="nodes-grid">
            {nodes.map((node) => (
              <DecoNodeCard
                key={node.node_id}
                node={node}
                onClick={() => setSelectedNode(node)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Node Detail Modal */}
      {selectedNode && (
        <div className="node-detail-modal">
          <div className="modal-overlay" onClick={() => setSelectedNode(null)}></div>
          <div className="modal-content">
            <button
              className="modal-close"
              onClick={() => setSelectedNode(null)}
              aria-label="Close modal"
            >
              ✕
            </button>

            <div className="modal-header">
              <h2>{selectedNode.node_name || 'Node Details'}</h2>
              <span className={`modal-status status-${selectedNode.status}`}>
                {selectedNode.status === 'online' ? '● Online' : '● Offline'}
              </span>
            </div>

            <div className="modal-body">
              <div className="detail-grid">
                {/* Node ID */}
                <div className="detail-item">
                  <label>Node ID</label>
                  <code>{selectedNode.node_id}</code>
                </div>

                {/* Model */}
                {selectedNode.model && selectedNode.model !== 'unknown' && (
                  <div className="detail-item">
                    <label>Model</label>
                    <span>{selectedNode.model}</span>
                  </div>
                )}

                {/* Firmware */}
                <div className="detail-item">
                  <label>Firmware Version</label>
                  <span>{selectedNode.firmware_version || 'Unknown'}</span>
                </div>

                {/* Uptime */}
                <div className="detail-item">
                  <label>Uptime (seconds)</label>
                  <span>{selectedNode.uptime_seconds || 0}</span>
                </div>

                {/* Connected Clients */}
                <div className="detail-item">
                  <label>Connected Clients</label>
                  <span>{selectedNode.connected_clients || 0}</span>
                </div>

                {/* Signal Strength */}
                <div className="detail-item">
                  <label>Signal Strength</label>
                  <div className="signal-bar">
                    <div
                      className="signal-fill"
                      style={{ width: `${selectedNode.signal_strength || 0}%` }}
                    ></div>
                    <span className="signal-text">{selectedNode.signal_strength || 0}%</span>
                  </div>
                </div>

                {/* Status */}
                <div className="detail-item">
                  <label>Status</label>
                  <span className={`status-badge-detail ${selectedNode.status}`}>
                    {selectedNode.status || 'Unknown'}
                  </span>
                </div>

                {/* Last Updated */}
                <div className="detail-item">
                  <label>Last Updated</label>
                  <span>{new Date(selectedNode.last_updated).toLocaleString()}</span>
                </div>
              </div>

              {/* Raw Data (Debug) */}
              {selectedNode.raw_data && (
                <details className="raw-data-details">
                  <summary>Raw API Data</summary>
                  <pre>{JSON.stringify(selectedNode.raw_data, null, 2)}</pre>
                </details>
              )}
            </div>

            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setSelectedNode(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DecoNodesPage;
