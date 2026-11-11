const { chromium } = require('playwright');
const root = 'http://127.0.0.1:18080/api/v1/admin/material-hub/view/materials';

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1672, height: 941 } });
    const url = new URL(root); url.searchParams.set('q', 'QA изолированный материал B25');
    await page.goto(url.href, { waitUntil: 'networkidle' });
    const row = page.locator('.catalog-table tbody tr').filter({ hasText: 'QA изолированный материал B25' });
    await row.waitFor();
    if (!(await row.innerText()).includes('58,00 ₽')) throw new Error('Tonne to kg price is incorrect');
    await row.locator('[data-select-material]').click();
    const detail = page.locator('.catalog-detail');
    if (await detail.locator('.offers-table tbody tr').count() !== 3) throw new Error('Expected three original QA offers');
    if (!(await detail.innerText()).includes('Не рассчитано')) throw new Error('Pallet was incorrectly converted');
    const external = detail.locator('a[href="https://example.test/material-1"]');
    if (await external.count() !== 2) throw new Error('Offer name or original source URL missing');
    await detail.getByRole('link', { name: 'QA поставщик 1' }).click();
    await page.getByRole('heading', { name: 'QA поставщик 1' }).waitFor();
    await page.goBack({ waitUntil: 'networkidle' });
    await page.getByRole('link', { name: 'QA изолированный аналог B20' }).click();
    await page.getByRole('heading', { name: 'QA изолированный аналог B20' }).waitFor();
    const ranged = new URL(root); ranged.searchParams.set('q', 'QA изолированный материал B25');
    ranged.searchParams.set('minimum', '60'); ranged.searchParams.set('maximum', '80');
    await page.goto(ranged.href, { waitUntil: 'networkidle' });
    if (!(await page.locator('.catalog-table tbody').innerText()).includes('70,00 ₽')) throw new Error('Range price does not reflect the selected offers');
    console.log('QA offers: suppliers, source, analog, safe conversion and price range PASS');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
