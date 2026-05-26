import coverage from '../test-utils/playwrightCoverage';
import path from 'path';

const { test, expect } = coverage;

test.describe('Vision Pipeline E2E', () => {
  test('Complete End-to-End Flow', async ({ page }) => {
    // Increase overall timeout in case navigation or LLM processing takes time
    test.setTimeout(90000);

    // 1. Visit the app
    await page.goto('/');
    
    // Debugging: let's verify if the UI is completely rendered by waiting for a specific base element
    await expect(page.getByRole('heading', { name: /VisionPipeline/i })).toBeVisible({ timeout: 15000 });

    // 2. Setup Configuration First!
    // Adding console log listening for any React/Vite errors
    page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
    page.on('pageerror', exception => console.log(`BROWSER ERROR: "${exception}"`));

    // Wait for the button
    const systemBtn = page.getByRole('button', { name: "system", exact: true });
    await expect(systemBtn).toBeVisible({ timeout: 10000 });
    await systemBtn.click();
    
    await expect(page.getByText('System Settings')).toBeVisible({ timeout: 10000 });

    // Add model
    await page.fill('input[placeholder="owner/model-name"]', 'test-model');
    await page.getByRole('button', { name: 'Add', exact: true }).click();
    await expect(page.getByText('test-model')).toBeVisible();

    // Fill API details
    await page.fill('input[placeholder="Enter OPENROUTER API KEY"]', 'dummy-test-key');

    // Save Configuration
    page.once('dialog', async dialog => {
      await dialog.accept();
    });
    await page.getByRole('button', { name: /Apply Full Configuration/i }).click();
    await page.waitForTimeout(1000);

    // 4. Test Ingestion
    await page.getByRole('button', { name: "identify", exact: true }).click();
    await expect(page.getByText('Identify Asset')).toBeVisible();

    // Upload an image
    await page.locator('input[type="file"]').first().setInputFiles(path.join(__dirname, '../data/uploads/sriracha.png'));

    // Wait for Review Queue
    await expect(page.getByText('Review Queue')).toBeVisible({ timeout: 65000 });
  });
});
