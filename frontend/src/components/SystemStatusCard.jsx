// 2026-03-12: Extracted from App.js — System Status card
import React from 'react';

export default function SystemStatusCard({
  apiStatus,
  pollingConfig,
  formatDate,
  vendorNamesPresent,
  deviceCount,
}) {
  return (
    <div className="status-card status-card-compact">
      <h2>System Status</h2>
      <p>API: <strong className={apiStatus === 'connected' ? 'status-ok' : 'status-error'}>{apiStatus}</strong></p>
      {pollingConfig && (
        <p>Scan: <strong>{pollingConfig.interval}s</strong> &mdash; {formatDate(pollingConfig.last_scan)}</p>
      )}
      <p>Vendors: <strong>{vendorNamesPresent}/{deviceCount}</strong></p>
    </div>
  );
}
