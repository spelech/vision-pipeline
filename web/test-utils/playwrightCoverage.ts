import fs from 'node:fs/promises';
import path from 'node:path';

import { expect, test as base } from '@playwright/test';


function sanitizeFileName(value: string): string {
  return value.replace(/[^a-zA-Z0-9._-]+/g, '_');
}

export { expect };

export const test = base.extend({
  page: async ({ page, browserName }, use, testInfo) => {
    const collectCoverage = process.env.PW_COLLECT_COVERAGE === '1' && browserName === 'chromium';

    if (!collectCoverage) {
      await use(page);
      return;
    }

    await page.coverage.startJSCoverage({ resetOnNavigation: false, reportAnonymousScripts: false });

    await use(page);

    const coverage = await page.coverage.stopJSCoverage();
    const coverageDir = path.resolve(process.cwd(), 'coverage', 'playwright');
    const titlePath = [...testInfo.titlePath, browserName].join('__');
    const outputFile = path.join(coverageDir, `${sanitizeFileName(titlePath)}.json`);

    await fs.mkdir(coverageDir, { recursive: true });
    await fs.writeFile(outputFile, JSON.stringify(coverage, null, 2), 'utf8');
  },
});

export default { test, expect };