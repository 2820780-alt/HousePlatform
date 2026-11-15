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
      await page.locator('#name').fill(`QA grillage ${width}`);
      const option=page.locator('#technology option').filter({hasText:'Монолитный железобетонный ростверк свайного фундамента · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('Grillage draft unavailable');
      await page.locator('#technology').selectOption(technology);
      for(const [key,value] of Object.entries({'geometry.length':'12','geometry.width':'0.4','geometry.height':'0.8',
        'strip.overlap_volume':'0.2','pile.count':'5'})) await page.locator(`input[data-key="${key}"]`).fill(value);
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      const fill=async()=>{
        await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
        await page.locator('[name="terms"]').fill('qa test only');
        for(const [key,value] of Object.entries({factory_6:'3',factory_8:'2',screw_89:'0',screw_108:'0',screw_108_long:'0'}))
          await page.locator(`input[name$=".${key}.count"]`).fill(value);
        for(const role of ['rebar_top','rebar_bottom','stirrups'])
          for(const [part,value] of Object.entries({length:'12',count:'4',lap_length:'0.5',lap_count:'2'}))
            await page.locator(`input[name$=".${role}.${part}"]`).fill(value);
      };
      await fill();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      const unconfirmed=page.url(), warning=await page.locator('body').innerText();
      if(!warning.includes('Проверьте состав комплексной работы и отсутствие повторного учёта'))
        throw new Error('Bundled work confirmation not required');
      await page.locator('[name="grillage_rebar_disjoint_confirmed"]').check();
      await page.locator('[name="grillage_bundle_scope_confirmed"]').check();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot')&&url.href!==unconfirmed,{timeout:60000}),page.getByRole('button',{name:'Пересчитать',exact:true}).click()]);
      const original=page.url(), text=await page.locator('body').innerText();
      for(const expected of ['3,64 м³','3 шт.','2 шт.','49 м','12 м','Нет цены','Смета неполная'])
        if(!text.includes(expected)) throw new Error(`Missing ${expected} at ${width}px`);
      await page.getByRole('link',{name:'К геометрии'}).click(); await page.locator('input[data-key="geometry.width"]').fill('0.5');
      const before=page.url();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision')&&url.href!==before,{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click(); await fill();
      await page.locator('[name="grillage_rebar_disjoint_confirmed"]').check(); await page.locator('[name="grillage_bundle_scope_confirmed"]').check();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      const revised=page.url();
      if(!(await page.locator('body').innerText()).includes('4,6 м³')) throw new Error('Grillage recalculation failed');
      await page.goto(original);
      if(!(await page.locator('body').innerText()).includes('3,64 м³')) throw new Error('Original grillage snapshot changed');
      await page.goto(revised);
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-grillage-${width}.png`),fullPage:true}); await page.close();
    }
    process.stdout.write('Grillage QA: explicit pile choice, disjoint rebar and bundle scope, snapshots desktop/mobile PASS\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
