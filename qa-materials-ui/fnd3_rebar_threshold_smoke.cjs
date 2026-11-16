const path = require('node:path'), crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(__dirname, 'browsers');
const { chromium } = require('playwright');
const base = 'http://127.0.0.1:18002';
const technology = '92bd1515-a232-4c07-a4eb-663efebc78bc';
const destination = `/api/v1/admin/module2/calculation-builder/${technology}`;
const credentials = { email:`qa-${crypto.randomBytes(12).toString('hex')}@example.invalid`,
  password:crypto.randomBytes(24).toString('hex'), view_only:false };
const fixture = spawnSync('docker', ['exec','-i','houseplatform-vertical-qa-20261113',
  'python','qa-materials-ui/vertical_auth_fixture.py'], {input:JSON.stringify(credentials),encoding:'utf8'});
if (fixture.status !== 0) throw new Error('Could not create isolated QA login');

(async()=>{
  const browser = await chromium.launch({headless:true});
  try {
    for (const width of [1440,390]) {
      const page = await browser.newPage({viewport:{width,height:941}});
      page.on('dialog', dialog => dialog.accept());
      await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
      await page.locator('#email').fill(credentials.email);
      await page.locator('#password').fill(credentials.password);
      await Promise.all([page.waitForURL(url=>url.pathname===destination,{timeout:60000}),page.locator('#login-submit').click()]);
      const form = page.locator('form[action$="/add"]');
      await form.locator('select[name="preset"]').selectOption('reinforcement');
      await form.getByText('Диапазоны для продольной арматуры').click();
      for (const [name,value] of Object.entries({'range.0.lower':'350','range.0.upper':'500','range.0.count':'4',
        'range.1.lower':'500','range.1.upper':'700','range.1.count':'6','rule_source':'Тестовые данные QA'}))
        await form.locator(`[name="${name}"]`).fill(value);
      await form.locator('[name="range.1.inclusive"]').check();
      await Promise.all([page.waitForNavigation({waitUntil:'load',timeout:60000}),
        form.getByRole('button',{name:'Добавить блок'}).click()]);
      const summary = page.locator('summary').filter({hasText:/^\s*\d+\. Продольная арматура\s*$/}).last();
      const section = summary.locator('..');
      await summary.click();
      const update = section.locator('form[action$="/update"]');
      const name = `QA rebar ranges ${crypto.randomBytes(6).toString('hex')}`;
      await update.locator('input[name="name"]').fill(name);
      await Promise.all([page.waitForNavigation({waitUntil:'load',timeout:60000}),
        update.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      const saved = page.locator('details').filter({has:page.locator('summary').getByText(name,{exact:false})}).last();
      await saved.locator('summary').first().click();
      const ranges = saved.locator('details').filter({has:page.locator('summary').getByText('Диапазоны количества',{exact:true})});
      await ranges.locator('summary').click();
      const counts = ranges.locator('input[name$=".count"]');
      if (await counts.nth(0).inputValue() !== '4' || await counts.nth(1).inputValue() !== '6')
        throw new Error('Rebar ranges were not preserved');
      if (await page.evaluate(()=>document.documentElement.scrollWidth > innerWidth)) throw new Error(`Overflow at ${width}px`);
      await saved.locator('form[action$="/delete"] button[type="submit"]').click();
      await page.waitForFunction(text=>![...document.querySelectorAll('summary')].some(item=>item.textContent.includes(text)),name,{timeout:60000});
      await page.close();
    }
    process.stdout.write('M2 QA: explicit reinforcement ranges and source saved desktop/mobile PASS\n');
  } finally { await browser.close(); }
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
