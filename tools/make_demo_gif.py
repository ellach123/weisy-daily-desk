"""Record docs/demo-zh.gif and docs/demo-en.gif: the 今日 / Today page, two items ticked off, the mouse cheering each time.

    python tools/make_demo_gif.py            (both languages)
    python tools/make_demo_gif.py en         (one language)

Needs Windows + Microsoft Edge and Pillow (pip install pillow). It starts server.py on a test port with
throw-away starter data in that language, drives a headless Edge through the DevTools protocol (a tiny WebSocket client
below, standard library only), takes screenshots while the cheer animation runs and joins them into a GIF.
Everything temporary lives in build/demo-tmp inside the repository and is removed afterwards.
"""
import base64
import io
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / 'build' / 'demo-tmp'
DOCS = ROOT / 'docs'
BROWSER_LANG = {'zh': 'zh-CN', 'en': 'en-GB'}
PORT = 8797
EDGE = os.environ.get('EDGE_PATH') or next((p for p in (r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                                                          r'C:/Program Files/Microsoft/Edge/Application/msedge.exe') if Path(p).exists()), 'msedge')
VIEW_W, VIEW_H = 1000, 760   # browser window; the GIF is this wide, no scaling, so text stays sharp


class DevTools:
    """Just enough of a WebSocket client to send DevTools commands and read their answers."""

    def __init__(self, ws_url):
        host_port, path = ws_url[len('ws://'):].split('/', 1)
        host, port = host_port.split(':')
        self.sock = socket.create_connection((host, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET /{path} HTTP/1.1\r\nHost: {host_port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                           f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        head = b''
        while b'\r\n\r\n' not in head:
            head += self.sock.recv(1)
        if b' 101 ' not in head.split(b'\r\n')[0]:
            raise RuntimeError('DevTools refused the connection')
        self.next_id = 0

    def _send(self, text):
        data = text.encode()
        mask = os.urandom(4)
        n = len(data)
        head = b'\x81' + (bytes([0x80 | n]) if n < 126 else b'\xfe' + struct.pack('>H', n) if n < 65536 else b'\xff' + struct.pack('>Q', n))
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _exact(self, n):
        buf = b''
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RuntimeError('DevTools connection closed')
            buf += chunk
        return buf

    def _recv(self):
        parts = []
        while True:
            b0, b1 = self._exact(2)
            n = b1 & 0x7f
            if n == 126:
                n = struct.unpack('>H', self._exact(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._exact(8))[0]
            parts.append(self._exact(n))
            if b0 & 0x80:  # final fragment
                return b''.join(parts).decode()

    def call(self, method, **params):
        self.next_id += 1
        self._send(json.dumps({'id': self.next_id, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self._recv())
            if msg.get('id') == self.next_id:
                if 'error' in msg:
                    raise RuntimeError(f'{method}: {msg["error"]}')
                return msg.get('result', {})

    def js(self, expression):
        r = self.call('Runtime.evaluate', expression=expression, returnByValue=True, awaitPromise=True)
        return r.get('result', {}).get('value')


def wait_until(check, seconds=20):
    end = time.time() + seconds
    while time.time() < end:
        if check():
            return True
        time.sleep(0.1)
    raise RuntimeError('timed out')


def record(lang):
    out = DOCS / f'demo-{lang}.gif'
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True)
    server = subprocess.Popen([sys.executable, str(ROOT / 'server.py'), '--port', str(PORT), '--data', str(TMP / 'data'), '--keep-alive'],
                              env={**os.environ, 'WEISY_LANG': lang}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    profile = TMP / 'edge-profile'
    edge = None
    try:
        subprocess.run([sys.executable, str(ROOT / 'tools' / 'build.py')], check=True, stdout=subprocess.DEVNULL)
        wait_until(lambda: _ping())
        edge = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--hide-scrollbars', f'--lang={BROWSER_LANG[lang]}', f'--user-data-dir={profile}',
                                 '--remote-debugging-port=0', f'--window-size={VIEW_W},{VIEW_H}', 'about:blank'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = profile / 'DevToolsActivePort'
        wait_until(port_file.exists)
        port = int(port_file.read_text().splitlines()[0])
        pages = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list'))
        dt = DevTools(next(p for p in pages if p['type'] == 'page')['webSocketDebuggerUrl'])
        dt.call('Emulation.setDeviceMetricsOverride', width=VIEW_W, height=VIEW_H, deviceScaleFactor=1, mobile=False)
        dt.call('Page.navigate', url=f'http://127.0.0.1:{PORT}/#today')
        wait_until(lambda: dt.js('document.querySelectorAll(\'[data-act="dv-toggle"]\').length') == 4)
        time.sleep(1.0)  # fonts and the mascot settle
        # the area to record: from the top of the page down to the end of the today list
        # down to the third item of the list, so both ticked items and a bit of context are in the picture
        bottom = dt.js('Math.ceil(document.querySelectorAll(".dv-row")[2].getBoundingClientRect().bottom)') or VIEW_H
        clip = {'x': 0, 'y': 0, 'width': VIEW_W, 'height': min(VIEW_H, int(bottom) + 12), 'scale': 1}

        frames = []  # (image, seconds shown)

        def shoot(seconds):
            end = time.time() + seconds
            while time.time() < end:
                t0 = time.time()
                png = base64.b64decode(dt.call('Page.captureScreenshot', format='png', clip=clip)['data'])
                frames.append([Image.open(io.BytesIO(png)).convert('RGB'), 0])
                if len(frames) > 1:
                    frames[-2][1] = t0 - frames[-2][2]
                frames[-1].append(t0)

        def tick(n):
            # a soft ring where the "click" happens (only in this recording), then the real click
            dt.js(f'''(() => {{ const b = document.querySelectorAll('[data-act="dv-toggle"]')[{n}]; const r = b.getBoundingClientRect();
                const d = document.createElement('div'); d.id = 'demo-tap';
                d.style.cssText = `position:fixed;left:${{r.left + r.width / 2 - 14}}px;top:${{r.top + r.height / 2 - 14}}px;width:28px;height:28px;`
                  + 'border-radius:50%;background:rgba(42,67,192,.25);border:2px solid rgba(42,67,192,.6);pointer-events:none;z-index:99';
                document.body.appendChild(d); setTimeout(() => d.remove(), 450); b.click(); }})()''')

        shoot(1.2)
        tick(0)
        shoot(2.6)
        shoot(0.6)
        tick(1)
        shoot(2.6)
        shoot(1.0)
        # last frame: give it the same length as the one before
        frames[-1][1] = frames[-2][1] if len(frames) > 1 else 0.1
        durations = [max(40, int(round(f[1] * 1000 / 10)) * 10) for f in frames]  # GIF timing is in 10 ms steps
        # one palette for all frames (taken from a still and a cheering frame), so colours never jump between frames
        sample = Image.new('RGB', (frames[0][0].width, frames[0][0].height * 2))
        sample.paste(frames[0][0], (0, 0)); sample.paste(frames[len(frames) // 4][0], (0, frames[0][0].height))
        palette = sample.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        images = [f[0].quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
        out.parent.mkdir(exist_ok=True)
        images[0].save(out, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True, disposal=1)
        print(f'{out.relative_to(ROOT)}: {len(images)} frames, {sum(durations) / 1000:.1f} s, '
              f'{images[0].width}x{images[0].height}, {out.stat().st_size / 1024:.0f} KB')
    finally:
        if edge:
            edge.kill()
            edge.wait()
            subprocess.run(['powershell', '-NoProfile', '-Command',
                            "Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*' + $env:P + '*' }"
                            " | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                           env={**os.environ, 'P': str(profile)}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        server.terminate()
        server.wait()
        for _ in range(40):  # Edge can hold its profile folder for a moment
            shutil.rmtree(TMP, ignore_errors=True)
            if not TMP.exists():
                break
            time.sleep(0.25)


def _ping():
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/ping', timeout=1)
        return True
    except OSError:
        return False


if __name__ == '__main__':
    for lang in [a for a in sys.argv[1:] if a in BROWSER_LANG] or list(BROWSER_LANG):
        record(lang)
