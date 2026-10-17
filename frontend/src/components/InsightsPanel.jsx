// 2026-03-12: Extracted from App.js — collapsible insights toggle + digest/health cards
import React from 'react';

export default function InsightsPanel({
  showInsights,
  setShowInsights,
  activeAlerts,
  dailyDigest,
  healthScore,
}) {
  return (
    <>
      {/* 2026-03-12: Collapsible insights toggle — attached to status strip */}
      <button className="insights-toggle" onClick={() => setShowInsights(v => !v)} aria-expanded={showInsights}>
        <svg viewBox="0 0 16 16" width="14" height="14" style={{ transform: showInsights ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>
          <path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        Insights &amp; Alerts
        {!showInsights && activeAlerts.length > 0 && <span className="insights-badge">{activeAlerts.length}</span>}
        <span className="insights-hint">{showInsights ? 'collapse' : 'expand'}</span>
      </button>

      {showInsights && (
        <div className="status-split status-split-2">
          {/* Daily Digest Card */}
          <div className="status-card digest-card">
            <h2>Yesterday's Summary</h2>
            {dailyDigest ? (
              <div className="digest-grid">
                <div className="digest-stat">
                  <div className="digest-value">{dailyDigest.online_devices}</div>
                  <div className="digest-label">Devices Online</div>
                </div>
                <div className="digest-stat">
                  <div className="digest-value">{dailyDigest.new_devices_count}</div>
                  <div className="digest-label">New Devices</div>
                </div>
                {dailyDigest.speed ? (
                  <>
                    <div className="digest-stat">
                      <div className="digest-value">{dailyDigest.speed.avg_download}</div>
                      <div className="digest-label">Avg Mbps</div>
                    </div>
                    <div className="digest-stat">
                      <div className="digest-value">{dailyDigest.speed.max_download}</div>
                      <div className="digest-label">Best Mbps</div>
                    </div>
                  </>
                ) : (
                  <div className="digest-stat">
                    <div className="digest-value">&mdash;</div>
                    <div className="digest-label">No tests</div>
                  </div>
                )}
                {dailyDigest.avg_signal_rsrp && (
                  <div className="digest-stat">
                    <div className="digest-value">{dailyDigest.avg_signal_rsrp}</div>
                    <div className="digest-label">Avg RSRP</div>
                  </div>
                )}
              </div>
            ) : (
              <div className="digest-empty">Loading digest...</div>
            )}
          </div>

          {/* Health Score Card */}
          <div className="status-card health-card">
            <h2>Network Health</h2>
            {healthScore ? (
              <div className="health-content">
                <div className="score-gauge-container">
                  <svg viewBox="0 0 100 100" className="score-gauge">
                    <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border, #333)" strokeWidth="8" />
                    <circle cx="50" cy="50" r="42" fill="none"
                      stroke={healthScore.score >= 80 ? '#27ae60' : healthScore.score >= 60 ? '#f39c12' : '#c0392b'}
                      strokeWidth="8"
                      strokeDasharray={`${healthScore.score * 2.64} 264`}
                      strokeLinecap="round"
                      transform="rotate(-90 50 50)"
                    />
                    <text x="50" y="46" textAnchor="middle" className="score-number" fill="var(--text, #e0e0e0)">{healthScore.score}</text>
                    <text x="50" y="60" textAnchor="middle" className="score-label-svg" fill="var(--text-muted, #556277)">/ 100</text>
                  </svg>
                </div>
                <div className="health-details">
                  <div className="health-fact">{healthScore.streak_days} day uptime streak</div>
                  <div className="health-fact">Speed record: {healthScore.speed_record_mbps} Mbps</div>
                  <div className="health-fact">{healthScore.devices_ever_seen} devices ever seen</div>
                </div>
              </div>
            ) : (
              <div className="digest-empty">Loading score...</div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
