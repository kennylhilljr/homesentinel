import React from 'react';
import './DeviceCard.css';

/**
 * DeviceCard Component
 * Displays a compact device card showing key information with click to expand
 * References TaskCard styling patterns for dark theme and badge layout
 */
function DeviceCard({ device, groups, isNew, onClick }) {
  const getGroupColor = (groupId) => {
    const group = groups.find(g => g.group_id === groupId);
    return group?.color || '#6b7280';
  };

  const getStatusIndicator = () => {
    return device.status === 'online' ? 'online' : 'offline';
  };

  const getStatusLabel = () => {
    return device.status === 'online' ? 'Online' : 'Offline';
  };

  return (
    <div
      className={`device-card device-card-${getStatusIndicator()}${isNew ? ' device-card-new' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          onClick();
        }
      }}
      aria-label={`Device ${device.friendly_name || device.mac_address}`}
    >
      <div className="device-card-header">
        <div className="device-card-title">
          <div className={`status-indicator status-${getStatusIndicator()}`} aria-hidden="true" />
              <span className="sr-only">{getStatusLabel()}</span>
          <span className="device-name-card">
            {device.friendly_name || device.mac_address}
          </span>
          {/* 2026-03-12: NEW badge in grid view for devices first seen in last 24h */}
          {isNew && <span className="device-new-badge">NEW</span>}
        </div>
        <span className="status-badge-card">{getStatusLabel()}</span>
      </div>

      <div className="device-card-body">
        <div className="device-card-row">
          <span className="device-card-label">IP:</span>
          <span className="device-card-value monospace">{device.current_ip || 'N/A'}</span>
        </div>

        <div className="device-card-row">
          <span className="device-card-label">MAC:</span>
          <span className="device-card-value monospace mac-truncate">{device.mac_address}</span>
        </div>

        {device.vendor_name && (
          <div className="device-card-row">
            <span className="device-card-label">Vendor:</span>
            <span className="device-card-badge vendor-badge">{device.vendor_name}</span>
          </div>
        )}

        {device.device_type && (
          <div className="device-card-row">
            <span className="device-card-label">Type:</span>
            <span className="device-card-badge type-badge">{device.device_type}</span>
          </div>
        )}

        {device.device_group_ids && device.device_group_ids.length > 0 && (
          <div className="device-card-row">
            <span className="device-card-label">Groups:</span>
            <div className="device-card-groups">
              {device.device_group_ids.map((groupId) => (
                <span
                  key={groupId}
                  className="group-badge"
                  style={{ backgroundColor: getGroupColor(groupId) }}
                  title={groups.find(g => g.group_id === groupId)?.name || groupId}
                >
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="device-card-footer">
        <span className="device-card-small">Click to view details</span>
      </div>
    </div>
  );
}

export default DeviceCard;
