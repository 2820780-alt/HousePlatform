const path=require('node:path'), crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(__dirname,'browsers');
const {chromium}=require('playwright');
const base='http://127.0.0.1:18002', destination='/api/v1/admin/module7/foundations/view';
const credentials={email:`qa-${crypto.randomBytes(12).toString('hex')}@example.invalid`,
  password:crypto.randomBytes(24).toString('hex'),view_only:false};
const fixture=spawnSync('docker',['exec','-i','houseplatform-vertical-qa-20261113','python',
  'qa-materials-ui/vertical_auth_fixture.py'],{input:JSON.stringify(credentials),encoding:'utf8'});
if(fixture.status!==0) throw new Error('Could not create isolated QA login');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    for(const width of [1440,390]){
      const page=await browser.newPage({viewport:{width,height:941}});
      await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
      await page.locator('#email').fill(credentials.email); await page.locator('#password').fill(credentials.password);
      await Promise.all([page.waitForURL(url=>url.pathname===destination,{timeout:60000}),page.locator('#login-submit').click()]);
      await page.locator('#name').fill(`QA precast ${width}`);
      const option=page.locator('#technology option').filter({hasText:'Сборный ленточный фундамент из ФБС (ФЛ по проекту) · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('Precast draft unavailable');
      await page.locator('#technology').selectOption(technology);
      for(const [key,value] of Object.entries({'layout.fbs_main':'10','layout.fbs_short':'4','layout.fbs_shorter':'2','layout.fl':'8'}))
        await page.locator(`input[data-key="${key}"]`).fill(value);
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
      await page.locator('[name="terms"]').fill('qa test only');
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      const missing=page.url();
      if(!(await page.locator('body').innerText()).includes('Не задано: Объём раствора по раскладке и швам'))
        throw new Error('Missing mortar not flagged');
      await page.locator('input[name$=".mortar.volume"]').fill('0.75');
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot')&&url.href!==missing,{timeout:60000}),page.getByRole('button',{name:'Пересчитать',exact:true}).click()]);
      const original=page.url(), text=await page.locator('body').innerText();
      for(const expected of ['10 шт.','4 шт.','2 шт.','8 шт.','16 шт.','0,75 м³','Нет цены','Смета неполная'])
        if(!text.includes(expected)) throw new Error(`Missing ${expected} at ${width}px`);
      await page.getByRole('link',{name:'К геометрии'}).click(); await page.locator('input[data-key="layout.fbs_main"]').fill('20');
      const before=page.url();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision')&&url.href!==before,{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
      await page.locator('[name="terms"]').fill('qa test only');
      await page.locator('input[name$=".mortar.volume"]').fill('0.75');
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      const revised=page.url();
      if(!(await page.locator('body').innerText()).includes('26 шт.')) throw new Error('Precast recalculation failed');
      await page.goto(original);
      if(!(await page.locator('body').innerText()).includes('16 шт.')) throw new Error('Original precast snapshot changed');
      await page.goto(revised);
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-precast-${width}.png`),fullPage:true}); await page.close();
    }
    process.stdout.write('Precast QA: FBS/FL layout, explicit mortar, separate works, snapshots desktop/mobile PASS\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
