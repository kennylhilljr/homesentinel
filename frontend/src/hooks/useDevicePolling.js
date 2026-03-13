// 2026-03-12: Extracted from App.js — custom hook for all data fetching and polling logic
import { useState, useEffect, useRef } from 'react';
import { buildUrl } from '../utils/apiConfig';

export default function useDevicePolling() {
  const [apiStatus, setApiStatus] = useState('connecting...');
  const [devices, setDevices] = useState([]);
  const [pollingConfig, setPollingConfig] = useState(null);
  const [lastScanTime, setLastScanTime] = useState(null);
  const [deviceGroups, setDeviceGroups] = useState([]);
  const [clientNodeMap, setClientNodeMap] = useState({});
  const [decoNodeMacs, setDecoNodeMacs] = useState(new Set());
  const [decoNodesMap, setDecoNodesMap] = useState({});
  const [decoNodeDetails, setDecoNodeDetails] = useState({});
  const [speedTestData, setSpeedTestData] = useState(null);
  const [speedTestRunning, setSpeedTestRunning] = useState(false);
  const [chesterInfo, setChesterInfo] = useState(null);
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [anomalyInsights, setAnomalyInsights] = useState([]);
  const [dailyDigest, setDailyDigest] = useState(null);
  const [healthScore, setHealthScore] = useState(null);
  const [unseenCount, setUnseenCount] = useState(0);
  // 2026-03-12: Default to home=true until backend confirms, avoids flash of "Away"
  const [homeStatus, setHomeStatus] = useState({ is_home: true, method: 'init', detail: 'loading...', auto_scan_active: true, auto_scan_paused: false });
  // 2026-03-11: Banner notification state (replaces all alert() popups)
  const [banner, setBanner] = useState(null); // { message, type: 'success'|'error'|'info' }

  const showBanner = (message, type = 'info') => {
    setBanner({ message, type });
    setTimeout(() => setBanner(null), type === 'error' ? 6000 : 4000);
  };

  // 2026-03-12: Refs for polling interval IDs (used by visibility handler to pause/resume)
  const fastIntervalRef = useRef(null);
  const slowIntervalRef = useRef(null);
  const speedIntervalRef = useRef(null);
  const notifIntervalRef = useRef(null);
  // Store polling callbacks in a ref so the visibility handler can restart intervals
  const pollingCallbacksRef = useRef(null);

  // 2026-03-12: Dismiss an active alert
  const dismissAlert = async (alertId) => {
    try {
      await fetch(buildUrl(`/events/alerts/${alertId}/dismiss`), { method: 'POST' });
      setActiveAlerts(prev => prev.filter(a => a.alert_id !== alertId));
    } catch (error) {
      console.error('Failed to dismiss alert:', error);
    }
  };

  const handleDeviceUpdate = (updatedDevice) => {
    setDevices(prev => prev.map(d => d.device_id === updatedDevice.device_id ? updatedDevice : d));
  };

  // 2026-03-11: Manual speed test trigger
  const runSpeedTest = async () => {
    setSpeedTestRunning(true);
    try {
      const response = await fetch(buildUrl('/speedtest/run'), { method: 'POST' });
      if (response.ok) {
        const result = await response.json();
        if (result.error) {
          showBanner(`Speed test error: ${result.error}`, 'error');
        } else {
          // Refresh latest data
          const latestResp = await fetch(buildUrl('/speedtest/latest'));
          if (latestResp.ok) {
            setSpeedTestData(await latestResp.json());
          }
          showBanner('Speed test completed', 'success');
        }
      } else {
        showBanner('Speed test failed. Check Chester connectivity.', 'error');
      }
    } catch (error) {
      console.error('Speed test failed:', error);
      showBanner('Speed test failed. Check Chester connectivity.', 'error');
    } finally {
      setSpeedTestRunning(false);
    }
  };

  // Main data fetching effect
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(buildUrl('/health'));
        if (response.ok) {
          await response.json();
          setApiStatus('connected');
        } else {
          setApiStatus('error');
        }
      } catch (error) {
        console.error('Health check failed:', error);
        setApiStatus('disconnected');
      }
    };

    const getDevices = async () => {
      try {
        const response = await fetch(buildUrl('/devices'));
        if (response.ok) {
          const data = await response.json();
          setDevices(data.devices || []);
          setLastScanTime(data.timestamp);
        }
      } catch (error) {
        console.error('Failed to fetch devices:', error);
      }
    };

    const getPollingConfig = async () => {
      try {
        const response = await fetch(buildUrl('/config/polling'));
        if (response.ok) {
          const data = await response.json();
          setPollingConfig(data);
        }
      } catch (error) {
        console.error('Failed to fetch polling config:', error);
      }
    };

    const getDeviceGroups = async () => {
      try {
        const response = await fetch(buildUrl('/device-groups'));
        if (response.ok) {
          const data = await response.json();
          setDeviceGroups(data.groups || []);
        }
      } catch (error) {
        console.error('Failed to fetch device groups:', error);
      }
    };

    // 2026-03-10: Fetch Deco client-to-node mapping for dashboard "Deco" column
    const getClientNodeMap = async () => {
      try {
        const response = await fetch(buildUrl('/deco/client-node-map'));
        if (response.ok) {
          const data = await response.json();
          setClientNodeMap(data.client_node_map || {});
          // 2026-03-11: Store normalized Deco node MACs for mesh toggle exclusion
          if (data.nodes) {
            const nodeMacs = new Set(
              Object.keys(data.nodes).map(m => m.toLowerCase().replace(/-/g, ':'))
            );
            setDecoNodeMacs(nodeMacs);
            setDecoNodesMap(data.nodes);
            // 2026-03-11: Store node details for backhaul signal icons
            if (data.node_details) {
              const normalized = {};
              for (const [k, v] of Object.entries(data.node_details)) {
                const nk = k.toLowerCase().replace(/-/g, ':');
                normalized[nk] = v;
              }
              setDecoNodeDetails(normalized);
            }
          }
        }
      } catch (error) {
        // Silently fail — Deco may not be configured
      }
    };

    // 2026-03-11: Fetch latest speed test result with % change
    const getSpeedTestLatest = async () => {
      try {
        const response = await fetch(buildUrl('/speedtest/latest'));
        if (response.ok) {
          const data = await response.json();
          setSpeedTestData(data);
        }
      } catch (error) {
        // Silently fail — speed test may not have run yet
      }
    };

    // 2026-03-11: Fetch Chester 5G cellular info for dashboard card
    const getChesterInfo = async () => {
      try {
        const response = await fetch(buildUrl('/chester/system-info'));
        if (response.ok) {
          const data = await response.json();
          setChesterInfo(data);
        }
      } catch (error) {
        // Silently fail — Chester may not be reachable
      }
    };

    // 2026-03-12: Home/Away network detection
    const getHomeStatus = async () => {
      try {
        const response = await fetch(buildUrl('/network/home-status'));
        if (response.ok) {
          const data = await response.json();
          setHomeStatus(data);
        }
      } catch (error) {
        // Silently fail
      }
    };

    // 2026-03-12: Fetch active alerts for dashboard card
    const getActiveAlerts = async () => {
      try {
        const response = await fetch(buildUrl('/events/alerts?limit=10'));
        if (response.ok) {
          const data = await response.json();
          setActiveAlerts(data.alerts || []);
        }
      } catch (error) { /* silent */ }
    };

    // 2026-03-12: Fetch speed insights, filter anomalies for dashboard
    const getAnomalyInsights = async () => {
      try {
        const response = await fetch(buildUrl('/speedtest/insights'));
        if (response.ok) {
          const data = await response.json();
          setAnomalyInsights(data.filter(i => i.insight_type === 'anomaly'));
        }
      } catch (error) { /* silent */ }
    };

    // 2026-03-12: Fetch daily digest (yesterday's summary)
    const getDailyDigest = async () => {
      try {
        const response = await fetch(buildUrl('/digest/daily'));
        if (response.ok) setDailyDigest(await response.json());
      } catch (error) { /* silent */ }
    };

    // 2026-03-12: Fetch network health score
    const getHealthScore = async () => {
      try {
        const response = await fetch(buildUrl('/network/health-score'));
        if (response.ok) setHealthScore(await response.json());
      } catch (error) { /* silent */ }
    };

    checkHealth();
    getDevices();
    getPollingConfig();
    getDeviceGroups();
    getClientNodeMap();
    getSpeedTestLatest();
    getChesterInfo();
    getHomeStatus();
    getActiveAlerts();
    getAnomalyInsights();
    getDailyDigest();
    getHealthScore();

    // 2026-03-12: SSE connection for real-time device updates (replaces 5s polling)
    // With SSE, fast poll is slowed to 15s as a fallback; SSE pushes trigger immediate refresh.
    const fastPoll = () => {
      checkHealth();
      getDevices();
      getPollingConfig();
      getDeviceGroups();
      getHomeStatus();
      getActiveAlerts();
    };
    const slowPoll = () => {
      getClientNodeMap();
      getChesterInfo();
      getHealthScore();
    };
    const speedPoll = () => {
      getSpeedTestLatest();
      getAnomalyInsights();
    };

    pollingCallbacksRef.current = { fastPoll, slowPoll, speedPoll };

    // 2026-03-12: SSE — connect to /api/sse/events for push updates
    let eventSource = null;
    try {
      eventSource = new EventSource('/api/sse/events');
      eventSource.addEventListener('device_update', () => {
        // Server pushed a device update — refresh immediately
        getDevices();
        getActiveAlerts();
        getHomeStatus();
      });
      eventSource.addEventListener('connected', () => {
        console.log('SSE: connected to server');
      });
      eventSource.onerror = () => {
        // SSE failed — fast polling will cover us as fallback
        console.warn('SSE: connection lost, relying on polling fallback');
      };
    } catch (e) {
      console.warn('SSE: not available, using polling only');
    }

    // 2026-03-12: Slowed fast poll from 5s to 15s — SSE handles real-time push
    fastIntervalRef.current = setInterval(fastPoll, 15000);
    slowIntervalRef.current = setInterval(slowPoll, 30000);
    speedIntervalRef.current = setInterval(speedPoll, 60000);

    return () => {
      clearInterval(fastIntervalRef.current);
      clearInterval(slowIntervalRef.current);
      clearInterval(speedIntervalRef.current);
      if (eventSource) eventSource.close();
    };
  }, []);

  // 2026-03-12: Browser push notifications — request permission + poll unseen alerts
  useEffect(() => {
    if ('Notification' in window && !localStorage.getItem('hs_notification_asked')) {
      Notification.requestPermission();
      localStorage.setItem('hs_notification_asked', '1');
    }

    const pollUnseen = async () => {
      try {
        const response = await fetch(buildUrl('/events/alerts/unseen'));
        if (!response.ok) return;
        const alerts = await response.json();
        setUnseenCount(alerts.length);

        if ('Notification' in window && Notification.permission === 'granted' && alerts.length > 0) {
          for (const alert of alerts) {
            const msg = alert.alert_type === 'new_device'
              ? `New device detected: ${alert.device_name}`
              : alert.alert_type === 'device_offline'
                ? `Device offline: ${alert.device_name}`
                : `Device reconnected: ${alert.device_name}`;
            try { new Notification('HomeSentinel', { body: msg, icon: '/favicon.ico' }); } catch (e) { /* silent */ }
          }
          const ids = alerts.map(a => a.alert_id);
          await fetch(buildUrl('/events/alerts/mark-seen'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ alert_ids: ids }),
          });
        }
      } catch (error) { /* silent */ }
    };

    pollUnseen();
    notifIntervalRef.current = setInterval(pollUnseen, 10000);
    if (pollingCallbacksRef.current) {
      pollingCallbacksRef.current.notifPoll = pollUnseen;
    }
    return () => clearInterval(notifIntervalRef.current);
  }, []);

  // 2026-03-12: Pause all polling when the browser tab is hidden to avoid
  // unnecessary network requests. Resume when the user returns to the tab.
  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) {
        clearInterval(fastIntervalRef.current);
        clearInterval(slowIntervalRef.current);
        clearInterval(speedIntervalRef.current);
        clearInterval(notifIntervalRef.current);
      } else {
        const cbs = pollingCallbacksRef.current;
        if (cbs) {
          if (cbs.fastPoll) {
            cbs.fastPoll();
            fastIntervalRef.current = setInterval(cbs.fastPoll, 5000);
          }
          if (cbs.slowPoll) {
            slowIntervalRef.current = setInterval(cbs.slowPoll, 30000);
          }
          if (cbs.speedPoll) {
            speedIntervalRef.current = setInterval(cbs.speedPoll, 60000);
          }
          if (cbs.notifPoll) {
            notifIntervalRef.current = setInterval(cbs.notifPoll, 10000);
          }
        }
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  return {
    devices, setDevices,
    apiStatus,
    pollingConfig,
    lastScanTime,
    chesterInfo,
    speedTestData, speedTestRunning,
    deviceGroups,
    clientNodeMap, setClientNodeMap,
    decoNodeMacs,
    decoNodesMap,
    decoNodeDetails,
    activeAlerts,
    anomalyInsights,
    dailyDigest,
    healthScore,
    homeStatus, setHomeStatus,
    unseenCount,
    showBanner, banner, setBanner,
    // action functions
    runSpeedTest,
    dismissAlert,
    handleDeviceUpdate,
    // polling refs for manual scan trigger
    pollingCallbacksRef,
  };
}
