const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(__dirname, 'browsers');
const { chromium } = require('playwright');
const base = 'http://127.0.0.1:18002';
const destination = '/api/v1/admin/module7/foundations/view';
const credentials = { email: `qa-${crypto.randomBytes(12).toString('hex')}@example.invalid`,
  password: crypto.randomBytes(24).toString('hex'), view_only: false };
const fixture = spawnSync('docker', ['exec', '-i', 'houseplatform-vertical-qa-20261113',
  'python', 'qa-materials-ui/vertical_auth_fixture.py'], { input: JSON.stringify(credentials), encoding: 'utf8' });
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
      await page.locator('#name').fill(`QA geometry ${width}`);
      const option = page.locator('#technology option').filter({ hasText: 'Ребристая железобетонная фундаментная плита' }).first();
      const tech = await option.getAttribute('value');
      if (!tech) throw new Error('QA ribbed slab technology unavailable');
      await page.locator('#technology').selectOption(tech);
      const values = { 'geometry.net_area': '50', 'geometry.slab_thickness': '0.2',
        'geometry.rib_length': '20', 'geometry.rib_width': '0.4', 'geometry.rib_height': '0.3',
        'geometry.rib_overlap_volume': '0' };
      for (const [key, value] of Object.entries(values)) await page.locator(`input[data-key="${key}"]`).fill(value);
      await Promise.all([page.waitForURL(url => url.searchParams.has('revision'), { timeout: 60000 }),
        page.getByRole('button', { name: 'Сохранить', exact: true }).click()]);
      const first = page.url();
      await page.locator('input[data-key="geometry.net_area"]').fill('70');
      await Promise.all([page.waitForURL(url => url.searchParams.has('revision') && url.href !== first, { timeout: 60000 }),
        page.getByRole('button', { name: 'Сохранить', exact: true }).click()]);
      const revised = page.url();
      await page.reload();
      if (await page.locator('input[data-key="geometry.net_area"]').inputValue() !== '70')
        throw new Error('Latest revision failed to reopen');
      await page.goto(first);
      if (await page.locator('input[data-key="geometry.net_area"]').inputValue() !== '50')
        throw new Error('Original revision changed');
      if (await page.locator('#name').inputValue() !== `QA geometry ${width}`)
        throw new Error('Original revision lost its object name');
      await page.goto(revised);
      if (await page.locator('input[data-key="geometry.net_area"]').inputValue() !== '70')
        throw new Error('Revised geometry unavailable');
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
        throw new Error(`Horizontal overflow at ${width}px`);
      await page.screenshot({ path: path.join(__dirname, `fnd3-m7-${width}.png`), fullPage: true });
      await page.close();
    }
    process.stdout.write('M7 QA: geometry entry, revision, reopen, desktop/mobile PASS\n');
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
