const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(__dirname, 'browsers');
const { chromium } = require('playwright');
const base = 'http://127.0.0.1:18002';
const destination = '/api/v1/admin/module7/foundations/view';
const credentials = { email: `qa-${crypto.randomBytes(12).toString('hex')}@example.invalid`,
  password: crypto.randomBytes(24).toString('hex'), view_only:false };
let stage = 'setup';
const fixture = spawnSync('docker', ['exec','-i','houseplatform-vertical-qa-20261113','python',
  'qa-materials-ui/vertical_auth_fixture.py'], { input:JSON.stringify(credentials), encoding:'utf8' });
if (fixture.status !== 0) throw new Error('Could not create isolated QA login');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    for (const width of [1440,390]) {
      const page=await browser.newPage({viewport:{width,height:941}});
      await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
      await page.locator('#email').fill(credentials.email);
      await page.locator('#password').fill(credentials.password);
      stage='login';
      await Promise.all([page.waitForURL(url=>url.pathname===destination,{timeout:60000}),page.locator('#login-submit').click()]);
      await page.locator('#name').fill(`QA slab ${width}`);
      const option=page.locator('#technology option').filter({hasText:'Монолитная железобетонная фундаментная плита · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('Monolithic slab draft unavailable');
      await page.locator('#technology').selectOption(technology);
      await page.locator('input[data-key="geometry.net_area"]').fill('50');
      await page.locator('input[data-key="geometry.slab_thickness"]').fill('0.2');
      stage='initial geometry';
      try {
        await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:30000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      } catch (error) { throw new Error(`Initial geometry failed: ${await page.locator('#message').innerText()} (${error.message})`); }
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      const fillAndCalculate=async()=>{
        await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
        await page.locator('[name="terms"]').fill('qa test only');
        for(const group of ['lower_x','lower_y','upper_x','upper_y'])
          for(const [part,value] of Object.entries({length:'12',count:'4',lap_length:'0.5',lap_count:'2',mass_per_m:'0.888'}))
            await page.locator(`input[name$=".${group}.${part}"]`).fill(value);
        await page.locator('input[name$=".formwork.material_area"]').fill('8');
        await page.locator('input[name$=".formwork.installation_area"]').fill('20');
        await page.locator('[name="slab_roles_confirmed"]').check();
        await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      };
      stage='initial estimate'; await fillAndCalculate();
      const original=page.url();
      const body=await page.locator('body').innerText();
      for(const expected of ['Материалы','Работы','10 м³','49 м','43,512 кг','Нет цены','Смета неполная'])
        if(!body.includes(expected)) throw new Error(`Missing ${expected} at ${width}px`);
      stage='geometry revision'; await page.getByRole('link',{name:'К геометрии'}).click();
      await page.locator('input[data-key="geometry.net_area"]').fill('70');
      const previous=page.url();
      try {
        await Promise.all([page.waitForURL(url=>url.searchParams.has('revision')&&url.href!==previous,{timeout:30000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      } catch (error) { throw new Error(`Geometry revision failed: ${await page.locator('#message').innerText()} (${error.message})`); }
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      stage='revised estimate'; await fillAndCalculate();
      if(!(await page.locator('body').innerText()).includes('14 м³')) throw new Error('Slab geometry recalculation failed');
      const revised=page.url();
      await page.goto(original);
      if(!(await page.locator('body').innerText()).includes('10 м³')) throw new Error('Original slab snapshot changed');
      await page.goto(revised);
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-slab-${width}.png`),fullPage:true});
      await page.close();
    }
    process.stdout.write('Monolithic slab QA: concrete, four rebar groups, formwork and missing prices desktop/mobile PASS\n');
  } finally { await browser.close(); }
})().catch(error=>{process.stderr.write(`${stage}: ${error.message}\n`);process.exitCode=1;});
