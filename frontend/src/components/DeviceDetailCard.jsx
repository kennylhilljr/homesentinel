import React, { useState, useEffect, useRef, useCallback } from 'react';
import './DeviceDetailCard.css';
import { buildUrl } from '../utils/apiConfig';

/**
 * DeviceDetailCard Component
 * Modal/panel showing all device details with inline editing capability
 * Displays: ID, MAC, IP history, hostname, vendor, friendly name, device type, groups, status, timestamps, notes
 */
function DeviceDetailCard({ device, groups, onClose, onUpdate }) {
  const [editField, setEditField] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState({
    friendly_name: device?.friendly_name || '',
    device_type: device?.device_type || '',
    notes: device?.notes || '',
  });
  // 2026-03-12: Presence timeline heatmap state
  const [presenceHistory, setPresenceHistory] = useState(null);

  useEffect(() => {
    setFormData({
      friendly_name: device?.friendly_name || '',
      device_type: device?.device_type || '',
      notes: device?.notes || '',
    });
  }, [device]);

  // 2026-03-12: Fetch presence history on mount
  useEffect(() => {
    if (!device?.device_id) return;
    const fetchPresence = async () => {
      try {
        const response = await fetch(buildUrl(`/devices/${device.device_id}/presence-history?days=7`));
        if (response.ok) setPresenceHistory(await response.json());
      } catch (err) { /* silent */ }
    };
    fetchPresence();
  }, [device?.device_id]);

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const formatMacAddress = (mac) => {
    if (!mac) return 'N/A';
    return mac.toUpperCase();
  };

  const getGroupColor = (groupId) => {
    const group = groups.find(g => g.group_id === groupId);
    return group?.color || '#6b7280';
  };

  const getGroupName = (groupId) => {
    const group = groups.find(g => g.group_id === groupId);
    return group?.name || 'Unknown Group';
  };

  const handleFieldChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSaveField = async (field) => {
    setIsSaving(true);
    setError(null);

    try {
      const updateData = {};
      updateData[field] = formData[field];

      const response = await fetch(
        buildUrl(`/devices/${device.device_id}`),
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(updateData),
        }
      );

      if (response.ok) {
        const updatedDevice = await response.json();
        if (onUpdate) {
          onUpdate(updatedDevice);
        }
        setEditField(null);
      } else {
        throw new Error('Failed to update device');
      }
    } catch (err) {
      console.error('Error saving device field:', err);
      setError('Failed to save changes. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      friendly_name: device?.friendly_name || '',
      device_type: device?.device_type || '',
      notes: device?.notes || '',
    });
    setEditField(null);
    setError(null);
  };

  // 2026-03-12: Focus trap — keep Tab inside the modal
  const containerRef = useRef(null);
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key !== 'Tab') return;
    const focusable = containerRef.current?.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable || focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus(); }
    } else {
      if (document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }, [onClose]);

  useEffect(() => {
    // Focus the close button on mount
    const closeBtn = containerRef.current?.querySelector('.detail-card-close');
    if (closeBtn) closeBtn.focus();
  }, []);

  if (!device) {
    return null;
  }

  return (
    <div className="detail-card-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label={`Device details: ${device.friendly_name || device.mac_address}`} onKeyDown={handleKeyDown}>
      <div className="detail-card-container" ref={containerRef} onClick={(e) => e.stopPropagation()}>
        {/* Close Button */}
        <button
          className="detail-card-close"
          onClick={onClose}
          aria-label="Close device details"
          title="Close (Esc)"
        >
          ×
        </button>

        {/* Header */}
        <div className="detail-card-header">
          <div className="detail-card-title-section">
            <h2 className="detail-card-title">Device Details</h2>
            <p className="detail-card-subtitle">
              {device.friendly_name || 'Unnamed Device'}
            </p>
          </div>
          <div className="detail-card-header-actions">
            <button
              className="detail-advanced-toggle"
              onClick={() => setShowAdvanced(!showAdvanced)}
              title="Show less-used diagnostic fields"
            >
              {showAdvanced ? 'Hide Advanced' : 'Show Advanced'}
            </button>
            <div className={`detail-card-status status-${device.status}`}>
              <span className={`status-indicator status-${device.status}`} aria-hidden="true"></span>
              <span className="status-text">
                {device.status === 'online' ? 'Online' : 'Offline'}
              </span>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="detail-card-error">
            <p>{error}</p>
          </div>
        )}

        {/* Main Content */}
        <div className="detail-card-content">
          {/* Core Device Information */}
          <section className="detail-section">
            <h3 className="detail-section-title">Core Information</h3>

            {/* MAC Address */}
            <div className="detail-field">
              <label className="detail-label">MAC Address</label>
              <div className="detail-value monospace">{formatMacAddress(device.mac_address)}</div>
            </div>

            {/* Current IP */}
            <div className="detail-field">
              <label className="detail-label">Current IP Address</label>
              <div className="detail-value monospace">{device.current_ip || 'N/A'}</div>
            </div>
          </section>

          {/* Device Classification */}
          <section className="detail-section">
            <h3 className="detail-section-title">Classification</h3>

            {/* Vendor Name */}
            {device.vendor_name && (
              <div className="detail-field">
                <label className="detail-label">Vendor Name</label>
                <div className="detail-value badge vendor-badge">
                  {device.vendor_name}
                </div>
              </div>
            )}

            {/* Friendly Name - Editable */}
            <div className="detail-field">
              <label className="detail-label">Friendly Name</label>
              {editField === 'friendly_name' ? (
                <div className="detail-edit-field">
                  <input
                    type="text"
                    value={formData.friendly_name}
                    onChange={(e) => handleFieldChange('friendly_name', e.target.value)}
                    placeholder="Enter friendly name"
                    autoFocus
                  />
                  <div className="detail-edit-buttons">
                    <button
                      className="btn-save-small"
                      onClick={() => handleSaveField('friendly_name')}
                      disabled={isSaving}
                    >
                      {isSaving ? 'Saving...' : 'Save'}
                    </button>
                    <button
                      className="btn-cancel-small"
                      onClick={handleCancel}
                      disabled={isSaving}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="detail-value-with-action">
                  <span className="detail-value">
                    {formData.friendly_name || 'Not set'}
                  </span>
                  <button
                    className="detail-edit-btn"
                    onClick={() => setEditField('friendly_name')}
                    title="Edit friendly name"
                  >
                    Edit
                  </button>
                </div>
              )}
            </div>

            {/* Device Type - Editable */}
            <div className="detail-field">
              <label className="detail-label">Device Type</label>
              {editField === 'device_type' ? (
                <div className="detail-edit-field">
                  <select
                    value={formData.device_type}
                    onChange={(e) => handleFieldChange('device_type', e.target.value)}
                    autoFocus
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
                  <div className="detail-edit-buttons">
                    <button
                      className="btn-save-small"
                      onClick={() => handleSaveField('device_type')}
                      disabled={isSaving}
                    >
                      {isSaving ? 'Saving...' : 'Save'}
                    </button>
                    <button
                      className="btn-cancel-small"
                      onClick={handleCancel}
                      disabled={isSaving}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="detail-value-with-action">
                  <span className="detail-value badge type-badge">
                    {formData.device_type || 'Not set'}
                  </span>
                  <button
                    className="detail-edit-btn"
                    onClick={() => setEditField('device_type')}
                    title="Edit device type"
                  >
                    Edit
                  </button>
                </div>
              )}
            </div>
          </section>

          {/* Groups */}
          {showAdvanced && device.device_group_ids && device.device_group_ids.length > 0 && (
            <section className="detail-section">
              <h3 className="detail-section-title">Groups</h3>
              <div className="detail-field">
                <div className="group-list">
                  {device.device_group_ids.map((groupId) => (
                    <div key={groupId} className="group-item-detail">
                      <span
                        className="group-color"
                        style={{ backgroundColor: getGroupColor(groupId) }}
                      ></span>
                      <span className="group-name">{getGroupName(groupId)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* Status & Timestamps */}
          <section className="detail-section">
            <h3 className="detail-section-title">Activity</h3>

            <div className="detail-field">
              <label className="detail-label">Status</label>
              <div className={`detail-value status-badge status-${device.status}`}>
                {device.status === 'online' ? 'Online' : 'Offline'}
              </div>
            </div>

            <div className="detail-field">
              <label className="detail-label">Last Seen</label>
              <div className="detail-value timestamp">{formatDate(device.last_seen)}</div>
            </div>

            {/* 2026-03-12: 7-day presence heatmap */}
            {presenceHistory && presenceHistory.history && (
              <div className="detail-field">
                <label className="detail-label">Presence History (7 days)</label>
                <div className="presence-grid">
                  <div className="presence-hours">
                    {[0, 6, 12, 18].map(h => (
                      <span key={h} className="presence-hour-label">{h}h</span>
                    ))}
                  </div>
                  {presenceHistory.history.map((day) => (
                    <div key={day.date} className="presence-day">
                      <span className="presence-day-label">{day.day_label}</span>
                      <div className="presence-cells">
                        {day.hourly.map((online, h) => (
                          <div
                            key={h}
                            className={`presence-cell ${online ? 'online' : day.event_count > 0 ? 'offline' : 'unknown'}`}
                            title={`${day.day_label} ${h}:00 — ${online ? 'Online' : 'Offline'}`}
                          />
                        ))}
                      </div>
                      <span className="presence-minutes">{day.online_minutes > 0 ? `${Math.round(day.online_minutes / 60)}h` : ''}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>

          {showAdvanced && (
            <section className="detail-section">
              <h3 className="detail-section-title">Advanced</h3>

              <div className="detail-field">
                <label className="detail-label">Device ID (UUID)</label>
                <div className="detail-value monospace">{device.device_id}</div>
              </div>

              {device.hostname && (
                <div className="detail-field">
                  <label className="detail-label">Hostname</label>
                  <div className="detail-value">{device.hostname}</div>
                </div>
              )}

              <div className="detail-field">
                <label className="detail-label">First Seen</label>
                <div className="detail-value timestamp">{formatDate(device.first_seen)}</div>
              </div>

              {device.last_ip_change && (
                <div className="detail-field">
                  <label className="detail-label">Last IP Change</label>
                  <div className="detail-value timestamp">{formatDate(device.last_ip_change)}</div>
                </div>
              )}

              {device.ip_history && device.ip_history.length > 0 && (
                <div className="detail-field">
                  <label className="detail-label">IP History</label>
                  <div className="ip-history-list">
                    {device.ip_history.map((ip, idx) => (
                      <div key={idx} className="ip-history-item">
                        <span className="ip-value monospace">{ip}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          {/* Notes - Editable */}
          <section className="detail-section">
            <h3 className="detail-section-title">Notes</h3>
            {editField === 'notes' ? (
              <div className="detail-edit-field">
                <textarea
                  value={formData.notes}
                  onChange={(e) => handleFieldChange('notes', e.target.value)}
                  placeholder="Add notes about this device..."
                  rows="4"
                  autoFocus
                />
                <div className="detail-edit-buttons">
                  <button
                    className="btn-save-small"
                    onClick={() => handleSaveField('notes')}
                    disabled={isSaving}
                  >
                    {isSaving ? 'Saving...' : 'Save'}
                  </button>
                  <button
                    className="btn-cancel-small"
                    onClick={handleCancel}
                    disabled={isSaving}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="detail-field">
                <div className="detail-value-with-action">
                  <div className="notes-display">
                    {formData.notes || 'No notes'}
                  </div>
                  <button
                    className="detail-edit-btn"
                    onClick={() => setEditField('notes')}
                    title="Edit notes"
                  >
                    Edit
                  </button>
                </div>
              </div>
            )}
          </section>
        </div>

        {/* Footer Actions */}
        <div className="detail-card-footer">
          <button className="btn-close" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default DeviceDetailCard;
