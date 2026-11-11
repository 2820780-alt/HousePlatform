const { chromium } = require('playwright');
const { randomUUID } = require('node:crypto');

const base = 'http://127.0.0.1:18080';

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1672, height: 941 } });
    const marker = `QA material ${randomUUID()}`;
    const created = await page.request.post(`${base}/api/v1/admin/materials`, {
      data: { canonical_name: marker },
    });
    if (created.status() !== 201) throw new Error(`QA creation failed: HTTP ${created.status()}`);
    const material = await created.json();
    const updated = await page.request.put(`${base}/api/v1/admin/materials/${material.id}`, {
      data: { description: 'QA-only update' },
    });
    if (!updated.ok() || (await updated.json()).id !== material.id) throw new Error('QA update changed the material ID');
    await page.goto(`${base}/api/v1/admin/material-hub/view/materials?preset=needs_price`, {
      waitUntil: 'networkidle', timeout: 60000,
    });
    await page.locator('#material-search').fill(marker);
    const row = page.locator('#material-table tbody tr').filter({ hasText: marker });
    await row.waitFor({ state: 'visible', timeout: 10000 });
    await row.getByRole('button', { name: 'Открыть карточку материала' }).click();
    await page.locator('#material-details-dialog[aria-hidden="false"]').waitFor();
    await page.screenshot({ path: 'qa-materials-ui/screenshots/baseline-card-1672.png' });
    console.log('QA-only create/update retained ID; no-price item opened in the current UI.');
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error.message); process.exitCode = 1; });
