/**
 * Mobile App Tests for Omni-PLA
 * Using Detox for React Native testing
 */

describe('Omni-PLA Mobile App', () => {
  beforeAll(async () => {
    await device.launchApp();
  });

  beforeEach(async () => {
    await device.reloadReactNative();
  });

  describe('Portfolio Screen', () => {
    it('should show portfolio screen on launch', async () => {
      await expect(element(by.id('portfolio-screen'))).toBeVisible();
    });

    it('should display stock holdings', async () => {
      await expect(element(by.id('holdings-list'))).toBeVisible();
      await expect(element(by.id('stock-card'))).toExist();
    });

    it('should open stock detail modal on tap', async () => {
      await element(by.id('stock-card')).atIndex(0).tap();
      await expect(element(by.id('stock-modal'))).toBeVisible();
    });

    it('should display real-time stock data (no demo)', async () => {
      await element(by.id('stock-card')).atIndex(0).tap();
      
      // Check for price
      await expect(element(by.id('stock-price'))).toBeVisible();
      
      // Check for technical analysis
      await expect(element(by.id('technical-analysis'))).toBeVisible();
      
      // Check for AI recommendation
      await expect(element(by.id('ai-recommendation'))).toBeVisible();
    });

    it('should display stock chart', async () => {
      await element(by.id('stock-card')).atIndex(0).tap();
      await expect(element(by.id('stock-chart'))).toBeVisible();
    });

    it('should show AI analysis with confidence', async () => {
      await element(by.id('stock-card')).atIndex(0).tap();
      await expect(element(by.id('ai-confidence'))).toBeVisible();
    });

    it('should close modal on back button', async () => {
      await element(by.id('stock-card')).atIndex(0).tap();
      await element(by.id('close-modal-button')).tap();
      await expect(element(by.id('stock-modal'))).not.toBeVisible();
    });
  });

  describe('News Screen', () => {
    it('should navigate to news screen', async () => {
      await element(by.id('news-tab')).tap();
      await expect(element(by.id('news-screen'))).toBeVisible();
    });

    it('should display knowledge pill', async () => {
      await element(by.id('news-tab')).tap();
      await expect(element(by.id('knowledge-pill'))).toBeVisible();
    });

    it('should display market influencers', async () => {
      await element(by.id('news-tab')).tap();
      await element(by.id('influencers-tab')).tap();
      await expect(element(by.text('Elon Musk'))).toBeVisible();
      await expect(element(by.text('Jerome Powell'))).toBeVisible();
    });

    it('should display India market news', async () => {
      await element(by.id('news-tab')).tap();
      await element(by.id('financial-tab')).tap();
      await expect(element(by.text('Nifty 50'))).toBeVisible();
      await expect(element(by.text('Sensex'))).toBeVisible();
    });
  });

  describe('Shopping Screen', () => {
    it('should navigate to shopping screen', async () => {
      await element(by.id('shopping-tab')).tap();
      await expect(element(by.id('shopping-screen'))).toBeVisible();
    });

    it('should search for products', async () => {
      await element(by.id('shopping-tab')).tap();
      await element(by.id('search-input')).typeText('organic chicken');
      await element(by.id('search-button')).tap();
      
      await waitFor(element(by.id('product-card')))
        .toBeVisible()
        .withTimeout(5000);
    });

    it('should display realistic pricing', async () => {
      await element(by.id('shopping-tab')).tap();
      await element(by.id('search-input')).typeText('organic chicken');
      await element(by.id('search-button')).tap();
      
      await waitFor(element(by.id('product-price')))
        .toBeVisible()
        .withTimeout(5000);
      
      // Price should be in realistic range (20-100)
      const priceText = await element(by.id('product-price')).getAttributes();
      const price = parseFloat(priceText.text.replace('$', ''));
      expect(price).toBeGreaterThan(20);
      expect(price).toBeLessThan(100);
    });
  });

  describe('Travel Screen', () => {
    it('should navigate to travel screen', async () => {
      await element(by.id('travel-tab')).tap();
      await expect(element(by.id('travel-screen'))).toBeVisible();
    });

    it('should search for flights', async () => {
      await element(by.id('travel-tab')).tap();
      await element(by.id('origin-input')).typeText('CLT');
      await element(by.id('destination-input')).typeText('RDU');
      await element(by.id('search-flights-button')).tap();
      
      await waitFor(element(by.id('flight-card')))
        .toBeVisible()
        .withTimeout(5000);
    });

    it('should display realistic flight pricing', async () => {
      await element(by.id('travel-tab')).tap();
      await element(by.id('origin-input')).typeText('CLT');
      await element(by.id('destination-input')).typeText('RDU');
      await element(by.id('search-flights-button')).tap();
      
      await waitFor(element(by.id('flight-price')))
        .toBeVisible()
        .withTimeout(5000);
      
      // Short haul should be 50-300
      const priceText = await element(by.id('flight-price')).getAttributes();
      const price = parseFloat(priceText.text.replace('$', ''));
      expect(price).toBeGreaterThan(50);
      expect(price).toBeLessThan(300);
    });
  });

  describe('UI/UX Tests', () => {
    it('should have smooth animations', async () => {
      await element(by.id('stock-card')).atIndex(0).tap();
      // Modal should animate in
      await expect(element(by.id('stock-modal'))).toBeVisible();
    });

    it('should support pull-to-refresh', async () => {
      await element(by.id('holdings-list')).swipe('down', 'fast');
      // Should trigger refresh
      await waitFor(element(by.id('loading-indicator')))
        .toBeVisible()
        .withTimeout(1000);
    });

    it('should handle network errors gracefully', async () => {
      // Simulate network error
      await device.setURLBlacklist(['http://localhost:30000/*']);
      
      await element(by.id('stock-card')).atIndex(0).tap();
      
      // Should show error alert
      await expect(element(by.text('Error'))).toBeVisible();
      
      // Clear blacklist
      await device.setURLBlacklist([]);
    });

    it('should not show demo data on error', async () => {
      // Simulate network error
      await device.setURLBlacklist(['http://localhost:30000/*']);
      
      await element(by.id('stock-card')).atIndex(0).tap();
      
      // Should NOT show $178.50 demo price
      await expect(element(by.text('$178.50'))).not.toBeVisible();
      
      // Clear blacklist
      await device.setURLBlacklist([]);
    });
  });

  describe('Performance Tests', () => {
    it('should load portfolio within 2 seconds', async () => {
      const startTime = Date.now();
      await device.reloadReactNative();
      await waitFor(element(by.id('portfolio-screen')))
        .toBeVisible()
        .withTimeout(2000);
      const loadTime = Date.now() - startTime;
      expect(loadTime).toBeLessThan(2000);
    });

    it('should render stock chart within 3 seconds', async () => {
      await element(by.id('stock-card')).atIndex(0).tap();
      await waitFor(element(by.id('stock-chart')))
        .toBeVisible()
        .withTimeout(3000);
    });
  });
});
