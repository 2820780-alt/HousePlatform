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
      const option=page.locator('#technology option').filter({hasText:'Буронабивные железобетонные сваи · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('Bored-pile draft unavailable');
      await page.goto(`${base}/api/v1/admin/module2/calculation-builder/${technology}`);
      const form=page.locator('form[data-compose-form]').first();
      const name=`QA count ${crypto.randomBytes(6).toString('hex')}`;
      await form.locator('input[name="name"]').fill(name);
      await form.locator('input[name="step.1.label"]').fill('Количество свай');
      await form.locator('select[name="step.1.operation"]').selectOption('INPUT');
      await form.locator('select[name="step.1.unit"]').selectOption('m');
      const disabled=await form.locator('select[name="step.1.source"] option[value="pile.count"]').evaluate(item=>item.disabled);
      if(!disabled) throw new Error('Incompatible geometry unit was offered');
      await form.locator('select[name="step.1.unit"]').selectOption('piece');
      await form.locator('select[name="step.1.source"]').selectOption('pile.count');
      await form.locator('select[name="material_step"]').selectOption('1');
      await Promise.all([page.waitForURL(url=>url.pathname.endsWith(technology),{waitUntil:'load',timeout:60000}),
        form.getByRole('button',{name:'Создать расчёт'}).click()]);
      const section=page.locator('details').filter({has:page.locator('summary').getByText(name,{exact:false})}).last();
      await section.locator('summary').first().click();
      await page.screenshot({path:path.join(__dirname,`fnd3-builder-${width}.png`),fullPage:true});
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      const remove=section.locator('form[action$="/delete"] button[type="submit"]');
      await remove.click();
      await page.waitForFunction(text=>![...document.querySelectorAll('summary')].some(item=>item.textContent.includes(text)),name,{timeout:60000});
      await page.close();
    }
    process.stdout.write('M2 builder QA: typed pile geometry, create and delete own test block desktop/mobile PASS\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
