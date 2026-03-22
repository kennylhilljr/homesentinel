import React, { useState, useEffect } from 'react';
import { buildUrl } from '../utils/apiConfig';
import './SettingsPage.css';

function SettingsPage({ theme = 'blue-steel', onThemeChange = () => {} }) {
  const [decoMode, setDecoMode] = useState('cloud');
  const [decoUsername, setDecoUsername] = useState('');
  const [decoPassword, setDecoPassword] = useState('');
  const [localEndpoint, setLocalEndpoint] = useState('http://192.168.12.1:8080');
  const [decoStatus, setDecoStatus] = useState(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  // Alexa settings
  const [alexaClientId, setAlexaClientId] = useState('');
  const [alexaClientSecret, setAlexaClientSecret] = useState('');
  const [alexaAllowedOrigin, setAlexaAllowedOrigin] = useState('https://charissa-nonrefractional-dwana.ngrok-free.dev');
  const [alexaReturnUrl, setAlexaReturnUrl] = useState('https://charissa-nonrefractional-dwana.ngrok-free.dev/api/alexa/auth/callback');
  const [alexaStatus, setAlexaStatus] = useState(null);
  const [alexaSaving, setAlexaSaving] = useState(false);
  const [alexaCookies, setAlexaCookies] = useState('');
  const [cookieSaving, setCookieSaving] = useState(false);
  const [cookieResult, setCookieResult] = useState(null);

  // HiBoost settings
  const [hiboostAccount, setHiboostAccount] = useState('');
  const [hiboostPassword, setHiboostPassword] = useState('');
  const [hiboostStatus, setHiboostStatus] = useState(null);
  const [hiboostSaving, setHiboostSaving] = useState(false);
  const [hiboostTesting, setHiboostTesting] = useState(false);
  const [hiboostResult, setHiboostResult] = useState(null);

  // Chester settings
  const [chesterHost, setChesterHost] = useState('192.168.12.1');
  const [chesterPort, setChesterPort] = useState(80);
  const [chesterUsername, setChesterUsername] = useState('admin');
  const [chesterPassword, setChesterPassword] = useState('');
  const [chesterHttps, setChesterHttps] = useState(false);
  const [chesterStatus, setChesterStatus] = useState(null);
  const [chesterSaving, setChesterSaving] = useState(false);
  const [chesterTesting, setChesterTesting] = useState(false);
  const [chesterResult, setChesterResult] = useState(null);

  useEffect(() => {
    fetchDecoStatus();
    fetchAlexaStatus();
    fetchChesterStatus();
    fetchHiboostStatus();
  }, []);

  const fetchDecoStatus = async () => {
    try {
      const response = await fetch(buildUrl('/settings/deco/status'));
      if (response.ok) {
        const data = await response.json();
        setDecoStatus(data);
        if (data.username) setDecoUsername(data.username);
        if (data.mode) setDecoMode(data.mode);
      }
    } catch (err) {
      console.error('Failed to fetch Deco status:', err);
    }
  };

  const fetchAlexaStatus = async () => {
    try {
      const response = await fetch(buildUrl('/alexa/status'));
      if (response.ok) {
        const data = await response.json();
        setAlexaStatus(data);
        if (data.oauth_config?.allowed_origin) {
          setAlexaAllowedOrigin(data.oauth_config.allowed_origin);
        }
        if (data.oauth_config?.redirect_uri) {
          setAlexaReturnUrl(data.oauth_config.redirect_uri);
        }
      }
    } catch (err) {
      console.error('Failed to fetch Alexa status:', err);
    }
  };

  const fetchChesterStatus = async () => {
    try {
      const response = await fetch(buildUrl('/settings/chester/status'));
      if (response.ok) {
        const data = await response.json();
        setChesterStatus(data);
        if (data.host) setChesterHost(data.host);
        if (data.username) setChesterUsername(data.username);
        if (data.use_https !== undefined) setChesterHttps(Boolean(data.use_https));
      }
    } catch (err) {
      console.error('Failed to fetch Chester status:', err);
    }
  };

  const saveDeco = async () => {
    setSaving(true);
    setTestResult(null);
    try {
      const response = await fetch(buildUrl('/settings/deco/credentials'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: decoUsername,
          password: decoPassword,
          mode: decoMode,
          local_endpoint: decoMode === 'local' ? localEndpoint : null,
        }),
      });
      if (response.ok) {
        await fetchDecoStatus();
        setTestResult({ success: true, message: 'Credentials saved successfully.' });
      } else {
        setTestResult({ success: false, message: 'Failed to save credentials.' });
      }
    } catch (err) {
      setTestResult({ success: false, message: `Error: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const testDeco = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const response = await fetch(buildUrl('/settings/deco/test'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: decoUsername,
          password: decoPassword,
          mode: decoMode,
          local_endpoint: decoMode === 'local' ? localEndpoint : null,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setTestResult(data);
      } else {
        setTestResult({ success: false, message: 'Test request failed.' });
      }
    } catch (err) {
      setTestResult({ success: false, message: `Connection error: ${err.message}` });
    } finally {
      setTesting(false);
    }
  };

  const saveAlexaCookies = async () => {
    setCookieSaving(true);
    setCookieResult(null);
    try {
      const response = await fetch(buildUrl('/alexa/cookies'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cookies: alexaCookies }),
      });
      const data = await response.json();
      setCookieResult(data);
      await fetchAlexaStatus();
    } catch (err) {
      setCookieResult({ success: false, message: `Error: ${err.message}` });
    } finally {
      setCookieSaving(false);
    }
  };

  const startAlexaOAuth = async () => {
    setAlexaSaving(true);
    try {
      const response = await fetch(buildUrl('/alexa/auth'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: alexaClientId,
          client_secret: alexaClientSecret,
          allowed_origin: alexaAllowedOrigin,
          redirect_uri: alexaReturnUrl,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        if (data.auth_url) {
          window.open(data.auth_url, '_blank', 'width=600,height=700');
        }
        await fetchAlexaStatus();
      }
    } catch (err) {
      console.error('Failed to start Alexa OAuth:', err);
    } finally {
      setAlexaSaving(false);
    }
  };

  const saveChester = async () => {
    setChesterSaving(true);
    setChesterResult(null);
    try {
      const response = await fetch(buildUrl('/settings/chester/credentials'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host: chesterHost,
          port: Number(chesterPort),
          username: chesterUsername,
          password: chesterPassword,
          use_https: chesterHttps,
          verify_ssl: false,
        }),
      });
      const data = await response.json();
      setChesterResult(data);
      await fetchChesterStatus();
    } catch (err) {
      setChesterResult({ success: false, message: `Error: ${err.message}` });
    } finally {
      setChesterSaving(false);
    }
  };

  const testChester = async () => {
    setChesterTesting(true);
    setChesterResult(null);
    try {
      const response = await fetch(buildUrl('/settings/chester/test'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host: chesterHost,
          port: Number(chesterPort),
          username: chesterUsername,
          password: chesterPassword,
          use_https: chesterHttps,
          verify_ssl: false,
        }),
      });
      const data = await response.json();
      setChesterResult(data);
    } catch (err) {
      setChesterResult({ success: false, message: `Error: ${err.message}` });
    } finally {
      setChesterTesting(false);
    }
  };

  const fetchHiboostStatus = async () => {
    try {
      const response = await fetch(buildUrl('/settings/hiboost/status'));
      if (response.ok) {
        const data = await response.json();
        setHiboostStatus(data);
        if (data.account) setHiboostAccount(data.account);
      }
    } catch (err) {
      console.error('Failed to fetch HiBoost status:', err);
    }
  };

  const saveHiboost = async () => {
    setHiboostSaving(true);
    setHiboostResult(null);
    try {
      const response = await fetch(buildUrl('/settings/hiboost/credentials'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account: hiboostAccount, password: hiboostPassword }),
      });
      const data = await response.json();
      setHiboostResult(data);
      await fetchHiboostStatus();
    } catch (err) {
      setHiboostResult({ success: false, message: `Error: ${err.message}` });
    } finally {
      setHiboostSaving(false);
    }
  };

  const testHiboost = async () => {
    setHiboostTesting(true);
    setHiboostResult(null);
    try {
      const response = await fetch(buildUrl('/settings/hiboost/test'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account: hiboostAccount, password: hiboostPassword }),
      });
      const data = await response.json();
      setHiboostResult(data);
    } catch (err) {
      setHiboostResult({ success: false, message: `Error: ${err.message}` });
    } finally {
      setHiboostTesting(false);
    }
  };

  return (
    <div className="settings-page">
      <h1>Settings</h1>
      <p>Configure integrations and credentials</p>

      <div className="settings-section">
        <h2>Interface Theme</h2>
        <p className="section-description">Choose a professional color system for the dashboard.</p>
        <div className="theme-picker">
          <button
            type="button"
            className={`theme-option ${theme === 'blue-steel' ? 'active' : ''}`}
            onClick={() => onThemeChange('blue-steel')}
          >
            <span className="theme-name">Blue Steel</span>
            <span className="theme-note">Clean blue enterprise palette</span>
            <span className="theme-preview theme-preview-blue-steel" aria-hidden="true" />
          </button>
          <button
            type="button"
            className={`theme-option ${theme === 'deep-slate' ? 'active' : ''}`}
            onClick={() => onThemeChange('deep-slate')}
          >
            <span className="theme-name">Deep Slate</span>
            <span className="theme-note">Muted slate-blue operations palette</span>
            <span className="theme-preview theme-preview-deep-slate" aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* Deco Settings */}
      <div className="settings-section">
        <h2>TP-Link Deco</h2>
        <p className="section-description">Connect to your Deco mesh network via cloud or local API</p>

        {decoStatus && (
          <div className={`status-banner ${decoStatus.authenticated ? 'connected' : decoStatus.configured ? 'disconnected' : 'disconnected'}`}>
            <span className={`status-dot ${decoStatus.authenticated ? 'green' : decoStatus.configured ? 'yellow' : 'red'}`} aria-hidden="true"></span>
            {decoStatus.authenticated
              ? `Connected (${decoStatus.mode} API)`
              : decoStatus.configured
              ? 'Credentials saved but not authenticated'
              : 'Not configured'}
          </div>
        )}

        <div className="mode-toggle">
          <button
            className={`mode-btn ${decoMode === 'cloud' ? 'active' : ''}`}
            onClick={() => setDecoMode('cloud')}
            type="button"
          >
            <h3>Cloud API</h3>
            <p>wap.tplinkcloud.com</p>
          </button>
          <button
            className={`mode-btn ${decoMode === 'local' ? 'active' : ''}`}
            onClick={() => setDecoMode('local')}
            type="button"
          >
            <h3>Local LAN</h3>
            <p>Direct router connection</p>
          </button>
        </div>

        <div className="form-group">
          <label htmlFor="deco-username">
            {decoMode === 'cloud' ? 'TP-Link Account Email' : 'Router Username'}
          </label>
          <input
            id="deco-username"
            type="text"
            value={decoUsername}
            onChange={(e) => setDecoUsername(e.target.value)}
            placeholder={decoMode === 'cloud' ? 'your@email.com' : 'admin'}
          />
        </div>

        <div className="form-group">
          <label htmlFor="deco-password">Password</label>
          <input
            id="deco-password"
            type="password"
            value={decoPassword}
            onChange={(e) => setDecoPassword(e.target.value)}
            placeholder="Enter password"
          />
        </div>

        {decoMode === 'local' && (
          <div className="form-group">
            <label htmlFor="local-endpoint">Local Endpoint URL</label>
            <input
              id="local-endpoint"
              type="text"
              value={localEndpoint}
              onChange={(e) => setLocalEndpoint(e.target.value)}
              placeholder="http://192.168.0.1:8080"
            />
          </div>
        )}

        {testResult && (
          <div className={`test-result ${testResult.success ? 'success' : 'failure'}`}>
            {testResult.success ? '\u2713' : '\u2717'} {testResult.message}
          </div>
        )}

        <div className="btn-row">
          <button className="btn btn-primary" onClick={saveDeco} disabled={saving || !decoUsername || !decoPassword}>
            {saving ? 'Saving...' : 'Save Credentials'}
          </button>
          <button className="btn btn-secondary" onClick={testDeco} disabled={testing || !decoUsername || !decoPassword}>
            {testing ? 'Testing...' : 'Test Connection'}
          </button>
        </div>
      </div>

      {/* Alexa Settings */}
      <div className="settings-section">
        <h2>Amazon Alexa</h2>
        <p className="section-description">Connect to Alexa Smart Home for device inventory and control</p>

        {alexaStatus && (
          <div className={`status-banner ${alexaStatus.authenticated ? 'connected' : 'disconnected'}`}>
            <span className={`status-dot ${alexaStatus.authenticated ? 'green' : 'red'}`} aria-hidden="true"></span>
            {alexaStatus.authenticated
              ? 'Connected to Alexa'
              : alexaStatus.configured
              ? 'OAuth configured but not authenticated'
              : 'Not configured'}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="alexa-client-id">LWA Client ID</label>
          <input
            id="alexa-client-id"
            type="text"
            value={alexaClientId}
            onChange={(e) => setAlexaClientId(e.target.value)}
            placeholder="amzn1.application-oa2-client.xxxx"
          />
        </div>

        <div className="form-group">
          <label htmlFor="alexa-client-secret">LWA Client Secret</label>
          <input
            id="alexa-client-secret"
            type="password"
            value={alexaClientSecret}
            onChange={(e) => setAlexaClientSecret(e.target.value)}
            placeholder="Enter client secret"
          />
        </div>

        <div className="alexa-web-settings">
          <h3>Amazon Security Profile - Web Settings</h3>
          <p className="section-description">
            Add these values under Security Profile - Web Settings in Amazon Developer Console.
          </p>

          <div className="form-group">
            <label htmlFor="alexa-allowed-origin">Allowed JavaScript Origin</label>
            <input
              id="alexa-allowed-origin"
              type="text"
              value={alexaAllowedOrigin}
              onChange={(e) => setAlexaAllowedOrigin(e.target.value)}
              placeholder="https://localhost:8443"
            />
          </div>

          <div className="form-group">
            <label htmlFor="alexa-return-url">Allowed Return URL</label>
            <input
              id="alexa-return-url"
              type="text"
              value={alexaReturnUrl}
              onChange={(e) => setAlexaReturnUrl(e.target.value)}
              placeholder="https://localhost:8443/api/alexa/auth/callback"
            />
          </div>
        </div>

        <div className="btn-row">
          <button
            className="btn btn-primary"
            onClick={startAlexaOAuth}
            disabled={alexaSaving || !alexaClientId || !alexaClientSecret || !alexaAllowedOrigin || !alexaReturnUrl}
          >
            {alexaSaving ? 'Connecting...' : 'Connect Alexa Account'}
          </button>
        </div>

        <hr style={{ margin: '1.5rem 0', borderColor: '#333' }} />

        <h3 style={{ marginBottom: '0.5rem' }}>Browser Cookie Authentication</h3>
        <p className="section-description" style={{ marginBottom: '1rem' }}>
          Import your Alexa-connected devices (lights, plugs, sensors, Echo speakers) by pasting
          your browser cookies. This gives HomeSentinel read access to your full device inventory.
        </p>

        {alexaStatus?.cookies_set && (
          <div className="status-banner connected" style={{ marginBottom: '1rem' }}>
            <span className="status-dot green" aria-hidden="true"></span>
            Alexa cookies configured
          </div>
        )}

        {cookieResult && (
          <div className={`status-banner ${cookieResult.success ? 'connected' : 'disconnected'}`} style={{ marginBottom: '1rem' }}>
            <span className={`status-dot ${cookieResult.success ? 'green' : 'red'}`} aria-hidden="true"></span>
            {cookieResult.message || (cookieResult.success ? 'Cookies saved successfully' : 'Cookie auth failed')}
            {cookieResult.test_result?.customer_name && ` — ${cookieResult.test_result.customer_name}`}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="alexa-cookies">Cookie String</label>
          <textarea
            id="alexa-cookies"
            rows={4}
            value={alexaCookies}
            onChange={(e) => setAlexaCookies(e.target.value)}
            placeholder="Paste your alexa.amazon.com cookies here..."
            style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.8rem', resize: 'vertical' }}
          />
        </div>

        <details style={{ marginBottom: '1rem', color: 'var(--text-muted, #556277)', fontSize: '0.85rem' }}>
          <summary style={{ cursor: 'pointer', color: 'var(--text-muted, #556277)' }}>How to get your cookies</summary>
          <ol style={{ paddingLeft: '1.2rem', marginTop: '0.5rem', lineHeight: '1.6' }}>
            <li>Open <strong>alexa.amazon.com</strong> in your browser and log in</li>
            <li>Open DevTools (<strong>F12</strong> or <strong>Cmd+Option+I</strong>)</li>
            <li>Go to the <strong>Network</strong> tab</li>
            <li>Reload the page</li>
            <li>Click any request to <strong>alexa.amazon.com</strong></li>
            <li>In the request headers, find <strong>Cookie:</strong> and copy the entire value</li>
            <li>Paste it into the field above</li>
          </ol>
        </details>

        <div className="btn-row">
          <button
            className="btn btn-primary"
            onClick={saveAlexaCookies}
            disabled={cookieSaving || !alexaCookies.trim()}
          >
            {cookieSaving ? 'Saving...' : 'Save & Test Cookies'}
          </button>
        </div>
      </div>

      {/* HiBoost Settings */}
      <div className="settings-section">
        <h2>HiBoost Signal Booster</h2>
        <p className="section-description">
          Connect to your HiBoost signal booster via Signal Supervisor cloud API
        </p>

        {hiboostStatus && (
          <div className={`status-banner ${hiboostStatus.configured ? 'connected' : 'disconnected'}`}>
            <span className={`status-dot ${hiboostStatus.configured ? 'green' : 'red'}`} aria-hidden="true"></span>
            {hiboostStatus.authenticated
              ? 'Connected to Signal Supervisor'
              : hiboostStatus.configured
              ? 'Credentials saved'
              : 'Not configured'}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="hiboost-account">Account (Phone or Email)</label>
          <input
            id="hiboost-account"
            type="text"
            value={hiboostAccount}
            onChange={(e) => setHiboostAccount(e.target.value)}
            placeholder="Phone number or email"
          />
        </div>

        <div className="form-group">
          <label htmlFor="hiboost-password">Password</label>
          <input
            id="hiboost-password"
            type="password"
            value={hiboostPassword}
            onChange={(e) => setHiboostPassword(e.target.value)}
            placeholder="Enter password"
          />
        </div>

        {hiboostResult && (
          <div className={`test-result ${hiboostResult.success ? 'success' : 'failure'}`}>
            {hiboostResult.success ? '\u2713' : '\u2717'} {hiboostResult.message}
            {hiboostResult.device_count != null && ` (${hiboostResult.device_count} device${hiboostResult.device_count !== 1 ? 's' : ''})`}
          </div>
        )}

        <div className="btn-row">
          <button
            className="btn btn-primary"
            onClick={saveHiboost}
            disabled={hiboostSaving || !hiboostAccount || !hiboostPassword}
          >
            {hiboostSaving ? 'Saving...' : 'Save Credentials'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={testHiboost}
            disabled={hiboostTesting || !hiboostAccount || !hiboostPassword}
          >
            {hiboostTesting ? 'Testing...' : 'Test Connection'}
          </button>
        </div>
      </div>

      {/* Chester Settings */}
      <div className="settings-section">
        <h2>Chester Router (ImmortalWrt/OpenWrt)</h2>
        <p className="section-description">
          Connect to your Chester router using OpenWrt ubus/rpcd API
        </p>

        {chesterStatus && (
          <div className={`status-banner ${chesterStatus.authenticated ? 'connected' : 'disconnected'}`}>
            <span className={`status-dot ${chesterStatus.authenticated ? 'green' : 'red'}`} aria-hidden="true"></span>
            {chesterStatus.authenticated
              ? `Connected (${chesterStatus.endpoint})`
              : chesterStatus.configured
              ? 'Credentials saved but not authenticated'
              : 'Not configured'}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="chester-host">Router Host/IP</label>
          <input
            id="chester-host"
            type="text"
            value={chesterHost}
            onChange={(e) => setChesterHost(e.target.value)}
            placeholder="192.168.1.1"
          />
        </div>

        <div className="form-group">
          <label htmlFor="chester-port">Port</label>
          <input
            id="chester-port"
            type="number"
            value={chesterPort}
            onChange={(e) => setChesterPort(e.target.value)}
            placeholder="80"
          />
        </div>

        <div className="form-group">
          <label htmlFor="chester-username">Username</label>
          <input
            id="chester-username"
            type="text"
            value={chesterUsername}
            onChange={(e) => setChesterUsername(e.target.value)}
            placeholder="root"
          />
        </div>

        <div className="form-group">
          <label htmlFor="chester-password">Password</label>
          <input
            id="chester-password"
            type="password"
            value={chesterPassword}
            onChange={(e) => setChesterPassword(e.target.value)}
            placeholder="Router password"
          />
        </div>

        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={chesterHttps}
              onChange={(e) => setChesterHttps(e.target.checked)}
            />{' '}
            Use HTTPS
          </label>
        </div>

        {chesterResult && (
          <div className={`test-result ${chesterResult.success ? 'success' : 'failure'}`}>
            {chesterResult.success ? '\u2713' : '\u2717'} {chesterResult.message}
          </div>
        )}

        <div className="btn-row">
          <button
            className="btn btn-primary"
            onClick={saveChester}
            disabled={chesterSaving || !chesterHost || !chesterUsername || !chesterPassword}
          >
            {chesterSaving ? 'Saving...' : 'Save Chester Credentials'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={testChester}
            disabled={chesterTesting || !chesterHost || !chesterUsername || !chesterPassword}
          >
            {chesterTesting ? 'Testing...' : 'Test Chester Connection'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default SettingsPage;
