// 2026-03-11: Speed Insights page — deep metrics, charts, and AI-driven insights
// from Ookla speedtest results run on the Chester 5G router via SSH.
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { buildUrl } from '../utils/apiConfig';
import './SpeedInsightsPage.css';

function SpeedInsightsPage() {
  const [latest, setLatest] = useState(null);
  const [change, setChange] = useState(null);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [hourlyAvgs, setHourlyAvgs] = useState([]);
  const [insights, setInsights] = useState([]);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testRunning, setTestRunning] = useState(false);
  const [historyHours, setHistoryHours] = useState(24);
  // 2026-03-12: Live Chester cell info for carrier table
  const [chesterInfo, setChesterInfo] = useState(null);
  // 2026-03-12: Collapsible sections to reduce scroll depth
  const [showCellular, setShowCellular] = useState(false);
  const [showCarrierTable, setShowCarrierTable] = useState(false);
  // 2026-03-11: Inline banner notification (replaces alert() popups)
  const [banner, setBanner] = useState(null);
  const showBanner = (message, type = 'info') => {
    setBanner({ message, type });
    setTimeout(() => setBanner(null), type === 'error' ? 6000 : 4000);
  };

  const fetchAll = useCallback(async () => {
    try {
      const [latestRes, historyRes, hourlyRes, insightsRes, schedulerRes] = await Promise.all([
        fetch(buildUrl('/speedtest/latest')),
        fetch(buildUrl(`/speedtest/history?hours=${historyHours}`)),
        fetch(buildUrl('/speedtest/hourly-averages?days=7')),
        fetch(buildUrl('/speedtest/insights')),
        fetch(buildUrl('/speedtest/scheduler/status')),
      ]);

      if (latestRes.ok) {
        const d = await latestRes.json();
        setLatest(d.latest);
        setChange(d.change);
      }
      if (historyRes.ok) {
        const d = await historyRes.json();
        setHistory(d.tests || []);
        setStats(d.stats || null);
      }
      if (hourlyRes.ok) {
        const d = await hourlyRes.json();
        setHourlyAvgs(d.hourly || []);
      }
      if (insightsRes.ok) {
        const d = await insightsRes.json();
        setInsights(d.insights || []);
      }
      if (schedulerRes.ok) {
        setSchedulerStatus(await schedulerRes.json());
      }
    } catch (err) {
      console.error('Failed to fetch speed data:', err);
    } finally {
      setLoading(false);
    }
  }, [historyHours]);

  // 2026-03-12: Fetch Chester cell info for carrier aggregation table
  const fetchChester = useCallback(async () => {
    try {
      const res = await fetch(buildUrl('/chester/system-info'));
      if (res.ok) setChesterInfo(await res.json());
    } catch (e) { /* Chester may not be reachable */ }
  }, []);

  useEffect(() => {
    fetchAll();
    fetchChester();
    const interval = setInterval(fetchAll, 60000);
    const chesterInterval = setInterval(fetchChester, 30000);
    return () => { clearInterval(interval); clearInterval(chesterInterval); };
  }, [fetchAll, fetchChester]);

  const runTest = async () => {
    setTestRunning(true);
    try {
      const res = await fetch(buildUrl('/speedtest/run'), { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        if (result.error) {
          showBanner(`Speed test error: ${result.error}`, 'error');
        } else {
          showBanner('Speed test completed', 'success');
        }
        await fetchAll();
      }
    } catch (err) {
      showBanner('Speed test failed. Check Chester connectivity.', 'error');
    } finally {
      setTestRunning(false);
    }
  };

  // 2026-03-12: Use browser's local timezone instead of hardcoded America/New_York
  const formatTime = (ts) => {
    if (!ts) return '';
    const d = new Date(ts + (ts.includes('Z') ? '' : 'Z'));
    return d.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const formatDateTime = (ts) => {
    if (!ts) return '';
    const d = new Date(ts + (ts.includes('Z') ? '' : 'Z'));
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const renderChangeArrow = (pct, invertColor) => {
    if (pct == null) return null;
    const isGood = invertColor ? pct < 0 : pct > 0;
    const arrow = pct > 0 ? '\u25B2' : pct < 0 ? '\u25BC' : '';
    const cls = isGood ? 'si-change-good' : 'si-change-bad';
    return <span className={`si-change ${cls}`}>{arrow} {Math.abs(pct)}%</span>;
  };

  const insightIcon = (type) => {
    switch (type) {
      case 'trend': return '\u{1F4C8}';
      case 'hourly_pattern': return '\u{1F552}';
      case 'anomaly': return '\u26A0\uFE0F';
      case 'recommendation': return '\u{1F4A1}';
      default: return '\u{1F50D}';
    }
  };

  // Prepare chart data — add formatted time
  const chartData = history.map(t => ({
    ...t,
    time: formatTime(t.timestamp),
    dateTime: formatDateTime(t.timestamp),
  }));

  // Hourly chart — fill missing hours
  const hourlyChart = Array.from({ length: 24 }, (_, i) => {
    const found = hourlyAvgs.find(h => h.hour === i);
    return {
      hour: `${i.toString().padStart(2, '0')}:00`,
      download: found ? Math.round(found.avg_download * 10) / 10 : 0,
      upload: found ? Math.round(found.avg_upload * 10) / 10 : 0,
      ping: found ? Math.round(found.avg_ping * 10) / 10 : 0,
      samples: found ? found.sample_count : 0,
    };
  });

  // 2026-03-12: Extracted from inline IIFEs into useMemo for cleaner JSX and
  // to avoid recomputing on every render when inputs haven't changed.
  const bandCombinationData = useMemo(() => {
    const bandMap = {};
    chartData.forEach(t => {
      if (!t.cellular_ca_bands) return;
      try {
        const bands = typeof t.cellular_ca_bands === 'string' ? JSON.parse(t.cellular_ca_bands) : t.cellular_ca_bands;
        const key = bands.map(b => b.band.replace('NR5G BAND ', 'n')).sort().join('+');
        if (!bandMap[key]) bandMap[key] = { speeds: [], count: 0 };
        bandMap[key].speeds.push(t.download_mbps);
        bandMap[key].count++;
      } catch (e) { /* skip bad data */ }
    });
    return Object.entries(bandMap)
      .map(([combo, d]) => ({
        combo,
        avg_download: Math.round(d.speeds.reduce((a, b) => a + b, 0) / d.speeds.length * 10) / 10,
        max_download: Math.round(Math.max(...d.speeds) * 10) / 10,
        tests: d.count,
      }))
      .sort((a, b) => b.avg_download - a.avg_download);
  }, [chartData]);

  const carrierHistoryData = useMemo(() => {
    const bandInventory = {};
    const totalTests = chartData.filter(t => t.cellular_ca_bands).length;

    chartData.forEach(t => {
      if (!t.cellular_ca_bands) return;
      try {
        const bands = typeof t.cellular_ca_bands === 'string' ? JSON.parse(t.cellular_ca_bands) : t.cellular_ca_bands;
        const ts = t.timestamp;
        bands.forEach(b => {
          const key = `${b.arfcn}-${b.band}`;
          if (!bandInventory[key]) {
            bandInventory[key] = {
              band: b.band, arfcn: b.arfcn, bandwidth: b.bandwidth || '-',
              pccCount: 0, sccCount: 0, totalCount: 0,
              firstSeen: ts, lastSeen: ts,
              avgDownload: [], cellIds: new Set(),
            };
          }
          const entry = bandInventory[key];
          entry.totalCount++;
          if (b.role === 'PCC') entry.pccCount++;
          else entry.sccCount++;
          if (ts < entry.firstSeen) entry.firstSeen = ts;
          if (ts > entry.lastSeen) entry.lastSeen = ts;
          if (t.download_mbps) entry.avgDownload.push(t.download_mbps);
          if (t.cellular_cell_id) entry.cellIds.add(t.cellular_cell_id);
        });
      } catch (e) {}
    });

    // Parse live CA entries from Chester
    const liveArfcns = new Set();
    const liveRole = {};
    if (chesterInfo && chesterInfo.ca_band) {
      chesterInfo.ca_band.forEach(entry => {
        const parts = entry.replace(/"/g, '').split(',').map(s => s.trim());
        const role = parts[0];
        const arfcn = parts[1];
        const band = parts[3];
        const key = `${arfcn}-${band}`;
        liveArfcns.add(key);
        liveRole[key] = role;
        if (!bandInventory[key]) {
          bandInventory[key] = {
            band, arfcn, bandwidth: parts[2] || '-',
            pccCount: 0, sccCount: 0, totalCount: 0,
            firstSeen: null, lastSeen: null,
            avgDownload: [], cellIds: new Set(),
          };
        }
      });
    }

    return Object.entries(bandInventory).map(([key, v]) => ({
      key,
      ...v,
      avgDl: v.avgDownload.length > 0
        ? (v.avgDownload.reduce((a, b) => a + b, 0) / v.avgDownload.length).toFixed(1)
        : '-',
      pct: totalTests > 0 ? Math.round((v.totalCount / totalTests) * 100) : 0,
      isLive: liveArfcns.has(key),
      liveRole: liveRole[key] || null,
      isNew: v.totalCount <= 2 && v.firstSeen === v.lastSeen,
      cellIdList: [...v.cellIds].join(', '),
    })).sort((a, b) => b.totalCount - a.totalCount);
  }, [chartData, chesterInfo]);

  if (loading) {
    return <div className="si-page"><div className="si-loading">Loading speed data...</div></div>;
  }

  return (
    <div className="si-page">
      <div aria-live="polite" aria-atomic="true" role="status">
        {banner && (
          <div className={`app-banner app-banner-${banner.type}`}>
            {banner.message}
            <button className="banner-close" onClick={() => setBanner(null)} aria-label="Dismiss notification">&times;</button>
          </div>
        )}
      </div>
      <div className="si-header">
        <h2>Speed Insights</h2>
        <div className="si-header-actions">
          {schedulerStatus && (
            <span className="si-scheduler-badge">
              {schedulerStatus.is_running ? 'Auto-testing every 30 min' : 'Scheduler stopped'}
              {schedulerStatus.test_count > 0 && ` (${schedulerStatus.test_count} tests)`}
            </span>
          )}
          <button
            className="btn-run-test"
            onClick={runTest}
            disabled={testRunning}
          >
            {testRunning ? 'Running...' : 'Run Speed Test'}
          </button>
        </div>
      </div>

      {/* Current Speed — big hero metrics */}
      {latest ? (
        <div className="si-hero">
          <div className="si-hero-metric si-download">
            <div className="si-hero-label">Download</div>
            <div className="si-hero-value">{latest.download_mbps.toFixed(1)}</div>
            <div className="si-hero-unit">Mbps</div>
            {change && renderChangeArrow(change.download_pct, false)}
          </div>
          <div className="si-hero-metric si-upload">
            <div className="si-hero-label">Upload</div>
            <div className="si-hero-value">{latest.upload_mbps.toFixed(1)}</div>
            <div className="si-hero-unit">Mbps</div>
            {change && renderChangeArrow(change.upload_pct, false)}
          </div>
          <div className="si-hero-metric si-ping">
            <div className="si-hero-label">Ping</div>
            <div className="si-hero-value">{latest.ping_ms.toFixed(0)}</div>
            <div className="si-hero-unit">ms</div>
            {change && renderChangeArrow(change.ping_pct, true)}
          </div>
          {latest.jitter_ms != null && (
            <div className="si-hero-metric si-jitter">
              <div className="si-hero-label">Jitter</div>
              <div className="si-hero-value">{latest.jitter_ms.toFixed(1)}</div>
              <div className="si-hero-unit">ms</div>
            </div>
          )}
          <div className="si-hero-meta">
            <span>Server: {latest.server_name || 'N/A'}</span>
            <span>ISP: {latest.isp || 'N/A'}</span>
            <span>IP: {latest.external_ip || 'N/A'}</span>
            {latest.cellular_band && <span>Band: {latest.cellular_band}</span>}
            {latest.cellular_rsrp != null && <span>RSRP: {latest.cellular_rsrp} dBm</span>}
            <span>Tested: {formatDateTime(latest.timestamp)}</span>
          </div>
        </div>
      ) : (
        <div className="si-hero si-empty">
          <p>No speed test results yet. Click "Run Speed Test" to begin.</p>
        </div>
      )}

      {/* 24-Hour Stats Summary */}
      {stats && stats.test_count > 0 && (
        <div className="si-stats-bar">
          <div className="si-stat">
            <span className="si-stat-label">Tests ({historyHours}h)</span>
            <span className="si-stat-value">{stats.test_count}</span>
          </div>
          <div className="si-stat">
            <span className="si-stat-label">Avg Download</span>
            <span className="si-stat-value">{stats.avg_download} Mbps</span>
          </div>
          <div className="si-stat">
            <span className="si-stat-label">Peak Download</span>
            <span className="si-stat-value">{stats.max_download} Mbps</span>
          </div>
          <div className="si-stat">
            <span className="si-stat-label">Avg Upload</span>
            <span className="si-stat-value">{stats.avg_upload} Mbps</span>
          </div>
          <div className="si-stat">
            <span className="si-stat-label">Avg Ping</span>
            <span className="si-stat-value">{stats.avg_ping} ms</span>
          </div>
          <div className="si-stat">
            <span className="si-stat-label">Best Ping</span>
            <span className="si-stat-value">{stats.min_ping} ms</span>
          </div>
        </div>
      )}

      {/* Speed History Chart */}
      {chartData.length > 0 && (
        <div className="si-card">
          <div className="si-card-header">
            <h3>Speed History</h3>
            <div className="si-timerange">
              {[6, 12, 24, 48, 72, 168].map(h => (
                <button
                  key={h}
                  className={`si-timerange-btn ${historyHours === h ? 'active' : ''}`}
                  onClick={() => setHistoryHours(h)}
                >
                  {h < 48 ? `${h}h` : `${h / 24}d`}
                </button>
              ))}
            </div>
          </div>
          <div role="img" aria-label={`Speed history chart showing download and upload speeds over ${historyHours} hours. ${chartData.length} data points.`}>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="gradDl" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradUl" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit=" Mbps" width={70} />
              <Tooltip
                formatter={(val, name) => [`${val} Mbps`, name]}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.dateTime || ''}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="download_mbps"
                name="Download"
                stroke="#22c55e"
                fill="url(#gradDl)"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
              <Area
                type="monotone"
                dataKey="upload_mbps"
                name="Upload"
                stroke="#3b82f6"
                fill="url(#gradUl)"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </AreaChart>
          </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Ping / Jitter Chart */}
      {chartData.length > 0 && (
        <div className="si-card">
          <h3>Latency History</h3>
          <div role="img" aria-label="Latency history chart showing ping and jitter over time in milliseconds.">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit=" ms" width={60} />
              <Tooltip
                formatter={(val, name) => [`${val} ms`, name]}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.dateTime || ''}
              />
              <Legend />
              <Line type="monotone" dataKey="ping_ms" name="Ping" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="jitter_ms" name="Jitter" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Hourly Pattern Chart */}
      {hourlyChart.some(h => h.download > 0) && (
        <div className="si-card">
          <h3>Average Speed by Hour of Day <span className="si-subtitle">(last 7 days)</span></h3>
          <div role="img" aria-label="Bar chart showing average download and upload speeds grouped by hour of day over the last 7 days.">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={hourlyChart} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="hour" tick={{ fontSize: 10 }} interval={1} />
              <YAxis tick={{ fontSize: 11 }} unit=" Mbps" width={70} />
              <Tooltip formatter={(val, name) => {
                const unit = name === 'Ping' ? ' ms' : ' Mbps';
                return [`${val}${unit}`, name];
              }} />
              <Legend />
              <Bar dataKey="download" name="Download" fill="#22c55e" radius={[3, 3, 0, 0]} />
              <Bar dataKey="upload" name="Upload" fill="#3b82f6" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 2026-03-12: Collapsible cellular analysis section */}
      {chartData.some(t => t.cellular_rsrp != null || t.cellular_ca_count != null || t.cellular_ca_bands) && (
        <button className="si-section-toggle" onClick={() => setShowCellular(v => !v)} aria-expanded={showCellular}>
          <svg className="si-toggle-chevron" viewBox="0 0 16 16" width="14" height="14" style={{ transform: showCellular ? 'rotate(90deg)' : 'rotate(0deg)' }}>
            <path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Cellular Analysis
          <span className="si-toggle-hint">{showCellular ? 'collapse' : 'expand'}</span>
        </button>
      )}

      {showCellular && chartData.some(t => t.cellular_rsrp != null) && (
        <div className="si-card">
          <h3>Cellular Signal vs Download Speed</h3>
          <div role="img" aria-label="Dual-axis line chart correlating cellular RSRP signal strength in dBm with download speed in Mbps over time.">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="speed" tick={{ fontSize: 11 }} unit=" Mbps" width={70} />
              <YAxis yAxisId="signal" orientation="right" tick={{ fontSize: 11 }} unit=" dBm" width={65} />
              <Tooltip />
              <Legend />
              <Line yAxisId="speed" type="monotone" dataKey="download_mbps" name="Download (Mbps)" stroke="#22c55e" strokeWidth={2} dot={{ r: 2 }} />
              <Line yAxisId="signal" type="monotone" dataKey="cellular_rsrp" name="RSRP (dBm)" stroke="#ef4444" strokeWidth={2} dot={{ r: 2 }} />
            </LineChart>
          </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 2026-03-12: Download vs CA Band Count */}
      {showCellular && chartData.some(t => t.cellular_ca_count != null) && (
        <div className="si-card">
          <h3>Download Speed vs Carrier Aggregation Count</h3>
          <div role="img" aria-label="Dual-axis chart showing download speed vs number of carrier aggregation bands active during each speed test.">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData.filter(t => t.cellular_ca_count != null)} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="speed" tick={{ fontSize: 11 }} unit=" Mbps" width={70} />
              <YAxis yAxisId="ca" orientation="right" tick={{ fontSize: 11 }} domain={[0, 6]} width={40} label={{ value: 'CA', angle: -90, position: 'insideRight', fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line yAxisId="speed" type="monotone" dataKey="download_mbps" name="Download (Mbps)" stroke="#22c55e" strokeWidth={2} dot={{ r: 3 }} />
              <Line yAxisId="ca" type="stepAfter" dataKey="cellular_ca_count" name="CA Bands" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 2026-03-12: Average Download by Band Combination (extracted from IIFE into useMemo) */}
      {showCellular && bandCombinationData.length > 0 && (
          <div className="si-card">
            <h3>Average Download by Band Combination</h3>
            <div role="img" aria-label={`Horizontal bar chart comparing average and max download speeds across ${bandCombinationData.length} different NR band combinations.`}>
            <ResponsiveContainer width="100%" height={Math.max(180, bandCombinationData.length * 40)}>
              <BarChart data={bandCombinationData} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 11 }} unit=" Mbps" />
                <YAxis type="category" dataKey="combo" tick={{ fontSize: 10 }} width={140} />
                <Tooltip formatter={(val, name) => [`${val} Mbps`, name]} />
                <Legend />
                <Bar dataKey="avg_download" name="Avg Download" fill="#22c55e" radius={[0, 3, 3, 0]} />
                <Bar dataKey="max_download" name="Max Download" fill="#86efac" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
            </div>
          </div>
      )}

      {/* 2026-03-12: Collapsible CA history table */}
      {chartData.some(t => t.cellular_ca_bands) && (
        <button className="si-section-toggle" onClick={() => setShowCarrierTable(v => !v)} aria-expanded={showCarrierTable}>
          <svg className="si-toggle-chevron" viewBox="0 0 16 16" width="14" height="14" style={{ transform: showCarrierTable ? 'rotate(90deg)' : 'rotate(0deg)' }}>
            <path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Carrier Aggregation History
          <span className="si-toggle-hint">{showCarrierTable ? 'collapse' : 'expand'}</span>
        </button>
      )}

      {/* 2026-03-12: Carrier history table — extracted from IIFE into useMemo (carrierHistoryData) */}
      {showCarrierTable && carrierHistoryData.length > 0 && (
          <div className="si-card">
            <div className="si-card-header">
              <h3>Carrier Aggregation History <span className="si-subtitle">All bands ever connected — sorted by frequency</span></h3>
              {chesterInfo && <span className="si-ca-live-dot">LIVE</span>}
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="si-ca-table">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Band</th>
                    <th>DL ARFCN</th>
                    <th>BW</th>
                    <th>Role</th>
                    <th>Seen</th>
                    <th>% of Tests</th>
                    <th>Avg DL (Mbps)</th>
                    <th>Cell IDs</th>
                    <th>First Seen</th>
                    <th>Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {carrierHistoryData.map((c) => (
                    <tr key={c.key} className={c.isLive ? 'si-ca-live' : 'si-ca-inactive'}>
                      <td>
                        {c.isLive
                          ? <span className="si-ca-status si-ca-status-on">{c.liveRole || 'ON'}</span>
                          : <span className="si-ca-status si-ca-status-off">OFF</span>}
                        {c.isNew && <span className="si-ca-new">NEW</span>}
                      </td>
                      <td className="si-ca-band">{c.band.replace('NR5G BAND ', 'n')}</td>
                      <td>{c.arfcn}</td>
                      <td>{c.bandwidth}</td>
                      <td>
                        {c.pccCount > 0 && <span className="si-ca-role pcc">PCC ×{c.pccCount}</span>}
                        {c.pccCount > 0 && c.sccCount > 0 && ' '}
                        {c.sccCount > 0 && <span className="si-ca-role scc">SCC ×{c.sccCount}</span>}
                      </td>
                      <td>{c.totalCount}</td>
                      <td>
                        <div className="si-ca-pct-bar">
                          <div className="si-ca-pct-fill" style={{ width: `${c.pct}%` }} />
                          <span>{c.pct}%</span>
                        </div>
                      </td>
                      <td>{c.avgDl}</td>
                      <td className="si-ca-cellids">{c.cellIdList || '-'}</td>
                      <td>{c.firstSeen ? formatTime(c.firstSeen) : 'Now'}</td>
                      <td>{c.lastSeen ? formatTime(c.lastSeen) : 'Now'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
      )}

      {/* AI Insights */}
      {insights.length > 0 && (
        <div className="si-card si-insights">
          <h3>AI-Driven Insights</h3>
          <div className="si-insights-list">
            {insights.map((insight) => (
              <div key={insight.insight_id} className={`si-insight si-insight-${insight.insight_type}`}>
                <div className="si-insight-icon">{insightIcon(insight.insight_type)}</div>
                <div className="si-insight-content">
                  <div className="si-insight-title">{insight.title}</div>
                  <div className="si-insight-desc">{insight.description}</div>
                  {insight.confidence != null && (
                    <div className="si-insight-confidence">
                      Confidence: {Math.round(insight.confidence * 100)}%
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state when no data at all */}
      {!latest && history.length === 0 && insights.length === 0 && (
        <div className="si-card si-empty-state">
          <h3>No Speed Test Data Yet</h3>
          <p>Speed tests run automatically every 30 minutes on the Chester 5G router.</p>
          <p>Click "Run Speed Test" above to get your first result, or wait for the scheduler.</p>
        </div>
      )}
    </div>
  );
}

export default SpeedInsightsPage;
