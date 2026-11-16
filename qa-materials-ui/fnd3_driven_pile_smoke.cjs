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
      await page.locator('#name').fill(`QA driven pile ${width}`);
      const option=page.locator('#technology option').filter({hasText:'Забивные заводские железобетонные сваи · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('Factory-pile draft unavailable');
      await page.locator('#technology').selectOption(technology);
      await page.locator('input[data-key="pile.count"]').fill('5');
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
      await page.locator('[name="terms"]').fill('qa test only');
      await page.locator('input[name$=".pile_first.count"]').fill('3');
      await page.locator('input[name$=".pile_second.count"]').fill('3');
      await page.locator('input[name$=".pile.head_treatment_count"]').fill('3');
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      const incorrect=page.url(), warning=await page.locator('body').innerText();
      if(!warning.includes('Распределение количества свай по исполнениям не подтверждено'))
        throw new Error('Allocation mismatch not flagged');
      await page.locator('input[name$=".pile_second.count"]').fill('2');
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot')&&url.href!==incorrect,{timeout:60000}),page.getByRole('button',{name:'Пересчитать',exact:true}).click()]);
      const correct=page.url(), text=await page.locator('body').innerText();
      for(const expected of ['Материалы','Работы','3 шт.','2 шт.','5 шт.','Нет цены','Смета неполная'])
        if(!text.includes(expected)) throw new Error(`Missing ${expected} at ${width}px`);
      if(text.includes('Распределение количества свай по исполнениям не подтверждено')) throw new Error('Valid allocation rejected');
      if(!text.includes('Подтвердите, что обработка голов не входит в стоимость погружения свай'))
        throw new Error('Head treatment scope warning missing');
      await page.locator('[name="driven_head_scope_confirmed"]').check();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot')&&url.href!==correct,{timeout:60000}),
        page.getByRole('button',{name:'Пересчитать',exact:true}).click()]);
      if((await page.locator('body').innerText()).includes('Подтвердите, что обработка голов не входит в стоимость погружения свай'))
        throw new Error('Head treatment scope confirmation rejected');
      await page.goto(incorrect);
      if(!(await page.locator('body').innerText()).includes('Распределение количества свай по исполнениям не подтверждено'))
        throw new Error('Original allocation snapshot changed');
      await page.goto(correct);
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-driven-head-${width}.png`),fullPage:true}); await page.close();
    }
    process.stdout.write('Factory-pile QA: explicit variants, allocation safeguard, immutable snapshots desktop/mobile PASS\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
