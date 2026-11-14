const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(__dirname, 'browsers');
const { chromium } = require('playwright');

const base = 'http://127.0.0.1:18002';
const technology = process.argv[2];
const targetTechnology = process.argv[3];
const output = path.join(__dirname, 'vertical-screenshots');
if (!/^[0-9a-f-]{36}$/.test(technology || '')) throw new Error('QA technology ID required');
if (!/^[0-9a-f-]{36}$/.test(targetTechnology || '')) throw new Error('Second QA technology ID required');
fs.mkdirSync(output, { recursive: true });

function createQaLogin(viewOnly = false) {
  const credentials = { email: `qa-${crypto.randomBytes(12).toString('hex')}@example.invalid`,
                        password: crypto.randomBytes(24).toString('hex'), view_only: viewOnly };
  const result = spawnSync('docker', ['exec', '-i', 'houseplatform-vertical-qa-20261113',
                                      'python', 'qa-materials-ui/vertical_auth_fixture.py'],
                           { input: JSON.stringify(credentials), encoding: 'utf8' });
  if (result.status !== 0) throw new Error('Failed to create isolated QA login');
  return credentials;
}

async function login(page, credentials, destination) {
  await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
  await page.locator('#email').fill(credentials.email);
  await page.locator('#password').fill(credentials.password);
  await Promise.all([page.waitForURL(url => url.pathname === destination, { timeout: 60000 }),
                     page.locator('#login-submit').click()]);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const credentials = createQaLogin();
    const page = await browser.newPage({ viewport: { width: 1440, height: 941 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const marker = Date.now().toString();
    await login(page, credentials, '/api/v1/admin/vertical-m1/works');
    const csrfStatus = await page.evaluate(async () => (await fetch('/api/v1/admin/vertical-m1/works/save', {
      method: 'POST', credentials: 'same-origin', body: new FormData(),
    })).status);
    if (csrfStatus !== 403) throw new Error('Missing CSRF token was not rejected');
    await page.locator('input[name=name]').fill(`QA work ${marker}`);
    await page.locator('select[name=unit]').selectOption('m3');
    await page.getByRole('button', { name: 'Сохранить' }).first().click();
    await page.waitForURL(/\/works\/manual_/);
    const work = new URL(page.url()).pathname.split('/').pop();
    await page.getByRole('link', { name: 'Цена для расчёта' }).click();
    let form = page.locator('form[method=post]').first();
    await form.locator('[name=region]').fill('QA region');
    await form.locator('[name=terms]').fill('QA terms');
    await form.locator('[name=amount]').fill('500');
    await form.getByRole('button', { name: 'Сохранить' }).click();
    await page.waitForURL(/region=/);
    if (!(await page.locator('body').innerText()).includes('500')) throw new Error('Work price missing');

    await page.goto(`${base}/api/v1/admin/material-hub/view/materials`, { waitUntil: 'networkidle' });
    await page.locator('[data-add-material]').click();
    await page.locator('#editor-name').fill(`QA vertical concrete ${marker}`);
    await page.locator('#editor-category').selectOption({ label: 'Бетон, цемент и растворы' });
    const unit = await page.locator('#editor-base-unit option').evaluateAll(options =>
      options.find(o => o.value && /\((м³|м3|m3)\)/i.test(o.textContent))?.value);
    if (!unit) throw new Error('Cubic metre unit unavailable in QA');
    await page.locator('#editor-base-unit').selectOption(unit);
    await page.locator('#editor-form button[type=submit]').click();
    await page.waitForURL(/\/materials\/[^/?]+/, { timeout: 60000 });
    const material = new URL(page.url()).pathname.split('/').pop();
    await page.getByRole('link', { name: 'Цена для расчёта' }).click();
    form = page.locator('form[method=post]').first();
    await form.locator('[name=region]').fill('QA region');
    await form.locator('[name=terms]').fill('QA terms');
    await form.locator('[name=amount]').fill('1000');
    await form.getByRole('button', { name: 'Сохранить' }).click();
    await page.waitForURL(/region=/);
    const materialPrice = page.url();
    for (const [supplier, amount] of [['QA vertical supplier 1', '1200'], ['QA vertical supplier 2', '1400']]) {
      form = page.locator('form[action$="/offers"]');
      await form.locator('[name=supplier_id]').selectOption({ label: supplier });
      await form.locator('[name=amount]').fill(amount);
      await form.locator('[name=confirmed]').check();
      await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                         form.getByRole('button', { name: 'Добавить предложение' }).click()]);
    }
    if (!(await page.locator('body').innerText()).includes('1300')) throw new Error('Offer average is incorrect');

    const workbench = `${base}/api/v1/admin/module2/workbench/${technology}`;
    await page.goto(`${workbench}?tab=materials`, { waitUntil: 'networkidle' });
    await page.getByText('Добавить требование', { exact: true }).click();
    form = page.locator('form[action$="/save-requirement"]').filter({ hasNot: page.locator('[name="item_id"]') });
    await form.locator('[name=code]').fill('QA_MATERIAL');
    await form.locator('[name=selector_kind]').selectOption('CANONICAL_MATERIAL');
    await form.locator('[name=canonical_material_id]').selectOption(material);
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                       form.getByRole('button', { name: 'Добавить' }).click()]);
    if (await page.getByRole('alert').count()) throw new Error('M2 material role could not be created');
    await page.goto(`${workbench}?tab=works`, { waitUntil: 'networkidle' });
    await page.getByText('Добавить работу из Work Catalog M1', { exact: true }).click();
    form = page.locator('form[action$="/save-work-step"]').filter({ hasNot: page.locator('[name="item_id"]') });
    await form.locator('[name=work_code]').selectOption(work);
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                       form.getByRole('button', { name: 'Добавить' }).click()]);
    if (await page.getByRole('alert').count()) throw new Error('M2 work step could not be created');

    const builder = `${base}/api/v1/admin/module2/calculation-builder/${technology}`;
    await page.goto(builder, { waitUntil: 'networkidle' });
    form = page.locator('form[action$="/add"]');
    await form.locator('[name=material_id]').selectOption(material);
    await form.locator('[name=work_code]').selectOption(work);
    await form.locator('[name=material_requirement_id]').selectOption({ index: 1 });
    await form.locator('[name=work_step_id]').selectOption({ index: 1 });
    await form.getByRole('button', { name: 'Добавить блок' }).click();
    await page.waitForLoadState('networkidle');
    if (await page.getByRole('alert').count()) throw new Error('Block creation failed');
    await page.getByText('1. Объём конструкции', { exact: true }).click();
    const sourceId = await page.locator('form[action$="/update"] input[name=block_id]').first().inputValue();
    const templateName = `QA template ${marker}`;
    form = page.locator('form[action$="/save-template"]').first();
    await form.locator('[name=template_name]').fill(templateName);
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                       form.getByRole('button', { name: 'Сохранить как шаблон' }).click()]);
    const targetBuilder = `${base}/api/v1/admin/module2/calculation-builder/${targetTechnology}`;
    await page.goto(targetBuilder, { waitUntil: 'networkidle' });
    const library = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Добавить из библиотеки' }) });
    const chosenTemplate = library.locator('details').filter({ hasText: templateName }).first();
    await chosenTemplate.locator('summary').click();
    form = chosenTemplate.locator('form[action$="/copy-template"]');
    for (const part of ['length', 'width', 'height']) await form.locator(`[name="mapping.geometry.${part}"]`).selectOption(`geometry.${part}`);
    await form.locator('[name=material_id]').selectOption(material);
    await form.locator('[name=work_code]').selectOption(work);
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                       form.getByRole('button', { name: 'Добавить копию' }).click()]);
    await page.getByText(`1. ${templateName}`, { exact: true }).click();
    form = page.locator('form[action$="/update"]').first();
    await form.locator('[name="default.geometry.width"]').fill('0.75');
    await form.locator('[name="source.geometry.width"]').fill('QA only');
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                       form.getByRole('button', { name: 'Сохранить' }).click()]);
    await page.getByText(`1. ${templateName}`, { exact: true }).click();
    form = page.locator('form[action$="/save-template"]').first();
    await form.locator('[name=template_name]').fill(templateName);
    await form.locator('[name=template_key]').selectOption({ label: `${templateName} · № 1` });
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                       form.getByRole('button', { name: 'Сохранить как шаблон' }).click()]);
    await page.getByRole('link', { name: 'Предварительный расчёт' }).click();
    form = page.locator('form[method=post]');
    for (const [name, value] of Object.entries({ name: `QA copy ${marker}`, length_m: '10', width_m: '0,5',
                                                height_m: '1', region: 'QA region', terms: 'QA terms' }))
      await form.locator(`[name="${name}"]`).fill(value);
    const copyScopes = form.locator('input[name^="scope."]');
    for (let i = 0; i < await copyScopes.count(); i++) await copyScopes.nth(i).fill(`QA copy role ${i}`);
    await Promise.all([page.waitForURL(/snapshot=/, { timeout: 60000 }),
                       form.getByRole('button', { name: 'Рассчитать' }).click()]);
    if (!(await page.locator('body').innerText()).includes('9000.00')) throw new Error('Copied technology calculation failed');
    await page.goto(targetBuilder, { waitUntil: 'networkidle' });
    const direct = page.locator('form[action$="/copy-technology"]').filter({
      has: page.locator(`input[name="source_id"][value="${sourceId}"]`),
    });
    await direct.locator('xpath=..').locator('summary').click();
    for (const part of ['length', 'width', 'height']) await direct.locator(`[name="mapping.geometry.${part}"]`).selectOption(`geometry.${part}`);
    await direct.locator('[name=material_id]').selectOption(material);
    await direct.locator('[name=work_code]').selectOption(work);
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                       direct.getByRole('button', { name: 'Добавить копию' }).click()]);
    if (!(await page.getByText('2. Объём конструкции', { exact: true }).count())) throw new Error('Technology copy missing');
    await page.getByText(`1. ${templateName}`, { exact: true }).click();
    if (await page.locator('form[action$="/update"]').first().locator('[name="default.geometry.width"]').inputValue() !== '0.75')
      throw new Error('Template update changed the existing copy');
    await page.goto(builder, { waitUntil: 'networkidle' });
    await page.getByText('1. Объём конструкции', { exact: true }).click();
    if (await page.locator('form[action$="/update"]').first().locator('[name="default.geometry.width"]').inputValue())
      throw new Error('Editing the target changed the source');
    await page.screenshot({ path: path.join(output, 'builder-1440.png'), fullPage: true });
    await page.getByRole('link', { name: 'Предварительный расчёт' }).click();
    form = page.locator('form[method=post]');
    await form.locator('[name=name]').fill(`QA object ${marker}`);
    await form.locator('[name=length_m]').fill('10');
    await form.locator('[name=width_m]').fill('0,4');
    await form.locator('[name=height_m]').fill('1');
    await form.locator('[name=region]').fill('QA region');
    await form.locator('[name=terms]').fill('QA terms');
    const scopes = form.locator('input[name^="scope."]');
    for (let i = 0; i < await scopes.count(); i++) await scopes.nth(i).fill(`QA role ${i}`);
    await form.getByRole('button', { name: 'Рассчитать' }).click();
    await page.waitForURL(/snapshot=/, { timeout: 60000 });
    if (!(await page.locator('body').innerText()).includes('7200.00')) throw new Error('First total is incorrect');
    await page.screenshot({ path: path.join(output, 'estimate-1440.png'), fullPage: true });
    await page.locator('[name=width_m]').fill('0,5');
    await page.getByRole('button', { name: 'Пересчитать' }).click();
    await page.waitForFunction(() => document.body.innerText.includes('9000.00'), null, { timeout: 60000 });
    const estimate = page.url();
    await page.goto(materialPrice, { waitUntil: 'networkidle' });
    for (let i = 0; i < 2; i++) {
      page.once('dialog', dialog => dialog.accept());
      await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                         page.getByRole('button', { name: 'Исключить из расчёта' }).first().click()]);
    }
    if (!(await page.locator('body').innerText()).includes('ручная резервная')) throw new Error('Manual fallback missing');
    await page.goto(estimate, { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'Пересчитать' }).click();
    await page.waitForFunction(() => document.body.innerText.includes('7500.00'), null, { timeout: 60000 });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, 'estimate-390.png'), fullPage: true });
    await page.setViewportSize({ width: 1440, height: 941 });
    await page.goto(builder, { waitUntil: 'networkidle' });
    form = page.locator('form[action$="/add"]');
    await form.locator('[name=preset]').selectOption('reinforcement');
    await form.locator('summary').click();
    for (const [name, value] of Object.entries({
      'range.0.lower': '350', 'range.0.upper': '500', 'range.0.count': '3',
      'range.1.lower': '500', 'range.1.upper': '501', 'range.1.count': '4', rule_source: 'QA only',
    })) await form.locator(`[name="${name}"]`).fill(value);
    await form.locator('[name="range.1.inclusive"]').check();
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                       form.getByRole('button', { name: 'Добавить блок' }).click()]);
    await page.getByText('2. Продольная арматура', { exact: true }).click();
    form = page.locator('form[action$="/update"]').filter({ has: page.locator('input[value="Продольная арматура"]') });
    for (const [key, value] of Object.entries({
      'reinforcement.cover': '40', 'reinforcement.diameter': '12', 'reinforcement.min_spacing': '100',
      'reinforcement.max_spacing': '200', 'reinforcement.lap_length': '0.5', 'reinforcement.joints': '2',
      'material.mass_per_m': '0.888',
    })) {
      await form.locator(`[name="default.${key}"]`).fill(value);
      await form.locator(`[name="source.${key}"]`).fill('QA only');
    }
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle' }),
                       form.getByRole('button', { name: 'Сохранить' }).click()]);
    await page.getByRole('link', { name: 'Предварительный расчёт' }).click();
    form = page.locator('form[method=post]');
    for (const [name, value] of Object.entries({ name: `QA rebar ${marker}`, length_m: '10', width_m: '0,35',
                                                height_m: '1', region: 'QA region', terms: 'QA terms' }))
      await form.locator(`[name="${name}"]`).fill(value);
    const rebarScopes = form.locator('input[name^="scope."]');
    for (let i = 0; i < await rebarScopes.count(); i++) await rebarScopes.nth(i).fill(`QA scope ${i}`);
    await form.getByRole('button', { name: 'Рассчитать' }).click();
    await page.waitForURL(/snapshot=/, { timeout: 60000 });
    if (!(await page.locator('body').innerText()).includes('27,528')) throw new Error('Rebar quantity for 350 mm is incorrect');
    await page.locator('[name=width_m]').fill('0,5');
    await page.getByRole('button', { name: 'Пересчитать' }).click();
    await page.waitForFunction(() => document.body.innerText.includes('36,408'), null, { timeout: 60000 });
    await page.screenshot({ path: path.join(output, 'reinforcement-1440.png'), fullPage: true });
    if (errors.length) throw new Error(errors.join('; '));
    const readOnly = await browser.newPage();
    await login(readOnly, createQaLogin(true), '/api/v1/module2');
    const denied = await readOnly.goto(builder);
    if (!denied || denied.status() !== 403) throw new Error('VIEW account accessed the calculation editor');
    await readOnly.close();
    console.log('QA browser: work, material, two offers, average, fallback, concrete and reinforcement PASS');
    console.log('QA browser: template versioning, cross-technology copy and independent settings PASS');
    console.log('QA browser: explicit M2 material role and work step linked to the block PASS');
    console.log('QA browser: real login, missing CSRF rejection and VIEW denial PASS');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
