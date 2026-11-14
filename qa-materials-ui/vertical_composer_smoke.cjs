const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(__dirname, 'browsers');
const { chromium } = require('playwright');

const technology = process.argv[2];
if (!/^[0-9a-f-]{36}$/.test(technology || '')) throw new Error('QA technology ID required');
const credentials = { email: `qa-${crypto.randomBytes(12).toString('hex')}@example.invalid`,
  password: crypto.randomBytes(24).toString('hex'), view_only: false };
const provision = spawnSync('docker', ['exec', '-i', 'houseplatform-vertical-qa-20261113',
  'python', 'qa-materials-ui/vertical_auth_fixture.py'], { input: JSON.stringify(credentials), encoding: 'utf8' });
if (provision.status !== 0) throw new Error('Failed to create isolated QA login');
const base = 'http://127.0.0.1:18002';
const output = path.join(__dirname, 'vertical-screenshots');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 941 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const builder = `/api/v1/admin/module2/calculation-builder/${technology}`;
    await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(builder)}`);
    await page.locator('#email').fill(credentials.email);
    await page.locator('#password').fill(credentials.password);
    await Promise.all([page.waitForURL(url => url.pathname === builder), page.locator('#login-submit').click()]);
    const form = page.locator('form[action$="/compose"]');
    await form.locator('[name="name"]').fill('QA площадь');
    const first = form.locator('details').nth(0);
    await first.locator('[name="step.1.label"]').fill('Длина');
    await first.locator('[name="step.1.operation"]').selectOption('INPUT');
    await first.locator('[name="step.1.unit"]').selectOption('m');
    await first.locator('[name="step.1.source"]').selectOption('geometry.length');
    const second = form.locator('details').nth(1);
    await second.locator('summary').click();
    await second.locator('[name="step.2.label"]').fill('Ширина параметра');
    await second.locator('[name="step.2.operation"]').selectOption('INPUT');
    await second.locator('[name="step.2.unit"]').selectOption('m');
    const third = form.locator('details').nth(2);
    await third.locator('summary').click();
    await third.locator('[name="step.3.label"]').fill('Площадь');
    await third.locator('[name="step.3.operation"]').selectOption('MULTIPLY');
    await third.locator('[name="step.3.unit"]').selectOption('m2');
    await third.locator('[name="step.3.ref.1"]').selectOption('1');
    await third.locator('[name="step.3.ref.2"]').selectOption('2');
    await form.locator('[name="material_step"]').selectOption('3');
    await page.screenshot({ path: path.join(output, 'composer-1440.png'), fullPage: true });
    await Promise.all([page.waitForNavigation(), form.getByRole('button', { name: 'Создать расчёт' }).click()]);
    if (await page.getByRole('alert').count()) throw new Error('Composed block could not be saved');
    await page.getByText('1. QA площадь', { exact: true }).click();
    await page.getByText('Изменить схему расчёта', { exact: true }).click();
    const edit = page.locator('form[action$="/compose-update"]');
    await edit.locator('details').nth(1).locator('summary').click();
    await edit.locator('[name="step.2.label"]').fill('Проектная ширина');
    await Promise.all([page.waitForNavigation(), edit.getByRole('button', { name: 'Сохранить схему' }).click()]);
    if (await page.getByRole('alert').count()) throw new Error('Composed block could not be edited');
    await page.getByRole('link', { name: 'Предварительный расчёт' }).click();
    const estimate = page.locator('form[method="post"]');
    for (const [name, value] of Object.entries({ name: 'QA объект', length_m: '10', width_m: '0.5',
      height_m: '1', region: 'QA region', terms: 'QA terms' })) await estimate.locator(`[name="${name}"]`).fill(value);
    await estimate.locator('input[name^="scope."]').fill('QA площадь');
    const parameter = estimate.locator('input[name^="parameter."]');
    if (await parameter.count() !== 1) throw new Error('Missing custom parameter');
    await parameter.fill('0,4');
    await Promise.all([page.waitForURL(/snapshot=/), estimate.getByRole('button', { name: 'Рассчитать' }).click()]);
    if (!(await page.locator('body').innerText()).includes('4 m2')) throw new Error('Incorrect composed quantity');
    if (await page.locator('input[name^="parameter."]').inputValue() !== '0.4') throw new Error('Parameter not restored');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, 'composer-preview-390.png'), fullPage: true });
    if (errors.length) throw new Error(errors.join('; '));
    console.log('QA browser: custom composition, scoped parameter and snapshot PASS');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
