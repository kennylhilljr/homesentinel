import React from 'react';
import DecoTopologyView from '../components/DecoTopologyView';
import '../pages/DecoTopologyPage.css';

/**
 * DecoTopologyPage Component
 * Page for displaying network topology visualization
 */
function DecoTopologyPage() {
  return (
    <div className="deco-topology-page">
      <div className="page-header">
        <div className="header-title">
          <h1>Network Topology</h1>
          <p>Visual map showing Deco nodes and their connected devices</p>
        </div>
      </div>

      <DecoTopologyView autoRefreshInterval={30000} />
    </div>
  );
}

export default DecoTopologyPage;
