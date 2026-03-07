import React from 'react';
import './DecoNodeCard.css';

/**
 * DecoNodeCard Component
 * Displays a single Deco node with status, firmware, clients, and signal health
 */
function DecoNodeCard({ node, onClick }) {
  /**
   * Format uptime from seconds to human-readable string
   * @param {number} seconds - Uptime in seconds
   * @returns {string} Formatted uptime string
   */
  const formatUptime = (seconds) => {
    if (!seconds || seconds < 0) return 'Unknown';

    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    const parts = [];
    if (days > 0) parts.push(`${days} day${days !== 1 ? 's' : ''}`);
    if (hours > 0) parts.push(`${hours} hour${hours !== 1 ? 's' : ''}`);
    if (minutes > 0 && days === 0) parts.push(`${minutes} minute${minutes !== 1 ? 's' : ''}`);

    return parts.length > 0 ? parts.join(', ') : 'Just started';
  };

  /**
   * Get signal quality indicator based on percentage
   * @param {number} strength - Signal strength 0-100
   * @returns {object} Color and label for signal indicator
   */
  const getSignalQuality = (strength) => {
    if (strength >= 70) {
      return { color: '#10b981', label: 'Excellent', className: 'signal-excellent' };
    } else if (strength >= 50) {
      return { color: '#f59e0b', label: 'Good', className: 'signal-good' };
    } else if (strength >= 30) {
      return { color: '#f97316', label: 'Fair', className: 'signal-fair' };
    } else {
      return { color: '#ef4444', label: 'Poor', className: 'signal-poor' };
    }
  };

  /**
   * Render circular signal strength indicator
   */
  const SignalStrengthIndicator = ({ strength }) => {
    const quality = getSignalQuality(strength);
    const radius = 45;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (strength / 100) * circumference;

    return (
      <div className={`signal-indicator-container ${quality.className}`}>
        <svg width="100" height="100" viewBox="0 0 100 100" className="signal-ring">
          {/* Background circle */}
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="4"
          />
          {/* Progress circle */}
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke={quality.color}
            strokeWidth="4"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform="rotate(-90 50 50)"
            className="signal-progress"
          />
        </svg>
        <div className="signal-text">
          <div className="signal-percentage">{strength}%</div>
          <div className="signal-label">{quality.label}</div>
        </div>
      </div>
    );
  };

  /**
   * Render status badge
   */
  const StatusBadge = ({ status }) => {
    const isOnline = status === 'online';
    return (
      <span className={`status-badge ${isOnline ? 'status-online' : 'status-offline'}`}>
        <span className={`status-dot ${isOnline ? 'online' : 'offline'}`}></span>
        {isOnline ? 'Online' : 'Offline'}
      </span>
    );
  };

  if (!node) {
    return <div className="node-card loading">Loading...</div>;
  }

  const signalQuality = getSignalQuality(node.signal_strength || 0);

  return (
    <div
      className={`deco-node-card ${(node.status || 'unknown').toLowerCase()}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          onClick();
        }
      }}
      aria-label={`Deco Node ${node.node_name || node.node_id}`}
    >
      {/* Header with name and status */}
      <div className="node-card-header">
        <div className="node-info-primary">
          <h3 className="node-name">{node.node_name || 'Unknown Node'}</h3>
          <p className="node-id-small">{node.node_id}</p>
        </div>
        <div className="header-actions">
          <StatusBadge status={node.status || 'unknown'} />
        </div>
      </div>

      {/* Main content */}
      <div className="node-card-content">
        {/* Left column - Text info */}
        <div className="node-info-column">
          {/* Firmware version */}
          <div className="node-info-row">
            <span className="node-label">Firmware:</span>
            <span className="node-value firmware">{node.firmware_version || 'Unknown'}</span>
          </div>

          {/* Uptime */}
          <div className="node-info-row">
            <span className="node-label">Uptime:</span>
            <span className="node-value uptime">{formatUptime(node.uptime_seconds)}</span>
          </div>

          {/* Connected clients */}
          <div className="node-info-row">
            <span className="node-label">Clients:</span>
            <span className="node-value clients">
              <span className="client-count">{node.connected_clients || 0}</span>
              {' '}connected
            </span>
          </div>

          {/* Model */}
          {node.model && node.model !== 'unknown' && (
            <div className="node-info-row">
              <span className="node-label">Model:</span>
              <span className="node-value model">{node.model}</span>
            </div>
          )}
        </div>

        {/* Right column - Signal indicator */}
        <div className="node-signal-column">
          <SignalStrengthIndicator strength={node.signal_strength || 0} />
        </div>
      </div>

      {/* Footer */}
      <div className="node-card-footer">
        <span className="footer-text">Click to view more details</span>
        {node.last_updated && (
          <span className="footer-timestamp">
            Updated: {new Date(node.last_updated).toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  );
}

export default DecoNodeCard;
