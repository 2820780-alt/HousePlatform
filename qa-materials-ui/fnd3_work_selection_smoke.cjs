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
      page.on('dialog',dialog=>dialog.accept());
      await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
      await page.locator('#email').fill(credentials.email); await page.locator('#password').fill(credentials.password);
      await Promise.all([page.waitForURL(url=>url.pathname===destination,{timeout:60000}),page.locator('#login-submit').click()]);
      const option=page.locator('#technology option').filter({hasText:'Мастичная гидроизоляция подземной части · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('Coating draft unavailable');
      const builder=`${base}/api/v1/admin/module2/calculation-builder/${technology}`;
      const name=`QA work selection ${crypto.randomBytes(6).toString('hex')}`;
      let created=false;
      try {
        await page.goto(builder);
        const form=page.locator('form[data-compose-form]').first();
        await form.locator('input[name="name"]').fill(name);
        await form.locator('input[name="step.1.label"]').fill('Площадь нанесения');
        await form.locator('select[name="step.1.operation"]').selectOption('INPUT');
        await form.locator('select[name="step.1.unit"]').selectOption('m2');
        await form.locator('select[name="step.1.source"]').selectOption('geometry.area');
        const primer=form.locator('select[name="work_code"] option').filter({hasText:'Нанесение праймера под гидроизоляцию'}).first();
        const primerCode=await primer.getAttribute('value');
        if(!primerCode) throw new Error('Primer work unavailable');
        await form.locator('select[name="work_code"]').selectOption(primerCode);
        await form.locator('select[name="work_step"]').selectOption('1');
        await Promise.all([page.waitForNavigation({waitUntil:'load',timeout:60000}),form.getByRole('button',{name:'Создать расчёт'}).click()]);
        let section=page.locator('details').filter({has:page.locator('summary').getByText(name,{exact:false})}).last();
        await section.locator('summary').first().click();
        const detailId=await section.locator('form[action$="/delete"] input[name="block_id"]').inputValue();
        created=true;
        await page.goto(`${base}${destination}`);
        await page.locator('#name').fill(`QA selected work ${width}`);
        await page.locator('#technology').selectOption(technology);
        await page.locator('input[data-key="geometry.area"]').fill('20');
        await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
        await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
        await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
        await page.locator('[name="terms"]').fill('qa test only');
        await page.locator('input[name$=".primer.consumption"]').fill('0.25');
        await page.locator('input[name$=".mastic.consumption"]').fill('1.5');
        const choices=page.locator('input[name="work_block_id"]');
        if(await choices.count()!==3) throw new Error('Expected bundled and detailed work choices');
        const values=await choices.evaluateAll(items=>items.map(item=>item.value));
        const excludedIds=values.filter(value=>value!==detailId);
        if(excludedIds.length!==2) throw new Error('Other work choices not found');
        await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
        const both=page.url();
        if(!(await page.locator('body').innerText()).includes('Не включено в итог')) throw new Error('Double-count protection missing');
        for(const id of excludedIds) await page.locator(`input[name="work_block_id"][value="${id}"]`).uncheck();
        await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot')&&url.href!==both,{timeout:60000}),
          page.getByRole('button',{name:'Пересчитать',exact:true}).click()]);
        const selected=page.url();
        for(const id of excludedIds)
          if(await page.locator(`input[name="work_block_id"][value="${id}"]`).isChecked()) throw new Error('Excluded work selection was not saved');
        if(!(await page.locator(`input[name="work_block_id"][value="${detailId}"]`).isChecked())) throw new Error('Detailed selection was not saved');
        if((await page.locator('body').innerText()).includes('Не включено в итог')) throw new Error('Single selected work was excluded');
        await page.goto(both);
        if(!(await page.locator('body').innerText()).includes('Не включено в итог')) throw new Error('Earlier snapshot changed');
        await page.goto(selected);
        if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      } finally {
        if(created){
          await page.goto(builder);
          const section=page.locator('details').filter({has:page.locator('summary').getByText(name,{exact:false})}).last();
          await section.locator('summary').first().click();
          await section.locator('form[action$="/delete"] button[type="submit"]').click();
          await page.waitForFunction(text=>![...document.querySelectorAll('summary')].some(item=>item.textContent.includes(text)),name,{timeout:60000});
        }
        await page.close();
      }
    }
    process.stdout.write('QA work selection: explicit alternative, double-count guard and immutable snapshot desktop/mobile PASS\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
