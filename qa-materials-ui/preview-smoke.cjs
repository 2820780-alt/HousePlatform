const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

const base = 'http://127.0.0.1:18080';
const output = path.join(__dirname, 'screenshots');
const sizes = [[1672, 941], [1440, 941], [1280, 941], [768, 941], [390, 844]];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    for (const [width, height] of sizes) {
      const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const response = await page.goto(`${base}/api/v1/admin/material-hub/view/materials`, {
        waitUntil: 'networkidle', timeout: 60000,
      });
      if (!response || response.status() !== 200) throw new Error(`Preview HTTP failed at ${width}px`);
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error(`Global overflow at ${width}px`);
      await page.screenshot({ path: path.join(output, `preview-${width}.png`) });
      const links = page.locator('[data-select-material]');
      if (await links.count() > 1) {
        const label = await links.nth(1).innerText();
        await links.nth(1).click();
        await page.waitForFunction(text => document.querySelector('.catalog-detail h2')?.textContent.trim() === text.trim(), label);
        if (!/\/materials\/[^/]+$/.test(new URL(page.url()).pathname)) throw new Error('Dedicated material URL was not retained');
        if (await page.locator('.catalog-panel').count()) throw new Error('Catalogue still appears on the detail page');
        await page.screenshot({ path: path.join(output, `detail-${width}.png`) });
        await page.locator('[data-back]').click();
        if (!(await page.locator('.catalog-panel').isVisible())) throw new Error('Return did not restore catalogue');
      }
      if (errors.length) throw new Error(errors.join('; '));
      if (width === 1672 && await page.locator('.pagination a').filter({ hasText: 'Вперёд' }).count()) {
        const first = await page.locator('.catalog-table tbody tr').first().getAttribute('data-material-id');
        await page.locator('.pagination a').filter({ hasText: 'Вперёд' }).click();
        if ((await page.locator('.catalog-table tbody tr').first().getAttribute('data-material-id')) === first) throw new Error('Pagination did not change the page');
      }
      console.log(`${width}x${height}: layout and selection PASS`);
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
