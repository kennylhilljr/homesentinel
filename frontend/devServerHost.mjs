const LOOPBACK = /^(localhost|127\.\d{1,3}\.\d{1,3}\.\d{1,3}|::1|\[::1\])$/i;

export const DEFAULT_FRONTEND_HOST = '127.0.0.1';

export function isLoopbackHost(host) {
  return LOOPBACK.test(host);
}

// The dev server serves plain HTTP and proxies /api to the backend, so a non-loopback
// bind would expose the API (and any X-API-Key the dashboard sends) to the network
// unencrypted. Any non-loopback bind is an explicit insecure choice. For LAN access,
// serve the built dashboard from the backend over HTTPS instead.
export function resolveDevServerHost(env) {
  const host = (env.HOMESENTINEL_FRONTEND_HOST || '').trim() || DEFAULT_FRONTEND_HOST;
  const override = ['1', 'true', 'yes'].includes((env.HOMESENTINEL_ALLOW_INSECURE_BIND || '').trim().toLowerCase());
  if (!isLoopbackHost(host) && !override) {
    throw new Error(`Refusing to bind the dev server to ${host}: it proxies /api to the backend over plain HTTP. Set HOMESENTINEL_ALLOW_INSECURE_BIND=1 to allow it.`);
  }
  return host;
}
