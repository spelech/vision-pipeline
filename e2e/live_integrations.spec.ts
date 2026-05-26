import coverage from '../test-utils/playwrightCoverage';
import path from 'path';
require('dotenv').config({ path: '.env.remote' });

const { test, expect } = coverage;

test.describe('Live Integrations E2E', () => {
  test('Complete End-to-End Flow with Mealie and Homebox', async ({ page }) => {
    test.setTimeout(180000); 
    await page.goto('/');

    await page.getByRole('button', { name: "system", exact: true }).click();
    await expect(page.getByText('System Settings')).toBeVisible();

    await page.getByPlaceholder('Enter OPENROUTER API KEY').fill(process.env.OPENROUTER_API_KEY || '');
    await page.getByPlaceholder('owner/model-name').fill('openai/gpt-4o-mini');
    
    await page.getByRole('button', { name: "Add", exact: true }).click();
    await expect(page.getByText('gpt-4o-mini')).toBeVisible();

    page.once('dialog', async dialog => {
      await dialog.accept();
    });
    await page.getByRole('button', { name: /Apply Full Configuration/i }).click();
    await page.waitForTimeout(500);

    await page.getByRole('button', { name: "pipelines", exact: true }).click();
    await expect(page.getByText('Pipeline Builder')).toBeVisible();
    await page.getByRole('button', { name: "Create Custom", exact: true }).click();
    await expect(page.getByText('Pipeline Architecture')).toBeVisible();

    await page.getByRole('button', { name: "+ mealie", exact: true }).click();
    await page.getByRole('button', { name: "+ homebox", exact: true }).click();

    page.once('dialog', async dialog => {
      await dialog.accept();
    });
    await page.getByRole('button', { name: "Persist Registry", exact: true }).click();
    await page.waitForTimeout(500);

    await page.getByRole('button', { name: "identify", exact: true }).click();
    await expect(page.getByText('Identify Asset')).toBeVisible();

    // Try setting the file natively without clicking to avoid flakiness with click/file choosers combinations
    await page.locator('input[type="file"]').first().setInputFiles(path.join(__dirname, '../data/uploads/sriracha.png'));

    await expect(page.getByText('Review Queue')).toBeVisible({ timeout: 60000 });
  });
});
