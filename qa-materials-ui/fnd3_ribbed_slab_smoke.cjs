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
      await page.locator('#name').fill(`QA ribbed slab ${width}`);
      const option=page.locator('#technology option').filter({hasText:'Ребристая железобетонная фундаментная плита · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('Ribbed-slab draft unavailable');
      await page.locator('#technology').selectOption(technology);
      for(const [key,value] of Object.entries({'geometry.net_area':'50','geometry.slab_thickness':'0.2',
        'geometry.rib_length':'20','geometry.rib_width':'0.4','geometry.rib_height':'0.3','geometry.rib_overlap_volume':'0.1'}))
        await page.locator(`input[data-key="${key}"]`).fill(value);
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
      await page.locator('[name="terms"]').fill('qa test only');
      const fillDetails=async()=>{
        for(const role of ['slab_lower','slab_upper','rib_longitudinal','stirrups'])
          for(const [part,value] of Object.entries({length:'12',count:'4',lap_length:'0.5',lap_count:'2',mass_per_m:'0.888'}))
            await page.locator(`input[name$=".${role}.${part}"]`).fill(value);
        await page.locator('input[name$=".formwork.material_area"]').fill('8');
        await page.locator('input[name$=".formwork.installation_area"]').fill('20');
        for(const layer of ['sand','gravel'])
          for(const [part,value] of Object.entries({area:'50',thickness:'0.2',supply_factor:'1.2'}))
            await page.locator(`input[name$=".preparation.${layer}.${part}"]`).fill(value);
      };
      await fillDetails();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      const unconfirmed=page.url();
      if(!(await page.locator('body').innerText()).includes('Не включено в итог: проверьте состав и связи.'))
        throw new Error('Rib/slab disjoint confirmation not required');
      await page.locator('[name="ribbed_concrete_disjoint_confirmed"]').check();
      await page.locator('[name="ribbed_rebar_disjoint_confirmed"]').check();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot')&&url.href!==unconfirmed,{timeout:60000}),page.getByRole('button',{name:'Пересчитать',exact:true}).click()]);
      const original=page.url(), text=await page.locator('body').innerText();
      for(const expected of ['10 м³','12 м³','2,3 м³','49 м','43,512 кг','Материалы','Работы','Нет цены','Смета неполная'])
        if(!text.includes(expected)) throw new Error(`Missing ${expected} at ${width}px`);
      if(text.includes('Не включено в итог: проверьте состав и связи.')) throw new Error('Confirmed rib/slab sections rejected');
      await page.getByRole('link',{name:'К геометрии'}).click();
      await page.locator('input[data-key="geometry.net_area"]').fill('70');
      const before=page.url();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision')&&url.href!==before,{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
      await page.locator('[name="terms"]').fill('qa test only');
      await fillDetails();
      await page.locator('[name="ribbed_concrete_disjoint_confirmed"]').check();
      await page.locator('[name="ribbed_rebar_disjoint_confirmed"]').check();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      const revised=page.url();
      if(!(await page.locator('body').innerText()).includes('14 м³')) throw new Error('Ribbed slab recalculation failed');
      await page.goto(original);
      if(!(await page.locator('body').innerText()).includes('10 м³')) throw new Error('Original ribbed slab snapshot changed');
      await page.goto(revised);
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-ribbed-slab-${width}.png`),fullPage:true}); await page.close();
    }
    process.stdout.write('Ribbed slab QA: disjoint concrete volumes, confirmation, snapshots desktop/mobile PASS\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
