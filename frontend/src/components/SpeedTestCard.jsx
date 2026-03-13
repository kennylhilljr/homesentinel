// 2026-03-12: Extracted from App.js — Speed Test card
import React from 'react';

export default function SpeedTestCard({
  speedTestData,
  speedTestRunning,
  runSpeedTest,
  formatDate,
}) {
  const renderChange = (pct, invertColor) => {
    if (pct == null) return null;
    // For ping, negative = good (invertColor=true)
    const isGood = invertColor ? pct < 0 : pct > 0;
    const arrow = pct > 0 ? '\u25B2' : pct < 0 ? '\u25BC' : '';
    const cls = isGood ? 'change-good' : 'change-bad';
    return <span className={`speed-change ${cls}`}>{arrow} {Math.abs(pct)}%</span>;
  };

  return (
    <div className="status-card speedtest-card">
      <h2>Speed Test
        <button
          className="btn-speedtest-run"
          onClick={runSpeedTest}
          disabled={speedTestRunning}
          title="Run speed test on Chester router via SSH"
        >
          {speedTestRunning ? 'Testing...' : 'Run Now'}
        </button>
      </h2>
      {speedTestData && speedTestData.latest ? (() => {
        const st = speedTestData.latest;
        const ch = speedTestData.change;
        return (
          <div className="speedtest-results">
            <div className="speedtest-metrics">
              <div className="speed-metric download">
                <span className="speed-label">Download</span>
                <span className="speed-value">{st.download_mbps.toFixed(1)}</span>
                <span className="speed-unit">Mbps</span>
                {ch && renderChange(ch.download_pct, false)}
              </div>
              <div className="speed-metric upload">
                <span className="speed-label">Upload</span>
                <span className="speed-value">{st.upload_mbps.toFixed(1)}</span>
                <span className="speed-unit">Mbps</span>
                {ch && renderChange(ch.upload_pct, false)}
              </div>
              <div className="speed-metric ping">
                <span className="speed-label">Ping</span>
                <span className="speed-value">{st.ping_ms.toFixed(0)}</span>
                <span className="speed-unit">ms</span>
                {ch && renderChange(ch.ping_pct, true)}
              </div>
              {st.jitter_ms != null && (
                <div className="speed-metric jitter">
                  <span className="speed-label">Jitter</span>
                  <span className="speed-value">{st.jitter_ms.toFixed(1)}</span>
                  <span className="speed-unit">ms</span>
                </div>
              )}
            </div>
            <div className="speedtest-meta">
              <span>via {st.server_name || 'Unknown'}</span>
              <span>{st.isp || ''}</span>
              <span>{formatDate(st.timestamp)}</span>
            </div>
          </div>
        );
      })() : (
        <div className="speedtest-empty">
          <p>No speed test results yet</p>
          <p className="text-muted">Tests run every 30 minutes on the Chester router</p>
        </div>
      )}
    </div>
  );
}
