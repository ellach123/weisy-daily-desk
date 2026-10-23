"""End-to-end test: seed a throw-away data folder from tests/sample-data.json, start server.py on a test port,
run tests/test.js in headless Edge against it (the page posts its PASS/FAIL report back), then check the
data file, backups, restart persistence, the first-run starter data and the server's safety rules.

    python tests/test_local.py

Windows + Microsoft Edge. Set EDGE_PATH if Edge is installed somewhere else.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / 'tests' / 'tmp'
PORT = 8799
EDGE = os.environ.get('EDGE_PATH') or next((p for p in (r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                                                          r'C:/Program Files/Microsoft/Edge/Application/msedge.exe') if Path(p).exists()), 'msedge')
SAMPLE = ROOT / 'tests' / 'sample-data.json'
checks = []


def check(name, cond, extra=''):
    checks.append(('PASS' if cond else 'FAIL', name, extra))


def stop_test_browser():
    """Headless Edge detaches from the process that started it: stop everything using the test profile."""
    prof = str(TMP / 'edge-profile')
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    "Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*' + $env:TEST_PROFILE + '*' }"
                    " | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                   env={**os.environ, 'TEST_PROFILE': prof}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def clear_tmp():
    """The headless Edge can hold its profile folder for a moment after it exits: retry for a few seconds."""
    stop_test_browser()  # also one left over from an interrupted run
    for _ in range(40):
        shutil.rmtree(TMP, ignore_errors=True)
        if not TMP.exists():
            return
        time.sleep(0.25)


def seed():
    data = json.load(open(SAMPLE, encoding='utf-8'))['collections']
    t = datetime.date.today()
    o, y, y3 = t - datetime.timedelta(days=140), t - datetime.timedelta(days=1), t - datetime.timedelta(days=3)
    data['habitLogs'] = {
        f'h-fitness_{t:%Y-%m}': {'habitId': 'h-fitness', 'month': f'{t:%Y-%m}', 'days': {f'{t:%Y-%m-%d}': {'tags': ['跑步'], 'did': ''}}},
        f'h-study_{o:%Y-%m}': {'habitId': 'h-study', 'month': f'{o:%Y-%m}', 'days': {f'{o:%Y-%m-%d}': {'tags': [], 'did': '旧笔记'}}},
    }
    data['daily'] = {f'{y:%Y-%m-%d}': {'date': f'{y:%Y-%m-%d}', 'items': [
        {'id': 'y1', 'text': '昨天没做完A', 'done': False, 'doneAt': '', 'areaId': 'side', 'taskId': 'c05'},
        {'id': 'y2', 'text': '昨天做完了', 'done': True, 'doneAt': '2026-01-01T00:00:00Z', 'areaId': '', 'taskId': ''},
        {'id': 'y3', 'text': '三天前的老任务', 'done': False, 'doneAt': '', 'areaId': '', 'taskId': '', 'since': f'{y3:%Y-%m-%d}'},
    ]}}
    clear_tmp()
    TMP.mkdir(parents=True)
    with open(TMP / 'weisy.json', 'w', encoding='utf-8') as f:
        json.dump({'format': 1, 'collections': data}, f, ensure_ascii=False)
    return data


def start(data_dir=TMP, extra=('--keep-alive',), lang='zh'):
    """lang fixes the language of a first run's examples, whatever the language of the computer running the tests."""
    p = subprocess.Popen([sys.executable, str(ROOT / 'server.py'), '--port', str(PORT), '--data', str(data_dir), '--test', *extra],
                         env={**os.environ, 'WEISY_LANG': lang})
    for _ in range(50):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/ping', timeout=1)
            return p
        except OSError:
            time.sleep(0.1)
    raise RuntimeError('server did not start')


def call(method, path, body=None, headers=None):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', method=method,
                                 data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, {}


def browser_report(page, data_dir, out_name, profile='edge-profile', extra=()):
    """Open page in a real-time headless Edge (a fresh profile); the page posts its PASS/FAIL report back to the server
    (into data_dir). The report is kept in tests/<out_name>. Returns its first line and whether everything passed."""
    report = data_dir / 'test-result.txt'
    edge = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', f'--user-data-dir={TMP / profile}', '--window-size=1400,1700', *extra,
                             '--remote-debugging-port=0', f'http://127.0.0.1:{PORT}/{page}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(240):
        if report.exists():
            break
        time.sleep(0.25)
    edge.kill(); edge.wait()
    stop_test_browser()
    time.sleep(0.5)
    text = report.read_text(encoding='utf-8') if report.exists() else 'NO REPORT (the page test did not finish)'
    (ROOT / 'tests' / out_name).write_text(text, encoding='utf-8')
    first = text.splitlines()[0] if text else ''
    nums = first.split()[1].split('/') if first.startswith('RESULT:') else ['0', '1']
    return first, nums[0] == nums[1]


def wait_exit(p, seconds):
    for _ in range(int(seconds * 10)):
        if p.poll() is not None:
            return True
        time.sleep(0.1)
    return False


def presence_tests():
    """The server stops itself when the last window is closed. Logic first (fake clock), then real processes."""
    sys.path.insert(0, str(ROOT))
    import server
    t = [0.0]
    mk = lambda: server.Presence(timeout=10, bye_grace=2, start_grace=20, clock=lambda: t[0])
    t[0] = 0; pr = mk(); t[0] = 19
    a = not pr.expired(); t[0] = 20
    check('nobody shows up after start: the server waits the start grace, then stops', a and pr.expired())
    t[0] = 0; pr = mk(); pr.hello('a'); t[0] = 5; pr.bye('a'); t[0] = 6.9
    a = not pr.expired(); t[0] = 7
    check('after the last window says bye the server stops once the short grace has passed', a and pr.expired())
    t[0] = 0; pr = mk(); pr.hello('a'); pr.hello('b'); t[0] = 1; pr.bye('a'); t[0] = 5; pr.hello('b'); t[0] = 9
    a = not pr.expired(); t[0] = 16
    check('one window closing does not stop the server while another is open; a silent one times out',
          a and pr.expired())
    t[0] = 0; pr = mk(); pr.hello('a'); pr.bye('a'); t[0] = 1; pr.hello('a2'); t[0] = 5
    check('a reload (bye, then hello from the new page) does not stop the server', not pr.expired())
    t[0] = 0; pr = mk(); pr.hello('a'); t[0] = 100; pr.resume()
    a = not pr.expired(); t[0] = 0; pr = mk(); pr.hello('a'); t[0] = 100
    check('after the computer slept the windows get a fresh start, without it they would count as gone', a and pr.expired())
    with __import__('tempfile').TemporaryDirectory() as td:
        root, home = Path(td) / 'app', Path(td) / 'home'
        root.mkdir()
        e = {'APPDATA': str(home)} if os.name == 'nt' else {}
        base = home / 'Weisy-Data' if os.name == 'nt' else home / '.weisy-data'
        check('data folder: the Weisy-Data folder in AppData (home folder elsewhere), and nothing is created there yet',
              server.default_data_dir(root, e, home) == base and not base.exists())
        check('data folder: home folder when there is no AppData', server.default_data_dir(root, {}, home) == home / '.weisy-data')
        notes = root / '.weisy'
        notes.mkdir()
        chosen = Path(td) / 'elsewhere' / 'Weisy-Data'
        chosen.mkdir(parents=True)
        (notes / 'location.txt').write_text(str(chosen), encoding='utf-8-sig')  # a BOM must not matter
        check('data folder: a folder chosen on the first run (.weisy/location.txt) is used', server.default_data_dir(root, e, home) == chosen)
        chosen.rmdir()
        try:
            server.default_data_dir(root, e, home)
            check('data folder: a chosen folder that has gone missing is refused, not silently replaced', False)
        except server.DataLocationError as err:
            check('data folder: a chosen folder that has gone missing is refused, not silently replaced',
                  str(chosen) in str(err) and 'location.txt' in str(err))
        # the real program says so too (this is what start.bat shows when it could not start): run a copy in a
        # throw-away program folder so the real one is not touched
        shutil.copy2(ROOT / 'server.py', root / 'server.py')
        r = subprocess.run([sys.executable, str(root / 'server.py'), '--check'], capture_output=True, text=True,
                           env={**os.environ, 'APPDATA': str(home), 'HOME': str(home), 'USERPROFILE': str(home)})
        check('server.py --check refuses a missing data folder with a clear message', r.returncode == 2 and str(chosen) in r.stderr, r.stderr.strip()[:60])
        (notes / 'location.txt').write_text('  \n', encoding='utf-8')
        check('data folder: an empty location.txt is ignored', server.default_data_dir(root, e, home) == base)
        (root / 'data').mkdir(); (root / 'data' / 'weisy.json').write_text('{}')
        check('data folder: an existing data/weisy.json next to the program is still used', server.default_data_dir(root, e, home) == root / 'data')
        check('Weisy leaves nothing in the user folders on its own (checking only: no Weisy-Data was created)', not base.exists())
    # a browser's idle spare connection must not block everyone else (it once froze the window on a white page)
    import socket
    p = start(TMP / 'threads')
    try:
        idle = socket.create_connection(('127.0.0.1', PORT))
        t0 = time.time()
        st, _ = call('GET', '/api/ping')
        idle.close()
        check('an idle connection does not block other requests', st == 200 and time.time() - t0 < 2, f'{time.time() - t0:.2f}s')
    finally:
        p.terminate(); p.wait()
    # real processes with short timers
    short = ['--idle-timeout', '3', '--bye-grace', '1', '--start-grace', '30']
    d = TMP / 'presence'
    p = start(d, short)
    try:
        for _ in range(5):  # 5 s: longer than the idle timeout, so only the hellos keep it alive
            call('POST', '/api/hello?id=win1'); time.sleep(1)
        check('a window that keeps saying hello keeps the server running', p.poll() is None)
        check('another website cannot say hello', call('POST', '/api/hello?id=evil', None, {'Origin': 'https://evil.example'})[0] == 403)
        check('a bad window id is refused', call('POST', '/api/hello?id=a/b')[0] == 400)
        call('POST', '/api/hello?id=win2'); call('POST', '/api/bye?id=win1'); time.sleep(2.5)
        check('closing one of two windows leaves the server running', p.poll() is None)
        call('POST', '/api/bye?id=win2')
        check('closing the last window stops the server within seconds', wait_exit(p, 6))
    finally:
        if p.poll() is None:
            p.terminate()
        p.wait()
    p = start(d, short)
    try:
        call('POST', '/api/hello?id=silent')
        check('a window that goes silent (crashed) is given up after the idle timeout', wait_exit(p, 8))
    finally:
        if p.poll() is None:
            p.terminate()
        p.wait()
    p = start(d, ['--start-grace', '2'])
    try:
        check('a server that nobody ever opened stops after the start grace', wait_exit(p, 6))
    finally:
        if p.poll() is None:
            p.terminate()
        p.wait()


def main():
    # the report has Chinese words; a console or CI log with another default encoding (cp1252 on GitHub's Windows
    # machines) must not crash the run after every check has passed
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'build.py'), '--test'], check=True, stdout=subprocess.DEVNULL)
    seeded = seed()
    srv = start()
    try:
        first, passed = browser_report('test.html#today', TMP, 'result.txt')
        check(f'browser test: {first}', passed)
        saved = json.load(open(TMP / 'weisy.json', encoding='utf-8'))
        today = datetime.date.today().isoformat()
        day = saved['collections'].get('daily', {}).get(today)
        check('page edits are written to the data file', bool(day) and any(i['text'] == '家常菜 练习 W2' and i.get('taskId') == 'c03' for i in day['items']))
        check('moved items are saved with their since date', bool(day) and any(i['text'] == '三天前的老任务' and i.get('since') for i in day['items']))
        y = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        check('the source day lost the moved items', [i['text'] for i in saved['collections']['daily'][y]['items']] == ['昨天做完了'])
        backups = list((TMP / 'backups').glob('weisy-*.json'))
        check('a dated backup was made before the first change of the day', len(backups) == 1 and backups[0].name == f'weisy-{today}.json')
        b = json.load(open(backups[0], encoding='utf-8')) if backups else {}
        check('the backup holds the data as it was before today\'s edits', b.get('collections', {}).get('daily', {}).get(today) is None)
        check('milestones added in the page are saved on the task',
              any(m.get('title') == '测试里程碑' for m in saved['collections']['tasks']['c02'].get('milestones', []))
              and len(saved['collections']['tasks']['c02']['milestones']) == len(seeded['tasks']['c02']['milestones']) + 1)
        check('no half-written temp files are left', not list(TMP.glob('.weisy-*.tmp')))
        # safety rules
        check('another website cannot write (Origin check)', call('PUT', '/api/doc/tasks/evil', {'x': 1}, {'Origin': 'https://evil.example'})[0] == 403)
        check('another website cannot read the data', call('GET', '/api/data', None, {'Origin': 'https://evil.example'})[0] == 403)
        check('bad ids are refused', call('PUT', '/api/doc/tasks/..', {'x': 1})[0] in (400, 404))
        check('updating a missing document is refused', call('PATCH', '/api/doc/tasks/nope', {'x': 1})[0] == 404)
        check('non-object bodies are refused', call('PUT', '/api/doc/tasks/zz', [1, 2])[0] == 400)
        check('only page files are served', call('GET', '/server.py')[0] == 404 and call('GET', '/../server.py')[0] == 404)
        st, _ = call('PATCH', '/api/doc/tasks/c01', {'notes': 'patched'})
        check('a valid update works', st == 200)
    finally:
        srv.terminate(); srv.wait()
    # restart: the data must still be there
    srv = start()
    try:
        st, body = call('GET', '/api/data')
        check('after a restart the data is all there', st == 200 and body['collections']['tasks']['c01']['notes'] == 'patched'
              and len(body['collections']['tasks']) == len(saved['collections']['tasks']))  # the page test adds tasks too
    finally:
        srv.terminate(); srv.wait()
    # first run: no data file yet -> the three types plus the examples from starter.json, dated today
    fresh = TMP / 'fresh'
    srv = start(fresh)
    try:
        st, body = call('GET', '/api/data')
        cols = body.get('collections', {})
        today = datetime.date.today().isoformat()
        titles = [d.get('title') or d.get('name') for c in ('tasks', 'gigPaths', 'gigs', 'habits') for d in cols.get(c, {}).values()]
        titles += [i['text'] for d in cols.get('daily', {}).values() for i in d['items']]
        check('a first run starts with the three types and the examples (all titled 示例：)',
              st == 200 and sorted(a['name'] for a in cols['areas'].values()) == sorted(['主线', '支线', '长期'])
              and len(cols.get('tasks', {})) == 4 and len(cols.get('gigPaths', {})) == 3 and len(cols.get('gigs', {})) == 3 and len(cols.get('habits', {})) == 3
              and all(t.startswith('示例：') for t in titles), f'{len(titles)} example titles')
        check('the example today-list is dated the day of the first run', list(cols.get('daily', {})) == [today]
              and cols['daily'][today]['date'] == today and '__today__' not in json.dumps(cols, ensure_ascii=False))
        check('a Chinese first run leaves the language unset (the page shows 中文)', 'lang' not in cols.get('settings', {}).get('ui', {}))
    finally:
        srv.terminate(); srv.wait()
    # the same first run on an English system: the same examples in English, and the page set to English
    fresh_en = TMP / 'fresh-en'
    srv = start(fresh_en, lang='en')
    try:
        st, body = call('GET', '/api/data')
        en = body.get('collections', {})
        titles = [d.get('title') or d.get('name') for c in ('tasks', 'gigPaths', 'gigs', 'habits') for d in en.get(c, {}).values()]
        titles += [i['text'] for d in en.get('daily', {}).values() for i in d['items']]
        same_ids = all(sorted(en.get(c, {})) == sorted(cols.get(c, {})) for c in ('areas', 'tasks', 'gigPaths', 'gigs', 'habits', 'daily'))
        check('an English first run brings the same examples in English (all titled Example:)',
              st == 200 and same_ids and sorted(a['name'] for a in en['areas'].values()) == sorted(['Main', 'Side', 'Long-term'])
              and all(t.startswith('Example: ') for t in titles)
              and not any('一' <= ch <= '鿿' for ch in json.dumps(en, ensure_ascii=False)), f'{len(titles)} example titles')
        check('an English first run sets the page to English', en.get('settings', {}).get('ui', {}).get('lang') == 'en')
        # every page and dialog of that English desk, looked at for Chinese that nobody translated
        # (an English browser, as on an English system, whatever the language of the computer running the tests)
        first, passed = browser_report('test-en.html#today', fresh_en, 'result-en.txt', 'edge-profile-en', ('--lang=en-US',))
        check(f'English check: {first}', passed)
    finally:
        srv.terminate(); srv.wait()
    sys.path.insert(0, str(ROOT))
    import server
    check('the system language decides the examples, WEISY_LANG overrides it',
          server.system_lang({'WEISY_LANG': 'en'}) == 'en' and server.system_lang({'WEISY_LANG': 'zh'}) == 'zh'
          and server.system_lang({'WEISY_LANG': 'xx'}) in ('zh', 'en'))
    presence_tests()
    fails = [c for c in checks if c[0] == 'FAIL']
    for c in checks:
        print(f'{c[0]}  {c[1]}' + (f'  — {c[2]}' if c[2] else ''))
    print(f'ALL CHECKS: {len(checks) - len(fails)}/{len(checks)} passed; full browser reports in tests/result.txt and tests/result-en.txt')
    clear_tmp()
    for f in (ROOT / 'app' / 'test.html', ROOT / 'app' / 'test-en.html'):
        if f.exists():
            f.unlink()
    return fails


if __name__ == '__main__':
    sys.exit(1 if main() else 0)  # a failing check fails the run (CI relies on this)
