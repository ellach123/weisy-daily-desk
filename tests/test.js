/* Interaction test for Weisy. tools/build.py --test builds it into app/test.html; tests/test_local.py runs it. */
(async () => {
  const out = [];
  const ok = (name, cond, extra) => out.push(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra !== undefined ? '  — ' + extra : ''}`);
  const wait = ms => new Promise(r => setTimeout(r, ms));
  // wait until a condition holds (a save reaches the server at its own pace), at most ms; a fixed wait made one check flaky
  const until = async (cond, ms = 3000) => { const end = Date.now() + ms; while (!cond() && Date.now() < end) await wait(20); return cond(); };
  const $$ = s => [...document.querySelectorAll(s)];
  const q = s => document.querySelector(s);
  const key = (k, o = {}, t = document.body) => t.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...o }));
  const pad = n => String(n).padStart(2, '0');
  const d0 = new Date(), today = `${d0.getFullYear()}-${pad(d0.getMonth() + 1)}-${pad(d0.getDate())}`;
  // the seeded data carries sample check-ins (tests/test_local.py): h-fitness today, h-study 140 days ago
  const ago = n => { const d = new Date(); d.setDate(d.getDate() - n); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const add = async text => { const i = q('#dv-input'); i.focus(); i.value = text; i.form.requestSubmit(); await wait(20); };
  const rows = () => $$('.dv-row');
  const rowByText = t => rows().find(r => r.querySelector('.dv-text').value === t);
  const setSel = (sel, v) => { sel.value = v; sel.dispatchEvent(new Event('change', { bubbles: true })); };
  const show = () => {
    const pre = document.createElement('pre');
    pre.style.cssText = 'position:fixed;inset:0;z-index:9999;margin:0;padding:16px;background:#fff;color:#000;font:13px/1.55 monospace;white-space:pre-wrap;overflow:auto';
    const fails = out.filter(l => l.startsWith('FAIL')).length;
    pre.textContent = `RESULT: ${out.length - fails}/${out.length} passed\n\n` + out.join('\n');
    document.body.appendChild(pre);
    if (window.__TEST__) fetch('/api/test-result', { method: 'POST', body: pre.textContent }).catch(() => {});
  };
  try {
    for (let i = 0; i < 100 && !document.querySelector('.dv'); i++) await wait(100); // wait until the page has its data
    await wait(200);
    // ---- page structure ----
    ok('今日 shows the daily list', !!q('.dv') && !!q('#dv-input'));
    ok('canvas is completely gone', !q('[id^="cv-"], [class*="cv-"]'));
    ok('the Chinese name 潦草鼠鼠之家 shows in the header and the window title', q('.brand-name')?.textContent === '潦草鼠鼠之家' && document.title.includes('潦草鼠鼠之家'));
    ok('date header + legend kept', !!q('#dv-head .today-head h1') && !!q('#dv-head .legend'));
    ok('the 今天完成 / 进行中 / 未完成 numbers are gone from 今日', !q('.tally') && !/今天完成|进行中|未完成/.test(q('#dv-head').innerText));
    const start = rows().length;

    // ---- add items ----
    await add('家常菜 练习 W2');
    ok('Enter in the input adds a row', rows().length === start + 1);
    ok('input is cleared and keeps focus for the next item', q('#dv-input').value === '' && document.activeElement === q('#dv-input'));
    await add('陶艺课 第二段');
    await add('买菜');
    ok('items keep the order they were typed', rows().slice(-3).map(r => r.querySelector('.dv-text').value).join('|') === '家常菜 练习 W2|陶艺课 第二段|买菜');

    // ---- suggestion ----
    let r = rowByText('家常菜 练习 W2');
    const sug = r.querySelector('[data-act="dv-link"]');
    ok('a matching big task is suggested', !!sug && sug.dataset.task === 'c03', sug && sug.textContent);
    sug.click(); await wait(20);
    r = rowByText('家常菜 练习 W2');
    ok('关联 links it and fills the branch', r.querySelector('.dv-task').value === 'c03' && r.querySelector('.dv-area').value === 'side');
    ok('suggestion disappears once linked', !r.querySelector('.dv-sug'));
    r = rowByText('陶艺课 第二段');
    ok('“陶艺课” is matched to the pottery-class task', r.querySelector('[data-act="dv-link"]')?.dataset.task === 'c02');
    r.querySelector('.dv-sx').click(); await wait(20);
    ok('× dismisses a wrong suggestion', !rowByText('陶艺课 第二段').querySelector('.dv-sug'));
    ok('nothing suggested for unrelated text', !rowByText('买菜').querySelector('.dv-sug'));

    // ---- branch & big task selects ----
    r = rowByText('陶艺课 第二段');
    setSel(r.querySelector('.dv-area'), 'main'); await wait(20);
    r = rowByText('陶艺课 第二段');
    const opts = [...r.querySelectorAll('.dv-task option')].map(o => o.value).filter(Boolean);
    const mainIds = window.__DATA__.tasks.filter(t => t.areaId === 'main' && t.status !== 'done').map(t => t.id);
    ok('choosing a branch narrows the big-task list to that branch', opts.length === mainIds.length && opts.every(v => mainIds.includes(v)), opts.join(','));
    setSel(r.querySelector('.dv-task'), 'c02'); await wait(20);
    r = rowByText('陶艺课 第二段');
    ok('choosing a big task sets it', r.querySelector('.dv-task').value === 'c02');
    r = rowByText('买菜');
    setSel(r.querySelector('.dv-task'), 'c03'); await wait(20);
    r = rowByText('买菜');
    ok('choosing a big task first fills the branch automatically', r.querySelector('.dv-area').value === 'side');
    setSel(r.querySelector('.dv-area'), 'long'); await wait(20);
    r = rowByText('买菜');
    ok('switching to another branch clears a big task from the old branch', r.querySelector('.dv-task').value === '' && r.querySelector('.dv-area').value === 'long');
    setSel(r.querySelector('.dv-area'), ''); await wait(20);
    await until(() => rowByText('买菜')?.querySelector('.dv-area').value === '');
    ok('其它 is allowed', rowByText('买菜').querySelector('.dv-area').value === '');

    // ---- edit, done, delete ----
    r = rowByText('买菜');
    const inp = r.querySelector('.dv-text'); inp.focus(); inp.value = '买菜和水果';
    inp.dispatchEvent(new Event('change', { bubbles: true })); inp.blur(); await wait(30);
    ok('editing the text saves it', !!rowByText('买菜和水果'));
    rowByText('买菜和水果').querySelector('[data-act="dv-toggle"]').click(); await wait(20);
    ok('checkbox marks it done (struck through)', rowByText('买菜和水果').classList.contains('is-done'));
    ok('counter shows done / total', /1\/\d+ 完成/.test(q('.dv-count').textContent), q('.dv-count').textContent);
    rowByText('买菜和水果').querySelector('[data-act="dv-toggle"]').click(); await wait(20);
    await until(() => { const row = rowByText('买菜和水果'); return !!row && !row.classList.contains('is-done'); });
    ok('checkbox again un-does it', !rowByText('买菜和水果').classList.contains('is-done'));
    rowByText('买菜和水果').querySelector('[data-act="dv-del"]').click(); await wait(20);
    ok('× deletes the row', !rowByText('买菜和水果'));

    // ---- typing is never lost to a background refresh ----
    const box = q('#dv-input'); box.focus(); box.value = '还没按回车';
    window.dispatchEvent(new Event('resize'));
    document.querySelector('[data-view="today"]').click(); await wait(30);
    ok('a refresh while typing keeps the unsent text', q('#dv-input').value === '还没按回车');
    box.value = ''; box.blur(); await wait(20);

    // ---- day navigation ----
    q('[data-act="dv-day"]').click(); await wait(20);
    ok('‹ shows the previous day', !!q('.dv-nav h2') && !q('.dv-nav h2').textContent.includes('今日清单') && !!q('[data-act="dv-day"][data-d="' + today + '"]'));
    ok('previous day keeps its own list (nothing carried over)', !rowByText('家常菜 练习 W2'));
    q('[data-act="dv-day"][data-d="' + today + '"]').click(); await wait(20);
    ok('回到今天 returns to today', q('.dv-nav h2').textContent.includes('今日清单') && !!rowByText('家常菜 练习 W2'));

    // ---- saved ----
    await until(() => { const w = window.__writes['daily/' + today]; return !!w && w.items.length === rows().length; });
    await until(() => (window.__writes['daily/' + today]?.items || []).some(i => i.text === '家常菜 练习 W2' && i.taskId === 'c03' && i.areaId === 'side'));
    const saved = window.__writes['daily/' + today];
    ok('the day is saved as one document', !!saved && saved.items.length === rows().length, saved ? saved.items.length + ' items' : 'none');
    ok('saved items carry branch and big task', saved && saved.items.some(i => i.text === '家常菜 练习 W2' && i.taskId === 'c03' && i.areaId === 'side'));

    // ---- move unfinished items to a chosen date ----
    const yday = ago(1), md2 = s => `${Number(s.slice(5, 7))}/${Number(s.slice(8, 10))}`;
    const tmr = (() => { const d = new Date(); d.setDate(d.getDate() + 1); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; })();
    const moveVia = async (rowText, date) => {
      rowByText(rowText).querySelector('[data-act="dv-move"]').click(); await wait(20);
      const inp = q('#dv-mvdate'); inp.value = date; inp.dispatchEvent(new Event('input', { bubbles: true }));
      q('[data-act="dv-move-go"]').click(); await wait(250); // two saves in a row (target day, then source day)
    };
    ok('no "still unfinished" banner on today', !/没完成|未完成的条目|移入未完成/.test(q('.dv').innerText));
    ok('unfinished rows on today have 移到', !!rowByText('家常菜 练习 W2').querySelector('[data-act="dv-move"]'));
    rowByText('家常菜 练习 W2').querySelector('[data-act="dv-move"]').click(); await wait(20);
    ok('移到 opens a date box only (no quick options)', !!q('.dv-pop #dv-mvdate') && q('.dv-pop').querySelectorAll('button').length === 1);
    ok('from today the date box starts at tomorrow', q('#dv-mvdate').value === tmr, q('#dv-mvdate').value);
    const mi = q('#dv-mvdate'); mi.value = today; mi.dispatchEvent(new Event('input', { bubbles: true }));
    ok('the day being viewed cannot be chosen (确定 disabled)', q('[data-act="dv-move-go"]').disabled);
    key('Escape'); await wait(20);
    ok('Esc closes the date box', !q('.dv-pop'));
    rowByText('家常菜 练习 W2').querySelector('[data-act="dv-move"]').click(); await wait(20);
    q('.dv-nav h2').click(); await wait(20);
    ok('clicking elsewhere closes it too', !q('.dv-pop'));

    await add('挪到明天的事');
    const beforeMove = rows().length;
    await moveVia('挪到明天的事', tmr);
    ok('moving to tomorrow removes it from today', !rowByText('挪到明天的事') && rows().length === beforeMove - 1);
    let tmw = window.__writes['daily/' + tmr];
    ok('tomorrow gets it at the end with since = today', !!tmw && tmw.items[tmw.items.length - 1].text === '挪到明天的事' && tmw.items[tmw.items.length - 1].since === today);
    q(`[data-act="dv-day"][data-d="${tmr}"]`).click(); await wait(20);
    ok('on tomorrow it shows “M/D 起” of the day it was added to', rowByText('挪到明天的事')?.querySelector('.dv-since')?.textContent === `${md2(today)} 起`);
    await moveVia('挪到明天的事', today);
    q(`[data-act="dv-day"][data-d="${today}"]`).click(); await wait(20);
    ok('moved back to its own day, the 起 label disappears', !!rowByText('挪到明天的事') && !rowByText('挪到明天的事').querySelector('.dv-since'));
    await moveVia('挪到明天的事', ago(2));
    await until(() => (window.__writes['daily/' + ago(2)]?.items || []).some(i => i.text === '挪到明天的事' && i.since === today) && !rowByText('挪到明天的事'));
    const pw = window.__writes['daily/' + ago(2)];
    ok('can move to an earlier date', !!pw && pw.items.some(i => i.text === '挪到明天的事' && i.since === today) && !rowByText('挪到明天的事'));

    q(`[data-act="dv-day"][data-d="${yday}"]`).click(); await wait(20);
    ok('a past day shows 移到 on each unfinished row', !!rowByText('昨天没做完A')?.querySelector('[data-act="dv-move"]') && !!rowByText('三天前的老任务')?.querySelector('[data-act="dv-move"]'));
    ok('done rows have no 移到', !rowByText('昨天做完了').querySelector('[data-act="dv-move"]'));
    rowByText('昨天没做完A').querySelector('[data-act="dv-move"]').click(); await wait(20);
    ok('from a past day the date box starts at today', q('#dv-mvdate').value === today);
    key('Escape'); await wait(10);
    await until(() => !(window.__writes['daily/' + today]?.items || []).some(i => i.text === '挪到明天的事')); // its move off today is saved
    const todayBefore = window.__writes['daily/' + today].items.length;
    await moveVia('昨天没做完A', today);
    ok('the moved row leaves the old day at once', !rowByText('昨天没做完A') && !!rowByText('昨天做完了'));
    await moveVia('三天前的老任务', today);
    await until(() => { const w = window.__writes['daily/' + yday]; return !!w && w.items.map(i => i.text).join('|') === '昨天做完了'; });
    const yw = window.__writes['daily/' + yday];
    ok('old day is saved without the moved rows', !!yw && yw.items.map(i => i.text).join('|') === '昨天做完了', yw && yw.items.map(i => i.text).join('|'));
    await until(() => (window.__writes['daily/' + today]?.items || []).slice(-2).map(i => i.text).join('|') === '昨天没做完A|三天前的老任务');
    const tw = window.__writes['daily/' + today].items;
    ok('today gets them at the end, in the order moved', tw.length === todayBefore + 2 && tw.slice(-2).map(i => i.text).join('|') === '昨天没做完A|三天前的老任务', tw.slice(-2).map(i => i.text).join('|'));
    ok('moved rows keep branch and big task', tw.find(i => i.text === '昨天没做完A').taskId === 'c05' && tw.find(i => i.text === '昨天没做完A').areaId === 'side');
    ok('since = the day list it was first added to', tw.find(i => i.text === '昨天没做完A').since === yday);
    ok('since keeps the earliest day after several moves', tw.find(i => i.text === '三天前的老任务').since === ago(3));
    q(`[data-act="dv-day"][data-d="${today}"]`).click(); await wait(20);
    const mA = rowByText('昨天没做完A'), mB = rowByText('三天前的老任务');
    ok('today shows “M/D 起” after the text', mA?.querySelector('.dv-since')?.textContent === `${md2(yday)} 起` && mB?.querySelector('.dv-since')?.textContent === `${md2(ago(3))} 起`, `${mA?.querySelector('.dv-since')?.textContent} / ${mB?.querySelector('.dv-since')?.textContent}`);
    ok('no “顺延 N 天” wording anywhere', !/顺延/.test(q('.dv').innerText));
    ok('rows added today have no 起 label', !rowByText('家常菜 练习 W2').querySelector('.dv-since'));
    ok('moved rows are the last two on today', rows().slice(-2).map(r => r.querySelector('.dv-text').value).join('|') === '昨天没做完A|三天前的老任务');

    // ---- shortcuts ----
    key('n');
    ok('N opens the new-task window again on 今日', !q('#modal').hidden && !!q('#tf-title'));
    key('Escape');

    // ---- right column: every big task ----
    const bt = q('.bt');
    ok('任务 column is shown on 今日', !!bt && q('.bt-h h2').textContent.trim() === '任务');
    ok('今日 says 今日清单 / 任务, never 大任务 or 今日任务', /今日清单/.test(q('#main').innerText) && !/大任务|今日任务/.test(document.body.innerText));
    const dvR = q('.dv').getBoundingClientRect(), btR = bt.getBoundingClientRect();
    ok('it sits to the right of the daily list, top-aligned', btR.left >= dvR.right && Math.abs(btR.top - dvR.top) < 2, `${Math.round(dvR.right)} → ${Math.round(btR.left)}`);
    const btItems = $$('.bt > .bt-list .bt-item');
    const openN = window.__DATA__.tasks.filter(t => t.status !== 'done').length;
    ok('lists every unfinished big task', btItems.length === openN, `${btItems.length}/${openN}`);
    ok('each task carries its own 主线/支线/长期 tag', btItems.every(b => /^(主线|支线|长期)$/.test((b.querySelector('.atag')?.textContent || '').trim())));
    const rankOf = { 主线: 0, 支线: 1, 长期: 2 }, ranks = btItems.map(b => rankOf[b.querySelector('.atag').textContent.trim()]);
    ok('ordered 主线 → 支线 → 长期', ranks.every((r, i) => i === 0 || r >= ranks[i - 1]), ranks.join(''));
    ok('the last 长期 task is the last in the column', btItems[btItems.length - 1]?.dataset.id === 'c11');
    const anyRow = rows().find(r => r.querySelector('.dv-area').value === ''); // 其它: the picker lists every branch
    ok('in the task picker the storeroom task sits under 长期, and the branch picker has no 系统', !!anyRow.querySelector('.dv-task optgroup[label="长期"] option[value="c11"]') && ![...anyRow.querySelectorAll('.dv-area option, .dv-task optgroup')].some(o => (o.label || o.textContent).includes('系统')));
    ok('no group headings and no 下一步 line', !bt.innerText.includes('下一步') && !bt.querySelector('.area-h, .tier-h, .cv-dg'));
    const c03b = q('.bt-item[data-id="c03"]');
    const pushN = () => Number((q('.bt-h .n')?.textContent.match(/今日正在推进 (\d+) 项/) || [])[1]);
    const linkedToday = () => new Set(rows().map(r => r.querySelector('.dv-task').value).filter(Boolean)).size;
    ok('the column says 今日正在推进 N 项 = different tasks linked today (no 未完成 count)', pushN() === linkedToday() && pushN() === $$('.bt-item.on').length && !/未完成/.test(q('.bt-h').textContent), `${q('.bt-h .n')?.textContent} / linked ${linkedToday()}`);
    const n0 = pushN();
    await add('临时关联测试');
    setSel(rowByText('临时关联测试').querySelector('.dv-task'), 'c07'); await wait(30);
    ok('linking a row to another task counts up at once', pushN() === n0 + 1);
    rowByText('临时关联测试').querySelector('[data-act="dv-del"]').click(); await wait(30);
    ok('deleting it counts back down at once', pushN() === n0);
    ok('a big task linked today is highlighted with a count', !!c03b && c03b.classList.contains('on') && /今天 \d+ 条/.test(c03b.textContent), c03b && c03b.querySelector('.bt-today')?.textContent);
    ok('an unlinked big task is not highlighted', !q('.bt-item[data-id="c07"]').classList.contains('on'));
    ok('the big task of a moved item is highlighted today', q('.bt-item[data-id="c05"]').classList.contains('on'));
    const doneN = window.__DATA__.tasks.filter(t => t.status === 'done').length;
    if (doneN) {
      ok('done big tasks are collapsed by default', !q('.bt-done'));
      q('[data-act="bt-done"]').click(); await wait(20);
      ok('已完成 expands them', $$('.bt-done').length === doneN);
      q('[data-act="bt-done"]').click(); await wait(20);
    } else ok('no 已完成 toggle when nothing is done', !q('[data-act="bt-done"]'));
    q('.bt-item[data-id="c02"]').click(); await wait(20);
    ok('clicking a task opens its detail panel, not the editor', !q('#drawer').hidden && q('#modal').hidden && q('#drawer .d-title')?.textContent === window.__DATA__.tasks.find(t => t.id === 'c02').title);
    key('Escape'); await wait(10);

    // ---- big tasks show their daily items ----
    q('[data-view="board"]').click(); await wait(30);
    const c03 = q('.card[data-id="c03"]');
    ok('看板 card shows its daily items', !!c03 && /今日清单：本周 \d+ 件 · 最近/.test(c03.textContent), c03 && c03.querySelector('.card-daily')?.textContent);
    ok('看板 has no 今日焦点 marks', !q('#main').innerText.includes('今日焦点'));
    c03.click(); await wait(20);
    ok('a 看板 card opens the detail panel, whose 进展日志 lists its daily items', !q('#drawer').hidden && q('#modal').hidden && q('#drawer .log')?.textContent.includes('家常菜 练习 W2'));
    q('#drawer [data-act="edit"]').click(); await wait(20);
    ok('task editor has no 放进今日焦点 option', !q('#modal').hidden && !q('#tf-focus'));
    key('Escape'); await wait(10); key('Escape'); await wait(10);
    q('.card[data-id="c05"]').click(); await wait(20);
    ok('a moved item is listed once in its task (no duplicate)', [...document.querySelectorAll('#drawer .log li')].filter(li => li.textContent.includes('昨天没做完A')).length === 1);
    key('Escape'); await wait(10);
    q('[data-view="projects"]').click(); await wait(30);
    ok('任务 tiles show no 下一步 line', !$$('#main .pcard .pact').length && !$$('#main .pcard').some(c => [...c.querySelectorAll('.pcard-main > span')].some(x => x.textContent.trim().startsWith('下一步'))));
    ok('任务 card shows its daily items', $$('.pdaily').some(x => x.textContent.includes('今日清单')));

    // ---- one kind of thing — 任务 — with its own milestones and progress log ----
    ok('the 项目 tab is now called 任务', q('[data-view="projects"]').textContent.trim() === '任务');
    ok('the page title is 任务', q('.view-head h1').textContent.trim().startsWith('任务'));
    ok('no 新建里程碑项目 button and no 项目 wording', !q('[data-act="new-project"]') && !/项目/.test(q('.view-head').innerText));
    ok('no 大任务 / 今日任务 wording on 任务', !/大任务|今日任务/.test(document.body.innerText));
    const tilesN = $$('#main .pcard').length;
    ok('one tile per task, nothing else', tilesN === window.__DATA__.tasks.length, `${tilesN}/${window.__DATA__.tasks.length}`);
    ok('the storeroom task is a task of its own under 长期', !!q('.pcard-main[data-id="c11"]') && window.__DATA__.tasks.find(t => t.id === 'c11')?.areaId === 'long');
    ok('no 系统 category anywhere', !window.__DATA__.areas.some(a => a.id === 'system') && !$$('.chip').some(c => c.textContent.includes('系统')) && !/系统/.test(q('#main').innerText));
    const c02ms = q('.pcard-ms[data-act="open-ms"][data-id="c02"]');
    ok('the pottery-class task shows its milestone progress', !!c02ms && /\d+\/5 里程碑/.test(c02ms.textContent), c02ms && c02ms.textContent.trim().slice(0, 40));
    ok('task titles are unchanged', window.__DATA__.tasks.find(t => t.id === 'c02').title.startsWith('申请周末陶艺'));
    c02ms.click(); await wait(30);
    const dr = () => q('#drawer');
    ok('clicking the progress opens 里程碑 and 进展日志', !dr().hidden && dr().innerText.includes('里程碑') && dr().innerText.includes('进展日志') && dr().querySelectorAll('.ms').length === 5);
    let mf = dr().querySelector('[data-form="ms-add"]');
    mf.querySelector('[name="title"]').value = '测试里程碑'; mf.requestSubmit(); await wait(80);
    await until(() => (window.__writes['tasks/c02']?.milestones || []).some(m => m.title === '测试里程碑'));
    ok('a milestone added there is saved on the task', (window.__writes['tasks/c02']?.milestones || []).some(m => m.title === '测试里程碑'));
    ok('…and shows at once, with the cursor still in the box', dr().querySelectorAll('.ms').length === 6 && document.activeElement === dr().querySelector('[data-form="ms-add"] [name="title"]'));
    [...dr().querySelectorAll('.ms')].find(x => x.textContent.includes('测试里程碑')).querySelector('[data-act="ms-toggle"]').click(); await wait(80);
    await until(() => (window.__writes['tasks/c02']?.milestones || []).find(m => m.title === '测试里程碑')?.done === true);
    ok('ticking a milestone saves it', (window.__writes['tasks/c02']?.milestones || []).find(m => m.title === '测试里程碑')?.done === true);
    const logLis = () => [...dr().querySelectorAll('.log li')];
    const potRow = logLis().find(li => li.textContent.includes('陶艺课 第二段'));
    ok('进展日志 lists the today-list items linked to the task, unticked ones with ○', !!potRow && potRow.querySelector('.lg-st')?.textContent === '○' && potRow.querySelector('.date').textContent === today);
    const logDates = logLis().map(li => li.querySelector('.date').textContent);
    const handN = (window.__DATA__.tasks.find(t => t.id === 'c02').log || []).length;
    ok('older hand-written entries sit in the same timeline, newest first', handN > 0 && logLis().filter(li => !li.querySelector('.lg-st')).length === handN && logDates.every((d, i) => i === 0 || d <= logDates[i - 1]), logDates.join(' '));
    ok('no box for typing a log entry by hand', !dr().querySelector('[data-form="log-add"]'));
    ok('linked entries are not deleted from here (only in 今日清单)', !potRow.querySelector('[data-act="log-del"]'));
    dr().querySelector('[data-act="edit"]').click(); await wait(30);
    ok('编辑任务 in the drawer opens the task editor', !q('#modal').hidden && q('#tf-title')?.value.startsWith('申请周末陶艺'));
    key('Escape'); await wait(20);
    ok('Esc closes the editor first, the drawer stays', q('#modal').hidden && !dr().hidden);
    key('Escape'); await wait(20);
    ok('a second Esc closes the drawer', dr().hidden);
    q('.pcard-main[data-id="c02"]').click(); await wait(30);
    ok('clicking the tile itself also opens the detail panel', !dr().hidden && q('#modal').hidden);
    const sec = name => [...dr().querySelectorAll('.dsec')].find(x => x.querySelector('h3')?.textContent.trim().startsWith(name));
    ok('备注 is an edit box in the panel, line breaks kept', !!sec('备注')?.querySelector('textarea#dn-notes') && q('#dn-notes').value.includes('\n') && q('#dn-notes').value.includes('日程'));
    ok('panel order: 下一步/备注 before 里程碑 before 进展日志', (() => { const hs = $$('#drawer .dsec h3').map(h => h.textContent.trim().replace(/\s.*$/, '')); return hs.indexOf('下一步') < hs.indexOf('备注') && hs.indexOf('备注') < hs.indexOf('里程碑') && hs.indexOf('里程碑') < hs.indexOf('进展日志'); })(), $$('#drawer .dsec h3').map(h => h.textContent.trim()).join(' | '));
    ok('下一步 box is there even when empty, with a hint', !!q('#dn-next') && q('#dn-next').placeholder.includes('马上能动手'));
    const nx = q('#dn-next'); nx.focus(); nx.value = '面板里写的下一步'; nx.dispatchEvent(new Event('change', { bubbles: true })); await wait(100);
    ok('下一步 saves when the box is left', window.__writes['tasks/c02']?.next === '面板里写的下一步' && q('#dn-next').value === '面板里写的下一步');
    q('#dn-next').focus(); key('Enter', {}, q('#dn-next')); await wait(20);
    ok('Enter leaves the 下一步 box', document.activeElement !== q('#dn-next'));
    const no = q('#dn-notes'); no.focus(); no.value = no.value + '\n面板新增一行'; no.dispatchEvent(new Event('change', { bubbles: true })); await wait(100);
    ok('备注 saves with its line breaks', (window.__writes['tasks/c02']?.notes || '').endsWith('\n面板新增一行'));
    const no2 = q('#dn-notes'); no2.focus(); no2.value += '\nEsc前写的'; key('Escape', {}, no2); await wait(100);
    ok('Esc while typing still saves, and closes the panel', dr().hidden && (window.__writes['tasks/c02']?.notes || '').endsWith('Esc前写的'));
    q('.pcard-main[data-id="c02"]').click(); await wait(30);
    dr().querySelector('[data-act="edit"]').click(); await wait(30);
    ok('the task editor has no 项目 field', !q('#tf-project') && !/项目/.test([...q('#modal').querySelectorAll('label')].map(l => l.firstChild.textContent).join('')));
    ok('the task window has no 下一步 / 备注 (标题 / 类型 / 状态 / 截止日期 only)', !q('#tf-next') && !q('#tf-notes') && [...q('#modal').querySelectorAll('label.f')].map(l => l.firstChild.textContent.trim()).join('/') === '标题/类型/状态/截止日期');
    ok('the editor is just the form: no milestone / log section', !q('#modal [data-act="open-ms"]') && !/里程碑|进展日志/.test(q('#modal').innerText));
    q('#tf-status').value = 'waiting'; q('form[data-form="task"]').requestSubmit(); await wait(300); // save + re-render
    const c02w = window.__writes['tasks/c02'];
    ok('保存 in the window keeps 下一步 / 备注 as they were, back in the panel', q('#modal').hidden && !dr().hidden && c02w?.status === 'waiting' && c02w.next === '面板里写的下一步' && c02w.notes.endsWith('Esc前写的'));
    dr().querySelector('[data-act="edit"]').click(); await wait(30);
    q('#tf-status').value = 'doing'; q('form[data-form="task"]').requestSubmit(); await wait(100);
    key('Escape'); await wait(20);
    key('n'); await wait(20);
    ok('the new-task window is just the form', !q('#modal').hidden && !q('#modal [data-act="open-ms"]') && !q('#tf-project') && !q('#tf-next') && !q('#tf-notes') && !/进展日志/.test(q('#modal').innerText));
    q('#tf-title').value = '新建后直接写下一步'; q('#tf-area').value = 'main'; q('form[data-form="task"]').requestSubmit(); await wait(200);
    ok('添加 opens the new task’s detail panel with the cursor in 下一步', !dr().hidden && dr().querySelector('.d-title')?.textContent === '新建后直接写下一步' && document.activeElement === q('#dn-next'));
    key('Escape'); await wait(20);
    q('[data-view="board"]').click(); await wait(30);
    ok('看板 cards show no project name', !q('.card .proj'));
    ok('看板 cards show no 下一步 line', !$$('.col-list .card .card-next').length && !$$('.col-list .card').some(c => /下一步\s/.test(c.querySelector('.card-title') ? c.textContent.replace(c.querySelector('.card-title').textContent, '') : '')));
    q('[data-view="projects"]').click(); await wait(30);
    for (const v of ['gigs', 'habits']) {
      q(`[data-view="${v}"]`).click(); await wait(30);
      ok(`${v} page renders`, q('#main').children.length > 0 && !q('#main .state'));
    }
    q('[data-view="habits"]').click(); await wait(30);
    // ---- the mouse on 习惯, cheering after a check-in ----
    ok('the mouse sits by 「＋ 新习惯」', !!q('.hab-head img.hab-mouse') && !!q('.hab-head [data-act="habit-new"]'));
    q('.hpanel[data-id="h-lang"] [data-act="habit-day"]').click(); await wait(30);
    q('form[data-form="checkin"]').requestSubmit(); await wait(150);
    await until(() => q('.hab-head .hab-cheer')?.textContent === '🥳🎉✨'); // cheers once the check-in is saved
    ok('checking in makes it cheer 🥳🎉✨', q('.hab-head .hab-cheer')?.textContent === '🥳🎉✨');
    await wait(2400);
    ok('…and the cheer goes away again', !q('.hab-head .hab-cheer'));
    q('.hpanel[data-id="h-lang"] [data-act="habit-day"]').click(); await wait(30);
    q('[data-act="ci-remove"]').click(); await wait(10); q('[data-act="ci-remove"]').click(); await wait(100);
    ok('removing a check-in does not cheer', !q('.hab-head .hab-cheer'));
    const weeksOf = id => { const g = q(`.hpanel[data-id="${id}"] .hm-grid`); return g ? g.children.length / 7 : -1; };
    ok('heatmap: no check-ins yet → 12 weeks', weeksOf('h-lang') === 12, weeksOf('h-lang'));
    ok('heatmap: first check-in this week → still the 12-week minimum', weeksOf('h-fitness') === 12, weeksOf('h-fitness'));
    ok('heatmap: first check-in 20 weeks ago → starts that week (21 weeks)', weeksOf('h-study') === 21, weeksOf('h-study') + ' weeks; ' + (q('.hpanel[data-id="h-study"] .hp-stat')?.textContent.trim() || 'no panel'));
    ok('heatmap: the old check-in is drawn in the first column', !!q('.hpanel[data-id="h-study"] .hm-grid').querySelector(`[data-d="${ago(140)}"].on`));
    // ---- 其它 is a type of its own, named 类型 everywhere ----
    key('n'); await wait(20);
    const areaSel = q('#tf-area');
    ok('the task window says 类型, ordered 主线/支线/长期/其它', areaSel.closest('label').firstChild.textContent.trim() === '类型' && [...areaSel.options].map(o => o.textContent).join('/') === '主线/支线/长期/其它', [...areaSel.options].map(o => o.textContent).join('/'));
    ok('a new task starts as 其它', areaSel.value === '');
    q('#tf-title').value = '其它测试任务'; q('form[data-form="task"]').requestSubmit();
    const savedOther = () => Object.values(window.__writes).find(v => v && v.title === '其它测试任务');
    await until(() => savedOther() && q('#modal').hidden);
    const newT = savedOther();
    ok('it saves without choosing a type', !!newT && newT.areaId === '' && q('#modal').hidden);
    q('[data-view="projects"]').click(); await wait(40);
    const noneH = $$('.area-h').find(h => h.textContent.includes('其它'));
    ok('任务 page: a 其它 group after 长期, holding it', !!noneH && $$('.area-h').indexOf(noneH) === $$('.area-h').length - 1 && noneH.parentElement.textContent.includes('其它测试任务'));
    ok('a 其它 chip appears after the types', $$('.chip').at(-1)?.textContent.includes('其它'));
    q('.chip[data-area="none"]').click(); await wait(40);
    ok('the 其它 chip shows only 其它 tasks', $$('#main .pcard').length === 1 && q('#main .pcard').textContent.includes('其它测试任务'));
    q('.chip[data-area="none"]').click(); await wait(10);
    key('n'); await wait(20);
    ok('with 其它 picked, a new task also starts as 其它', q('#tf-area').value === '');
    key('Escape'); await wait(10);
    q('.chip[data-area="all"]').click(); await wait(40);
    q('[data-view="board"]').click(); await wait(40);
    const qa = q('#quickAdd'); qa.value = '快速添加测试'; qa.form.requestSubmit(); await wait(120);
    ok('board quick add under 全部 adds it straight away as 其它', q('#modal').hidden && Object.values(window.__writes).some(v => v && v.title === '快速添加测试' && v.areaId === ''));
    ok('its card carries a grey 其它 tag', $$('.card').find(c => c.textContent.includes('快速添加测试'))?.querySelector('.atag')?.textContent.trim() === '其它');
    q('.chip[data-area="main"]').click(); await wait(40);
    const qa2 = q('#quickAdd'); qa2.value = '主线快速添加'; qa2.form.requestSubmit(); await wait(120);
    ok('with 主线 picked, quick add files it under 主线', Object.values(window.__writes).some(v => v && v.title === '主线快速添加' && v.areaId === 'main'));
    q('.chip[data-area="all"]').click(); await wait(40);
    q('[data-view="today"]').click(); await wait(40);
    const btAll = $$('.bt > .bt-list .bt-item');
    ok('今日 task column lists 其它 tasks last, tagged 其它', btAll.at(-1)?.querySelector('.atag')?.textContent.trim() === '其它');
    const r0 = rows().find(r => r.querySelector('.dv-area').value === '');
    ok('今日清单 uses the same order, and an untyped row still shows 其它', [...r0.querySelectorAll('.dv-area option')].map(o => o.textContent).join('/') === '主线/支线/长期/其它' && r0.querySelector('.dv-area').selectedOptions[0].textContent === '其它');
    ok('the 今日清单 task picker has a 其它 group', !!r0?.querySelector('.dv-task optgroup[label="其它"]'));
    rowByText('陶艺课 第二段').querySelector('[data-act="dv-toggle"]').click(); await wait(60);
    q('[data-view="projects"]').click(); await wait(40);
    q('.pcard-ms[data-act="open-ms"][data-id="c02"]').click(); await wait(40);
    const pot2 = [...q('#drawer').querySelectorAll('.log li')].find(li => li.textContent.includes('陶艺课 第二段'));
    ok('ticking it in 今日清单 turns it ✓ in the 进展日志', pot2?.querySelector('.lg-st')?.textContent === '✓');
    key('Escape'); await wait(20);
    q('[data-view="today"]').click(); await wait(40);
    q('.bt-item[data-id="c02"]').click(); await wait(30);
    ok('opened from 今日 too, the panel shows the ✓', [...q('#drawer').querySelectorAll('.log li')].find(li => li.textContent.includes('陶艺课 第二段'))?.querySelector('.lg-st')?.textContent === '✓');
    key('Escape'); await wait(20);
    rowByText('陶艺课 第二段').querySelector('[data-act="dv-toggle"]').click(); await wait(60);
    // ---- type and task can be picked in the add box ----
    const na = () => q('#dv-new-area'), nk = () => q('#dv-new-task');
    ok('the add box has a type picker starting blank (— 类型 —, no colour) and a task picker', [...na().options].map(o => o.textContent).join('/') === '— 类型 —/主线/支线/长期/其它' && na().value === '' && !na().classList.contains('typed') && nk().value === '');
    setSel(na(), 'main'); await wait(20);
    const groups = [...nk().querySelectorAll('optgroup')].map(g => g.label);
    ok('picking a type narrows the task list to that type', groups.length === 1 && groups[0] === '主线' && nk().querySelectorAll('optgroup option').length > 0, groups.join(','));
    setSel(nk(), 'c02'); await wait(20);
    await add('输入时就选好的');
    const pre = rowByText('输入时就选好的');
    ok('Enter adds it with that type and task', pre?.querySelector('.dv-area').value === 'main' && pre?.querySelector('.dv-task').value === 'c02' && !pre.querySelector('.dv-sug'));
    ok('…and both pickers go back to — 类型 — / no task', na().value === '' && na().selectedOptions[0].textContent === '— 类型 —' && !na().classList.contains('typed') && nk().value === '');
    await add('不选类型直接回车');
    ok('not choosing a type saves it as 其它', rowByText('不选类型直接回车')?.querySelector('.dv-area').selectedOptions[0].textContent === '其它');
    rowByText('不选类型直接回车').querySelector('[data-act="dv-del"]').click(); await wait(20);
    setSel(na(), 'none'); await wait(20);
    ok('picking 其它 colours the picker; it saves the same way', na().classList.contains('typed') && na().value === 'none');
    setSel(na(), ''); await wait(20);
    setSel(nk(), 'c03'); await wait(20);
    ok('picking a task first sets the type to match', na().value === 'side');
    const box2 = q('#dv-input'); box2.focus(); box2.value = '先打字再选';
    setSel(na(), 'long'); await wait(20);
    ok('changing the type to one the task is not in clears the task, even while text is typed', na().value === 'long' && nk().value === '' && q('#dv-input').value === '先打字再选');
    box2.form.requestSubmit(); await wait(30);
    ok('typed text + picks are added together', rowByText('先打字再选')?.querySelector('.dv-area').value === 'long');
    rowByText('输入时就选好的').querySelector('[data-act="dv-del"]').click(); await wait(20);
    // ---- the add box suggests a task while typing ----
    const typeIn = v => { const i = q('#dv-input'); i.focus(); i.value = v; i.dispatchEvent(new Event('input', { bubbles: true })); };
    const liveSug = () => q('#dv-new-sug [data-act="dv-new-use"]');
    typeIn('家常菜 练习 W3');
    ok('typing shows 「可能属于 … · 选用」 under the add box', liveSug()?.dataset.task === 'c03' && /可能属于：.*选用/.test(q('#dv-new-sug').textContent));
    liveSug().click(); await wait(20);
    ok('选用 fills the task and type pickers and hides the hint, text kept', nk().value === 'c03' && na().value === 'side' && !liveSug() && q('#dv-input').value === '家常菜 练习 W3' && document.activeElement === q('#dv-input'));
    q('#dv-input').form.requestSubmit(); await wait(30);
    ok('Enter adds it with the suggested task', rowByText('家常菜 练习 W3')?.querySelector('.dv-task').value === 'c03' && na().value === '' && !liveSug());
    rowByText('家常菜 练习 W3').querySelector('[data-act="dv-del"]').click(); await wait(20);
    typeIn('陶艺课 第三段');
    ok('a different text suggests a different task', liveSug()?.dataset.task === 'c02');
    q('#dv-new-sug .dv-sx').click(); await wait(20);
    typeIn('陶艺课 第三段 ');
    ok('× hides it for this item, even while typing on', !liveSug());
    q('#dv-input').form.requestSubmit(); await wait(30);
    ok('…and the row still gets its own suggestion after Enter', rowByText('陶艺课 第三段')?.querySelector('.dv-sug [data-act="dv-link"]')?.dataset.task === 'c02');
    rowByText('陶艺课 第三段').querySelector('[data-act="dv-del"]').click(); await wait(20);
    typeIn('家常菜 再来');
    ok('the next item suggests again', !!liveSug());
    setSel(nk(), 'c05'); await wait(20);
    ok('picking a task by hand hides the hint', !liveSug());
    setSel(nk(), ''); await wait(20);
    typeIn('');
    ok('an empty box shows no hint', !liveSug());
    rowByText('先打字再选').querySelector('[data-act="dv-del"]').click(); await wait(20);
    ok('nothing says 领域, 分支 or 未分类 any more', !/领域|分支|未分类/.test(document.body.innerText) && !q('[aria-label*="领域"], [aria-label*="分支"]'));
    q('[data-view="habits"]').click(); await wait(30);
    // ---- the little mouse ----
    q('[data-view="today"]').click(); await wait(40);
    const hr = new Date().getHours(), expect = hr >= 5 && hr < 12 ? '早上好！' : hr >= 12 && hr < 18 ? '下午好！' : hr >= 18 && hr < 23 ? '晚上好，辛苦啦' : '夜深了，早点休息';
    ok('the mouse is on 今日 with the greeting for this hour', !!q('.dv-pal img.dv-mouse') && q('#dv-greet')?.textContent === expect, q('#dv-greet')?.textContent);
    const tick = rows().find(r => !r.classList.contains('is-done'));
    tick.querySelector('[data-act="dv-toggle"]').click(); await wait(60);
    ok('ticking an item: ✨🎉🥳 appear and the bubble hides', q('.dv-pal.cheering') && q('.dv-cheer')?.textContent === '✨🎉🥳' && getComputedStyle(q('#dv-greet')).display === 'none');
    await wait(2400);
    ok('after the celebration the bubble is back', !q('.dv-pal.cheering') && !q('.dv-cheer') && getComputedStyle(q('#dv-greet')).display !== 'none');
    rows().find(r => r.dataset.id === tick.dataset.id).querySelector('[data-act="dv-toggle"]').click(); await wait(60);
    ok('un-ticking does not celebrate', !q('.dv-pal.cheering'));
    q('[data-view="habits"]').click(); await wait(30);
    q('[data-view="gigs"]').click(); await wait(40);
    const chipR = q('.grow .ptabs .chip')?.getBoundingClientRect(), actR = q('.grow .gacts [data-act="gig-new-plat"]')?.getBoundingClientRect();
    ok('副业 buttons and 编辑副业 / 添加平台 sit on one line', !!chipR && !!actR && Math.abs((chipR.top + chipR.bottom) / 2 - (actR.top + actR.bottom) / 2) < 4 && actR.left > chipR.right, chipR && actR ? `${Math.round((chipR.top + chipR.bottom) / 2)} vs ${Math.round((actR.top + actR.bottom) / 2)}` : 'missing');
    ok('…and no empty note line when there is nothing to say', !q('.gbar') && (q('.gnote-line') ? q('.gnote-line').textContent.trim().length > 0 : true));
    q('[data-view="habits"]').click(); await wait(30);
    ok('five tabs (no job-search page)', $$('.tab').length === 5 && !q('[data-view="jobs"]'));
    // ---- tabs drag right away (no long hold); a plain click still switches the page ----
    const tabIds = () => $$('.tab').map(b => b.dataset.view);
    const tBefore = tabIds(), t0 = q('.tab'), t1 = $$('.tab')[1];
    const tr0 = t0.getBoundingClientRect(), tr1 = t1.getBoundingClientRect();
    const pt = (type, x, y, target = document) => target.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', button: 0, buttons: type === 'pointerup' ? 0 : 1, isPrimary: true }));
    const mv = (type, x, y) => document.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, button: 0, buttons: 1 }));
    const tcy = tr0.top + tr0.height / 2;
    pt('pointerdown', tr0.left + 5, tcy, t0); t0.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: tr0.left + 5, clientY: tcy, button: 0, buttons: 1 }));
    await wait(16);
    for (let x = tr0.left + 5; x <= tr1.right - 2; x += 8) { pt('pointermove', x, tcy); mv('mousemove', x, tcy); await wait(16); }
    pt('pointerup', tr1.right - 2, tcy); document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: tr1.right - 2, clientY: tcy, button: 0 }));
    await wait(300);
    const tAfter = tabIds();
    ok('dragging a tab a little way reorders it at once (no hold) and saves the order', tAfter[0] === tBefore[1] && tAfter[1] === tBefore[0] && JSON.stringify(window.__writes['settings/ui']?.tabOrder) === JSON.stringify(tAfter), `${tBefore.join(',')} → ${tAfter.join(',')}`);
    await wait(350);
    $$('.tab').find(b => b.dataset.view === 'habits').click(); await wait(40);
    ok('a plain click on a tab still switches the page', q('.tab[aria-current="page"]')?.dataset.view === 'habits');
    q('[data-view="today"]').click(); await wait(30);
    ok('back on 今日 the list is intact', !!rowByText('家常菜 练习 W2') && !!rowByText('陶艺课 第二段'));

    // ---- 中 / EN: the language switch also switches the examples nobody has changed, nothing else ----
    // two example tasks (one with its title changed) and an example habit without check-ins, saved the way a first run does
    const putDoc = (path, body) => fetch('/api/doc/' + path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    await putDoc('tasks/ex-holiday', { title: '示例：计划夏天的假期', areaId: 'main', status: 'doing', next: '定好出发日期', notes: '', due: '', order: 9000,
      milestones: [{ id: 'em1', title: '选好目的地', due: '', done: false }] });
    await putDoc('tasks/ex-bike', { title: '我的自行车：换内胎', areaId: 'side', status: 'todo', next: '换一条新内胎', notes: '', due: '', order: 9001, milestones: [] });
    await putDoc('habits/ex-sport', { name: '示例：运动', color: '#2B8A3E', order: 99, useTags: true, tags: ['跑步', '骑车', '游泳'], mins: true, longNote: false, didLabel: '备注', archived: false });
    document.dispatchEvent(new Event('visibilitychange')); // the page reloads the data, as when another window saved
    await until(() => !!q('.bt') && q('.bt').textContent.includes('示例：计划夏天的假期'));
    const before = JSON.stringify(window.__writes);
    const changedOthers = () => Object.keys(window.__writes).filter(k => /^(tasks|habits|gigs|gigPaths)\//.test(k) && !/\/ex-/.test(k)
      && JSON.stringify(window.__writes[k]) !== JSON.stringify(JSON.parse(before)[k]));
    q('#langBtn').click();
    await until(() => window.__writes['tasks/ex-holiday']?.title === 'Example: Plan the summer holiday' && window.__writes['areas/main']?.name === 'Main'
      && window.__writes['habits/ex-sport']?.name === 'Example: Exercise'); // each document is its own save
    const hol = window.__writes['tasks/ex-holiday'], bike = window.__writes['tasks/ex-bike'], sport = window.__writes['habits/ex-sport'];
    ok('EN: an untouched example task switches title, next step and milestones', !!hol && hol.title === 'Example: Plan the summer holiday'
      && hol.next === 'Agree on the dates' && hol.milestones[0].title === 'Pick the destination', hol && JSON.stringify([hol.title, hol.next]));
    ok('EN: an example whose title was changed keeps that title, its untouched next step switches', !!bike && bike.title === '我的自行车：换内胎' && bike.next === 'Fit a new inner tube');
    ok('EN: an example habit without check-ins switches name, label and options', !!sport && sport.name === 'Example: Exercise' && sport.didLabel === 'Notes'
      && sport.tags.join('/') === 'Running/Cycling/Swimming');
    ok('EN: the types switch too', window.__writes['areas/main']?.name === 'Main' && window.__writes['areas/side']?.desc === 'opens more doors');
    ok('EN: tasks and habits that are not examples are not touched', changedOthers().length === 0, changedOthers().join(', '));
    q('#langBtn').click();
    await until(() => window.__writes['tasks/ex-holiday']?.title === '示例：计划夏天的假期' && window.__writes['areas/main']?.name === '主线'
      && window.__writes['habits/ex-sport']?.name === '示例：运动' && window.__writes['areas/side']?.desc === '拓宽渠道');
    const hol2 = window.__writes['tasks/ex-holiday'], bike2 = window.__writes['tasks/ex-bike'];
    ok('中: switching back restores the examples', hol2.title === '示例：计划夏天的假期' && hol2.milestones[0].title === '选好目的地'
      && window.__writes['habits/ex-sport']?.tags.join('/') === '跑步/骑车/游泳' && window.__writes['areas/side']?.desc === '拓宽渠道');
    ok('中: the changed title is still the user\'s own', bike2.title === '我的自行车：换内胎' && bike2.next === '换一条新内胎');
    ok('中: the page is back in 中文', document.documentElement.lang === 'zh-CN' && q('.brand-name').textContent === '潦草鼠鼠之家');
  } catch (err) {
    out.push('FAIL  test crashed — ' + err.message + '\n' + err.stack);
  }
  show();
})();
