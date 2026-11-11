const { chromium } = require('playwright');
const path = require('node:path');
const base = 'http://127.0.0.1:18081/api/v1/admin/material-hub/view/materials';

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [1672, 1440, 1280, 768, 390]) {
      const page = await browser.newPage({ viewport: { width, height: width === 390 ? 844 : 941 } });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const url = new URL(base);
      url.searchParams.set('preset', 'without_price');
      url.searchParams.set('q', 'БСТ');
      const response = await page.goto(url.href, { waitUntil: 'networkidle' });
      if (!response || response.status() !== 200) throw new Error('Catalogue unavailable');
      if (!(await page.locator('.catalog-table').innerText()).includes('БСТ')) throw new Error('Concrete profiles missing');
      if (await page.locator('.catalog-detail').count()) throw new Error('Unexpected empty detail panel');
      await page.locator('[data-select-material]').first().click();
      if (!(await page.locator('.catalog-detail').innerText()).includes('Технические характеристики')) throw new Error('Characteristics missing');
      if (await page.locator('.catalog-panel').count()) throw new Error('Catalogue present on detail page');
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Global overflow');
      await page.screenshot({ path: path.join(__dirname, 'screenshots', `foundation-detail-${width}.png`) });
      if (width === 1672) {
        const detailUrl = page.url();
        await page.locator('[data-edit-material]').click();
        await page.locator('#editor-description').fill('Профиль для проверки на изолированной базе.');
        await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }), page.getByRole('button', { name: 'Сохранить' }).click()]);
        await page.reload({ waitUntil: 'networkidle' });
        if (page.url() !== detailUrl || !(await page.locator('.catalog-detail').innerText()).includes('Профиль для проверки')) throw new Error('Material editing did not retain its ID');
      }
      await page.locator('[data-back]').click();
      if (new URL(page.url()).searchParams.get('q') !== 'БСТ' || new URL(page.url()).searchParams.get('preset') !== 'without_price') throw new Error('Filters not preserved');
      if (errors.length) throw new Error(errors.join('; '));
      console.log(`${width}: foundation card and filter return PASS`);
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
