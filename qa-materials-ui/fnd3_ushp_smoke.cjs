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
      await page.locator('#name').fill(`QA USHP ${width}`);
      const option=page.locator('#technology option').filter({hasText:'Утепленная шведская плита (УШП) · черновик'}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error('USHP draft unavailable');
      await page.locator('#technology').selectOption(technology);
      for(const [key,value] of Object.entries({'geometry.net_area':'50','geometry.slab_thickness':'0.2',
        'geometry.rib_length':'20','geometry.rib_width':'0.4','geometry.rib_height':'0.3','geometry.rib_overlap_volume':'0.1',
        'geometry.wall_area':'0','geometry.slab_area':'6','geometry.edge_area':'2'}))
        await page.locator(`input[data-key="${key}"]`).fill(value);
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      const calculate=async()=>{
        await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
        await page.locator('[name="terms"]').fill('qa test only');
        for(const zone of ['slab','edge']){
          await page.locator(`input[name$=".xps_${zone}.sheet_length"]`).fill('1.2');
          await page.locator(`input[name$=".xps_${zone}.sheet_width"]`).fill('0.6');
        }
        for(const [part,value] of Object.entries({length:'12',count:'4',lap_length:'0.5',lap_count:'2',mass_per_m:'0.888'}))
          await page.locator(`input[name$=".lower_x.${part}"]`).fill(value);
        for(const layer of ['sand','gravel'])
          for(const [part,value] of Object.entries({area:'50',thickness:'0.2',supply_factor:'1.2'}))
            await page.locator(`input[name$=".preparation.${layer}.${part}"]`).fill(value);
        await page.locator('input[name$=".geotextile.area"]').fill('50');
        await page.locator('input[name$=".geotextile.overlap_area"]').fill('5');
        await page.locator('[name="ribbed_concrete_disjoint_confirmed"]').check();
        await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      };
      await calculate();
      const original=page.url(), text=await page.locator('body').innerText();
      for(const expected of ['10 м³','12 м³','55 м²','2,3 м³','6,48 м²','9 шт.','2,16 м²','3 шт.','49 м','Нет цены','Смета неполная'])
        if(!text.includes(expected)) throw new Error(`Missing ${expected} at ${width}px`);
      await page.getByRole('link',{name:'К геометрии'}).click(); await page.locator('input[data-key="geometry.net_area"]').fill('70');
      const before=page.url();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision')&&url.href!==before,{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click(); await calculate();
      const revised=page.url();
      if(!(await page.locator('body').innerText()).includes('14 м³')) throw new Error('USHP recalculation failed');
      await page.goto(original);
      if(!(await page.locator('body').innerText()).includes('10 м³')) throw new Error('Original USHP snapshot changed');
      await page.goto(revised);
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-ushp-${width}.png`),fullPage:true}); await page.close();
    }
    process.stdout.write('USHP QA: disjoint concrete, XPS zones, reinforcement, snapshots desktop/mobile PASS\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
