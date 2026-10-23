"""Build the page the local server serves.

    python tools/build.py          -> app/index.html (+ icons and the app manifest)
    python tools/build.py --test   -> also app/test.html (the page + tests/test.js) and app/test-en.html (+ tests/test_en.js)

src/workbench.html is the source. The build inlines the two local scripts it loads
(vendor/Sortable and local-store.js), adds the icon links and the web-app manifest, and fills in the
version number from the VERSION file (the only place it is kept), and the first run's examples in both
languages (starter.json, starter.en.json), so the page can switch untouched examples along with the language.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
APP = ROOT / 'app'
ICON_SIZES = (16, 20, 24, 30, 32, 40, 48)  # 20/30/40 = 16/24/32 at 125 % display scaling
ICON_VERSION = 2  # bump when the icon images change, so the browser drops its cached copy
VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
APP_ICONS = (16, 20, 24, 30, 32, 40, 48, 64, 96, 128, 192, 256, 512)  # listed in the app manifest


def rep(s, old, new):
    assert s.count(old) == 1, f'expected exactly one match for: {old[:80]}'
    return s.replace(old, new)


def build(test=False):
    page = rep((SRC / 'workbench.html').read_text(encoding='utf-8'), '__WEISY_VERSION__', VERSION)
    starters = {lang: json.loads((ROOT / name).read_text(encoding='utf-8'))['collections']
                for lang, name in (('zh', 'starter.json'), ('en', 'starter.en.json'))}
    page = rep(page, '__WEISY_STARTERS__', json.dumps(starters, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
    vendor = (SRC / 'vendor' / 'Sortable-1.15.2.min.js').read_text(encoding='utf-8')
    store = (SRC / 'local-store.js').read_text(encoding='utf-8')
    page = rep(page, '<script src="vendor/Sortable-1.15.2.min.js"></script>\n<script src="local-store.js"></script>',
               ('<script>window.__TEST__ = true;</script>\n' if test else '')
               + f'<script>{vendor}</script>\n<script>\n{store}\n</script>')
    head = ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            # one file per size so the browser never has to shrink a big picture itself
            + ''.join(f'<link rel="icon" type="image/png" sizes="{s}x{s}" href="/icon-{s}.png?v={ICON_VERSION}">\n' for s in ICON_SIZES)
            + f'<link rel="icon" type="image/png" sizes="256x256" href="/icon.png?v={ICON_VERSION}">\n'
            + f'<link rel="icon" type="image/x-icon" sizes="any" href="/icon.ico?v={ICON_VERSION}">\n'
            '<link rel="manifest" href="/manifest.webmanifest">\n'
            '<meta name="theme-color" content="#F3F4F1">\n'
            '<style>[hidden]{display:none!important}img{max-width:100%}</style>\n</head>\n<body>\n')
    out = head + page + '\n</body>\n</html>\n'
    if not test:
        (APP / 'index.html').write_text(out, encoding='utf-8')
        return APP / 'index.html'
    # test.html: the page test (Chinese sample data); test-en.html: the English check (an English first run)
    for script, name in (('test.js', 'test.html'), ('test_en.js', 'test-en.html')):
        tests = (ROOT / 'tests' / script).read_text(encoding='utf-8')
        (APP / name).write_text(out.replace('\n</body>\n</html>\n', f'\n<script>\n{tests}\n</script>\n</body>\n</html>\n'), encoding='utf-8')
    return APP / 'test.html'


def copy_assets():
    """Icons (src/assets, made by tools/make_icons.py) and the app manifest are served next to the page.
    The manifest lets Edge / Chrome install Weisy as an app with a sharp taskbar icon."""
    for old in APP.glob('icon*'):
        old.unlink()
    for name in ('icon.png', 'icon.ico', *(f'icon-{s}.png' for s in APP_ICONS)):
        shutil.copy2(SRC / 'assets' / name, APP / name)
    manifest = {
        # one file for both languages: the full name says both, the short one (under an icon) works in either
        'name': 'Weisy Daily Desk · 潦草鼠鼠之家', 'short_name': 'Weisy',
        'start_url': '/', 'scope': '/', 'display': 'standalone',
        'launch_handler': {'client_mode': 'focus-existing'},  # opening it again brings the open window forward
        'background_color': '#F3F4F1', 'theme_color': '#F3F4F1',
        'icons': [{'src': f'/icon-{s}.png?v={ICON_VERSION}', 'sizes': f'{s}x{s}', 'type': 'image/png', 'purpose': 'any'} for s in APP_ICONS],
    }
    (APP / 'manifest.webmanifest').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    APP.mkdir(exist_ok=True)
    copy_assets()
    print('built', build())
    if '--test' in sys.argv:
        print('built', build(test=True))
