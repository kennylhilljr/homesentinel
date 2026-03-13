import React, { useState, useCallback, useEffect } from 'react';
import './DeviceSearch.css';

const DeviceSearch = ({ onSearchResults }) => {
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showResults, setShowResults] = useState(false);
  const [expandedDeviceId, setExpandedDeviceId] = useState(null);

  // Debounced search function
  const performSearch = useCallback(async (searchQuery, status) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setShowResults(false);
      return;
    }

    setLoading(true);
    setError('');

    try {
      const params = new URLSearchParams();
      params.append('q', searchQuery.trim());
      if (status) {
        params.append('status', status);
      }

      const response = await fetch(`/api/devices/search?${params}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const data = await response.json();
      setResults(data.devices || []);
      setShowResults(true);

      // Call parent callback if provided
      if (onSearchResults) {
        onSearchResults(data.devices);
      }
    } catch (err) {
      setError(err.message);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [onSearchResults]);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      performSearch(query, statusFilter);
    }, 300);

    return () => clearTimeout(timer);
  }, [query, statusFilter, performSearch]);

  const handleQueryChange = (e) => {
    setQuery(e.target.value);
  };

  const handleStatusFilterChange = (e) => {
    setStatusFilter(e.target.value);
  };

  const handleClearSearch = () => {
    setQuery('');
    setStatusFilter('');
    setResults([]);
    setShowResults(false);
    setError('');
  };

  const toggleDeviceExpanded = (deviceId) => {
    setExpandedDeviceId(expandedDeviceId === deviceId ? null : deviceId);
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return 'Unknown';
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch {
      return dateString;
    }
  };

  const renderIPHistory = (ipHistory) => {
    if (!ipHistory || !Array.isArray(ipHistory) || ipHistory.length === 0) {
      return <div className="no-history">No IP history</div>;
    }

    return (
      <div className="ip-history-list">
        {ipHistory.map((entry, index) => (
          <div key={index} className="ip-history-entry">
            <span className="ip-address">{entry.ip}</span>
            <span className="ip-seen-date">{formatDateTime(entry.seen_at)}</span>
            {entry.current && <span className="ip-current-badge">Current</span>}
          </div>
        ))}
      </div>
    );
  };

  const renderDeviceCard = (device) => {
    const isExpanded = expandedDeviceId === device.device_id;
    const statusClass = device.status === 'online' ? 'status-online' : 'status-offline';

    return (
      <div key={device.device_id} className="search-result-card">
        <div className="card-header" onClick={() => toggleDeviceExpanded(device.device_id)}>
          <div className="card-header-left">
            <div className={`status-indicator ${statusClass}`}></div>
            <div className="device-info">
              <h4 className="device-name">
                {device.friendly_name || device.mac_address}
              </h4>
              <p className="device-mac">{device.mac_address}</p>
            </div>
          </div>
          <div className="card-header-right">
            <span className={`status-badge ${statusClass}`}>
              {device.status?.toUpperCase() || 'UNKNOWN'}
            </span>
            <span className="expand-icon">{isExpanded ? '−' : '+'}</span>
          </div>
        </div>

        {isExpanded && (
          <div className="card-details">
            <div className="detail-section">
              <h5>Network Information</h5>
              <div className="detail-row">
                <span className="detail-label">Current IP:</span>
                <span className="detail-value">{device.current_ip || 'Not assigned'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">MAC Address:</span>
                <span className="detail-value device-mono">{device.mac_address}</span>
              </div>
            </div>

            {device.vendor_name && (
              <div className="detail-section">
                <h5>Vendor</h5>
                <div className="detail-row">
                  <span className="detail-label">Vendor Name:</span>
                  <span className="detail-value">{device.vendor_name}</span>
                </div>
              </div>
            )}

            <div className="detail-section">
              <h5>IP History</h5>
              {renderIPHistory(device.ip_history)}
            </div>

            <div className="detail-section">
              <h5>Activity</h5>
              <div className="detail-row">
                <span className="detail-label">First Seen:</span>
                <span className="detail-value">{formatDateTime(device.first_seen)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Last Seen:</span>
                <span className="detail-value">{formatDateTime(device.last_seen)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Device Type:</span>
                <span className="detail-value">{device.device_type || 'Unknown'}</span>
              </div>
            </div>

            {device.notes && (
              <div className="detail-section">
                <h5>Notes</h5>
                <p className="device-notes">{device.notes}</p>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="device-search-container">
      <div className="search-box">
        <div className="search-input-group">
          <input
            type="text"
            placeholder="Search by MAC, IP, hostname, friendly name, or vendor..."
            value={query}
            onChange={handleQueryChange}
            className="search-input"
          />
          {query && (
            <button className="clear-button" onClick={handleClearSearch} title="Clear search" aria-label="Clear search">
              ✕
            </button>
          )}
        </div>

        <div className="search-filters">
          <select
            value={statusFilter}
            onChange={handleStatusFilterChange}
            className="status-filter"
          >
            <option value="">All Status</option>
            <option value="online">Online</option>
            <option value="offline">Offline</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="search-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {loading && query && (
        <div className="search-loading">
          <span className="spinner"></span>
          Searching...
        </div>
      )}

      {showResults && !loading && (
        <div className="search-results">
          {results.length > 0 ? (
            <>
              <div className="results-header">
                Found <strong>{results.length}</strong> device{results.length !== 1 ? 's' : ''}
              </div>
              <div className="results-list">
                {results.map((device) => renderDeviceCard(device))}
              </div>
            </>
          ) : (
            <div className="no-results">
              No devices found matching "{query}"
            </div>
          )}
        </div>
      )}

    </div>
  );
};

export default DeviceSearch;
