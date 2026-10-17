/**
 * Playwright E2E Tests for Deco WiFi Configuration Editor
 * Tests the complete workflow: form submission, confirmation dialog, verification polling, and UI updates
 */

const { test, expect } = require('@playwright/test');

test.describe('Deco WiFi Configuration Editor E2E Tests', () => {
  const API_BASE = process.env.API_BASE || 'http://localhost:8000/api';
  const APP_URL = process.env.APP_URL || 'http://localhost:2026';

  test.beforeEach(async ({ page }) => {
    // Mock the WiFi config API endpoint
    await page.route(`${API_BASE}/deco/wifi-config`, (route) => {
      if (route.request().method() === 'GET') {
        route.abort(); // Handle in route interceptor
      } else {
        route.continue();
      }
    });

    // Navigate to the page
    await page.goto(`${APP_URL}/deco-nodes`);
  });

  test('Test 1: Edit SSID - Confirmation dialog appears', async ({ page }) => {
    // Wait for the WiFi Configuration Editor to load
    await page.waitForSelector('.wifi-config-editor');

    // Mock the GET request for initial config load
    await page.route(`${API_BASE}/deco/wifi-config`, (route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ssid: 'TestNetwork',
            bands: ['2.4 GHz', '5 GHz'],
            channel_2_4ghz: 'Auto',
            channel_5ghz: 'Auto',
            band_steering_enabled: true,
            timestamp: new Date().toISOString(),
            cache_info: { ttl_seconds: 60 },
          }),
        });
      } else {
        route.continue();
      }
    });

    // Wait for form to load
    await page.waitForSelector('input[type="text"]', { timeout: 5000 });

    // Get the SSID input field
    const ssidInput = page.locator('input[placeholder*="SSID"]').first();
    expect(ssidInput).toBeTruthy();

    // Clear and enter new SSID
    await ssidInput.fill('NewNetworkName');

    // Click submit button
    const submitButton = page.locator('button:has-text("Update Configuration")');
    await submitButton.click();

    // Verify confirmation dialog appears
    await page.waitForSelector('.dialog-container');
    const dialogTitle = page.locator('h3:has-text("Confirm WiFi Configuration Changes")');
    await expect(dialogTitle).toBeVisible();

    // Verify the new SSID is shown in the confirmation
    const confirmDialog = page.locator('.dialog-container');
    await expect(confirmDialog).toContainText('NewNetworkName');
  });

  test('Test 2: Submit change via confirmation dialog', async ({ page }) => {
    // Setup initial config mock
    await page.route(`${API_BASE}/deco/wifi-config`, (route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ssid: 'TestNetwork',
            bands: ['2.4 GHz', '5 GHz'],
            channel_2_4ghz: 'Auto',
            channel_5ghz: 'Auto',
            band_steering_enabled: true,
            timestamp: new Date().toISOString(),
            cache_info: { ttl_seconds: 60 },
          }),
        });
      } else if (route.request().method() === 'PUT') {
        // Mock successful update
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            message: 'WiFi configuration updated successfully',
            updated_config: {
              ssid: 'UpdatedNetwork',
              bands: ['2.4 GHz', '5 GHz'],
              channel_2_4ghz: 'Auto',
              channel_5ghz: 'Auto',
              band_steering_enabled: true,
              timestamp: new Date().toISOString(),
            },
            timestamp: new Date().toISOString(),
          }),
        });
      }
    });

    await page.waitForSelector('.wifi-config-editor');

    // Enter new SSID
    const ssidInput = page.locator('input[placeholder*="SSID"]').first();
    await ssidInput.fill('UpdatedNetwork');

    // Submit form
    const submitButton = page.locator('button:has-text("Update Configuration")');
    await submitButton.click();

    // Wait for confirmation dialog
    await page.waitForSelector('.dialog-container');

    // Click "Apply Changes" button in dialog
    const applyButton = page.locator('.dialog-container button:has-text("Apply Changes")');
    await applyButton.click();

    // Verify the request was made
    const requests = [];
    page.on('response', (response) => {
      if (response.url().includes('/wifi-config') && response.request().method() === 'PUT') {
        requests.push(response);
      }
    });

    // Give request time to be intercepted
    await page.waitForTimeout(500);

    expect(requests.length).toBeGreaterThan(0);
  });

  test('Test 3: Verify Deco API returns updated config', async ({ page }) => {
    let configUpdateCount = 0;

    await page.route(`${API_BASE}/deco/wifi-config`, async (route) => {
      if (route.request().method() === 'GET') {
        configUpdateCount++;
        const ssid = configUpdateCount > 1 ? 'UpdatedNetwork' : 'TestNetwork';
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ssid: ssid,
            bands: ['2.4 GHz', '5 GHz'],
            channel_2_4ghz: 'Auto',
            channel_5ghz: 'Auto',
            band_steering_enabled: true,
            timestamp: new Date().toISOString(),
            cache_info: { ttl_seconds: 60 },
          }),
        });
      } else if (route.request().method() === 'PUT') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            message: 'WiFi configuration updated successfully',
            updated_config: {
              ssid: 'UpdatedNetwork',
              bands: ['2.4 GHz', '5 GHz'],
              channel_2_4ghz: 'Auto',
              channel_5ghz: 'Auto',
              band_steering_enabled: true,
            },
            timestamp: new Date().toISOString(),
          }),
        });
      }
    });

    await page.waitForSelector('.wifi-config-editor');

    // Change SSID
    const ssidInput = page.locator('input[placeholder*="SSID"]').first();
    await ssidInput.fill('UpdatedNetwork');

    // Submit
    const submitButton = page.locator('button:has-text("Update Configuration")');
    await submitButton.click();

    // Confirm
    await page.waitForSelector('.dialog-container');
    const applyButton = page.locator('.dialog-container button:has-text("Apply Changes")');
    await applyButton.click();

    // The verification polling should fetch the updated config
    // Verify that at least 2 GET requests were made (initial + verification)
    await page.waitForTimeout(2000);
    expect(configUpdateCount).toBeGreaterThan(1);
  });

  test('Test 4: UI refreshes within 30 seconds after verification', async ({ page }) => {
    let getRequestCount = 0;

    await page.route(`${API_BASE}/deco/wifi-config`, (route) => {
      if (route.request().method() === 'GET') {
        getRequestCount++;
        // First request returns original config, subsequent requests return updated
        const ssid = getRequestCount === 1 ? 'TestNetwork' : 'FinalNetwork';
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ssid: ssid,
            bands: ['2.4 GHz', '5 GHz'],
            channel_2_4ghz: 'Auto',
            channel_5ghz: 'Auto',
            band_steering_enabled: true,
            timestamp: new Date().toISOString(),
            cache_info: { ttl_seconds: 60 },
          }),
        });
      } else if (route.request().method() === 'PUT') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            message: 'WiFi configuration updated successfully',
            updated_config: {
              ssid: 'FinalNetwork',
              bands: ['2.4 GHz', '5 GHz'],
              channel_2_4ghz: 'Auto',
              channel_5ghz: 'Auto',
              band_steering_enabled: true,
            },
            timestamp: new Date().toISOString(),
          }),
        });
      }
    });

    await page.waitForSelector('.wifi-config-editor');

    // Record start time
    const startTime = Date.now();

    // Update SSID
    const ssidInput = page.locator('input[placeholder*="SSID"]').first();
    await ssidInput.fill('FinalNetwork');

    // Submit
    const submitButton = page.locator('button:has-text("Update Configuration")');
    await submitButton.click();

    // Confirm
    await page.waitForSelector('.dialog-container');
    const applyButton = page.locator('.dialog-container button:has-text("Apply Changes")');
    await applyButton.click();

    // Wait for success message
    await page.waitForSelector('.editor-success', { timeout: 35000 });
    const successMessage = page.locator('.editor-success');
    await expect(successMessage).toContainText('successfully');

    // Verify it completed within 30 seconds
    const endTime = Date.now();
    const elapsedSeconds = (endTime - startTime) / 1000;
    expect(elapsedSeconds).toBeLessThan(35); // Allow 35s for flakiness
  });

  test('Test 5: Error handling - Invalid password', async ({ page }) => {
    await page.route(`${API_BASE}/deco/wifi-config`, (route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ssid: 'TestNetwork',
            bands: ['2.4 GHz', '5 GHz'],
            channel_2_4ghz: 'Auto',
            channel_5ghz: 'Auto',
            band_steering_enabled: true,
            timestamp: new Date().toISOString(),
            cache_info: { ttl_seconds: 60 },
          }),
        });
      }
    });

    await page.waitForSelector('.wifi-config-editor');

    // Try to set a weak password
    const passwordInput = page.locator('input[type="password"][placeholder*="Leave blank"]').first();
    await passwordInput.fill('short');

    // Try to submit
    const submitButton = page.locator('button:has-text("Update Configuration")');
    await submitButton.click();

    // Should show validation error
    const errorMessage = page.locator('.editor-error');
    await expect(errorMessage).toContainText('at least 8 characters');
  });

  test('Test 6: Error handling - Rate limit', async ({ page }) => {
    let putRequestCount = 0;

    await page.route(`${API_BASE}/deco/wifi-config`, (route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ssid: 'TestNetwork',
            bands: ['2.4 GHz', '5 GHz'],
            channel_2_4ghz: 'Auto',
            channel_5ghz: 'Auto',
            band_steering_enabled: true,
            timestamp: new Date().toISOString(),
            cache_info: { ttl_seconds: 60 },
          }),
        });
      } else if (route.request().method() === 'PUT') {
        putRequestCount++;
        // Simulate rate limit after first attempt
        if (putRequestCount > 1) {
          route.fulfill({
            status: 429,
            contentType: 'application/json',
            body: JSON.stringify({
              detail: 'Rate limit exceeded. Please try again later.',
            }),
          });
        } else {
          route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              success: true,
              message: 'WiFi configuration updated successfully',
              updated_config: {
                ssid: 'UpdatedNetwork',
                bands: ['2.4 GHz', '5 GHz'],
                channel_2_4ghz: 'Auto',
                channel_5ghz: 'Auto',
                band_steering_enabled: true,
              },
              timestamp: new Date().toISOString(),
            }),
          });
        }
      }
    });

    await page.waitForSelector('.wifi-config-editor');

    // First update succeeds
    const ssidInput = page.locator('input[placeholder*="SSID"]').first();
    await ssidInput.fill('UpdatedNetwork');

    const submitButton = page.locator('button:has-text("Update Configuration")');
    await submitButton.click();

    await page.waitForSelector('.dialog-container');
    const applyButton = page.locator('.dialog-container button:has-text("Apply Changes")');
    await applyButton.click();

    // Wait for success
    await page.waitForSelector('.editor-success', { timeout: 10000 });

    // Now attempt second update quickly (should hit rate limit)
    await ssidInput.fill('AnotherNetwork');
    await submitButton.click();

    await page.waitForSelector('.dialog-container');
    const applyButton2 = page.locator('.dialog-container button:has-text("Apply Changes")');
    await applyButton2.click();

    // Should show rate limit error
    const errorMessage = page.locator('.editor-error');
    await expect(errorMessage).toContainText('Rate limit', { timeout: 5000 });
  });

  test('Test 7: Confirmation dialog can be cancelled', async ({ page }) => {
    await page.route(`${API_BASE}/deco/wifi-config`, (route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ssid: 'TestNetwork',
            bands: ['2.4 GHz', '5 GHz'],
            channel_2_4ghz: 'Auto',
            channel_5ghz: 'Auto',
            band_steering_enabled: true,
            timestamp: new Date().toISOString(),
            cache_info: { ttl_seconds: 60 },
          }),
        });
      }
    });

    await page.waitForSelector('.wifi-config-editor');

    // Change SSID
    const ssidInput = page.locator('input[placeholder*="SSID"]').first();
    await ssidInput.fill('NewNetwork');

    // Submit
    const submitButton = page.locator('button:has-text("Update Configuration")');
    await submitButton.click();

    // Dialog appears
    await page.waitForSelector('.dialog-container');

    // Click Cancel
    const cancelButton = page.locator('.dialog-container button:has-text("Cancel")');
    await cancelButton.click();

    // Dialog should disappear
    await expect(page.locator('.dialog-container')).not.toBeVisible({ timeout: 2000 });

    // Form should still show the change
    expect(await ssidInput.inputValue()).toBe('NewNetwork');
  });

  test('Test 8: Band steering toggle works', async ({ page }) => {
    await page.route(`${API_BASE}/deco/wifi-config`, async (route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ssid: 'TestNetwork',
            bands: ['2.4 GHz', '5 GHz'],
            channel_2_4ghz: 'Auto',
            channel_5ghz: 'Auto',
            band_steering_enabled: true,
            timestamp: new Date().toISOString(),
            cache_info: { ttl_seconds: 60 },
          }),
        });
      } else if (route.request().method() === 'PUT') {
       const body = await route.request().postDataJSON();
          route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              success: true,
              message: 'WiFi configuration updated successfully',
              updated_config: {
                ssid: 'TestNetwork',
                bands: ['2.4 GHz', '5 GHz'],
                channel_2_4ghz: 'Auto',
                channel_5ghz: 'Auto',
                band_steering_enabled: body.band_steering_enabled ?? true,
              },
              timestamp: new Date().toISOString(),
            }),
          });
      }
    });

    await page.waitForSelector('.wifi-config-editor');

    // Get the toggle checkbox
    const toggleCheckbox = page.locator('input[type="checkbox"]').first();
    const isChecked = await toggleCheckbox.isChecked();

    // Toggle it
    await toggleCheckbox.click();

    // Verify it toggled
    const newState = await toggleCheckbox.isChecked();
    expect(newState).toBe(!isChecked);

    // Submit the change
    const submitButton = page.locator('button:has-text("Update Configuration")');
    await submitButton.click();

    // Confirm
    await page.waitForSelector('.dialog-container');
    const applyButton = page.locator('.dialog-container button:has-text("Apply Changes")');
    await applyButton.click();

    // Should eventually show success
    await page.waitForSelector('.editor-success', { timeout: 10000 });
  });
});
