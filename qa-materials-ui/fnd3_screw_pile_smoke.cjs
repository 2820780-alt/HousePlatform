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
      await page.locator('#name').fill(`QA screw piles ${width}`);
      const option=page.locator('#technology option').filter({hasText:'Стальные винтовые сваи · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('Screw-pile draft unavailable');
      await page.locator('#technology').selectOption(technology);
      await page.locator('input[data-key="pile.count"]').fill('5');
      await page.locator('input[data-key="pile.head_count"]').fill('5');
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
      await page.locator('[name="terms"]').fill('qa test only');
      for(const [key,value] of Object.entries({screw_89:'3',screw_108_long:'2',screw_108:'0',head_89:'3',head_108:'2'}))
        await page.locator(`input[name$=".${key}.count"]`).fill(value);
      await page.locator('input[name$=".screw.weld_count"]').fill('3');
      await page.locator('input[name$=".screw.corrosion_area"]').fill('2.5');
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      const unconfirmed=page.url(), warning=await page.locator('body').innerText();
      if(!warning.includes('Проверьте распределение свай и оголовков и подтвердите их совместимость'))
        throw new Error('Head compatibility confirmation not required');
      await page.locator('[name="screw_head_match_confirmed"]').check();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot')&&url.href!==unconfirmed,{timeout:60000}),page.getByRole('button',{name:'Пересчитать',exact:true}).click()]);
      const correct=page.url(), text=await page.locator('body').innerText();
      for(const expected of ['Материалы','Работы','3 шт.','2 шт.','5 шт.','Нет цены','Не требуется','Смета неполная'])
        if(!text.includes(expected)) throw new Error(`Missing ${expected} at ${width}px`);
      if(text.includes('Проверьте распределение свай и оголовков и подтвердите их совместимость')) throw new Error('Confirmed allocation rejected');
      if(!text.includes('Подтвердите, что монтаж оголовков не входит в стоимость установки свай'))
        throw new Error('Head work scope warning missing');
      if(!text.includes('Проверьте состав расценки сварки соединений') ||
          !text.includes('Проверьте состав расценки антикоррозионной обработки'))
        throw new Error('Optional work scope warning missing');
      await page.locator('[name="screw_head_work_scope_confirmed"]').check();
      await page.locator('[name="screw_weld_scope_confirmed"]').check();
      await page.locator('[name="screw_corrosion_scope_confirmed"]').check();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot')&&url.href!==correct,{timeout:60000}),
        page.getByRole('button',{name:'Пересчитать',exact:true}).click()]);
      if((await page.locator('body').innerText()).includes('Подтвердите, что монтаж оголовков не входит в стоимость установки свай'))
        throw new Error('Head work scope confirmation rejected');
      if((await page.locator('body').innerText()).includes('Проверьте состав расценки сварки соединений'))
        throw new Error('Optional work scope confirmation rejected');
      await page.goto(unconfirmed);
      if(!(await page.locator('body').innerText()).includes('Проверьте распределение свай и оголовков'))
        throw new Error('Original unconfirmed snapshot changed');
      await page.goto(correct);
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-screw-optional-${width}.png`),fullPage:true}); await page.close();
    }
    process.stdout.write('Screw-pile QA: variants, explicit head confirmation and snapshots desktop/mobile PASS\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
