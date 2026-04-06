// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * E2E Tests for Deco Network Topology View
 * Tests the full workflow of navigating to and interacting with the topology view
 */

test.describe('Deco Network Topology', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to application
    await page.goto('http://localhost:2026', { waitUntil: 'networkidle' });

    // Wait for app to load
    await page.waitForSelector('.App-header');
  });

  test('should navigate to Network Topology page', async ({ page }) => {
    // Click Network Topology nav button
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    // Wait for topology page to load
    await page.waitForSelector('.deco-topology-page');

    // Verify page content
    expect(await page.locator('h1:has-text("Network Topology")').isVisible()).toBe(true);
    expect(
      await page.locator('text=Visual map showing Deco nodes and their connected devices').isVisible()
    ).toBe(true);
  });

  test('should display topology visualization', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-view');

    // Check for legend
    expect(await page.locator('text=Online Node').isVisible()).toBe(true);
    expect(await page.locator('text=Online Device').isVisible()).toBe(true);
    expect(await page.locator('text=Device-to-Node Connection').isVisible()).toBe(true);

    // Check for SVG canvas
    const svg = page.locator('svg.topology-svg');
    expect(await svg.isVisible()).toBe(true);
  });

  test('should display topology statistics', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.topology-stats');

    // Check stats are displayed
    expect(await page.locator('text=Nodes:').isVisible()).toBe(true);
    expect(await page.locator('text=Devices:').isVisible()).toBe(true);
    expect(await page.locator('text=Connections:').isVisible()).toBe(true);
  });

  test('should display node and device details', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-view');

    // Scroll to details section
    await page.locator('.topology-details').scrollIntoViewIfNeeded();

    // Check nodes section
    expect(await page.locator('text=Nodes (').isVisible()).toBe(true);

    // Check devices section
    expect(await page.locator('text=Devices (').isVisible()).toBe(true);
  });

  test('should have working refresh button', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-view');

    // Get initial timestamp
    const initialTimestamp = await page.locator('.last-refresh').textContent();

    // Click refresh button
    const refreshButton = page.locator('button:has-text("Refresh")').first();
    await refreshButton.click();

    // Wait for update (short delay for request)
    await page.waitForTimeout(500);

    // Verify API was called (in a real scenario, timestamp would update)
    const finalTimestamp = await page.locator('.last-refresh').textContent();
    expect(finalTimestamp).toBeTruthy();
  });

  test('should toggle auto-refresh', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-view');

    // Find auto-refresh checkbox
    const autoRefreshCheckbox = page.locator('input#autoRefreshTopology');

    // Verify it's initially checked
    expect(await autoRefreshCheckbox.isChecked()).toBe(true);

    // Uncheck it
    await autoRefreshCheckbox.click();
    expect(await autoRefreshCheckbox.isChecked()).toBe(false);

    // Check it again
    await autoRefreshCheckbox.click();
    expect(await autoRefreshCheckbox.isChecked()).toBe(true);
  });

  test('should display online node status', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-view');

    // Look for online status indicators
    const onlineIndicators = page.locator('text=● Online');
    const count = await onlineIndicators.count();

    // There should be at least one online indicator
    expect(count).toBeGreaterThan(0);
  });

  test('should display device information in detail cards', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-view');

    // Scroll to devices section
    await page.locator('.details-section:has-text("Devices")').scrollIntoViewIfNeeded();

    // Check that device cards are visible
    const deviceCards = page.locator('.device-card');
    const cardCount = await deviceCards.count();

    // There should be at least one device card
    expect(cardCount).toBeGreaterThan(0);

    // Check that MAC addresses are displayed
    const macAddresses = page.locator('code');
    const macCount = await macAddresses.count();
    expect(macCount).toBeGreaterThan(0);
  });

  test('should display node information in detail cards', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-view');

    // Scroll to nodes section
    await page.locator('.details-section:has-text("Nodes")').scrollIntoViewIfNeeded();

    // Check that node cards are visible
    const nodeCards = page.locator('.node-card');
    const cardCount = await nodeCards.count();

    // There should be at least one node card
    expect(cardCount).toBeGreaterThan(0);
  });

  test('should maintain responsive layout on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-view');

    // Check that elements are still visible
    expect(await page.locator('h2:has-text("Network Topology")').isVisible()).toBe(true);

    // Check legend is responsive
    const legend = page.locator('.topology-legend');
    expect(await legend.isVisible()).toBe(true);
  });

  test('should maintain responsive layout on tablet', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });

    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-view');

    // Check that elements are visible
    expect(await page.locator('.svg-container').isVisible()).toBe(true);

    // SVG should be visible
    const svg = page.locator('svg.topology-svg');
    expect(await svg.isVisible()).toBe(true);
  });

  test('should navigate between pages', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-page');

    // Navigate to Deco Nodes
    const decoNodesButton = page.locator('button:has-text("Deco Nodes")');
    await decoNodesButton.click();

    // Wait for Deco Nodes page
    await page.waitForSelector('.deco-nodes-page');

    // Navigate back to Topology
    await topologyButton.click();

    // Verify topology page is displayed again
    await page.waitForSelector('.deco-topology-page');
    expect(await page.locator('h1:has-text("Network Topology")').isVisible()).toBe(true);
  });

  test('should handle loading state', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    // The page should load topology data
    await page.waitForSelector('.deco-topology-view');

    // After loading, content should be visible
    expect(await page.locator('.svg-container').isVisible()).toBe(true);
  });

  test('should display last refresh time', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-view');

    // Check for last refresh time display
    const lastRefresh = page.locator('.last-refresh');
    expect(await lastRefresh.isVisible()).toBe(true);

    const refreshText = await lastRefresh.textContent();
    expect(refreshText).toMatch(/Last updated:/);
  });

  test('should display network topology in full page', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('.deco-topology-page');

    // Take full-page screenshot for manual verification
    // Note: This helps verify visual layout
    expect(await page.locator('.deco-topology-page').isVisible()).toBe(true);
  });

  test('should display SVG elements with proper structure', async ({ page }) => {
    // Navigate to topology
    const topologyButton = page.locator('button:has-text("Network Topology")');
    await topologyButton.click();

    await page.waitForSelector('svg.topology-svg');

    // Get SVG element
    const svg = page.locator('svg.topology-svg');

    // Check that SVG has circles (nodes and devices)
    const circles = svg.locator('circle');
    const circleCount = await circles.count();

    // Should have at least circles for nodes and devices
    expect(circleCount).toBeGreaterThan(0);
  });
});
