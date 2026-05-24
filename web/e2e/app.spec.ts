import { test, expect } from '@playwright/test';

test.describe('Vision Pipeline Review Flow', () => {
  test.beforeEach(async ({ page }) => {
    page.on('console', msg => console.log(`BROWSER LOG: ${msg.text()}`));
    page.on('pageerror', err => console.log(`BROWSER ERROR: ${err.message}`));
    // Mock the queue API for consistent UI testing
    await page.route('**/api/queue', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 'test-item-1',
              filename: 'raw_9940b71b-4565-4014-8e1c-6fe79ea5febf.jpg',
              product_type: 'food',
              edit_data: {
                product_name: 'Premium Coffee Beans',
                brand: 'Vibe Cafe',
                category: 'Beverages',
                description: 'Freshly roasted beans for a perfect vibe.'
              },
              selected_services: ['homebox']
            }
          ]
        })
      });
    });

    await page.goto('/');
  });

  test('should display assets in the queue', async ({ page }) => {
    console.log('Page Title:', await page.title());
    console.log('Page Content:', await page.content());
    await expect(page.getByText('Review Queue')).toBeVisible();
    await expect(page.getByText('Premium Coffee Beans')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('food')).toBeVisible();
  });

  test('should expand asset card and edit fields', async ({ page }) => {
    // Click the expand button (ChevronDown)
    await page.getByLabel('Expand Asset').first().click();
    
    // Verify fields are visible
    const brandInput = page.getByLabel('Brand');
    await expect(brandInput).toHaveValue('Vibe Cafe');
    
    // Edit the brand
    await brandInput.fill('Vibe Roastary');
    await expect(brandInput).toHaveValue('Vibe Roastary');
  });

  test('should open and close the preview modal', async ({ page }) => {
    // Mock the preview API
    await page.route('**/api/preview/**', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payload: {
            name: 'Premium Coffee Beans',
            tags: ['coffee', 'vibe']
          }
        })
      });
    });

    // Expand card
    await page.locator('button:has(svg.lucide-chevron-down)').first().click();
    
    // Click Preview JSON
    await page.getByText('Preview JSON').click();
    
    // Verify modal is visible
    await expect(page.getByText('Pre-flight Review')).toBeVisible();
    await expect(page.getByText('Transmission Payload')).toBeVisible();
    
    // Close modal
    await page.locator('button:has(svg.lucide-x)').click();
    await expect(page.getByText('Pre-flight Review')).not.toBeVisible();
  });

  test('should execute and remove item from queue', async ({ page }) => {
    // Mock the execute API
    await page.route('**/api/execute', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true })
      });
    });

    // Expand card
    await page.locator('button:has(svg.lucide-chevron-down)').first().click();
    
    // Click Execute & Sync
    await page.getByText('Execute & Sync').click();
    
    // Verify item is gone
    await expect(page.getByText('Premium Coffee Beans')).not.toBeVisible();
    await expect(page.getByText(/Waiting for assets to ingest/i)).toBeVisible();
  });
});

