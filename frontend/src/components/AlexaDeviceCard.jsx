import React, { useState } from 'react';
import { buildUrl } from '../utils/apiConfig';
import './AlexaDeviceCard.css';

const DEVICE_ICONS = {
  light: '\u{1F4A1}',
  plug: '\u{1F50C}',
  thermostat: '\u{1F321}\uFE0F',
  lock: '\u{1F512}',
  camera: '\u{1F4F7}',
  echo: '\u{1F4E2}',
  tv: '\u{1F4FA}',
  washer: '\u{1F9FA}',
  dryer: '\u{1F32C}\uFE0F',
  climate: '\u{2744}\uFE0F',
  security: '\u{1F6E1}\uFE0F',
  sensor: '\u{1F4E1}',
  fan: '\u{1F32C}\uFE0F',
  scene: '\u{1F3AC}',
  hub: '\u{1F310}',
  other: '\u{1F4F1}',
};

function AlexaDeviceCard({ device, onStateChange }) {
  const [sending, setSending] = useState(false);
  const [brightness, setBrightness] = useState(device.parsed_state?.brightness || 100);
  const [targetTemp, setTargetTemp] = useState(
    device.parsed_state?.target_temperature?.value || 72
  );
  const [showUnlockPin, setShowUnlockPin] = useState(false);
  const [pin, setPin] = useState('');

  const icon = DEVICE_ICONS[device.device_type] || DEVICE_ICONS.other;
  const power = device.parsed_state?.power;
  const isOn = power === 'ON';
  const lockState = device.parsed_state?.lock_state;

  // Support both old (Alexa.PowerController) and new (turnOn/turnOff) capability formats
  const caps = device.capabilities || [];
  const hasPower = caps.includes('Alexa.PowerController') || caps.includes('turnOn') || caps.includes('turnOff');
  const hasBrightness = caps.includes('Alexa.BrightnessController') || caps.includes('setBrightness');
  const hasThermostat = caps.includes('Alexa.ThermostatController') || caps.includes('setTargetTemperature');
  const hasLock = caps.includes('Alexa.LockController') || caps.includes('lockAction');

  const sendCommand = async (command, params = null, pinValue = null) => {
    setSending(true);
    try {
      const body = { command, params };
      if (pinValue) body.pin = pinValue;

      const response = await fetch(
        buildUrl(`/alexa/devices/${device.endpoint_id}/command`),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      );
      if (response.ok && onStateChange) {
        onStateChange(device.endpoint_id);
      }
    } catch (err) {
      console.error('Command failed:', err);
    } finally {
      setSending(false);
    }
  };

  const handleBrightnessChange = (e) => {
    const val = parseInt(e.target.value);
    setBrightness(val);
  };

  const handleBrightnessCommit = () => {
    sendCommand('set_brightness', { brightness });
  };

  const handleUnlock = () => {
    if (!pin) return;
    sendCommand('unlock', null, pin);
    setShowUnlockPin(false);
    setPin('');
  };

  return (
    <div className={`alexa-device-card ${device.is_stale ? 'stale' : ''}`}>
      {device.is_stale && <span className="stale-indicator">Stale</span>}

      <div className="device-card-header">
        <div>
          <p className="device-name">
            <span className="device-icon">{icon}</span>
            {device.friendly_name}
          </p>
          <p className="device-manufacturer">
            {device.description || device.manufacturer || ''} {device.model && device.model !== device.description ? `\u2022 ${device.model}` : ''}
          </p>
        </div>
        <span className="device-type-badge">{device.device_type}</span>
      </div>

      {/* Power state */}
      {power && (
        <div className="power-state">
          <span className={`power-dot ${isOn ? 'on' : 'off'}`}></span>
          <span className="power-label">{isOn ? 'On' : 'Off'}</span>
        </div>
      )}

      {/* Controls */}
      <div className="device-controls">
        {/* Power toggle for devices with PowerController */}
        {hasPower && (
          <div className="power-toggle">
            <button
              className="on-btn"
              onClick={() => sendCommand('power_on')}
              disabled={sending || isOn}
            >
              Turn On
            </button>
            <button
              className="off-btn"
              onClick={() => sendCommand('power_off')}
              disabled={sending || !isOn}
            >
              Turn Off
            </button>
          </div>
        )}

        {/* Brightness slider */}
        {hasBrightness && (
          <div className="brightness-control">
            <label>Brightness: {brightness}%</label>
            <input
              type="range"
              min="0"
              max="100"
              value={brightness}
              onChange={handleBrightnessChange}
              onMouseUp={handleBrightnessCommit}
              onTouchEnd={handleBrightnessCommit}
            />
          </div>
        )}

        {/* Color swatch */}
        {device.parsed_state?.color && (
          <div>
            <span style={{ fontSize: '0.8rem', color: '#666' }}>Color: </span>
            <span
              className="color-swatch"
              style={{
                background: `hsl(${device.parsed_state.color.hue || 0}, ${(device.parsed_state.color.saturation || 0) * 100}%, ${(device.parsed_state.color.brightness || 0.5) * 50}%)`,
              }}
            ></span>
          </div>
        )}

        {/* Thermostat */}
        {hasThermostat && (
          <div className="thermostat-control">
            <div className="thermostat-display">
              <div>
                <span style={{ fontSize: '0.8rem', color: '#666' }}>Current</span>
                <div className="thermostat-current">
                  {device.parsed_state?.temperature?.value || '--'}&deg;
                </div>
              </div>
              <span className="thermostat-mode">
                {device.parsed_state?.thermostat_mode || 'AUTO'}
              </span>
            </div>
            <div className="thermostat-target">
              <label style={{ fontSize: '0.8rem' }}>Target:</label>
              <input
                type="number"
                value={targetTemp}
                onChange={(e) => setTargetTemp(parseInt(e.target.value))}
                min="50"
                max="90"
              />
              <button onClick={() => sendCommand('set_thermostat', { temperature: targetTemp })} disabled={sending}>
                Set
              </button>
            </div>
          </div>
        )}

        {/* Lock */}
        {hasLock && (
          <div className="lock-control">
            <div className="lock-status">
              <span className="lock-icon">{lockState === 'LOCKED' ? '\u{1F512}' : '\u{1F513}'}</span>
              <span>{lockState === 'LOCKED' ? 'Locked' : 'Unlocked'}</span>
            </div>
            <div className="lock-buttons">
              <button
                onClick={() => sendCommand('lock')}
                disabled={sending || lockState === 'LOCKED'}
              >
                Lock
              </button>
              <button
                onClick={() => setShowUnlockPin(true)}
                disabled={sending || lockState === 'UNLOCKED'}
              >
                Unlock
              </button>
            </div>
            {showUnlockPin && (
              <div className="pin-input">
                <input
                  type="password"
                  placeholder="Enter PIN"
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  maxLength={6}
                />
                <button onClick={handleUnlock} disabled={!pin}>
                  Confirm
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default AlexaDeviceCard;
