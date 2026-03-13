import React, { useState, useEffect } from 'react';
import './DeviceAlert.css';

/**
 * DeviceAlert Component
 * Displays alert notifications for new devices and status changes
 * Shows in a fixed notification area with dismiss capability
 */
function DeviceAlert({ alert, onDismiss, device = null }) {
  const [isVisible, setIsVisible] = useState(true);
  const [isDismissing, setIsDismissing] = useState(false);

  // Auto-dismiss new device alerts after 10 seconds
  useEffect(() => {
    if (alert.alert_type === 'new_device' && isVisible) {
      const timer = setTimeout(() => {
        setIsVisible(false);
      }, 10000);
      return () => clearTimeout(timer);
    }
  }, [alert.alert_type, isVisible]);

  const handleDismiss = async () => {
    setIsDismissing(true);
    try {
      const response = await fetch(`/api/events/alerts/${alert.alert_id}/dismiss`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to dismiss alert: ${response.status}`);
      }

      setIsVisible(false);
      if (onDismiss) {
        onDismiss(alert.alert_id);
      }
    } catch (error) {
      console.error('Error dismissing alert:', error);
      setIsDismissing(false);
    }
  };

  if (!isVisible) {
    return null;
  }

  const getAlertIcon = () => {
    const icons = {
      'new_device': '🔔',
      'device_reconnected': '✅',
      'device_offline': '⚠️'
    };
    return icons[alert.alert_type] || '📢';
  };

  const getAlertMessage = () => {
    const deviceName = device?.friendly_name || device?.mac_address || 'Unknown Device';

    const messages = {
      'new_device': `New device detected: ${deviceName}`,
      'device_reconnected': `Device reconnected: ${deviceName}`,
      'device_offline': `Device went offline: ${deviceName}`
    };
    return messages[alert.alert_type] || 'Device alert';
  };

  const getAlertColor = () => {
    const colors = {
      'new_device': 'alert-success',
      'device_reconnected': 'alert-info',
      'device_offline': 'alert-warning'
    };
    return colors[alert.alert_type] || 'alert-default';
  };

  return (
    <div className={`device-alert ${getAlertColor()} ${isDismissing ? 'dismissing' : ''}`}>
      <div className="alert-icon">{getAlertIcon()}</div>
      <div className="alert-content">
        <div className="alert-message">{getAlertMessage()}</div>
        {device?.vendor_name && (
          <div className="alert-details">Vendor: {device.vendor_name}</div>
        )}
        {device?.current_ip && (
          <div className="alert-details">IP: {device.current_ip}</div>
        )}
      </div>
      <button
        className="alert-close"
        onClick={handleDismiss}
        aria-label="Dismiss alert"
        disabled={isDismissing}
      >
        ✕
      </button>
    </div>
  );
}

/**
 * AlertContainer Component
 * Container for displaying multiple alerts
 */
export function AlertContainer({ alerts = [], onDismiss, devices = [] }) {
  return (
    <div className="alert-container">
      {alerts.map((alert) => {
        const device = devices.find(d => d.device_id === alert.device_id);
        return (
          <DeviceAlert
            key={alert.alert_id}
            alert={alert}
            onDismiss={onDismiss}
            device={device}
          />
        );
      })}
    </div>
  );
}

export default DeviceAlert;
