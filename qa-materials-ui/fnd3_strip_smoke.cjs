const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(__dirname, 'browsers');
const { chromium } = require('playwright');

const base = 'http://127.0.0.1:18002';
const technology = '92bd1515-a232-4c07-a4eb-663efebc78bc';
const destination = `/api/v1/admin/vertical-preview/${technology}`;
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
      const region = `qa-${crypto.randomBytes(8).toString('hex')}`;
      const terms = 'qa test only';
      await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
      await page.locator('#email').fill(credentials.email);
      await page.locator('#password').fill(credentials.password);
      await Promise.all([page.waitForURL(url => url.pathname === destination, { timeout: 60000 }),
        page.locator('#login-submit').click()]);
      await page.locator('[name="name"]').fill(`QA strip ${width}`);
      for (const [name, value] of Object.entries({ length_m: '12', width_m: '0.4', height_m: '0.8', region, terms }))
        await page.locator(`[name="${name}"]`).fill(value);
      const params = {
        'strip.overlap_volume': '0.2', 'formwork.material_area': '8', 'formwork.installation_area': '20',
        'rebar_top.length': '12', 'rebar_top.count': '4', 'rebar_top.lap_length': '0.5',
        'rebar_top.lap_count': '2', 'rebar_top.mass_per_m': '0.888',
        'rebar_bottom.length': '12', 'rebar_bottom.count': '4', 'rebar_bottom.lap_length': '0.5',
        'rebar_bottom.lap_count': '2', 'rebar_bottom.mass_per_m': '0.888',
        'stirrups.length': '2', 'stirrups.count': '30', 'stirrups.lap_length': '0.1',
        'stirrups.lap_count': '30', 'stirrups.mass_per_m': '0.395',
        'strip_auxiliary.wire.quantity': '3.5', 'strip_auxiliary.spacers.quantity': '40',
      };
      for (const [key, value] of Object.entries(params))
        await page.locator(`input[name$=".${key}"]`).fill(value);
      await page.locator('[name="strip_roles_confirmed"]').check();
      await Promise.all([page.waitForURL(url => url.searchParams.has('snapshot'), { timeout: 60000 }),
        page.getByRole('button', { name: 'Рассчитать', exact: true }).click()]);
      const original = page.url();
      const first = await page.locator('body').innerText();
      for (const expected of ['Материалы', 'Работы', '3,64', '49', '63', '43,512', '24,885', 'Нет цены', 'Смета неполная',
        'Вязальная проволока', 'Фиксатор защитного слоя', '3,5', '40'])
        if (!first.includes(expected)) throw new Error(`Strip result missing: ${expected} at ${width}px`);
      const csrf = await page.evaluate(() => decodeURIComponent((document.cookie.split('; ').find(
        item => item.startsWith('atom_csrf_token=')) || '').split('=').slice(1).join('=')));
      if (!csrf) throw new Error('QA CSRF token missing');
      for (const [kind, id, amount] of [
        ['material', 'fdd44181-e2ee-5a5f-b369-72b6cf4934e4', '1000'],
        ['material', 'af7b7e43-8c16-5660-9abd-9359991b61e1', '100'],
        ['material', '4530a113-8124-525f-8c97-d8664de9a687', '50'],
        ['material', '9aff2a3e-7d1b-5c75-b38a-0d7f7c0ab2a5', '200'],
        ['work', 'foundations_concrete_betonirovanie_konstrukciy', '500'],
        ['work', 'reinforcement_armirovanie_fundamenta', '40'],
        ['work', 'foundations_concrete_montazh_opalubki_fundamenta', '300'],
      ]) {
        const response = await page.request.post(`${base}/api/v1/admin/vertical-m1/prices/${kind}/${id}`,
          { form: { region, terms, amount }, headers: { 'X-CSRF-Token': csrf }, maxRedirects: 0 });
        if (response.status() !== 303 || (response.headers().location || '').includes('error='))
          throw new Error(`QA price setup failed for ${kind}`);
      }
      await page.locator('[name="width_m"]').fill('0.5');
      await Promise.all([page.waitForURL(url => url.searchParams.has('snapshot') && url.href !== original, { timeout: 60000 }),
        page.getByRole('button', { name: 'Пересчитать', exact: true }).click()]);
      const revised = page.url();
      const second = await page.locator('body').innerText();
      if (!second.includes('4,6') || !second.includes('31926.36') || !second.includes('Смета неполная'))
        throw new Error(`Strip recalculation or total failed at ${width}px`);
      await page.goto(original);
      const old = await page.locator('body').innerText();
      if (!old.includes('3,64') || !old.includes('Нет цены')) throw new Error('Saved snapshot changed');
      await page.goto(revised);
      await page.screenshot({ path: path.join(__dirname, `fnd3-strip-${width}.png`), fullPage: true });
      await page.close();
    }
    process.stdout.write('FND-3 strip QA: quantities, missing/known prices, recalculation and reopen desktop/mobile PASS\n');
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
