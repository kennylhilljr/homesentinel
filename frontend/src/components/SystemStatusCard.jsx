// 2026-03-12: Extracted from App.js — System Status card
// 2026-05-07: Stronger hierarchy — primary API status, grouped scan + coverage metrics
import React from 'react';

export default function SystemStatusCard({
  apiStatus,
  pollingConfig,
  formatDate,
  vendorNamesPresent,
  deviceCount,
  scanning = false,
}) {
  const isConnected = apiStatus === 'connected';
  const coverage = deviceCount > 0
    ? Math.round((vendorNamesPresent / deviceCount) * 100)
    : null;
  return (
    <div className="status-card status-card-compact system-status">
      <h2>System Status</h2>
      <div
        className={`system-status-primary ${isConnected ? 'is-ok' : 'is-error'}`}
        role="status"
        aria-live="polite"
      >
        <span className="system-status-dot" aria-hidden="true">
          {isConnected ? (
            <svg viewBox="0 0 12 12" width="10" height="10"><circle cx="6" cy="6" r="3" fill="currentColor" /></svg>
          ) : (
            <svg viewBox="0 0 12 12" width="10" height="10"><circle cx="6" cy="6" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" /><line x1="3" y1="3" x2="9" y2="9" stroke="currentColor" strokeWidth="1.5" /></svg>
          )}
        </span>
        <div className="system-status-text">
          <span className="system-status-label">API</span>
          <span className="system-status-value">{isConnected ? 'Connected' : apiStatus}</span>
        </div>
        {scanning && (
          <span className="system-status-scanning" aria-label="Scanning network">
            <span className="hs-spinner" aria-hidden="true" />
          </span>
        )}
      </div>
      {pollingConfig && (
        <div className="system-status-row">
          <span className="system-status-row-label">Scan</span>
          <span className="system-status-row-value">
            <strong>{pollingConfig.interval}s</strong>
            <span className="system-status-meta"> · last {formatDate(pollingConfig.last_scan)}</span>
          </span>
        </div>
      )}
      <div className="system-status-row">
        <span className="system-status-row-label">Vendors</span>
        <span className="system-status-row-value">
          <strong>{vendorNamesPresent}/{deviceCount}</strong>
          {coverage !== null && <span className="system-status-meta"> · {coverage}% identified</span>}
        </span>
      </div>
    </div>
  );
}
