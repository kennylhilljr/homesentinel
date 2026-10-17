// 2026-03-12: Extracted from App.js — compact status strip with device counts and changes
import React from 'react';

export default function StatusStrip({
  devices,
  onlineCount,
  offlineCount,
  homeStatus,
  activeAlerts,
  anomalyInsights,
  newDeviceCount,
  pollingConfig,
  formatDate,
}) {
  return (
    <div className="status-strip">
      <div className="strip-stats">
        <span className="strip-stat"><strong>{devices.length}</strong> devices</span>
        <span className="strip-stat strip-online"><strong>{onlineCount}</strong> online</span>
        <span className="strip-stat strip-offline"><strong>{offlineCount}</strong> offline</span>
        <span className={`strip-stat strip-home ${homeStatus?.is_home ? '' : 'strip-away'}`}>
          <svg viewBox="0 0 16 16" width="13" height="13" style={{verticalAlign: '-2px'}}>
            <path d="M2 8l6-5 6 5v6h-4v-3H6v3H2V8z"
              fill={homeStatus?.is_home ? '#2e7d32' : '#e67e22'}/>
          </svg>
          {homeStatus?.is_home ? 'Home' : 'Away'}
        </span>
      </div>
      <div className="strip-changes">
        {activeAlerts.length > 0 && (
          <span className="whats-new-item whats-new-offline">{activeAlerts.length} active alert{activeAlerts.length > 1 ? 's' : ''}</span>
        )}
        {newDeviceCount > 0 && (
          <span className="whats-new-item whats-new-device">{newDeviceCount} new</span>
        )}
        {anomalyInsights.length > 0 && (
          <span className="whats-new-item whats-new-anomaly">{anomalyInsights.length} anomal{anomalyInsights.length > 1 ? 'ies' : 'y'}</span>
        )}
        {pollingConfig && (
          <span className="strip-scan">Scanned {formatDate(pollingConfig.last_scan)}</span>
        )}
      </div>
    </div>
  );
}
