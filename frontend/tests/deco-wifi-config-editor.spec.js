/**
 * Playwright E2E Tests for the Deco WiFi Configuration view (read-only).
 *
 * WiFi changes are not supported yet: PUT /api/deco/wifi-config returns 501.
 * The editor shows the current settings read-only with an explanation and has
 * no save action, so the browser must never send a PUT.
 */

const { test, expect } = require('@playwright/test');

const UNSUPPORTED_MESSAGE = "WiFi changes aren't supported yet; change them in the Deco app";

test.describe('Deco WiFi Configuration (read-only) E2E Tests', () => {
  const API_BASE = process.env.API_BASE || 'http://localhost:8000/api';
  const APP_URL = process.env.APP_URL || 'http://localhost:2026';

  let wifiConfig;
  let writeRequests;

  test.beforeEach(async ({ page }) => {
    wifiConfig = {
      ssid: 'TestNetwork',
      band_steering_enabled: true,
      timestamp: new Date().toISOString(),
      cache_info: { ttl_seconds: 60 },
    };
    writeRequests = [];

    await page.route(`${API_BASE}/deco/wifi-config`, (route) => {
      const method = route.request().method();
      if (method === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(wifiConfig),
        });
        return;
      }
      writeRequests.push(method);
      route.fulfill({
        status: 501,
        contentType: 'application/json',
        body: JSON.stringify({ detail: UNSUPPORTED_MESSAGE }),
      });
    });

    await page.goto(`${APP_URL}/deco-nodes`);
    await page.waitForSelector('.wifi-config-editor .editor-container');
  });

  test('Test 1: Shows current settings read-only', async ({ page }) => {
    const editor = page.locator('.wifi-config-editor');
    await expect(editor.locator('.ssid-value')).toHaveText('TestNetwork');
    await expect(editor.locator('.band-steering-value')).toHaveText('Enabled');
    await expect(editor.locator('input, form, select, textarea')).toHaveCount(0);
  });

  test('Test 2: Explains that WiFi changes are not supported', async ({ page }) => {
    await expect(page.locator('.wifi-config-editor .editor-notice')).toHaveText(
      UNSUPPORTED_MESSAGE
    );
  });

  test('Test 3: No save action and no confirmation dialog', async ({ page }) => {
    const editor = page.locator('.wifi-config-editor');
    await expect(editor.getByRole('button', { name: /update|save|apply/i })).toHaveCount(0);
    await expect(page.locator('.dialog-overlay')).toHaveCount(0);
  });

  test('Test 4: Refresh reloads settings without writing', async ({ page }) => {
    wifiConfig = { ...wifiConfig, ssid: 'RenamedInDecoApp' };
    await page.locator('.wifi-config-editor').getByRole('button', { name: /Refresh/i }).click();

    await expect(page.locator('.wifi-config-editor .ssid-value')).toHaveText('RenamedInDecoApp');
    expect(writeRequests).toEqual([]);
  });
});
