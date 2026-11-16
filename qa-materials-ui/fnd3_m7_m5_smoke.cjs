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
      await page.locator('#name').fill(`QA M7-M5 ${width}`);
      await page.locator('#technology').selectOption('92bd1515-a232-4c07-a4eb-663efebc78bc');
      for (const [key, value] of Object.entries({ 'geometry.length':'12', 'geometry.width':'0.4',
        'geometry.height':'0.8', 'strip.overlap_volume':'0.2' }))
        await page.locator(`input[data-key="${key}"]`).fill(value);
      await Promise.all([page.waitForURL(url => url.searchParams.has('revision'), { timeout: 60000 }),
        page.getByRole('button', { name: 'Сохранить', exact: true }).click()]);
      await page.getByRole('link', { name: 'Открыть предварительную смету' }).click();
      await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
      await page.locator('[name="terms"]').fill('qa test only');
      const params = { 'formwork.material_area':'8', 'formwork.installation_area':'20',
        'rebar_top.length':'12', 'rebar_top.count':'4', 'rebar_top.lap_length':'0.5',
        'rebar_top.lap_count':'2', 'rebar_top.mass_per_m':'0.888',
        'rebar_bottom.length':'12', 'rebar_bottom.count':'4', 'rebar_bottom.lap_length':'0.5',
        'rebar_bottom.lap_count':'2', 'rebar_bottom.mass_per_m':'0.888',
        'stirrups.length':'2', 'stirrups.count':'30', 'stirrups.lap_length':'0.1',
        'stirrups.lap_count':'30', 'stirrups.mass_per_m':'0.395',
        'preparation.sand.area':'20', 'preparation.sand.thickness':'0.2', 'preparation.sand.supply_factor':'1.2',
        'preparation.gravel.area':'20', 'preparation.gravel.thickness':'0.2', 'preparation.gravel.supply_factor':'1.2',
        'geotextile.area':'20', 'geotextile.overlap_area':'2' };
      for (const [key,value] of Object.entries(params)) await page.locator(`input[name$=".${key}"]`).fill(value);
      await page.locator('[name="strip_roles_confirmed"]').check();
      await Promise.all([page.waitForURL(url => url.searchParams.has('snapshot'), { timeout: 60000 }),
        page.getByRole('button', { name:'Рассчитать', exact:true }).click()]);
      const body = await page.locator('body').innerText();
      for (const expected of ['Материалы', 'Работы', '3,64', '4,8', '22', '49', '63', 'Нет цены', 'Смета неполная'])
        if (!body.includes(expected)) throw new Error(`Missing ${expected} at ${width}px`);
      const concrete = page.locator('tr').filter({hasText:'Бетон ленты'}).first();
      if (!((await concrete.locator('a').first().getAttribute('href')) || '').includes('/material-hub/view/materials/'))
        throw new Error('Concrete material link missing');
      await concrete.getByText('Расчёт блока',{exact:true}).click();
      if (!(await concrete.innerText()).includes('Объём конструкции')) throw new Error('Calculation trace missing');
      const estimateUrl = page.url();
      await Promise.all([page.waitForURL(url=>url.pathname.includes('/material-hub/view/materials/'),{timeout:60000}),
        concrete.locator('a').first().click()]);
      if ((await page.locator('body').innerText()).includes('Страница не найдена')) throw new Error('Material card unavailable');
      await page.goto(estimateUrl);
      const work = page.locator('section').filter({has:page.getByRole('heading',{name:'Работы',exact:true})})
        .locator('a[href*="/vertical-m1/works/"]').first();
      await Promise.all([page.waitForURL(url=>url.pathname.includes('/vertical-m1/works/'),{timeout:60000}),work.click()]);
      if ((await page.locator('body').innerText()).includes('Страница не найдена')) throw new Error('Work card unavailable');
      await page.goto(estimateUrl);
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
        throw new Error(`Horizontal overflow at ${width}px`);
      await page.screenshot({ path:path.join(__dirname, `fnd3-m7-m5-${width}.png`), fullPage:true });
      await page.close();
    }
    process.stdout.write('M7 -> M5 strip: saved geometry, quantities and missing prices desktop/mobile PASS\n');
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(`${error.message}\n`); process.exitCode=1; });
