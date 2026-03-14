import React, { useState, useEffect } from 'react';
import EventLog from '../components/EventLog';

/**
 * EventLogPage Component
 * Page for viewing device events and alerts
 * 2026-03-14: Productionized event and alert viewing interface
 */
function EventLogPage() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);

  // Fetch all devices for the filter dropdown
  useEffect(() => {
    const fetchDevices = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/deco/clients-merged', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json'
          }
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
    <div style={{
      padding: '20px',
      backgroundColor: '#0a0a0a',
      minHeight: '100vh'
    }}>
      <div style={{
        maxWidth: '1400px',
        margin: '0 auto'
      }}>
        {/* Breadcrumb */}
        <div style={{
          marginBottom: '20px',
          fontSize: '13px',
          color: '#b0b0b0'
        }}>
          <a href="#" onClick={(e) => {
            e.preventDefault();
            // Navigate to dashboard (handled by parent App)
          }} style={{ color: '#3b82f6', textDecoration: 'none' }}>
            Dashboard
          </a>
          {' > '}
          <span>Events & Alerts</span>
        </div>

        {/* Page Header */}
        <div style={{
          marginBottom: '30px'
        }}>
          <h1 style={{
            fontSize: '32px',
            fontWeight: '700',
            color: '#ffffff',
            margin: '0 0 10px 0'
          }}>
            Events & Alerts
          </h1>
          <p style={{
            fontSize: '14px',
            color: '#b0b0b0',
            margin: '0'
          }}>
            Monitor device connection/disconnection events and manage active alerts
          </p>
        </div>

        {/* EventLog Component */}
        {loading ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '400px',
            color: '#b0b0b0',
            fontSize: '16px'
          }}>
            Loading devices...
          </div>
        ) : (
          <EventLog devices={devices} />
        )}
      </div>
    </div>
  );
}

export default EventLogPage;
