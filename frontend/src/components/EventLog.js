import React, { useState, useEffect } from 'react';
import './EventLog.css';

/**
 * EventLog Component
 * Displays device events with filtering by device, date range, and event type
 * Supports dismissal of alerts
 */
function EventLog({ devices = [] }) {
  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('events'); // 'events' or 'alerts'

  // Filter states
  const [selectedDevice, setSelectedDevice] = useState('');
  const [selectedEventType, setSelectedEventType] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [limit, setLimit] = useState(100);

  const eventTypes = ['connected', 'disconnected', 'online', 'offline', 'new_device'];

  // Fetch events
  const fetchEvents = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedDevice) params.append('device_id', selectedDevice);
      if (selectedEventType) params.append('event_type', selectedEventType);
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      params.append('limit', limit);
      params.append('offset', 0);

      const response = await fetch(`/api/events?${params}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch events: ${response.status}`);
      }

      const data = await response.json();
      setEvents(data.events || []);
    } catch (error) {
      console.error('Error fetching events:', error);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  };

  // Fetch alerts
  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/events/alerts', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch alerts: ${response.status}`);
      }

      const data = await response.json();
      setAlerts(data.alerts || []);
    } catch (error) {
      console.error('Error fetching alerts:', error);
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  };

  // Dismiss alert
  const dismissAlert = async (alertId) => {
    try {
      const response = await fetch(`/api/events/alerts/${alertId}/dismiss`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to dismiss alert: ${response.status}`);
      }

      // Refresh alerts
      await fetchAlerts();
    } catch (error) {
      console.error('Error dismissing alert:', error);
    }
  };

  // Fetch on tab change
  useEffect(() => {
    if (activeTab === 'events') {
      fetchEvents();
    } else {
      fetchAlerts();
    }
  }, [activeTab]);

  // Fetch on filter change
  useEffect(() => {
    if (activeTab === 'events') {
      fetchEvents();
    }
  }, [selectedDevice, selectedEventType, startDate, endDate, limit]);

  const getEventTypeColor = (eventType) => {
    const colors = {
      'new_device': '#22c55e',
      'connected': '#3b82f6',
      'disconnected': '#ef4444',
      'online': '#10b981',
      'offline': '#6b7280'
    };
    return colors[eventType] || '#9ca3af';
  };

  const getDeviceName = (deviceId) => {
    const device = devices.find(d => d.device_id === deviceId);
    return device?.friendly_name || device?.mac_address || deviceId;
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  return (
    <div className="event-log-container">
      <div className="event-log-header">
        <h2>Device Events & Alerts</h2>
        <div className="event-log-tabs">
          <button
            className={`tab-button ${activeTab === 'events' ? 'active' : ''}`}
            onClick={() => setActiveTab('events')}
          >
            Events ({events.length})
          </button>
          <button
            className={`tab-button ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => setActiveTab('alerts')}
          >
            Alerts ({alerts.length})
          </button>
        </div>
      </div>

      {activeTab === 'events' && (
        <div className="event-filters">
          <div className="filter-group">
            <label htmlFor="device-select">Device:</label>
            <select
              id="device-select"
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              className="filter-input"
            >
              <option value="">All Devices</option>
              {devices.map((device) => (
                <option key={device.device_id} value={device.device_id}>
                  {device.friendly_name || device.mac_address}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="event-type-select">Event Type:</label>
            <select
              id="event-type-select"
              value={selectedEventType}
              onChange={(e) => setSelectedEventType(e.target.value)}
              className="filter-input"
            >
              <option value="">All Types</option>
              {eventTypes.map((type) => (
                <option key={type} value={type}>
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="start-date">Start Date:</label>
            <input
              id="start-date"
              type="datetime-local"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label htmlFor="end-date">End Date:</label>
            <input
              id="end-date"
              type="datetime-local"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label htmlFor="limit-input">Limit:</label>
            <input
              id="limit-input"
              type="number"
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value))}
              min="10"
              max="1000"
              className="filter-input"
            />
          </div>
        </div>
      )}

      <div className="event-log-content">
        {loading && <div className="loading">Loading...</div>}

        {!loading && activeTab === 'events' && events.length === 0 && (
          <div className="empty-state">No events found</div>
        )}

        {!loading && activeTab === 'alerts' && alerts.length === 0 && (
          <div className="empty-state">No active alerts</div>
        )}

        {!loading && activeTab === 'events' && events.length > 0 && (
          <div className="event-list">
            {events.map((event) => (
              <div key={event.event_id} className="event-item">
                <div className="event-item-header">
                  <span
                    className="event-type-badge"
                    style={{ backgroundColor: getEventTypeColor(event.event_type) }}
                  >
                    {event.event_type}
                  </span>
                  <span className="event-device">{getDeviceName(event.device_id)}</span>
                  <span className="event-timestamp">{formatTimestamp(event.timestamp)}</span>
                </div>
                {event.description && (
                  <div className="event-description">{event.description}</div>
                )}
              </div>
            ))}
          </div>
        )}

        {!loading && activeTab === 'alerts' && alerts.length > 0 && (
          <div className="alert-list">
            {alerts.map((alert) => (
              <div key={alert.alert_id} className="alert-item">
                <div className="alert-item-header">
                  <span className="alert-type-badge" style={{ backgroundColor: getEventTypeColor(alert.alert_type) }}>
                    {alert.alert_type}
                  </span>
                  <span className="alert-device">{getDeviceName(alert.device_id)}</span>
                  <span className="alert-timestamp">{formatTimestamp(alert.created_at)}</span>
                </div>
                <button
                  className="dismiss-button"
                  onClick={() => dismissAlert(alert.alert_id)}
                >
                  Dismiss
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default EventLog;
