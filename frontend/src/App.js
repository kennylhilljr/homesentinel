import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [apiStatus, setApiStatus] = useState('connecting...');
  const [devices, setDevices] = useState([]);
  const [pollingConfig, setPollingConfig] = useState(null);
  const [lastScanTime, setLastScanTime] = useState(null);
  const [loading, setLoading] = useState(false);
  const [deviceGroups, setDeviceGroups] = useState([]);
  const [editingDevice, setEditingDevice] = useState(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [formData, setFormData] = useState({
    friendly_name: '',
    device_type: '',
    notes: '',
  });

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

    const getDeviceGroups = async () => {
      try {
        const response = await fetch('https://localhost:8443/api/device-groups', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });
        if (response.ok) {
          const data = await response.json();
          setDeviceGroups(data.groups || []);
        }
      } catch (error) {
        console.error('Failed to fetch device groups:', error);
      }
    };

    checkHealth();
    getDevices();
    getPollingConfig();
    getDeviceGroups();

    const interval = setInterval(() => {
      checkHealth();
      getDevices();
      getPollingConfig();
      getDeviceGroups();
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

  const openEditModal = (device) => {
    setEditingDevice(device);
    setFormData({
      friendly_name: device.friendly_name || '',
      device_type: device.device_type || '',
      notes: device.notes || '',
    });
    setShowEditModal(true);
  };

  const closeEditModal = () => {
    setShowEditModal(false);
    setEditingDevice(null);
    setFormData({
      friendly_name: '',
      device_type: '',
      notes: '',
    });
  };

  const saveDeviceChanges = async () => {
    if (!editingDevice) return;

    try {
      const response = await fetch(
        `https://localhost:8443/api/devices/${editingDevice.device_id}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(formData),
        }
      );

      if (response.ok) {
        const updatedDevice = await response.json();
        setDevices(devices.map(d => d.device_id === updatedDevice.device_id ? updatedDevice : d));
        closeEditModal();
        alert('Device updated successfully');
      } else {
        alert('Failed to update device');
      }
    } catch (error) {
      console.error('Failed to save device:', error);
      alert('Error saving device');
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getDeviceDisplayName = (device) => {
    return device.friendly_name || device.mac_address;
  };

  const vendorNamesPresent = devices.filter(d => d.vendor_name).length;

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
          <p>Devices with Vendor Info: <strong>{vendorNamesPresent}/{devices.length}</strong></p>
        </div>

        {deviceGroups.length > 0 && (
          <div className="groups-card">
            <h2>Device Groups ({deviceGroups.length})</h2>
            <div className="groups-container">
              {deviceGroups.map((group) => (
                <div key={group.group_id} className="group-item" style={{ borderLeftColor: group.color }}>
                  <h3>{group.name}</h3>
                  <p className="group-color" style={{ backgroundColor: group.color }}>Color: {group.color}</p>
                  <p className="group-timestamp">Created: {formatDate(group.created_at)}</p>
                </div>
              ))}
            </div>
          </div>
        )}

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
                    <th>Device Name</th>
                    <th>MAC Address</th>
                    <th>Vendor</th>
                    <th>IP Address</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {devices.map((device) => (
                    <tr key={device.device_id} className={`device-row ${device.status}`}>
                      <td className="device-name">
                        {getDeviceDisplayName(device)}
                      </td>
                      <td className="mac-address">{device.mac_address}</td>
                      <td className="vendor-name">{device.vendor_name || 'Unknown'}</td>
                      <td className="ip-address">{device.current_ip || 'N/A'}</td>
                      <td className="device-type">{device.device_type || 'unknown'}</td>
                      <td className={`status ${device.status}`}>
                        <span className={`status-badge ${device.status}`}>{device.status}</span>
                      </td>
                      <td className="actions">
                        <button
                          className="edit-button"
                          onClick={() => openEditModal(device)}
                          title="Edit device"
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p>No devices discovered yet. Click "Scan Now" to start discovery.</p>
          )}
        </div>

        {showEditModal && editingDevice && (
          <div className="modal-overlay">
            <div className="modal-content">
              <h2>Edit Device: {editingDevice.mac_address}</h2>
              <form>
                <div className="form-group">
                  <label htmlFor="friendly_name">Friendly Name:</label>
                  <input
                    type="text"
                    id="friendly_name"
                    value={formData.friendly_name}
                    onChange={(e) =>
                      setFormData({ ...formData, friendly_name: e.target.value })
                    }
                    placeholder="e.g., Living Room TV"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="device_type">Device Type:</label>
                  <select
                    id="device_type"
                    value={formData.device_type}
                    onChange={(e) =>
                      setFormData({ ...formData, device_type: e.target.value })
                    }
                  >
                    <option value="">Select type...</option>
                    <option value="mobile">Mobile</option>
                    <option value="computer">Computer</option>
                    <option value="iot">IoT</option>
                    <option value="printer">Printer</option>
                    <option value="router">Router</option>
                    <option value="tv">Smart TV</option>
                    <option value="camera">Camera</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="notes">Notes:</label>
                  <textarea
                    id="notes"
                    value={formData.notes}
                    onChange={(e) =>
                      setFormData({ ...formData, notes: e.target.value })
                    }
                    placeholder="Add any notes about this device..."
                    rows="4"
                  />
                </div>
                <div className="modal-buttons">
                  <button
                    type="button"
                    className="btn-save"
                    onClick={saveDeviceChanges}
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    className="btn-cancel"
                    onClick={closeEditModal}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        <div className="info-card">
          <h3>Welcome to HomeSentinel</h3>
          <p>This is the home network monitoring dashboard. The system is currently discovering devices on your network.</p>
          <p><strong>Backend:</strong> https://localhost:8443</p>
          <p><strong>Frontend:</strong> http://localhost:3000</p>
          <p><strong>Features:</strong> OUI vendor lookup, device metadata, and device grouping</p>
        </div>
      </main>
    </div>
  );
}

export default App;
