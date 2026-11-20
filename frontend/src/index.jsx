import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import ApiKeyPrompt from './components/ApiKeyPrompt';
import { installApiAuth } from './utils/apiAuth';

// Attach X-API-Key to /api requests when a key is stored (no-op otherwise).
installApiAuth(window);

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ApiKeyPrompt />
    <App />
  </React.StrictMode>
);
