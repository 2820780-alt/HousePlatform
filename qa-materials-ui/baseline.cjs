const { chromium } = require('playwright');
const path = require('node:path');
const fs = require('node:fs');

const base = 'http://127.0.0.1:18080';
const output = path.join(__dirname, 'screenshots');
const sizes = [[1672, 941], [1440, 941], [1280, 941], [768, 941], [390, 844]];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    for (const [width, height] of sizes) {
      const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
      const response = await page.goto(`${base}/api/v1/admin/material-hub/view/materials?preset=needs_price`, {
        waitUntil: 'networkidle', timeout: 60000,
      });
      if (!response || response.status() !== 200 || !(await page.locator('#material-table').count())) {
        throw new Error(`QA material catalogue did not load at ${width}px`);
      }
      await page.screenshot({ path: path.join(output, `baseline-${width}.png`) });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      console.log(`${width}x${height}: HTTP ${response.status()}, global overflow ${overflow}`);
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error.message); process.exitCode = 1; });
