/**
 * API Configuration Utility
 * Provides a centralized way to manage API endpoints for both development and production.
 *
 * 2026-03-11: Updated to auto-detect API base URL from the browser's current origin.
 * When served from FastAPI (production/ZeroTier), the frontend and API share the same
 * origin, so /api relative paths work automatically — no rebuild needed for different IPs.
 */

/**
 * Get the base API URL.
 *
 * Priority:
 * 1. REACT_APP_API_URL env var (build-time override)
 * 2. window.__API_URL__ global (runtime override via index.html)
 * 3. /api relative path — works for both:
 *    - CRA dev server (proxy in package.json → https://localhost:8443)
 *    - FastAPI production build (same origin, /api/* routes handled by FastAPI)
 *
 * @returns {string} Base API URL without trailing slash
 */
export function getApiUrl() {
  // 1. Build-time override
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }

  // 2. Runtime override (e.g. set in index.html before app loads)
  if (typeof window !== 'undefined' && window.__API_URL__) {
    return window.__API_URL__;
  }

  // 3. Relative /api — works everywhere:
  //    Dev: CRA proxy forwards /api → https://localhost:8443/api
  //    Prod: FastAPI serves both React build AND /api on the same port
  //    ZeroTier: Same as prod — https://<zerotier-ip>:8443/api
  return '/api';
}

/**
 * Build a full endpoint URL
 * @param {string} endpoint - The endpoint path (e.g., '/deco/nodes' or 'deco/nodes')
 * @returns {string} Full URL to the endpoint
 */
export function buildUrl(endpoint) {
  const baseUrl = getApiUrl();
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${baseUrl}${normalizedEndpoint}`;
}

export default {
  getApiUrl,
  buildUrl,
};
