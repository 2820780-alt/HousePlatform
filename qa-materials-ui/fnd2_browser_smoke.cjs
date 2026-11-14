const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(__dirname, 'browsers');
const { chromium } = require('playwright');

const base = 'http://127.0.0.1:18002';
const material = '3a8a8b8a-a3c9-5b71-bd82-c5ff86e1c42b';
const technology = '92bd1515-a232-4c07-a4eb-663efebc78bc';
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
      const destination = `/api/v1/admin/material-hub/view/materials/${material}`;
      await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
      await page.locator('#email').fill(credentials.email);
      await page.locator('#password').fill(credentials.password);
      await Promise.all([page.waitForURL(url => url.pathname === destination, { timeout: 60000 }),
                         page.locator('#login-submit').click()]);
      const body = await page.locator('body').innerText();
      if (!body.includes('Битумный праймер') || !/(?:^|\s)л(?:\s|$|[.,])/u.test(body))
        throw new Error(`New material or liter unit missing at ${width}px`);
      await page.screenshot({ path: path.join(__dirname, `fnd2-material-${width}.png`), fullPage: true });
      await page.goto(`${base}/api/v1/admin/material-hub/view/materials?preset=without_price&q=${encodeURIComponent('Битумный праймер')}`);
      if (!(await page.locator('body').innerText()).includes('Битумный праймер'))
        throw new Error(`Unpriced material missing from filter at ${width}px`);
      await page.goto(`${base}/api/v1/admin/module2/workbench/${technology}?tab=materials`, { waitUntil: 'networkidle' });
      const materials = await page.locator('body').innerText();
      if (!materials.includes('Песок для подготовки основания') || !materials.includes('Стяжные элементы опалубки'))
        throw new Error(`Foundation materials or conditional role missing at ${width}px`);
      await page.goto(`${base}/api/v1/admin/module2/workbench/${technology}?tab=works`, { waitUntil: 'networkidle' });
      const workbench = await page.locator('body').innerText();
      if (!workbench.includes('ленточный фундамент') || !workbench.includes('Бетонирование'))
        throw new Error(`Foundation workbench missing at ${width}px`);
      await page.screenshot({ path: path.join(__dirname, `fnd2-works-${width}.png`), fullPage: true });
      await page.close();
    }
    process.stdout.write('QA FND-2: material, liter and draft technology, desktop/mobile PASS\n');
  } finally {
    await browser.close();
  }
})().catch(error => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
