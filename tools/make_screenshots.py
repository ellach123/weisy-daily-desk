"""Take the README screenshots: docs/screenshot-<page>-zh.png and docs/screenshot-<page>-en.png.

    python tools/make_screenshots.py            (both languages)
    python tools/make_screenshots.py en         (one language)

Needs Windows + Microsoft Edge. For each language it starts server.py on a test port with a fresh, throw-away data
folder (so the pictures show that language's first-run examples) and saves each page with headless Edge in that
language (the browser's language also decides the date fields). The server's throw-away data lives in
build/shots-tmp inside the repository; Edge's profile and pictures go to a temporary folder of the system, because
Edge did not write its screenshots into the repository folder on the computer this was made on. Both are removed
afterwards. msedge.exe returns before the picture is written, so each picture is waited for.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / 'build' / 'shots-tmp'
DOCS = ROOT / 'docs'
PORT = 8794
EDGE = os.environ.get('EDGE_PATH') or next((p for p in (r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                                                          r'C:/Program Files/Microsoft/Edge/Application/msedge.exe') if Path(p).exists()), 'msedge')
WIDTH = 1400
# page (route) -> picture name and height; the heights fit the first-run examples
PAGES = (('today', 'today', 900), ('board', 'board', 760), ('projects', 'tasks', 800), ('gigs', 'gigs', 370), ('habits', 'habits', 820))
BROWSER_LANG = {'zh': 'zh-CN', 'en': 'en-GB'}  # en-GB: day / month / year in the date fields


def wait_for_server():
    for _ in range(100):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/ping', timeout=1) as r:
                if b'weisy' in r.read():
                    return True
        except OSError:
            time.sleep(0.1)
    return False


def wait_for_file(path, seconds=60):
    """Until the picture exists and has stopped growing."""
    size = -1
    for _ in range(seconds * 4):
        if path.exists() and path.stat().st_size > 0 and path.stat().st_size == size:
            return True
        size = path.stat().st_size if path.exists() else -1
        time.sleep(0.25)
    return False


def shoot(lang, work):
    data = TMP / f'data-{lang}'
    server = subprocess.Popen([sys.executable, str(ROOT / 'server.py'), '--port', str(PORT), '--data', str(data), '--keep-alive'],
                              env={**os.environ, 'WEISY_LANG': lang}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = True
    try:
        if not wait_for_server():
            sys.exit(f'the server on port {PORT} did not start')
        for route, name, height in PAGES:
            out = DOCS / f'screenshot-{name}-{lang}.png'
            shot = work / f'{name}-{lang}.png'
            subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--hide-scrollbars', f'--lang={BROWSER_LANG[lang]}',
                            f'--user-data-dir={work / ("edge-" + lang)}', f'--window-size={WIDTH},{height}', '--virtual-time-budget=4000',
                            f'--screenshot={shot}', f'http://127.0.0.1:{PORT}/#{route}'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            if wait_for_file(shot):
                shutil.copyfile(shot, out)
                print(out.relative_to(ROOT), 'new picture')
            else:
                ok = False
                print(out.relative_to(ROOT), 'FAILED: Edge wrote no picture (the old one, if any, is kept)')
    finally:
        server.terminate(); server.wait()
    return ok


def main():
    langs = [a for a in sys.argv[1:] if a in BROWSER_LANG] or list(BROWSER_LANG)
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'build.py')], check=True, stdout=subprocess.DEVNULL)
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True)
    work = Path(tempfile.mkdtemp(prefix='weisy-shots-'))
    try:
        ok = all([shoot(lang, work) for lang in langs])
    finally:
        time.sleep(2)  # Edge can hold its profile folder for a moment
        shutil.rmtree(TMP, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
