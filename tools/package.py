"""Build the Windows package that needs no Python: dist/Weisy-v<VERSION>-windows.zip

    .venv\\Scripts\\python tools\\package.py          (developer tools: pip install -r requirements-dev.txt)

Steps: build the page (tools/build.py) -> PyInstaller makes Weisy-daily-desk.exe in "one folder" form (not "one file":
that form unpacks itself into the user's temp folder on every start) -> zip it -> unzip the zip to a scratch
folder and start the real Weisy-daily-desk.exe once (smoke test: it must answer, save into the chosen data folder,
stop by itself after the window says goodbye, and write nothing anywhere else).
Everything written while packaging stays in build/ and dist/ (PyInstaller's cache included). Windows only.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'
DIST = ROOT / 'dist'
VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
NAME = f'Weisy-v{VERSION}'
ZIP = DIST / f'{NAME}-windows.zip'
PORT = 8780  # the packaged program always uses Weisy's own port; the smoke test checks that it is free first


def run(cmd, **kw):
    print('>', ' '.join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def version_file():
    """Windows file properties of Weisy-daily-desk.exe (shown in Explorer and Task Manager)."""
    nums = tuple(int(x) for x in VERSION.split('.')) + (0,)
    text = f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('080404b0', [
      StringStruct('CompanyName', 'ellach123'),
      StringStruct('FileDescription', '潦草鼠鼠之家 Weisy'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'Weisy-daily-desk'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', 'Weisy-daily-desk.exe'),
      StringStruct('ProductName', '潦草鼠鼠之家 Weisy'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
'''
    path = BUILD / 'version_info.txt'
    path.write_text(text, encoding='utf-8')
    return path


def package():
    shutil.rmtree(BUILD / 'pyi-dist', ignore_errors=True)
    shutil.rmtree(DIST, ignore_errors=True)
    BUILD.mkdir(exist_ok=True)
    DIST.mkdir()
    run([sys.executable, str(ROOT / 'tools' / 'build.py')])
    sep = os.pathsep
    data = [(ROOT / 'app', 'app'), (ROOT / 'starter.json', '.'), (ROOT / 'starter.en.json', '.'), (ROOT / 'tools' / 'setup.ps1', 'tools'),
            (ROOT / 'src' / 'assets' / 'icon.ico', 'src/assets'), (ROOT / 'src' / 'assets' / 'icon-64.png', 'src/assets')]
    env = {**os.environ, 'PYINSTALLER_CONFIG_DIR': str(BUILD / 'pyinstaller-cache')}  # keep its cache out of the user folders
    run([sys.executable, '-m', 'PyInstaller', str(ROOT / 'launcher.py'), '--name', 'Weisy-daily-desk', '--onedir', '--windowed',
         '--noconfirm', '--clean', '--icon', str(ROOT / 'src' / 'assets' / 'icon.ico'), '--version-file', str(version_file()),
         '--distpath', str(BUILD / 'pyi-dist'), '--workpath', str(BUILD / 'pyi-work'), '--specpath', str(BUILD),
         *[x for src, dest in data for x in ('--add-data', f'{src}{sep}{dest}')],
         *[x for m in ('tkinter', '_tkinter', 'unittest', 'pydoc_data', 'lib2to3') for x in ('--exclude-module', m)]],
        env=env, cwd=ROOT)
    folder = BUILD / 'pyi-dist' / 'Weisy-daily-desk'
    shutil.copy2(ROOT / 'LICENSE', folder / 'LICENSE.txt')
    py_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if py_license.exists():  # the package carries a Python runtime: include its licence
        shutil.copy2(py_license, folder / 'LICENSE-Python.txt')
    with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(folder.rglob('*')):
            if f.is_file():
                z.write(f, f'{NAME}/{f.relative_to(folder).as_posix()}')
    print(f'{ZIP.relative_to(ROOT)}: {ZIP.stat().st_size / 1024 / 1024:.1f} MB')


def _call(method, path):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', method=method)
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.read()


def _listening():
    try:
        return b'weisy' in _call('GET', '/api/ping')
    except OSError:
        return False


def smoke_test():
    """Unzip like a user would and start the real Weisy-daily-desk.exe once."""
    if _listening():
        sys.exit(f'Port {PORT} is in use (is Weisy open?): close it and run the smoke test again.')
    box = BUILD / 'smoke'
    shutil.rmtree(box, ignore_errors=True)
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(box)
    program = box / NAME
    data = box / 'my-data' / 'Weisy-Data'
    data.mkdir(parents=True)
    notes = program / '.weisy'
    notes.mkdir()
    (notes / 'location.txt').write_text(str(data), encoding='utf-8')          # as if the user had picked this folder
    (notes / 'desktop-shortcut.txt').write_text('no', encoding='utf-8')      # and answered the dialog
    appdata_default = Path(os.environ.get('APPDATA', '')) / 'Weisy-Data'
    had_default = appdata_default.exists()
    proc = subprocess.Popen([str(program / 'Weisy-daily-desk.exe')], env={**os.environ, 'WEISY_NO_WINDOW': '1'})
    checks = []
    try:
        for _ in range(100):
            if _listening():
                break
            time.sleep(0.1)
        checks.append(('Weisy-daily-desk.exe starts and answers', _listening()))
        _call('POST', '/api/hello?id=smoke')
        body = json.loads(_call('GET', '/api/data'))
        checks.append(('the first run brings the starter examples', len(body['collections'].get('tasks', {})) == 4))
        req = urllib.request.Request(f'http://127.0.0.1:{PORT}/api/doc/tasks/smoke', method='PUT',
                                     data=json.dumps({'title': 'smoke'}).encode(), headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=5).read()
        saved = json.loads((data / 'weisy.json').read_text(encoding='utf-8'))
        checks.append(('a change is saved in the chosen data folder', 'smoke' in saved['collections']['tasks']))
        checks.append(('the page carries the version number', f"'v{VERSION}'" in _call('GET', '/').decode('utf-8')))
        _call('POST', '/api/bye?id=smoke')
        try:
            proc.wait(timeout=25)
        except subprocess.TimeoutExpired:
            pass
        checks.append(('it stops by itself after the last window said goodbye', proc.poll() is not None))
        checks.append(('nothing was created in the default data folder in AppData', appdata_default.exists() == had_default))
        made = sorted(p.name for p in notes.iterdir())
        checks.append(('Weisy keeps its own notes in .weisy only', made == ['desktop-shortcut.txt', 'location.txt']))
    finally:
        if proc.poll() is None:
            proc.kill()
    for name, ok in checks:
        print(('PASS  ' if ok else 'FAIL  ') + name)
    shutil.rmtree(box, ignore_errors=True)
    if not all(ok for _, ok in checks):
        sys.exit('smoke test failed')
    print(f'smoke test: {len(checks)}/{len(checks)} passed')


if __name__ == '__main__':
    if '--smoke-only' not in sys.argv:
        package()
    smoke_test()
