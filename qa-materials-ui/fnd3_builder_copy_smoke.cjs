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
      const source=await page.locator('#technology option').filter({hasText:'Буронабивные железобетонные сваи · черновик'}).first().getAttribute('value');
      const target=await page.locator('#technology option').filter({hasText:'Монолитный железобетонный ростверк свайного фундамента · черновик'}).first().getAttribute('value');
      if(!source || !target) throw new Error('Required QA drafts unavailable');
      await page.goto(`${base}/api/v1/admin/module2/calculation-builder/${source}`);
      const existing=page.locator('details').filter({has:page.locator('summary').getByText('Бетон и бурение свай',{exact:false})}).first();
      const original=existing.locator('form[action$="/update"]');
      const sourceResources={};
      for(const key of ['material_id','work_code','material_requirement_id','work_step_id'])
        sourceResources[key]=await original.locator(`select[name="${key}"]`).inputValue();
      if(Object.values(sourceResources).some(value=>!value)) throw new Error('Source resources unavailable');
      const form=page.locator('form[data-compose-form]').first();
      const name=`QA copy ${crypto.randomBytes(6).toString('hex')}`;
      await form.locator('input[name="name"]').fill(name);
      for(const [index,label,unit,sourceKey] of [[1,'Число свай','piece','pile.count'],[2,'Объём бетона','m3','PARAMETER']]){
        if(index>1) await form.locator(`details[data-compose-step="${index}"] > summary`).click();
        await form.locator(`input[name="step.${index}.label"]`).fill(label);
        await form.locator(`select[name="step.${index}.operation"]`).selectOption('INPUT');
        await form.locator(`select[name="step.${index}.unit"]`).selectOption(unit);
        await form.locator(`select[name="step.${index}.source"]`).selectOption(sourceKey);
      }
      for(const [key,value] of Object.entries(sourceResources)) await form.locator(`select[name="${key}"]`).selectOption(value);
      await form.locator('select[name="material_step"]').selectOption('2');
      await form.locator('select[name="work_step"]').selectOption('1');
      await Promise.all([page.waitForNavigation({waitUntil:'load',timeout:60000}),form.getByRole('button',{name:'Создать расчёт'}).click()]);
      const sourceUrl=page.url();
      const own=page.locator('details').filter({has:page.locator('summary').getByText(name,{exact:false})}).first();
      if(!await own.count()) throw new Error('Source block not created');
      await page.goto(`${base}/api/v1/admin/module2/calculation-builder/${target}`);
      const targetResources=await page.locator('form[action$="/update"]').evaluateAll(forms=>{
        const result={};
        for(const form of forms){
          for(const keys of [['material_id','material_requirement_id'],['work_code','work_step_id']]) {
            const values=Object.fromEntries(keys.map(key=>[key,form.querySelector(`select[name="${key}"]`)?.value]));
            if(keys.every(key=>values[key]) && !result[keys[0]]) Object.assign(result,values);
          }
        }
        return ['material_id','work_code','material_requirement_id','work_step_id'].every(key=>result[key]) ? result : null;
      });
      if(!targetResources) throw new Error('Target resources unavailable');
      const sourceDetails=page.locator('details').filter({has:page.locator('summary').getByText(name,{exact:false})}).last();
      await sourceDetails.locator('summary').first().click();
      const copy=sourceDetails.locator('form[action$="/copy-technology"]');
      for(const input of await copy.locator('select[name^="mapping."]').all()){
        const name=await input.getAttribute('name'), key=name.slice('mapping.'.length);
        const same=input.locator('option').filter({hasText:'Параметр блока'});
        const geometry=input.locator('option').filter({hasText:'Количество свай'});
        const option=key==='pile.count' && await geometry.count() ? await geometry.first().getAttribute('value') :
          (await same.count() ? await same.first().getAttribute('value') : null);
        if(!option) throw new Error('Independent input mapping unavailable');
        await input.selectOption(option);
      }
      for(const [key,value] of Object.entries(targetResources)) await copy.locator(`select[name="${key}"]`).selectOption(value);
      await Promise.all([page.waitForNavigation({waitUntil:'load',timeout:60000}),copy.getByRole('button',{name:'Добавить копию'}).click()]);
      let cloned=page.locator('details').filter({has:page.locator('summary').getByText(name,{exact:false})}).first();
      if(!await cloned.count()) throw new Error('Target copy not created');
      await cloned.locator('summary').first().click();
      const renamed=`${name} target`;
      const update=cloned.locator('form[action$="/update"]');
      await update.locator('input[name="name"]').fill(renamed);
      await Promise.all([page.waitForNavigation({waitUntil:'load',timeout:60000}),update.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      cloned=page.locator('details').filter({has:page.locator('summary').getByText(renamed,{exact:false})}).first();
      if(!await cloned.count()) throw new Error('Target edit not saved');
      await cloned.locator('summary').first().click();
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-builder-copy-${width}.png`),fullPage:true});
      await cloned.locator('form[action$="/delete"] button[type="submit"]').click();
      await page.waitForFunction(text=>![...document.querySelectorAll('summary')].some(item=>item.textContent.includes(text)),renamed,{timeout:60000});
      await page.goto(sourceUrl);
      const sourceBlock=page.locator('details').filter({has:page.locator('summary').getByText(name,{exact:false})}).first();
      if(!await sourceBlock.count()) throw new Error('Source changed when copy was edited');
      await sourceBlock.locator('summary').first().click();
      const sourceEdit=sourceBlock.locator('form[action$="/update"]');
      for(const [key,value] of Object.entries(sourceResources))
        if(await sourceEdit.locator(`select[name="${key}"]`).inputValue()!==value) throw new Error(`Source ${key} changed`);
      await sourceBlock.locator('form[action$="/delete"] button[type="submit"]').click();
      await page.waitForFunction(text=>![...document.querySelectorAll('summary')].some(item=>item.textContent.includes(text)),name,{timeout:60000});
      await page.close();
    }
    process.stdout.write('M2 builder QA: M1 resources, cross-technology copy and independent edits desktop/mobile PASS\n');
  } finally { await browser.close(); }
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
