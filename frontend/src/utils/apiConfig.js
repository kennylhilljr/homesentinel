/**
 * API Configuration Utility
 * Provides a centralized way to manage API endpoints for both development and production
 */

/**
 * Get the base API URL from environment or window config
 * Supports:
 * - process.env.REACT_APP_API_URL environment variable
 * - window.__API_URL__ global variable (can be set by index.html or config script)
 * - Default fallback to /api (relative path for same-origin requests)
 *
 * @returns {string} Base API URL without trailing slash
 */
export function getApiUrl() {
  // 1. Check environment variable (set during build)
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }

  // 2. Check window global (for runtime configuration)
  if (typeof window !== 'undefined' && window.__API_URL__) {
    return window.__API_URL__;
  }

  // 3. Default: use relative path so CRA proxy handles the request
  // The proxy in package.json forwards to https://localhost:8443
  return '/api';
}

/**
 * Build a full endpoint URL
 * @param {string} endpoint - The endpoint path (e.g., '/deco/nodes' or 'deco/nodes')
 * @returns {string} Full URL to the endpoint
 */
export function buildUrl(endpoint) {
  const baseUrl = getApiUrl();
  // Ensure endpoint starts with /
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${baseUrl}${normalizedEndpoint}`;
}

// Override: set REACT_APP_API_URL=https://localhost:8443/api in .env

export default {
  getApiUrl,
  buildUrl,
};
