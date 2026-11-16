const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(__dirname, 'browsers');
const { chromium } = require('playwright');
const base='http://127.0.0.1:18002', destination='/api/v1/admin/module7/foundations/view';
const credentials={email:`qa-${crypto.randomBytes(12).toString('hex')}@example.invalid`,
  password:crypto.randomBytes(24).toString('hex'),view_only:false};
const fixture=spawnSync('docker',['exec','-i','houseplatform-vertical-qa-20261113','python',
  'qa-materials-ui/vertical_auth_fixture.py'],{input:JSON.stringify(credentials),encoding:'utf8'});
if(fixture.status!==0) throw new Error('Could not create isolated QA login');
let stage='setup';
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    for(const width of [1440,390]){
      const page=await browser.newPage({viewport:{width,height:941}});
      await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
      await page.locator('#email').fill(credentials.email); await page.locator('#password').fill(credentials.password);
      stage=`login ${width}`;
      await Promise.all([page.waitForURL(url=>url.pathname===destination,{timeout:60000}),page.locator('#login-submit').click()]);
      await page.locator('#name').fill(`QA coating ${width}`);
      const option=page.locator('#technology option').filter({hasText:'Мастичная гидроизоляция подземной части · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('Coating draft unavailable');
      await page.locator('#technology').selectOption(technology);
      await page.locator('input[data-key="geometry.area"]').fill('20');
      stage=`geometry ${width}`;
      try { await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:30000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]); }
      catch(error) { throw new Error(`Geometry save failed: ${await page.locator('#message').innerText()} (${error.message})`); }
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      const calculate=async()=>{
        await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
        await page.locator('[name="terms"]').fill('qa test only');
        await page.locator('input[name$=".primer.consumption"]').fill('0.25');
        await page.locator('input[name$=".mastic.consumption"]').fill('1.5');
        await page.locator('label').filter({hasText:'Нанесение праймера'}).locator('input[name="work_block_id"]').uncheck();
        await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      };
      stage=`first calculation ${width}`; await calculate();
      const original=page.url(), text=await page.locator('body').innerText();
      for(const expected of ['Материалы','Работы','5 л','30 кг','20 м²','Нет цены','Смета неполная'])
        if(!text.includes(expected)) throw new Error(`Missing ${expected} at ${width}px`);
      await page.locator('label').filter({hasText:'Нанесение праймера'}).locator('input[name="work_block_id"]').check();
      await page.locator('[name="coating_work_scope_confirmed"]').check();
      stage=`separate works ${width}`;
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot')&&url.href!==original,{timeout:60000}),
        page.getByRole('button',{name:'Пересчитать',exact:true}).click()]);
      const separate=page.url();
      const works=page.locator('section').filter({has:page.getByRole('heading',{name:'Работы',exact:true})});
      if(await works.locator('tbody tr').count()!==2) throw new Error('Separate works not present');
      if((await works.innerText()).includes('Не включено в итог')) throw new Error('Confirmed separate works excluded');
      await page.goto(original);
      if(await page.locator('[name="coating_work_scope_confirmed"]').isChecked()) throw new Error('Original snapshot changed');
      await page.goto(separate);
      await page.getByRole('link',{name:'К геометрии'}).click();
      await page.locator('input[data-key="geometry.area"]').fill('40');
      const before=page.url();
      stage=`revised geometry ${width}`;
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision')&&url.href!==before,{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click(); stage=`recalculation ${width}`; await calculate();
      const revised=page.url(), newText=await page.locator('body').innerText();
      if(!newText.includes('10 л')||!newText.includes('60 кг')) throw new Error('Coating recalculation failed');
      await page.goto(original);
      if(!(await page.locator('body').innerText()).includes('30 кг')) throw new Error('Original coating snapshot changed');
      await page.goto(revised);
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-coating-${width}.png`),fullPage:true});
      await page.close();
    }
    process.stdout.write('Coating QA: material units, confirmed separate works and recalculation desktop/mobile PASS\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(`${stage}: ${error.message}\n`);process.exitCode=1;});
