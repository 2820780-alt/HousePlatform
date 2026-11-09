import { spawn, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { createServer as createPortServer } from 'node:net';
import { mkdtempSync, mkdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { strict as assert } from 'node:assert';

const root = realpathSync(process.cwd());
const profile = mkdtempSync(path.join(root, '.m2-home-profile-'));
const resultsDir = mkdtempSync(path.join(root, 'qa-artifacts-m2-home-'));
const html = execFileSync(path.join(root, '.venv', 'Scripts', 'python.exe'),
  ['-X', 'utf8', 'tests/m2_home_visual_fixture.py'], { cwd: root, encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 });
const imagePaths = {
  '/api/v1/module2/home-assets/cutaway': path.join(root, 'app/assets/module2_home/cutaway.svg'),
  '/api/v1/module2/home-assets/exterior': path.join(root, 'app/assets/module2_home/exterior.svg'),
};
let savedAction = null;
const quickActionMutations = [];
const server = createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (pathname === '/api/v1/module2') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
  } else if (pathname === '/api/v1/quick-actions/user-module') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    if (req.method !== 'GET') quickActionMutations.push(pathname);
    res.end(JSON.stringify(savedAction ? [savedAction] : []));
  } else if (pathname === '/api/v1/quick-actions/user-module/fixture-action/run') {
    quickActionMutations.push(pathname);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'READY', route: '/qa-action-target' }));
  } else if (imagePaths[pathname]) {
    res.writeHead(200, { 'Content-Type': 'image/svg+xml' });
    res.end(readFileSync(imagePaths[pathname]));
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end('{}');
  }
});

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const listen = (s) => new Promise((resolve) => s.listen(0, '127.0.0.1', () => resolve(s.address().port)));
const close = (s) => new Promise((resolve) => s.close(resolve));
let browser;
let socket;
try {
  const appPort = await listen(server);
  const probe = createPortServer();
  const debugPort = await listen(probe);
  await close(probe);
  browser = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', [
    '--headless=new', '--disable-gpu', '--disable-background-networking', '--disable-sync',
    '--disable-extensions', '--no-first-run', '--no-default-browser-check',
    `--user-data-dir=${profile}`, `--remote-debugging-port=${debugPort}`, 'about:blank',
  ], { cwd: root, windowsHide: true, stdio: 'ignore' });
  let target;
  for (let attempt = 0; attempt < 80; attempt++) {
    try {
      const response = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: 'PUT' });
      if (response.ok) { target = await response.json(); break; }
    } catch {}
    await wait(250);
  }
  assert.ok(target?.webSocketDebuggerUrl, 'Edge did not start');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let nextId = 1;
  const pending = new Map();
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    }
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression, awaitPromise = false) => {
    const result = await send('Runtime.evaluate', { expression, awaitPromise, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  };
  await send('Page.enable');
  await send('Runtime.enable');
  const sizes = [[1440,900],[1600,900],[1280,800],[1024,768],[360,800],[390,844],[430,932],[768,1024]];
  const results = [];
  for (const [width, height] of sizes) {
    await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url: `http://127.0.0.1:${appPort}/api/v1/module2` });
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await evaluate("document.readyState === 'complete' && !!document.getElementById('home-house-image')")) break;
      await wait(100);
    }
    await evaluate("document.getElementById('home-house-image').decode().then(() => true)", true);
    const metrics = await evaluate(`(() => {
      const image = document.getElementById('home-house-image');
      const rect = image.getBoundingClientRect();
      const card = document.getElementById('home-card').getBoundingClientRect();
      return { scrollWidth: document.documentElement.scrollWidth, innerWidth, imageWidth: rect.width,
        imageHeight: rect.height, naturalWidth: image.naturalWidth, cardWidth: card.width,
        navCount: document.querySelectorAll('.m2-sidebar-items > .m2-nav-link, .m2-sidebar .m2-nav-heading > a').length };
    })()`);
    assert.ok(metrics.scrollWidth <= width + 1, `${width}: horizontal overflow ${metrics.scrollWidth}`);
    assert.ok(metrics.naturalWidth > 0 && metrics.imageWidth > width * (width < 740 ? .7 : .25), `${width}: image missing or too small`);
    assert.ok(metrics.cardWidth > 0 && metrics.navCount === 3, `${width}: card or navigation missing`);
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    writeFileSync(path.join(resultsDir, `${width}x${height}.png`), Buffer.from(shot.data, 'base64'));
    results.push({ width, height, ...metrics });
  }
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: `http://127.0.0.1:${appPort}/api/v1/module2` });
  await wait(1000);
  const hover = await evaluate(`(() => { const x = document.querySelector('g[data-view="cutaway"] .home-zone[data-part="roof"]'); x.dispatchEvent(new MouseEvent('mouseenter')); return !document.getElementById('home-tooltip').hidden; })()`);
  assert.equal(hover, true, 'hover tooltip did not open');
  const selection = await evaluate(`(() => { document.querySelector('g[data-view="cutaway"] .home-zone[data-part="roof"]').dispatchEvent(new MouseEvent('click', {bubbles:true})); return { title: document.getElementById('home-card-title').textContent, url: location.search }; })()`);
  assert.ok(selection.title.includes('Крыша') && selection.url.includes('part=roof'));
  const switched = await evaluate(`(() => { document.querySelector('[data-house-view="exterior"]').click(); return { src: document.getElementById('home-house-image').getAttribute('src'), pressed: document.querySelector('[data-house-view="exterior"]').getAttribute('aria-pressed') }; })()`);
  assert.ok(switched.src.endsWith('/exterior') && switched.pressed === 'true');
  await evaluate("document.getElementById('home-house-image').decode().then(() => true)", true);
  const exteriorShot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  writeFileSync(path.join(resultsDir, 'exterior-1440x900.png'), Buffer.from(exteriorShot.data, 'base64'));
  await evaluate('history.back()');
  await wait(300);
  const backState = await evaluate("({ url: location.search, pressed: document.querySelector('[data-house-view=cutaway]').getAttribute('aria-pressed') })");
  assert.ok(backState.url.includes('part=roof') && backState.pressed === 'true', 'history back did not restore view');
  const keyboard = await evaluate(`(() => { const zone = document.querySelector('g[data-view="cutaway"] .home-zone[data-part="floors"]');
    zone.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    return { title: document.getElementById('home-card-title').textContent, href: document.getElementById('home-card-link').getAttribute('href') };
  })()`);
  assert.ok(keyboard.title.includes('Перекрытия') && keyboard.href.endsWith('/FLOORS_AND_STAIRS'));
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await send('Emulation.setTouchEmulationEnabled', { enabled: true });
  await send('Page.navigate', { url: `http://127.0.0.1:${appPort}/api/v1/module2` });
  await wait(1000);
  const touchPoint = await evaluate(`(() => {
    const rect = document.querySelector('g[data-view="cutaway"] .home-zone[data-part="roof"] .home-hit').getBoundingClientRect();
    return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, width: rect.width, height: rect.height};
  })()`);
  assert.ok(touchPoint.width >= 40 && touchPoint.height >= 40, 'mobile hit area is too small');
  await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: touchPoint.x, y: touchPoint.y }] });
  await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  const touchTitle = await evaluate("document.getElementById('home-card-title').textContent");
  assert.ok(touchTitle.includes('Крыша'), 'touch did not select roof');
  const mobileMenu = await evaluate(`(() => { const button = document.querySelector('.m2-mobile-menu');
    const menu = document.getElementById('m2-sidebar-items');
    const initiallyHidden = getComputedStyle(menu).display === 'none'; button.click();
    return { initiallyHidden, expanded: button.getAttribute('aria-expanded'), visible: getComputedStyle(menu).display !== 'none' };
  })()`);
  assert.deepEqual(mobileMenu, { initiallyHidden: true, expanded: 'true', visible: true });
  assert.equal(quickActionMutations.length, 0, 'home created a quick action automatically');
  savedAction = { id: 'fixture-action', sourceModuleCode: 'MODULE_02_KNOWLEDGE_BASE',
    actionKey: 'VIEW', title: 'Сохранённое действие', route: '/qa-action-target', status: 'ACTIVE' };
  await send('Page.navigate', { url: `http://127.0.0.1:${appPort}/api/v1/module2` });
  await wait(1000);
  const savedVisible = await evaluate("!document.querySelector('[data-quick-action-module-bar]').hidden && document.querySelector('[data-quick-action-module-bar]').textContent.includes('Сохранённое действие')");
  assert.equal(savedVisible, true, 'saved quick action did not appear');
  await evaluate("document.querySelector('.atom-module-quick-action').click()");
  await wait(500);
  assert.deepEqual(quickActionMutations, ['/api/v1/quick-actions/user-module/fixture-action/run']);
  writeFileSync(path.join(resultsDir, 'result.json'), JSON.stringify({ results, hover, selection, switched, backState, keyboard, touchPoint, touchTitle, mobileMenu, savedVisible, quickActionMutations }, null, 2));
  console.log(JSON.stringify({ resultsDir, viewports: results.length, hover, selection, switched, backState, keyboard, touchPoint, touchTitle, mobileMenu, savedVisible, quickActionMutations }));
} finally {
  if (socket) socket.close();
  if (browser) {
    browser.kill();
    await Promise.race([new Promise((resolve) => browser.once('exit', resolve)), wait(3000)]);
  }
  await close(server);
  const resolvedProfile = realpathSync(profile);
  if (path.dirname(resolvedProfile) !== root || !path.basename(resolvedProfile).startsWith('.m2-home-profile-')) {
    throw new Error('Unexpected browser profile path; not removed');
  }
  for (let attempt = 0; attempt < 5; attempt++) {
    try { rmSync(resolvedProfile, { recursive: true, force: true }); break; }
    catch (error) { if (attempt === 4) throw error; await wait(500); }
  }
}
