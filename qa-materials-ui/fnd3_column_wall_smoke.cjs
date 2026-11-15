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
const scenarios=[
  {name:'Бетонные и железобетонные столбчатые фундаменты', fields:{'element.length':'0.4','element.width':'0.4',
    'element.height':'1.5','element.count':'10'}, change:'element.count', value:'20', before:'2,4 м³', after:'4,8 м³',
    roles:['column_rebar','stirrups'], slug:'column'},
  {name:'Монолитная железобетонная стена подвала', fields:{'geometry.wall_length':'20','geometry.wall_height':'3',
    'geometry.wall_thickness':'0.3','geometry.opening_area':'4','geometry.wall_overlap_volume':'0.2'},
    change:'geometry.wall_length', value:'30', before:'16,6 м³', after:'25,6 м³',
    roles:['inner_vertical','inner_horizontal','outer_vertical','outer_horizontal'], slug:'wall'},
];
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    for(const width of [1440,390]) for(const scenario of scenarios){
      const page=await browser.newPage({viewport:{width,height:941}});
      await page.goto(`${base}/api/v1/auth/login/view?next=${encodeURIComponent(destination)}`);
      await page.locator('#email').fill(credentials.email); await page.locator('#password').fill(credentials.password);
      await Promise.all([page.waitForURL(url=>url.pathname===destination,{timeout:60000}),page.locator('#login-submit').click()]);
      await page.locator('#name').fill(`QA ${scenario.slug} ${width}`);
      const option=page.locator('#technology option').filter({hasText:`${scenario.name} · черновик`}).first();
      const technology=await option.getAttribute('value');
      if(!technology) throw new Error(`${scenario.slug} draft unavailable`);
      await page.locator('#technology').selectOption(technology);
      for(const [key,value] of Object.entries(scenario.fields)) await page.locator(`input[data-key="${key}"]`).fill(value);
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision'),{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click();
      const calculate=async()=>{
        await page.locator('[name="region"]').fill(`qa-${crypto.randomBytes(8).toString('hex')}`);
        await page.locator('[name="terms"]').fill('qa test only');
        for(const role of scenario.roles)
          for(const [part,value] of Object.entries({length:'12',count:'4',lap_length:'0.5',lap_count:'2',mass_per_m:'0.888'}))
            await page.locator(`input[name$=".${role}.${part}"]`).fill(value);
        await page.locator('input[name$=".formwork.material_area"]').fill('8');
        await page.locator('input[name$=".formwork.installation_area"]').fill('20');
        await page.locator('[name="column_wall_rebar_disjoint_confirmed"]').check();
        await Promise.all([page.waitForURL(url=>url.searchParams.has('snapshot'),{timeout:60000}),page.getByRole('button',{name:'Рассчитать',exact:true}).click()]);
      };
      await calculate();
      const original=page.url(), text=await page.locator('body').innerText();
      for(const expected of [scenario.before,'49 м','43,512 кг','Материалы','Работы','Нет цены','Смета неполная'])
        if(!text.includes(expected)) throw new Error(`Missing ${expected} for ${scenario.slug} at ${width}px`);
      await page.getByRole('link',{name:'К геометрии'}).click();
      await page.locator(`input[data-key="${scenario.change}"]`).fill(scenario.value);
      const before=page.url();
      await Promise.all([page.waitForURL(url=>url.searchParams.has('revision')&&url.href!==before,{timeout:60000}),page.getByRole('button',{name:'Сохранить',exact:true}).click()]);
      await page.getByRole('link',{name:'Открыть предварительную смету'}).click(); await calculate();
      const revised=page.url();
      if(!(await page.locator('body').innerText()).includes(scenario.after)) throw new Error(`${scenario.slug} recalculation failed`);
      await page.goto(original);
      if(!(await page.locator('body').innerText()).includes(scenario.before)) throw new Error(`${scenario.slug} original snapshot changed`);
      await page.goto(revised);
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error(`Overflow at ${width}px`);
      await page.screenshot({path:path.join(__dirname,`fnd3-${scenario.slug}-${width}.png`),fullPage:true}); await page.close();
    }
    process.stdout.write('Column and wall QA: concrete, openings, recalculation and snapshots desktop/mobile PASS\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(`${error.message}\n`);process.exitCode=1;});
