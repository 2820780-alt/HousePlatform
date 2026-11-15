const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(__dirname, 'browsers');
const { chromium } = require('playwright');
const base = 'http://127.0.0.1:18002';
const destination = '/api/v1/admin/module7/foundations/view';
const credentials = { email: `qa-${crypto.randomBytes(12).toString('hex')}@example.invalid`,
  password: crypto.randomBytes(24).toString('hex'), view_only:false };
const fixture = spawnSync('docker',['exec','-i','houseplatform-vertical-qa-20261113','python',
  'qa-materials-ui/vertical_auth_fixture.py'],{input:JSON.stringify(credentials),encoding:'utf8'});
if(fixture.status !== 0) throw new Error('Could not create isolated QA login');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    for(const width of [1440,390]){
      const page=await browser.newPage({viewport:{width,height:941}});
      await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
      await page.locator('#email').fill(credentials.email);
      await page.locator('#password').fill(credentials.password);
      await Promise.all([page.waitForURL(url=>url.pathname===destination,{timeout:60000}),page.locator('#login-submit').click()]);
      await page.locator('#name').fill(`QA bored pile ${width}`);
      const option=page.locator('#technology option').filter({hasText:'Буронабивные железобетонные сваи · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('Bored-pile draft unavailable');
      await page.locator('#technology').selectOption(technology);
      for(const [key,value] of Object.entries({'pile.diameter':'0.4','pile.length':'2','pile.count':'5'}))
        await page.locator(`input[data-key="${key}"]`).fill(value);
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      const calculate=async()=>{
        await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
        await page.locator('[name="terms"]').fill('qa test only');
        for(const group of ['pile_longitudinal','stirrups'])
          for(const [part,value] of Object.entries({length:'2',count:'20',lap_length:'0.5',lap_count:'4',mass_per_m:'0.888'}))
            await page.locator(`input[name$=".${group}.${part}"]`).fill(value);
        await page.locator('[name="pile_roles_confirmed"]').check();
        await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      };
      await calculate();
      const original=page.url(), text=await page.locator('body').innerText();
      for(const expected of ['Материалы','Работы','1,256637','5 шт.','42 м','37,296 кг','Нет цены','Смета неполная'])
        if(!text.includes(expected)) throw new Error(`Missing ${expected} at ${width}px`);
      await page.getByRole('link',{name:'К геометрии'}).click();
      await page.locator('input[data-key="pile.count"]').fill('10');
      const before=page.url();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision')&&url.href!==before,{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      await calculate();
      if(!(await page.locator('body').innerText()).includes('2,513274')) throw new Error('Bored-pile recalculation failed');
      const revised=page.url();
      await page.goto(original);
      if(!(await page.locator('body').innerText()).includes('1,256637')) throw new Error('Original pile snapshot changed');
      await page.goto(revised);
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-bored-pile-${width}.png`),fullPage:true});
      await page.close();
    }
    process.stdout.write('Bored-pile QA: geometry, concrete, works, reinforcement, recalculation desktop/mobile PASS\n');
  } finally { await browser.close(); }
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
