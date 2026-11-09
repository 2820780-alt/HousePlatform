import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { strict as assert } from 'node:assert';
import { test } from 'node:test';

test('M2 sidebar menus start closed and toggle independently', () => {
  const template = readFileSync('templates/_module2_sidebar.html', 'utf8');
  const script = template.match(/<script>([\s\S]*?)<\/script>/)?.[1];
  assert.ok(script);
  assert.match(template, /id="m2-encyclopedia-menu" hidden/);
  assert.match(template, /id="m2-technologies-menu" hidden/);

  const menus = {
    'm2-encyclopedia-menu': { hidden: true },
    'm2-technologies-menu': { hidden: true },
  };
  const buttons = Object.keys(menus).map((id) => ({
    attributes: { 'aria-controls': id, 'aria-expanded': 'false' },
    getAttribute(name) { return this.attributes[name]; },
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(_event, callback) { this.click = callback; },
  }));
  runInNewContext(script, { document: {
    querySelectorAll: () => buttons,
    getElementById: (id) => menus[id],
  } });
  buttons[0].click();
  assert.equal(buttons[0].getAttribute('aria-expanded'), 'true');
  assert.equal(menus['m2-encyclopedia-menu'].hidden, false);
  assert.equal(menus['m2-technologies-menu'].hidden, true);
  buttons[0].click();
  assert.equal(buttons[0].getAttribute('aria-expanded'), 'false');
  assert.equal(menus['m2-encyclopedia-menu'].hidden, true);
  buttons[1].click();
  assert.equal(menus['m2-technologies-menu'].hidden, false);
});

test('encyclopedia menu loads public category names once and keeps text as text', async () => {
  const template = readFileSync('templates/_module2_sidebar.html', 'utf8');
  const script = [...template.matchAll(/<script>([\s\S]*?)<\/script>/g)][1]?.[1];
  assert.ok(script);
  let requests = 0;
  const button = {
    getAttribute: () => 'true',
    addEventListener(_event, callback) { this.click = callback; },
  };
  const list = { replaceChildren(fragment) { this.nodes = fragment.childNodes; } };
  const document = {
    querySelector: () => button,
    getElementById: () => list,
    createDocumentFragment: () => ({ childNodes: [], appendChild(node) { this.childNodes.push(node); } }),
    createElement: () => ({}),
  };
  const fetch = async () => {
    requests++;
    return { ok: true, json: async () => ({ categories: [{ code: 'FOUNDATIONS', name: '<Фундаменты>' }] }) };
  };
  runInNewContext(script, { document, fetch, encodeURIComponent });
  await button.click();
  await button.click();
  assert.equal(requests, 1);
  assert.equal(list.nodes[0].textContent, '<Фундаменты>');
  assert.equal(list.nodes[0].href, '/api/v1/module2/encyclopedia/categories/FOUNDATIONS');
});
