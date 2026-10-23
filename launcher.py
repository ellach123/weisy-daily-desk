"""Weisy launcher for the packaged Windows version (Weisy-daily-desk.exe, built by tools/package.py).

It does what start.bat does, without needing Python on the user's computer:
    1. Weisy already running -> just open its window.
    2. First start in this program folder -> the one-time dialog (tools/setup.ps1: data folder + desktop
       shortcut). Closing the dialog without a choice quits and creates nothing.
    3. Check the data folder; a problem is shown in a message box (there is no console window).
    4. Start the server in this process and open the window. The process ends by itself a few seconds
       after the last Weisy window is closed.
Like start.bat it writes only to the program folder (.weisy) and the chosen data folder.

From source (for testing): python launcher.py   (WEISY_NO_WINDOW=1 skips the dialog and the window)
"""
import ctypes
import os
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path

import server

PORT = server.DEFAULT_PORT
URL = f'http://127.0.0.1:{PORT}/'
NO_WINDOW = os.environ.get('WEISY_NO_WINDOW') == '1'
# message boxes speak the Windows display language, like the first-run dialog
TEXT = {
    'zh': {'title': '潦草鼠鼠之家', 'cannot_start': '潦草鼠鼠之家无法启动。', 'cannot_use': '潦草鼠鼠之家无法使用数据文件夹。',
           'port': f'端口 {PORT} 正被其他程序占用，潦草鼠鼠之家无法启动。'},
    'en': {'title': 'Weisy Daily Desk', 'cannot_start': 'Weisy Daily Desk cannot start.', 'cannot_use': 'Weisy Daily Desk cannot use its data folder.',
           'port': f'Port {PORT} is used by another program, so Weisy Daily Desk cannot start.'},
}[server.system_lang()]
TITLE = TEXT['title']


def message(text):
    if NO_WINDOW:
        server.say(text, file=sys.stderr)
    else:
        ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x10)  # MB_ICONERROR


def running():
    try:
        with urllib.request.urlopen(URL + 'api/ping', timeout=1) as r:
            return b'weisy' in r.read()
    except OSError:
        return False


def open_window():
    """Edge in app mode (a window of its own, like start.bat), otherwise the default browser."""
    if NO_WINDOW:
        return
    import winreg
    edge = None
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe') as key:
                edge = winreg.QueryValue(key, None)
                break
        except OSError:
            pass
    if edge and Path(edge).exists():
        subprocess.Popen([edge, f'--app={URL}'], close_fds=True)
    else:
        webbrowser.open(URL)


def first_run_setup():
    """The one-time dialog. False when it was closed without a choice (then nothing may be started or created)."""
    if NO_WINDOW or (server.ROOT / '.weisy' / 'desktop-shortcut.txt').exists():
        return True
    powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
    env = {**os.environ, 'WEISY_DIR': str(server.ROOT) + os.sep}
    if getattr(sys, 'frozen', False):
        env['WEISY_TARGET'] = sys.executable  # the desktop shortcut opens Weisy-daily-desk.exe (not start.bat)
    result = subprocess.run([str(powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(server.BUNDLE / 'tools' / 'setup.ps1')],
                            env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    return result.returncode != 3


def main():
    if running():
        open_window()
        return
    if not first_run_setup():
        return
    try:
        store = server.Store(server.resolve_data_dir())
    except server.DataLocationError as e:
        message(f"{TEXT['cannot_start']}\n\n{e}")
        return
    except OSError as e:
        message(f"{TEXT['cannot_use']}\n\n{e}")
        return
    try:
        server.serve(PORT, store, on_ready=open_window)
    except server.PortInUse:
        message(TEXT['port'])


if __name__ == '__main__':
    main()
