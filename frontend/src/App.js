import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [apiStatus, setApiStatus] = useState('connecting...');
  const [devices, setDevices] = useState([]);
  const [pollingConfig, setPollingConfig] = useState(null);
  const [lastScanTime, setLastScanTime] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Check backend API health
    const checkHealth = async () => {
      try {
        const response = await fetch('https://localhost:8443/api/health', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });
        if (response.ok) {
          const data = await response.json();
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
        const response = await fetch('https://localhost:8443/api/devices', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });
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
        const response = await fetch('https://localhost:8443/api/config/polling', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });
        if (response.ok) {
          const data = await response.json();
          setPollingConfig(data);
        }
      } catch (error) {
        console.error('Failed to fetch polling config:', error);
      }
    };

    checkHealth();
    getDevices();
    getPollingConfig();

    const interval = setInterval(() => {
      checkHealth();
      getDevices();
      getPollingConfig();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const triggerManualScan = async () => {
    setLoading(true);
    try {
      const response = await fetch('https://localhost:8443/api/devices/scan-now', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (response.ok) {
        const data = await response.json();
        console.log('Manual scan completed:', data);
        // Refresh devices after scan
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      }
    } catch (error) {
      console.error('Failed to trigger manual scan:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>HomeSentinel</h1>
        <p>Home Network Monitor & Device Management Platform</p>
      </header>
      <main className="App-main">
        <div className="status-card">
          <h2>System Status</h2>
          <p>API Connection: <strong className={apiStatus === 'connected' ? 'status-ok' : 'status-error'}>{apiStatus}</strong></p>
          {pollingConfig && (
            <>
              <p>Polling Interval: <strong>{pollingConfig.interval}s</strong></p>
              <p>Last Scanned: <strong>{formatDate(pollingConfig.last_scan)}</strong></p>
            </>
          )}
        </div>

        <div className="devices-card">
          <div className="devices-header">
            <h2>Network Devices ({devices.length})</h2>
            <button
              onClick={triggerManualScan}
              disabled={loading}
              className="scan-button"
            >
              {loading ? 'Scanning...' : 'Scan Now'}
            </button>
          </div>
          {devices.length > 0 ? (
            <>
              <p className="device-info">Last updated: {formatDate(lastScanTime)}</p>
              <table className="devices-table">
                <thead>
                  <tr>
                    <th>MAC Address</th>
                    <th>IP Address</th>
                    <th>Status</th>
                    <th>First Seen</th>
                    <th>Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {devices.map((device) => (
                    <tr key={device.device_id} className={`device-row ${device.status}`}>
                      <td className="mac-address">{device.mac_address}</td>
                      <td className="ip-address">{device.current_ip || 'N/A'}</td>
                      <td className={`status ${device.status}`}>
                        <span className={`status-badge ${device.status}`}>{device.status}</span>
                      </td>
                      <td className="timestamp">{formatDate(device.first_seen)}</td>
                      <td className="timestamp">{formatDate(device.last_seen)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p>No devices discovered yet. Click "Scan Now" to start discovery.</p>
          )}
        </div>

        <div className="info-card">
          <h3>Welcome to HomeSentinel</h3>
          <p>This is the home network monitoring dashboard. The system is currently discovering devices on your network.</p>
          <p><strong>Backend:</strong> https://localhost:8443</p>
          <p><strong>Frontend:</strong> http://localhost:3000</p>
        </div>
      </main>
    </div>
  );
}

export default App;
