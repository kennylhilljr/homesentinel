import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [apiStatus, setApiStatus] = useState('connecting...');
  const [devices, setDevices] = useState([]);

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
        }
      } catch (error) {
        console.error('Failed to fetch devices:', error);
      }
    };

    checkHealth();
    getDevices();

    const interval = setInterval(() => {
      checkHealth();
      getDevices();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

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
        </div>

        <div className="devices-card">
          <h2>Network Devices</h2>
          {devices.length > 0 ? (
            <ul className="devices-list">
              {devices.map((device, idx) => (
                <li key={idx}>{device.name || device.mac_address}</li>
              ))}
            </ul>
          ) : (
            <p>No devices discovered yet</p>
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
