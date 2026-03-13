// 2026-03-12: Extracted from App.js — 5G Signal card (Chester router metrics)
import React from 'react';

export default function CellularCard({ chesterInfo }) {
  return (
    <div className="status-card cellular-card">
      <h2>5G Signal</h2>
      {chesterInfo ? (
        <div className="cellular-info">
          <div className="cellular-type">
            <span className={`cellular-badge ${chesterInfo.is_5g ? 'badge-5g' : 'badge-lte'}`}>
              {chesterInfo.connection_type || 'Unknown'}
            </span>
            {chesterInfo.ca_band && chesterInfo.ca_band.length > 0 && (
              <span className="cellular-ca-count">{chesterInfo.ca_band.length}x CA</span>
            )}
          </div>
          <div className="cellular-metrics">
            <div className="cellular-metric">
              <span className="cellular-label">RSRP</span>
              <span className={`cellular-value ${
                chesterInfo.rsrp > -80 ? 'signal-excellent' :
                chesterInfo.rsrp > -100 ? 'signal-good' :
                chesterInfo.rsrp > -110 ? 'signal-fair' : 'signal-poor'
              }`}>{chesterInfo.rsrp} <small>dBm</small></span>
            </div>
            <div className="cellular-metric">
              <span className="cellular-label">SINR</span>
              <span className={`cellular-value ${
                chesterInfo.sinr > 20 ? 'signal-excellent' :
                chesterInfo.sinr > 10 ? 'signal-good' :
                chesterInfo.sinr > 0 ? 'signal-fair' : 'signal-poor'
              }`}>{chesterInfo.sinr} <small>dB</small></span>
            </div>
            <div className="cellular-metric">
              <span className="cellular-label">RSRQ</span>
              <span className="cellular-value">{chesterInfo.rsrq} <small>dB</small></span>
            </div>
            <div className="cellular-metric">
              <span className="cellular-label">Band</span>
              <span className="cellular-value">n{chesterInfo.band}</span>
            </div>
          </div>
          {chesterInfo.ca_band && chesterInfo.ca_band.length > 0 && (
            <div className="cellular-ca-list">
              {chesterInfo.ca_band.map((entry, i) => {
                const parts = entry.replace(/"/g, '').split(',');
                const role = parts[0]?.trim() || '';
                const bandName = parts[3]?.trim().replace('NR5G BAND ', 'n').replace('LTE BAND ', 'B') || '';
                const arfcn = parts[1]?.trim() || '';
                return (
                  <span key={i} className={`ca-chip ${role === 'PCC' ? 'ca-pcc' : 'ca-scc'}`}
                        title={`${role} — ARFCN ${arfcn}`}>
                    {role === 'PCC' ? '\u2605 ' : ''}{bandName}
                  </span>
                );
              })}
            </div>
          )}
          <div className="cellular-meta">
            <span>Cell {chesterInfo.cell_id}</span>
            <span>PCID {chesterInfo.pcid}</span>
            <span>ARFCN {chesterInfo.arfcn}</span>
          </div>
        </div>
      ) : (
        <p className="text-muted">Chester not reachable</p>
      )}
    </div>
  );
}
