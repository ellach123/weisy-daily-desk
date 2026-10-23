"""Weisy · local server

Runs only on this computer (127.0.0.1): serves the page and keeps all data in weisy.json.
The data lives outside the program folder, so an update is: delete the old program folder, unzip the new one,
start it and pick the same data folder again. Where the data goes:
    1. .weisy/location.txt next to server.py: one line with the folder the user chose in the first-run dialog
       (start.bat offers that). If that folder cannot be found the server refuses to start instead of
       quietly creating an empty set of data.
    2. otherwise the default: the Weisy-Data folder inside %APPDATA% (Windows) or ~/.weisy-data/ (macOS / Linux).
       It is only created when the user keeps the default - nothing is left there otherwise.
(A data/ folder next to server.py that already holds a weisy.json is still used first.)
Weisy's own small notes (location.txt, the shortcut answer) live in .weisy/ inside the program folder, so
deleting the program folder leaves nothing behind but the data.
Before the first change of each day it copies the data file to backups/ (the last 30 days are kept).
On the very first run the data file is created from starter.json (three task types and a few examples),
or from starter.en.json when the system language is not Chinese (WEISY_LANG=zh / en decides instead).

The server stops by itself shortly after the last Weisy window is closed (the page tells it).
Run it with --keep-alive to keep it running regardless.

Usage: double-click start.bat (Windows) or start.command (macOS), or run
    python server.py [--port 8780] [--data DATA_FOLDER] [--keep-alive] [--check]
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

if getattr(sys, 'frozen', False):
    # the packaged Windows version (Weisy-daily-desk.exe, see tools/package.py): the program folder is where the .exe is,
    # the page and the starter files travel inside the package
    ROOT = Path(sys.executable).resolve().parent
    BUNDLE = Path(getattr(sys, '_MEIPASS', ROOT))
else:
    ROOT = BUNDLE = Path(__file__).resolve().parent
APP = BUNDLE / 'app'
STARTER = {'zh': BUNDLE / 'starter.json', 'en': BUNDLE / 'starter.en.json'}
DEFAULT_PORT = 8780
NAME_RE = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')                  # collection names
ID_RE = re.compile(r'^(?!\.\.?$)[A-Za-z0-9_\-.~:@+]{1,200}$')    # same rule as the page
MAX_BODY = 5 * 1024 * 1024
KEEP_BACKUPS = 30
IDLE_TIMEOUT = 180   # seconds: a window that sends no sign of life for this long is treated as gone (crash, kill)
BYE_GRACE = 10       # seconds the server waits after the last window said goodbye (a reload says hello again at once)
START_GRACE = 180    # seconds the server waits for the first window after it was started


class DataLocationError(Exception):
    pass


def system_lang(env=os.environ):
    """'zh' when the system speaks Chinese, else 'en'; only used to pick the examples of a first run.
    WEISY_LANG=zh / en overrides it (the tests use that)."""
    forced = env.get('WEISY_LANG', '').strip().lower()
    if forced in STARTER:
        return forced
    code = ''
    if sys.platform == 'win32':
        try:
            import ctypes
            # Windows display language: primary language id 0x04 is Chinese
            return 'zh' if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x04 else 'en'
        except (AttributeError, OSError):
            pass
    for name in ('LC_ALL', 'LC_MESSAGES', 'LANG'):
        if env.get(name):
            code = env[name]
            break
    if not code:
        import locale
        code = locale.getlocale()[0] or ''
    return 'zh' if code.lower().startswith(('zh', 'chinese')) else 'en'


def standard_data_dir(env=os.environ, home=None):
    """The default data folder (used when the user did not choose another one)."""
    if os.name == 'nt' and env.get('APPDATA'):
        return Path(env['APPDATA']) / 'Weisy-Data'
    return (home or Path.home()) / '.weisy-data'


def default_data_dir(root=ROOT, env=os.environ, home=None):
    """Where the data lives when --data is not given (see the module docstring)."""
    local = root / 'data'
    if (local / 'weisy.json').exists():
        return local
    base = standard_data_dir(env, home)
    pointer = root / '.weisy' / 'location.txt'
    if pointer.is_file():
        text = pointer.read_text(encoding='utf-8-sig').strip()
        if text:
            target = Path(text)
            if not target.is_dir():
                raise DataLocationError('\n'.join([
                    'Weisy cannot find its data folder:',
                    f'    {target}',
                    f'It was chosen when Weisy was first started (written in {pointer}).',
                    'If the folder is on a drive or network location that is not connected, connect it and start Weisy again.',
                    f'If you moved or deleted it, put it back, or delete {pointer.name} to start fresh in the default folder ({base}).']))
            return target
    return base


class Presence:
    """Knows which Weisy windows are open, so the server can stop itself when the last one is closed.
    A window says hello every ~20 s and bye when it closes. No window left after BYE_GRACE -> stop.
    A window that goes silent for IDLE_TIMEOUT counts as gone. Minimised or sleeping windows only
    pause their hellos, so the timeout is generous; closing is detected by the bye, not by the timeout."""

    def __init__(self, timeout=IDLE_TIMEOUT, bye_grace=BYE_GRACE, start_grace=START_GRACE, clock=time.monotonic):
        self.timeout, self.bye_grace, self.clock = timeout, bye_grace, clock
        self.windows = {}                      # window id -> time of its last hello
        self.deadline = clock() + start_grace  # stop at this time unless a window shows up
        self.lock = threading.Lock()

    def hello(self, wid):
        with self.lock:
            self.windows[wid] = self.clock()
            self.deadline = None

    def bye(self, wid):
        with self.lock:
            self.windows.pop(wid, None)
            if not self.windows:
                self.deadline = self.clock() + self.bye_grace

    def resume(self):
        """The computer was asleep: nobody could say hello meanwhile, so everybody gets a fresh start."""
        with self.lock:
            now = self.clock()
            for wid in self.windows:
                self.windows[wid] = now
            if self.deadline is not None:
                self.deadline = max(self.deadline, now + self.bye_grace)

    def expired(self):
        with self.lock:
            now = self.clock()
            stale = [w for w, seen in self.windows.items() if now - seen > self.timeout]
            for w in stale:
                del self.windows[w]
            if stale and not self.windows:
                self.deadline = now
            return self.deadline is not None and now >= self.deadline


def watch(server, presence):
    """Background thread: stop the server once Presence says nobody is left."""
    last = time.monotonic()
    while True:
        time.sleep(1)
        now = time.monotonic()
        if now - last > 5:  # this thread was frozen: the computer slept
            presence.resume()
        last = now
        if presence.expired():
            server.shutdown()
            return


class Store:
    """All collections in one JSON file: {"format": 1, "savedAt": ..., "collections": {col: {id: doc}}}."""

    def __init__(self, data_dir: Path):
        self.lock = threading.RLock()  # requests run in parallel threads: one at a time touches the data
        self.dir = data_dir
        self.file = data_dir / 'weisy.json'
        self.backups = data_dir / 'backups'
        self.dir.mkdir(parents=True, exist_ok=True)
        self.backups.mkdir(exist_ok=True)
        if self.file.exists():
            with open(self.file, encoding='utf-8') as f:
                self.collections = json.load(f).get('collections', {})
        else:
            self.collections = self._starter()
            self._write()

    @staticmethod
    def _starter():
        """starter.json: the three task types plus a few examples (titled 示例：…) to delete later;
        starter.en.json is the same in English (titled Example: …) and also sets the page to English.
        "__today__" becomes the date of this first run, so the example today-list shows up on 今日."""
        starter = STARTER[system_lang()]
        if not starter.exists():
            return {}
        today = datetime.date.today().isoformat()
        with open(starter, encoding='utf-8') as f:
            text = f.read().replace('__today__', today)
        cols = json.loads(text).get('collections', {})
        for docs in cols.values():
            for doc in docs.values():
                if doc.get('createdAt') == '':
                    doc['createdAt'] = today
        return cols

    def _backup_today(self):
        today = datetime.date.today().isoformat()
        target = self.backups / f'weisy-{today}.json'
        if self.file.exists() and not target.exists():
            shutil.copy2(self.file, target)
            old = sorted(self.backups.glob('weisy-*.json'))
            for f in old[:-KEEP_BACKUPS]:
                f.unlink()

    def _write(self):
        payload = {'format': 1, 'savedAt': datetime.datetime.now().isoformat(timespec='seconds'), 'collections': self.collections}
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix='.weisy-', suffix='.tmp')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.file)  # atomic: the file is never half-written

    def snapshot(self):
        with self.lock:
            return json.dumps({'collections': self.collections}, ensure_ascii=False)

    def change(self, method, col, doc_id, body):
        with self.lock:
            self._backup_today()
            docs = self.collections.setdefault(col, {})
            if method == 'PUT':
                docs[doc_id] = body
            elif method == 'PATCH':
                if doc_id not in docs:
                    raise KeyError(doc_id)
                merge(docs[doc_id], body)
            elif method == 'DELETE':
                docs.pop(doc_id, None)
            self._write()


def merge(target, patch):
    """Same rule as the page's store: nested objects merge, everything else (arrays included) replaces."""
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            merge(target[k], v)
        else:
            target[k] = v


class Handler(BaseHTTPRequestHandler):
    store: Store = None
    port = DEFAULT_PORT
    presence: Presence = None  # None with --keep-alive
    timeout = 30  # an idle connection (browsers open spare ones) is dropped after this many seconds
    test_mode = False  # --test: the browser test posts its PASS/FAIL report to /api/test-result

    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, code, body=b'', ctype='application/json; charset=utf-8'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _same_origin(self):
        """Reads and writes are only accepted from the page itself, never from other websites."""
        origin = self.headers.get('Origin')
        allowed = {f'http://127.0.0.1:{self.port}', f'http://localhost:{self.port}'}
        if origin is not None and origin not in allowed:
            return False
        host = (self.headers.get('Host') or '').split(':')[0]
        return host in ('127.0.0.1', 'localhost')

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/ping':
            return self._send(200, {'ok': True, 'app': 'weisy'})
        if path == '/api/data':
            if not self._same_origin():
                return self._send(403, {'error': 'forbidden'})
            return self._send(200, self.store.snapshot())
        name = 'index.html' if path in ('/', '/index.html') else path.lstrip('/')
        types = {'html': 'text/html; charset=utf-8', 'png': 'image/png', 'ico': 'image/x-icon',
                 'webmanifest': 'application/manifest+json; charset=utf-8'}
        m = re.fullmatch(r'[A-Za-z0-9_\-]+\.(html|png|ico|webmanifest)', name)
        f = APP / name
        if not m or not f.is_file():
            return self._send(404, {'error': 'not found'})
        return self._send(200, f.read_bytes(), types[m.group(1)])

    def _doc_request(self, method):
        if not self._same_origin():
            return self._send(403, {'error': 'forbidden'})
        m = re.fullmatch(r'/api/doc/([^/]+)/([^/]+)', urlparse(self.path).path)
        if not m:
            return self._send(404, {'error': 'not found'})
        col, doc_id = unquote(m.group(1)), unquote(m.group(2))
        if not NAME_RE.match(col) or not ID_RE.match(doc_id):
            return self._send(400, {'error': 'bad collection or id'})
        body = None
        if method in ('PUT', 'PATCH'):
            n = int(self.headers.get('Content-Length') or 0)
            if n <= 0 or n > MAX_BODY:
                return self._send(400, {'error': 'bad body size'})
            try:
                body = json.loads(self.rfile.read(n).decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                return self._send(400, {'error': 'body is not JSON'})
            if not isinstance(body, dict):
                return self._send(400, {'error': 'body must be an object'})
        try:
            self.store.change(method, col, doc_id, body)
        except KeyError:
            return self._send(404, {'error': 'document does not exist'})
        except OSError as e:
            return self._send(500, {'error': f'could not save: {e}'})
        return self._send(200, {'ok': True})

    def do_POST(self):
        path = urlparse(self.path)
        if path.path in ('/api/hello', '/api/bye'):
            if not self._same_origin():
                return self._send(403, {'error': 'forbidden'})
            wid = (parse_qs(path.query).get('id') or [''])[0]
            if not NAME_RE.match(wid):
                return self._send(400, {'error': 'bad window id'})
            if self.presence:
                (self.presence.hello if path.path == '/api/hello' else self.presence.bye)(wid)
            return self._send(200, {'ok': True})
        if self.test_mode and urlparse(self.path).path == '/api/test-result' and self._same_origin():
            n = int(self.headers.get('Content-Length') or 0)
            (self.store.dir / 'test-result.txt').write_bytes(self.rfile.read(min(n, MAX_BODY)))
            return self._send(200, {'ok': True})
        return self._send(404, {'error': 'not found'})

    def do_PUT(self):
        self._doc_request('PUT')

    def do_PATCH(self):
        self._doc_request('PATCH')

    def do_DELETE(self):
        self._doc_request('DELETE')


class PortInUse(Exception):
    pass


def say(*args, **kwargs):
    """print(), but a missing or closed console (windowless start, packaged version) must never stop the server."""
    try:
        print(*args, **kwargs)
    except (OSError, ValueError, AttributeError):
        pass


def resolve_data_dir(data=None):
    """The data folder from --data or the default rules; DataLocationError if it cannot be used."""
    data_dir = Path(data) if data else default_data_dir()
    if data_dir.exists() and not os.access(data_dir, os.W_OK):
        raise DataLocationError(f'Weisy cannot write to its data folder:\n    {data_dir}')
    return data_dir


def serve(port, store, keep_alive=False, idle_timeout=IDLE_TIMEOUT, bye_grace=BYE_GRACE, start_grace=START_GRACE, on_ready=None):
    """Serve until the last window is gone (forever with keep_alive). on_ready() runs once the port is open."""
    Handler.store = store
    Handler.presence = None if keep_alive else Presence(idle_timeout, bye_grace, start_grace)
    Handler.port = port
    try:
        server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    except OSError as e:
        raise PortInUse(port) from e
    say(f'Weisy is running: http://127.0.0.1:{port}/   data: {store.file}')
    if Handler.presence:
        say('It stops by itself a few seconds after the last Weisy window is closed (--keep-alive to prevent that).')
        threading.Thread(target=watch, args=(server, Handler.presence), daemon=True).start()
    if on_ready:
        on_ready()
    server.serve_forever()
    server.server_close()


def main():
    ap = argparse.ArgumentParser(description='Weisy local server')
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--data', default=None, help='data folder (default: see above)')
    ap.add_argument('--keep-alive', action='store_true', help='do not stop when the last window is closed')
    ap.add_argument('--check', action='store_true', help='only check where the data is and whether it can be used')
    ap.add_argument('--test', action='store_true', help=argparse.SUPPRESS)
    for name, default in (('idle-timeout', IDLE_TIMEOUT), ('bye-grace', BYE_GRACE), ('start-grace', START_GRACE)):
        ap.add_argument(f'--{name}', type=float, default=default, help=argparse.SUPPRESS)  # shortened by the tests
    args = ap.parse_args()
    Handler.test_mode = args.test
    data_dir = args.data
    try:
        data_dir = resolve_data_dir(args.data)
        if args.check:
            say(f'Data folder: {data_dir}')
            return
        store = Store(data_dir)
    except DataLocationError as e:
        say(e, file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        say(f'Weisy cannot use its data folder {data_dir}:\n    {e}', file=sys.stderr)
        sys.exit(2)
    try:
        serve(args.port, store, args.keep_alive, args.idle_timeout, args.bye_grace, args.start_grace)
    except PortInUse:
        say(f'Port {args.port} is in use: Weisy may already be running.', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
