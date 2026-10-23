/* English check for Weisy. tools/build.py --test builds it into app/test-en.html; tests/test_local.py runs it on the
   data of an English first run (starter.en.json). Everything the user could have typed is English there, so a Chinese
   character on screen is a system text nobody translated. */
(async () => {
  const out = [];
  const ok = (name, cond, extra) => out.push(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra !== undefined ? '  — ' + extra : ''}`);
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const until = async (cond, ms = 3000) => { const end = Date.now() + ms; while (!cond() && Date.now() < end) await wait(20); return cond(); };
  const q = s => document.querySelector(s);
  const CJK = /[　-〿㐀-鿿＀-￯]/;
  // the 中 / EN button names the other language on purpose
  const ALLOWED = new Set(['中文', '切换到中文']);
  const show = () => {
    const pre = document.createElement('pre');
    pre.style.cssText = 'position:fixed;inset:0;z-index:9999;margin:0;padding:16px;background:#fff;color:#000;font:13px/1.55 monospace;white-space:pre-wrap;overflow:auto';
    const fails = out.filter(l => l.startsWith('FAIL')).length;
    pre.textContent = `RESULT: ${out.length - fails}/${out.length} passed\n\n` + out.join('\n');
    document.body.appendChild(pre);
    if (window.__TEST__) fetch('/api/test-result', { method: 'POST', body: pre.textContent }).catch(() => {});
  };
  /* Chinese text and attributes inside root (hidden ones too: a hidden note is shown some day). Typed values of
     inputs are data and not looked at; the options of a select are. */
  const chinese = (root = document.body) => {
    const found = new Set();
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) {
      if (n.parentElement.closest('style, script')) continue;
      // test before trimming: trim() would drop a full-width space (U+3000) copied from the Chinese text
      const raw = n.textContent, t = raw.trim();
      if (CJK.test(raw) && !ALLOWED.has(t)) found.add(t || JSON.stringify(raw));
    }
    root.querySelectorAll('*').forEach(el => ['title', 'placeholder', 'aria-label', 'data-confirm'].forEach(a => {
      const v = el.getAttribute(a);
      if (v && CJK.test(v) && !ALLOWED.has(v)) found.add(`${a}="${v}"`);
    }));
    return [...found];
  };
  const scan = (where, root) => { const f = chinese(root); ok(`${where}: no Chinese left`, f.length === 0, f.slice(0, 6).join(' | ')); };
  const click = async (sel, ms = 120) => { const el = q(sel); if (!el) return false; el.click(); await wait(ms); return true; };
  const view = async v => { await click(`.tab[data-view="${v}"]`, 200); };
  const modal = async (where, opener) => {
    const opened = await click(opener, 150);
    ok(`${where} opens`, opened && !q('#modal').hidden);
    if (opened) scan(where, q('#modal'));
    await click('#modal [data-act="close-modal"].btn', 80);
  };
  try {
    ok('before the data arrives an English browser already gets English (nothing remembered yet)', window.__LANG0__ === 'en',
      `${window.__LANG0__} (browser: ${navigator.language})`);
    await until(() => !!q('.dv'), 10000);
    await wait(200);
    ok('an English first run opens in English', document.documentElement.lang === 'en' && document.title === 'Weisy Daily Desk');

    // every system text has an English version, and none of them is Chinese (including those not on screen now)
    const D = window.__I18N__ || {};
    const any = new Proxy({}, { get: () => 2 });
    const val = v => (typeof v === 'function' ? v(any) : v);
    const missing = Object.keys(D.zh || {}).filter(k => !(k in (D.en || {})));
    const cjkEn = Object.entries(D.en || {}).filter(([, v]) => { const s = String(val(v)); return CJK.test(s) && !ALLOWED.has(s); }).map(([k]) => k);
    ok('every Chinese system text has an English version', !!D.zh && missing.length === 0, missing.join(', '));
    ok('no English system text contains Chinese', !!D.en && cjkEn.length === 0, cjkEn.join(', '));

    // the five pages
    for (const v of ['today', 'board', 'projects', 'gigs', 'habits']) { await view(v); scan(`page ${v}`, document.body); }
    ok('document title is English', !CJK.test(document.title));

    // 今日: the move box, an empty day, a toast
    await view('today');
    await click('.dv-row [data-act="dv-move"]');
    ok('the move box opens', !!q('.dv-pop'));
    scan('move box', q('.dv'));
    q('.dv-nav h2').click(); await wait(60);
    await click('.dv-nav [data-act="dv-day"]');
    scan('a day without items', q('.dv'));
    const pad = n => String(n).padStart(2, '0'), d0 = new Date(), today = `${d0.getFullYear()}-${pad(d0.getMonth() + 1)}-${pad(d0.getDate())}`;
    await click(`[data-act="dv-day"][data-d="${today}"]`);
    ok('back on today', !!q('.dv-nav h2') && q('.dv-nav h2').textContent.startsWith("Today's list"));
    const i = q('#dv-input'); i.focus(); i.value = 'Temporary item'; i.form.requestSubmit(); await wait(60);
    const row = [...document.querySelectorAll('.dv-row')].find(r => r.querySelector('.dv-text').value === 'Temporary item');
    row?.querySelector('[data-act="dv-del"]').click(); await wait(60);
    ok('deleting shows an English toast', /^Deleted: /.test(q('#toast').textContent), q('#toast').textContent);

    // 看板: an empty column shows its drop hint in English
    await view('board');
    const empty = [...document.querySelectorAll('.col-list')].find(l => !l.children.length);
    const hint = empty ? getComputedStyle(empty, '::before').content : '';
    ok('an empty board column says "Drop here"', hint === '"Drop here"', hint);

    // dialogs and the task drawer
    await modal('new task dialog', '[data-act="new-task"]');
    await view('projects');
    await click('[data-act="open-ms"]', 150);
    ok('task drawer opens', !q('#drawer').hidden);
    scan('task drawer', q('#drawer'));
    await click('#drawer [data-act="edit"]', 150);
    scan('edit task dialog', q('#modal'));
    await click('#modal [data-act="close-modal"].btn', 80);
    await click('#drawer [data-act="close-drawer"].x', 80);
    await view('gigs');
    await modal('platform dialog', '.gplat [data-act="gig-edit"]');
    await modal('side gig dialog', '[data-act="gpath-edit"]');
    await modal('new side gig dialog', '[data-act="gpath-new"]');
    await view('habits');
    await modal('check-in dialog', '.hpanel [data-act="habit-day"].btn');
    await modal('habit dialog', '[data-act="habit-edit"]');
    await modal('new habit dialog', '[data-act="habit-new"]');
    await view('today');
  } catch (err) {
    out.push('FAIL  test crashed — ' + err.message + '\n' + err.stack);
  }
  show();
})();
