import React, { useCallback, useEffect, useMemo, useState } from 'react';
import './LocalServicesPage.css';

const EMPTY_SUMMARY = { total: 0, healthy: 0, degraded: 0, down: 0, unexpected: 0, conflicts: 0 };

const titleCase = (value) => String(value || 'unknown').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
const formatDuration = (seconds) => {
  if (!Number.isFinite(seconds)) return '—';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return days ? `${days}d ${hours}h` : hours ? `${hours}h ${minutes}m` : `${minutes}m`;
};
const formatTime = (value) => value ? new Date(value).toLocaleString() : '—';

function Sparkline({ points = [], label }) {
  const values = points.map((point) => Number(point.value)).filter(Number.isFinite);
  if (values.length < 2) return <span className="local-services-no-trend">No trend</span>;
  const min = Math.min(...values);
  const range = Math.max(Math.max(...values) - min, 1);
  const path = values.map((value, index) => `${index ? 'L' : 'M'} ${index * (100 / (values.length - 1))} ${26 - ((value - min) / range) * 22}`).join(' ');
  return <svg className="local-services-sparkline" viewBox="0 0 100 30" role="img" aria-label={label} preserveAspectRatio="none"><path d={path} /></svg>;
}

function LocalServicesPage() {
  const [data, setData] = useState({ services: [], summary: EMPTY_SUMMARY, updated_at: null });
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [healthFilter, setHealthFilter] = useState('all');
  const [pendingAction, setPendingAction] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async (signal) => {
    try {
      setError('');
      const [servicesResponse, eventsResponse] = await Promise.all([
        fetch('/api/local-services', { signal, headers: { Accept: 'application/json' } }),
        fetch('/api/local-services/events', { signal, headers: { Accept: 'application/json' } }),
      ]);
      if (!servicesResponse.ok) throw new Error(`Service inventory unavailable (${servicesResponse.status})`);
      const nextData = await servicesResponse.json();
      setData({ services: nextData.services || [], summary: { ...EMPTY_SUMMARY, ...nextData.summary }, updated_at: nextData.updated_at });
      if (eventsResponse.ok) {
        const eventData = await eventsResponse.json();
        setEvents(Array.isArray(eventData) ? eventData : eventData.events || []);
      }
    } catch (requestError) {
      if (requestError.name !== 'AbortError') setError(requestError.message || 'Local service information is unavailable.');
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const filteredServices = useMemo(() => data.services.filter((service) => {
    const haystack = [service.name, service.process_name, service.port, service.bind_address].join(' ').toLowerCase();
    return haystack.includes(query.trim().toLowerCase()) && (healthFilter === 'all' || service.health_status === healthFilter);
  }), [data.services, healthFilter, query]);

  const runAction = async (service, action) => {
    if (!service.controllable || !window.confirm(`${titleCase(action)} ${service.name}? This may briefly interrupt service.`)) return;
    const key = `${service.id}:${action}`;
    setPendingAction(key);
    setNotice('');
    try {
      const response = await fetch(`/api/local-services/${encodeURIComponent(service.id)}/${action}`, { method: 'POST', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`${titleCase(action)} failed (${response.status})`);
      setNotice(`${service.name}: ${action} requested.`);
      await load();
    } catch (actionError) {
      setNotice(actionError.message);
    } finally {
      setPendingAction('');
    }
  };

  const cards = [
    ['Total services', data.summary.total, 'total'], ['Healthy', data.summary.healthy, 'healthy'],
    ['Degraded', data.summary.degraded, 'degraded'], ['Down', data.summary.down, 'down'],
    ['Unexpected', data.summary.unexpected, 'unexpected'], ['Conflicts', data.summary.conflicts, 'conflicts'],
  ];

  return (
    <main className="local-services-page">
      <header className="local-services-header">
        <div><p className="local-services-eyebrow">System observability</p><h1>Local Services</h1><p>See whether HomeSentinel and its local dependencies are running, reachable, and responsive.</p></div>
        <button className="local-services-refresh" type="button" onClick={() => { setLoading(true); load(); }} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>
      </header>

      {error && <div className="local-services-message local-services-error" role="alert"><strong>Inventory unavailable.</strong> {error} <button type="button" onClick={() => { setLoading(true); load(); }}>Try again</button></div>}
      {notice && <div className="local-services-message" role="status">{notice}</div>}

      <section className="local-services-summary" aria-label="Service overview">
        {cards.map(([label, value, tone]) => <article className={`local-services-stat stat-${tone}`} key={label}><span>{label}</span><strong>{value}</strong></article>)}
      </section>

      <section className="local-services-panel" aria-labelledby="service-inventory-title">
        <div className="local-services-panel-heading"><div><h2 id="service-inventory-title">Service inventory</h2><p>Process state and health are reported separately, so a running but slow service is easy to spot.</p></div><span className="local-services-updated">Updated {formatTime(data.updated_at)}</span></div>
        <div className="local-services-filters">
          <label><span className="sr-only">Search services</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, process, port…" /></label>
          <label><span>Health</span><select aria-label="Filter by health" value={healthFilter} onChange={(event) => setHealthFilter(event.target.value)}><option value="all">All</option><option value="healthy">Healthy</option><option value="degraded">Degraded</option><option value="down">Down</option><option value="unknown">Unknown</option></select></label>
        </div>
        <div className="local-services-table-wrap">
          <table><thead><tr><th>Service</th><th>Endpoint</th><th>Process</th><th>State</th><th>Health</th><th>Latency</th><th>Connections</th><th>Trend</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>{filteredServices.map((service) => <tr key={service.id} className={!service.expected ? 'is-unexpected' : ''}>
              <td><strong>{service.name}</strong>{!service.expected && <span className="local-services-tag">Unexpected</span>}<small>Changed {formatTime(service.last_changed)}</small></td>
              <td><span className="local-services-mono">{service.bind_address || '*'}:{service.port}</span><small>{String(service.protocol || 'tcp').toUpperCase()}</small></td>
              <td>{service.process_name || 'Unknown'}<small>PID {service.pid || '—'} · up {formatDuration(service.uptime_seconds)}</small></td>
              <td><span className={`local-services-pill state-${service.status || 'unknown'}`}>{titleCase(service.status)}</span></td>
              <td><span className={`local-services-pill health-${service.health_status || 'unknown'}`}>{titleCase(service.health_status)}</span></td>
              <td>{Number.isFinite(service.response_time_ms) ? `${Math.round(service.response_time_ms)} ms` : '—'}</td><td>{service.connections ?? '—'}</td>
              <td><Sparkline points={service.history} label={`${service.name} response time trend`} /></td>
              <td><div className="local-services-actions"><button type="button" disabled={!service.controllable || Boolean(pendingAction)} title={!service.controllable ? 'Read-only service' : ''} onClick={() => runAction(service, 'restart')} aria-label={`Restart ${service.name}`}>Restart</button><button className="danger" type="button" disabled={!service.controllable || Boolean(pendingAction)} onClick={() => runAction(service, 'stop')} aria-label={`Stop ${service.name}`}>Stop</button></div></td>
            </tr>)}</tbody>
          </table>
          {!loading && !filteredServices.length && <div className="local-services-empty">No services match these filters.</div>}
          {loading && !data.services.length && <div className="local-services-empty" role="status">Loading local services…</div>}
        </div>
      </section>

      <section className="local-services-panel" aria-labelledby="service-events-title"><div className="local-services-panel-heading"><div><h2 id="service-events-title">Recent service events</h2><p>Starts, stops, health changes, recoveries, and dependency degradation.</p></div></div>
        {events.length ? <ol className="local-services-events">{events.slice(0, 20).map((event, index) => <li key={event.id || `${event.timestamp}-${index}`}><span className={`event-dot event-${event.severity || event.event_type || 'info'}`} aria-hidden="true"/><div><strong>{titleCase(event.event_type || event.type)}</strong><p>{event.message || event.service_name || event.service_id || 'Local service event'}</p></div><time dateTime={event.timestamp}>{formatTime(event.timestamp)}</time></li>)}</ol> : <p className="local-services-empty">No service events recorded yet.</p>}
      </section>
    </main>
  );
}

export default LocalServicesPage;
