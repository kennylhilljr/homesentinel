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
      <DecoTopologyView autoRefreshInterval={30000} />
    </div>
  );
}

export default DecoTopologyPage;
