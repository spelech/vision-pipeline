import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

test.describe('Vision Pipeline Integration', () => {
  // These tests require a running backend at localhost:8000
  // and images in data/uploads/ for the frontend to show them.
  
  test.beforeEach(async ({ page }) => {
    // Check if backend is reachable
    try {
      const response = await page.request.get('http://localhost:8000/health');
      if (!response.ok()) {
        test.skip(true, 'Backend not reachable');
      }
    } catch {
      test.skip(true, 'Backend not reachable');
    }
    
    await page.goto('/');
  });

  test('should upload an image and appear in queue', async ({ page }) => {
    // 1. Go to Identify tab
    await page.getByRole('link', { name: 'Identify' }).click();
    await expect(page.getByText('Identify Asset')).toBeVisible();

    // 2. Upload a predefined image
    // Using an existing image from the repo for this test
    const imagePath = path.resolve(__dirname, '../../data/uploads/raw_9940b71b-4565-4014-8e1c-6fe79ea5febf.jpg');
    
    if (!fs.existsSync(imagePath)) {
      console.warn('Test image not found, skipping upload test');
      return;
    }

    await page.locator('input[type="file"]').setInputFiles(imagePath);

    // 3. The app should switch to Review tab automatically
    await expect(page.getByText('Review Queue')).toBeVisible({ timeout: 15000 });

    // 4. Verify something appeared (might take a moment for LLM processing)
    // We expect the backend to process the image and add it to the DB
    await expect(page.locator('.glass.rounded-\\[2rem\\]')).first().toBeVisible({ timeout: 30000 });
  });

  test('should allow editing and executing an asset', async ({ page }) => {
    // This test assumes there is already something in the queue
    await page.getByRole('link', { name: 'Review' }).click();
    
    const cardCount = await page.locator('.glass.rounded-\\[2rem\\]').count();
    if (cardCount === 0) {
      test.skip(true, 'Queue is empty, cannot test edit/execute');
    }

    // Expand the first card
    const firstCard = page.locator('.glass.rounded-\\[2rem\\]').first();
    await firstCard.locator('button:has(svg.lucide-chevron-down)').click();

    // Edit a field
    const brandInput = page.getByLabel('Brand');
    const originalValue = await brandInput.inputValue();
    await brandInput.fill(originalValue + ' Edited');

    // Click Execute & Sync
    await page.getByText('Execute & Sync').click();

    // Verify it's gone or loading
    // In a real integration test, we'd check the DB or success toast
    await expect(page.getByText('Syncing to services...')).toBeVisible();
  });
});
