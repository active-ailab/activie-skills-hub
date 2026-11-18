#!/usr/bin/env python3
"""On-demand local service, invoked by the skills-hub://open browser protocol."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

BASE = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8765'


def healthy():
    try:
        with urllib.request.urlopen(URL + '/api/session', timeout=1) as response:
            return bool(json.load(response).get('token'))
    except (OSError, ValueError):
        return False


def open_browser():
    # Wait for Windows to accept the URL before the short-lived WSL launcher
    # exits. Explorer's detached hand-off can be lost on subsequent launches.
    subprocess.run([
        'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        "Start-Process '" + URL + "' -ErrorAction Stop",
    ], check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE, timeout=30)


def install():
    distro = os.environ.get('WSL_DISTRO_NAME')
    if not distro:
        raise SystemExit('请在 WSL 内安装此本机网页入口。')
    local = subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', '[Environment]::GetFolderPath("LocalApplicationData")'], text=True).strip()
    folder = Path(subprocess.check_output(['wslpath', '-u', local], text=True).strip()) / 'SkillsHub'
    folder.mkdir(exist_ok=True)
    script = folder / 'open.vbs'
    command = subprocess.list2cmdline(['wsl.exe', '--distribution', distro, '--exec', sys.executable, str(BASE / 'launch.py'), 'open'])
    script.write_text('Set shell = CreateObject("WScript.Shell")\r\nshell.Run "' + command.replace('"', '""') + '", 0, False\r\n', encoding='utf-16')
    windows_script = subprocess.check_output(['wslpath', '-w', str(script)], text=True).strip()
    key = 'HKCU\\Software\\Classes\\skills-hub'
    for suffix, name, value in [('', None, 'URL:Skills Hub local reader'), ('', 'URL Protocol', ''), ('\\shell\\open\\command', None, 'wscript.exe "' + windows_script + '"')]:
        args = ['reg.exe', 'add', key + suffix, '/f', '/d', value]
        args.extend(['/v', name] if name else ['/ve'])
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
    print('已注册网页唤起入口：skills-hub://open（不设置开机启动）')
    return windows_script


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'install':
        install()
        return
    (BASE / '.state').mkdir(exist_ok=True)
    with (BASE / '.state/local-launch.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            for _ in range(100):
                if healthy():
                    open_browser()
                    return
                time.sleep(.1)
            raise SystemExit('本机服务启动超时')
        if healthy():
            open_browser()
            return
        with (BASE / '.state/local-service.log').open('a') as output:
            process = subprocess.Popen([sys.executable, '-u', str(BASE / 'local_server.py')], cwd=str(BASE), stdin=subprocess.DEVNULL, stdout=output, stderr=output)
        for _ in range(100):
            if healthy():
                open_browser()
                process.wait()
                return
            if process.poll() is not None:
                break
            time.sleep(.1)
        if process.poll() is None:
            process.terminate()
            process.wait()
        raise SystemExit('启动失败，请查看 .state/local-service.log')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        (BASE / '.state').mkdir(exist_ok=True)
        with (BASE / '.state/local-launch.log').open('a') as output:
            traceback.print_exc(file=output)
        raise
