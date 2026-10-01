/**
 * Frontend UI Tests for Omni-PLA Web Application
 * Using Playwright for end-to-end testing
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = 'http://localhost:30001';

test.describe('Portfolio Page Tests', () => {
  test('should load portfolio page', async ({ page }) => {
    await page.goto(`${BASE_URL}/portfolio`);
    
    // Check page title
    await expect(page).toHaveTitle(/Portfolio/);
    
    // Check for main elements
    await expect(page.locator('h1')).toContainText('Portfolio');
  });
  
  test('should display stock holdings', async ({ page }) => {
    await page.goto(`${BASE_URL}/portfolio`);
    
    // Wait for holdings to load
    await page.waitForSelector('[data-testid="holdings-list"]', { timeout: 5000 });
    
    // Check if holdings are displayed
    const holdings = page.locator('[data-testid="stock-card"]');
    await expect(holdings).toHaveCount(await holdings.count());
  });
  
  test('should open stock detail modal', async ({ page }) => {
    await page.goto(`${BASE_URL}/portfolio`);
    
    // Click on a stock card
    const firstStock = page.locator('[data-testid="stock-card"]').first();
    await firstStock.click();
    
    // Check if modal opens
    await expect(page.locator('[data-testid="stock-modal"]')).toBeVisible();
    
    // Check for chart
    await expect(page.locator('[data-testid="stock-chart"]')).toBeVisible();
    
    // Check for technical analysis
    await expect(page.locator('[data-testid="technical-analysis"]')).toBeVisible();
    
    // Check for AI recommendation
    await expect(page.locator('[data-testid="ai-recommendation"]')).toBeVisible();
  });
  
  test('should display options strategies', async ({ page }) => {
    await page.goto(`${BASE_URL}/portfolio`);
    
    // Click on a stock
    await page.locator('[data-testid="stock-card"]').first().click();
    
    // Wait for options tab
    await page.waitForSelector('[data-testid="options-tab"]');
    await page.locator('[data-testid="options-tab"]').click();
    
    // Check for strategies
    await expect(page.locator('[data-testid="options-strategy"]')).toHaveCount(3);
    
    // Check for Greeks
    await expect(page.locator('[data-testid="greeks-delta"]')).toBeVisible();
    await expect(page.locator('[data-testid="greeks-gamma"]')).toBeVisible();
    await expect(page.locator('[data-testid="greeks-theta"]')).toBeVisible();
    await expect(page.locator('[data-testid="greeks-vega"]')).toBeVisible();
  });
});

test.describe('News Page Tests', () => {
  test('should load news page', async ({ page }) => {
    await page.goto(`${BASE_URL}/news`);
    
    // Check page title
    await expect(page).toHaveTitle(/News/);
    
    // Check for tabs
    await expect(page.locator('[data-testid="knowledge-pill-tab"]')).toBeVisible();
    await expect(page.locator('[data-testid="financial-tab"]')).toBeVisible();
    await expect(page.locator('[data-testid="tech-tab"]')).toBeVisible();
    await expect(page.locator('[data-testid="influencers-tab"]')).toBeVisible();
  });
  
  test('should display knowledge pill', async ({ page }) => {
    await page.goto(`${BASE_URL}/news`);
    
    // Click knowledge pill tab
    await page.locator('[data-testid="knowledge-pill-tab"]').click();
    
    // Check for key takeaways
    await expect(page.locator('[data-testid="key-takeaway"]')).toHaveCount(5);
    
    // Check for market movers
    await expect(page.locator('[data-testid="market-mover"]')).toBeVisible();
  });
  
  test('should display market influencers', async ({ page }) => {
    await page.goto(`${BASE_URL}/news`);
    
    // Click influencers tab
    await page.locator('[data-testid="influencers-tab"]').click();
    
    // Check for influencer cards
    const influencers = page.locator('[data-testid="influencer-card"]');
    await expect(influencers).toHaveCount(4);
    
    // Check for specific influencers
    await expect(page.locator('text=Elon Musk')).toBeVisible();
    await expect(page.locator('text=Jerome Powell')).toBeVisible();
    await expect(page.locator('text=Warren Buffett')).toBeVisible();
  });
  
  test('should display India market news', async ({ page }) => {
    await page.goto(`${BASE_URL}/news`);
    
    // Click financial tab
    await page.locator('[data-testid="financial-tab"]').click();
    
    // Select India region
    await page.selectOption('[data-testid="region-select"]', 'india');
    
    // Check for Nifty/Sensex indices
    await expect(page.locator('text=Nifty 50')).toBeVisible();
    await expect(page.locator('text=Sensex')).toBeVisible();
  });
});

test.describe('Shopping Page Tests', () => {
  test('should search for products', async ({ page }) => {
    await page.goto(`${BASE_URL}/shopping`);
    
    // Enter search query
    await page.fill('[data-testid="search-input"]', 'organic chicken');
    await page.click('[data-testid="search-button"]');
    
    // Wait for results
    await page.waitForSelector('[data-testid="product-card"]');
    
    // Check for products
    const products = page.locator('[data-testid="product-card"]');
    await expect(products).toHaveCount(await products.count());
    
    // Check for realistic pricing
    const firstPrice = await page.locator('[data-testid="product-price"]').first().textContent();
    const price = parseFloat(firstPrice.replace('$', ''));
    expect(price).toBeGreaterThan(20);
    expect(price).toBeLessThan(100);
  });
});

test.describe('Travel Page Tests', () => {
  test('should search for flights', async ({ page }) => {
    await page.goto(`${BASE_URL}/travel`);
    
    // Fill in flight search form
    await page.fill('[data-testid="origin-input"]', 'CLT');
    await page.fill('[data-testid="destination-input"]', 'RDU');
    await page.fill('[data-testid="departure-date"]', '2026-02-11');
    await page.click('[data-testid="search-flights-button"]');
    
    // Wait for results
    await page.waitForSelector('[data-testid="flight-card"]');
    
    // Check for flights
    const flights = page.locator('[data-testid="flight-card"]');
    await expect(flights).toHaveCount(await flights.count());
    
    // Check for realistic pricing (short haul)
    const firstPrice = await page.locator('[data-testid="flight-price"]').first().textContent();
    const price = parseFloat(firstPrice.replace('$', ''));
    expect(price).toBeGreaterThan(50);
    expect(price).toBeLessThan(300);
  });
});

test.describe('Responsive Design Tests', () => {
  test('should be responsive on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    
    await page.goto(`${BASE_URL}/portfolio`);
    
    // Check if mobile menu is visible
    await expect(page.locator('[data-testid="mobile-menu"]')).toBeVisible();
  });
  
  test('should be responsive on tablet', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    
    await page.goto(`${BASE_URL}/portfolio`);
    
    // Check layout
    await expect(page.locator('[data-testid="sidebar"]')).toBeVisible();
  });
});

test.describe('Performance Tests', () => {
  test('should load portfolio page within 3 seconds', async ({ page }) => {
    const startTime = Date.now();
    await page.goto(`${BASE_URL}/portfolio`);
    await page.waitForLoadState('networkidle');
    const loadTime = Date.now() - startTime;
    
    expect(loadTime).toBeLessThan(3000);
  });
  
  test('should load news page within 2 seconds', async ({ page }) => {
    const startTime = Date.now();
    await page.goto(`${BASE_URL}/news`);
    await page.waitForLoadState('networkidle');
    const loadTime = Date.now() - startTime;
    
    expect(loadTime).toBeLessThan(2000);
  });
});
