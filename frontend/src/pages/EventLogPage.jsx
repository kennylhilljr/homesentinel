import React, { useState, useEffect } from 'react';
import EventLog from '../components/EventLog';
import './EventLogPage.css';

/**
 * EventLogPage Component
 * Page for viewing device events and alerts
 * 2026-03-14: Productionized event and alert viewing interface
 * 2026-05-07: Migrated inline styles to EventLogPage.css with design tokens
 */
function EventLogPage() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDevices = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/deco/clients-merged', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          setDevices(data || []);
        }
      } catch (error) {
        console.error('Error fetching devices:', error);
        setDevices([]);
      } finally {
        setLoading(false);
      }
    };

    fetchDevices();
  }, []);

  return (
    <div className="event-log-page">
      <div className="event-log-page-inner">
        <nav className="event-log-breadcrumb" aria-label="Breadcrumb">
          <button
            type="button"
            className="event-log-breadcrumb-link"
            onClick={() => {
              // Navigate to dashboard (handled by parent App)
            }}
          >
            Dashboard
          </button>
          {' > '}
          <span aria-current="page">Events &amp; Alerts</span>
        </nav>

        <div className="event-log-header">
          <h1>Events &amp; Alerts</h1>
          <p>Monitor device connection/disconnection events and manage active alerts</p>
        </div>

        {loading ? (
          <div
            className="event-log-loading"
            role="status"
            aria-live="polite"
            aria-busy="true"
          >
            <span className="hs-spinner" aria-hidden="true" />
            <span>Loading devices…</span>
          </div>
        ) : (
          <EventLog devices={devices} />
        )}
      </div>
    </div>
  );
}

export default EventLogPage;
