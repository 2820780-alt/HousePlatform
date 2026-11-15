const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(__dirname, 'browsers');
const { chromium } = require('playwright');

const base = 'http://127.0.0.1:18002';
const destination = '/api/v1/admin/vertical-m1/works';
const credentials = { email: `qa-${crypto.randomBytes(12).toString('hex')}@example.invalid`,
  password: crypto.randomBytes(24).toString('hex'), view_only: false };
const fixture = spawnSync('docker', ['exec', '-i', 'houseplatform-vertical-qa-20261113',
  'python', 'qa-materials-ui/vertical_auth_fixture.py'],
  { input: JSON.stringify(credentials), encoding: 'utf8' });
if (fixture.status !== 0) throw new Error('Could not create isolated QA login');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 941 } });
      await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
      await page.locator('#email').fill(credentials.email);
      await page.locator('#password').fill(credentials.password);
      await Promise.all([page.waitForURL(url => url.pathname === destination, { timeout: 60000 }),
        page.locator('#login-submit').click()]);
      if (!await page.locator('[data-module1-tab="work-costs"]').count())
        throw new Error(`Work navigation missing; page title: ${await page.title()}`);
      if (await page.locator('[data-module1-tab="work-costs"]').innerText() !== 'Работы')
        throw new Error('Work navigation missing');
      const name = `QA work ${crypto.randomBytes(8).toString('hex')}`;
      await page.getByRole('button', { name: '+ Добавить работу' }).click();
      await page.locator('#work-edit input[name="name"]').fill(name);
      await Promise.all([page.waitForURL(url => url.pathname.startsWith(`${destination}/`)),
        page.locator('#work-edit button[type="submit"]').click()]);
      if (!await page.getByRole('heading', { name, exact: true }).count())
        throw new Error('Created work card missing');
      await page.getByRole('button', { name: 'Редактировать работу' }).click();
      await page.locator('#work-edit textarea[name="description"]').fill('QA edit');
      await page.locator('#work-edit button[type="submit"]').click();
      await page.locator('section.work-panel > p').filter({ hasText: /^QA edit$/ }).waitFor({ timeout: 30000 });
      await page.locator('details summary').click();
      const price = page.locator('details form');
      await price.locator('[name="region"]').fill('QA region');
      await price.locator('[name="terms"]').fill('QA terms');
      await price.locator('[name="amount"]').fill('1234');
      await price.getByRole('button', { name: 'Сохранить цену' }).click();
      await page.getByText('Ручная резервная цена', { exact: true }).waitFor({ timeout: 30000 });
      if (width === 1440) {
        const region = `QA-${crypto.randomBytes(8).toString('hex')}`;
        await page.goto(`${base}/api/v1/admin/material-hub/view/work-costs`);
        await page.locator('#add-work-cost-button').click();
        await page.locator('#offer-work').selectOption('foundations_concrete_betonirovanie_konstrukciy');
        await page.locator('#offer-region').fill(region);
        await page.locator('#offer-fixed').fill('1234');
        const form = page.locator('#work-cost-form');
        const [created] = await Promise.all([
          page.waitForResponse(response => response.url().endsWith('/work-cost-offers') && response.request().method() === 'POST'),
          form.getByRole('button', { name: 'Сохранить черновик' }).click(),
        ]);
        if (!created.ok()) throw new Error(`Offer creation failed: ${created.status()}`);
        const offer = await created.json();
        await page.locator('#work-cost-search').fill(region);
        const row = page.locator('#work-cost-body tr').filter({ hasText: region });
        await row.getByRole('button', { name: 'Редактировать' }).click();
        await page.locator('#offer-fixed').fill('1500');
        const [edited] = await Promise.all([
          page.waitForResponse(response => response.url().endsWith(`/work-cost-offers/${offer.id}`) && response.request().method() === 'PUT'),
          form.getByRole('button', { name: 'Сохранить', exact: true }).click(),
        ]);
        if (!edited.ok() || Number((await edited.json()).fixedAmount) !== 1500)
          throw new Error('Offer edit failed');
        page.once('dialog', dialog => dialog.accept());
        const [deactivated] = await Promise.all([
          page.waitForResponse(response => response.url().endsWith(`/work-cost-offers/${offer.id}/deactivate`) && response.request().method() === 'POST'),
          row.getByRole('button', { name: 'Деактивировать' }).click(),
        ]);
        if (!deactivated.ok() || (await deactivated.json()).status !== 'inactive')
          throw new Error('Offer deactivation failed');
      }
      await page.goto(`${base}${destination}`);
      await page.locator('input[name="q"]').fill('Бетонирование');
      await page.getByRole('button', { name: 'Применить' }).click();
      const item = page.locator('.work-table tbody a').first();
      if (!await item.count()) throw new Error('Search returned no work');
      await item.click();
      if (!await page.getByRole('heading', { name: 'Основные данные' }).count())
        throw new Error('Work card missing');
      await page.getByRole('button', { name: 'Редактировать работу' }).click();
      if (!await page.locator('#work-edit input[name="name"]').isVisible())
        throw new Error('Edit form missing');
      await page.getByText('К работам', { exact: false }).click();
      if (await page.locator('input[name="q"]').inputValue() !== 'Бетонирование')
        throw new Error('Catalog search was not preserved');
      await page.screenshot({ path: path.join(__dirname, `fnd3-works-${width}.png`), fullPage: true });
      await page.close();
    }
    process.stdout.write('FND-3 work catalog desktop/mobile smoke: PASS\n');
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
