import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Vision Pipeline E2E', () => {
  test('Complete End-to-End Flow', async ({ page }) => {
    test.setTimeout(75000);

    // 1. Visit the app
    await page.goto('/');

    // 2. Setup Configuration First!
    await page.click('button:has-text("system")');
    await expect(page.getByText('System Settings')).toBeVisible();

    // Add model
    await page.fill('input[placeholder="owner/model-name"]', 'test-model');
    await page.click('button:has-text("Add")');
    await expect(page.getByText('test-model')).toBeVisible();

    // Fill API details
    await page.fill('input[placeholder="Enter OPENROUTER API KEY"]', 'dummy-test-key');

    // Save Configuration
    page.once('dialog', async dialog => {
      await dialog.accept();
    });
    await page.click('button:has-text("Apply Full Configuration")');
    await page.waitForTimeout(1000);

    // 4. Test Ingestion
    await page.click('button:has-text("identify")');
    await expect(page.getByText('Identify Asset')).toBeVisible();

    // Select the model we just added in the combobox
    

    // Upload an image
    await page.locator('input.cursor-pointer[type="file"]').setInputFiles(path.join(__dirname, '../data/uploads/sriracha.png'));

    // Wait for Review Queue
    await expect(page.getByText('Review Queue')).toBeVisible({ timeout: 65000 });
  });
});
