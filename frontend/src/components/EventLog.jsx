import React, { useState, useEffect, useCallback } from 'react';
import './EventLog.css';

/**
 * EventLog Component
 * Displays device events and alerts with filtering by device, date range, and event type
 * Supports dismissal of alerts and pagination
 * 2026-03-14: Enhanced with state transition event creation
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
  const [offset, setOffset] = useState(0);
  const [totalEvents, setTotalEvents] = useState(0);
  const [totalAlerts, setTotalAlerts] = useState(0);

  const eventTypes = ['connected', 'disconnected', 'online', 'offline', 'new_device'];

  // Fetch events with improved error handling
  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedDevice) params.append('device_id', selectedDevice);
      if (selectedEventType) params.append('event_type', selectedEventType);
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      params.append('limit', limit);
      params.append('offset', offset);

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
      setTotalEvents(data.total || 0);
    } catch (error) {
      console.error('Error fetching events:', error);
      setEvents([]);
      setTotalEvents(0);
    } finally {
      setLoading(false);
    }
  }, [selectedDevice, selectedEventType, startDate, endDate, limit, offset]);

  // Fetch alerts
  const fetchAlerts = useCallback(async () => {
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
      setTotalAlerts(data.total || 0);
    } catch (error) {
      console.error('Error fetching alerts:', error);
      setAlerts([]);
      setTotalAlerts(0);
    } finally {
      setLoading(false);
    }
  }, []);

  // Dismiss alert with refresh
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
  }, [activeTab, fetchEvents, fetchAlerts]);

  // Fetch events on filter change (reset offset to 0)
  useEffect(() => {
    if (activeTab === 'events') {
      setOffset(0);
    }
  }, [selectedDevice, selectedEventType, startDate, endDate, limit, activeTab]);

  // Fetch when offset changes
  useEffect(() => {
    if (activeTab === 'events') {
      fetchEvents();
    }
  }, [offset, activeTab, fetchEvents]);

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
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) return 'just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;
      return date.toLocaleDateString();
    } catch {
      return timestamp;
    }
  };

  const handleClearFilters = () => {
    setSelectedDevice('');
    setSelectedEventType('');
    setStartDate('');
    setEndDate('');
    setOffset(0);
  };

  const handlePreviousPage = () => {
    setOffset(Math.max(0, offset - limit));
  };

  const handleNextPage = () => {
    if (offset + limit < totalEvents) {
      setOffset(offset + limit);
    }
  };

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(totalEvents / limit);

  return (
    <div className="event-log-container">
      <div className="event-log-header">
        <h2>Device Events & Alerts</h2>
        <div className="event-log-tabs">
          <button
            className={`tab-button ${activeTab === 'events' ? 'active' : ''}`}
            onClick={() => setActiveTab('events')}
          >
            Events ({totalEvents})
          </button>
          <button
            className={`tab-button ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => setActiveTab('alerts')}
          >
            Alerts ({totalAlerts})
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

          <div className="filter-group">
            <label>&nbsp;</label>
            <button
              onClick={handleClearFilters}
              style={{
                padding: '8px 12px',
                backgroundColor: '#555',
                border: 'none',
                borderRadius: '4px',
                color: '#fff',
                cursor: 'pointer',
                fontSize: '13px'
              }}
            >
              Clear Filters
            </button>
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
          <>
            <div className="event-list">
              {events.map((event) => (
                <div key={event.event_id} className="event-item">
                  <div style={{ flex: 1 }}>
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
                </div>
              ))}
            </div>
            {/* Pagination controls */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '15px',
              borderTop: '1px solid #333',
              backgroundColor: '#262626',
              fontSize: '13px',
              color: '#b0b0b0'
            }}>
              <span>Page {currentPage} of {totalPages || 1} ({totalEvents} total)</span>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={handlePreviousPage}
                  disabled={offset === 0}
                  style={{
                    padding: '6px 12px',
                    backgroundColor: offset === 0 ? '#444' : '#3b82f6',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#fff',
                    cursor: offset === 0 ? 'not-allowed' : 'pointer',
                    fontSize: '12px',
                    opacity: offset === 0 ? 0.5 : 1
                  }}
                >
                  Previous
                </button>
                <button
                  onClick={handleNextPage}
                  disabled={offset + limit >= totalEvents}
                  style={{
                    padding: '6px 12px',
                    backgroundColor: offset + limit >= totalEvents ? '#444' : '#3b82f6',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#fff',
                    cursor: offset + limit >= totalEvents ? 'not-allowed' : 'pointer',
                    fontSize: '12px',
                    opacity: offset + limit >= totalEvents ? 0.5 : 1
                  }}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}

        {!loading && activeTab === 'alerts' && alerts.length > 0 && (
          <div className="alert-list">
            {alerts.map((alert) => (
              <div key={alert.alert_id} className="alert-item">
                <div className="event-item-header">
                  <span
                    className="alert-type-badge"
                    style={{ backgroundColor: getEventTypeColor(alert.alert_type) }}
                  >
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
