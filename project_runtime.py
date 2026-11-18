"""Start known local web applications and wait until their HTTP endpoint is ready."""
import hashlib
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = Path(__file__).resolve().parent
RUNNING = {}


def setting(name):
    if os.environ.get(name):
        return os.environ[name]
    try:
        values = json.loads((BASE / '.state/runtime-settings.json').read_text())
        return values.get(name)
    except (OSError, ValueError):
        return None


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def recipe(root, page):
    relative = page.relative_to(root).as_posix()
    for parent in page.parents:
        if root != parent and root not in parent.parents:
            break
        if (parent / 'server.py').is_file() and (parent / 'web/index.html').is_file():
            return dict(kind='script', entry=parent / 'server.py', args=['--host', '127.0.0.1'], cwd=parent)
        if (parent / 'web_app.py').is_file() and (parent / 'generate_outdoor_hike_gpx.py').is_file():
            return dict(kind='record', entry=parent / 'web_app.py', cwd=parent)
    if (root / 'web_release_server.py').is_file():
        return dict(kind='script', entry=root / 'web_release_server.py', args=['--host', '127.0.0.1', '--no-feishu-ws'], cwd=root, requirements=root / 'requirements_web.txt')
    if (root / 'web/app.py').is_file():
        return dict(kind='flask', entry=root / 'web/app.py', cwd=root / 'web', requirements=root / 'requirements.txt')
    if (root / 'app.py').is_file() and (root / 'requirements.txt').is_file():
        return dict(kind='script', entry=root / 'app.py', args=['--host', '127.0.0.1'], cwd=root, requirements=root / 'requirements.txt')
    if relative.startswith('cli/src/sport_config/templates/'):
        return dict(kind='module', entry='sport_config.web_app', cwd=root, source=root / 'cli/src', package=root / 'cli')
    if (root / 'jira_service/app.py').is_file():
        return dict(kind='jira', entry='jira_service.app', cwd=root, package=root)
    if (root / 'bin/active-agent.mjs').is_file():
        return dict(kind='node', entry=root / 'bin/active-agent.mjs', cwd=root)
    # LTHR's static front end connects to its separately configured API on 8080.
    if (root / 'lthr-jira-analyzer/server/app.py').is_file():
        return dict(kind='lthr', entry=root / 'lthr-jira-analyzer/server/app.py', cwd=root, port=8080)
    return None


def ensure_uv(log):
    installed = shutil.which('uv')
    if installed:
        return installed
    bootstrap = BASE / '.state/bootstrap'
    uv = bootstrap / 'bin/uv'
    if not uv.exists():
        command = [sys.executable, '-m', 'pip', 'install', '--timeout', '20', '--retries', '1', '--target', str(bootstrap), 'uv']
        if setting('SKILLS_HUB_PYPI_INDEX'):
            command += ['--index-url', setting('SKILLS_HUB_PYPI_INDEX')]
        subprocess.run(command, check=True, stdout=log, stderr=log, timeout=180)
    return str(uv)


def python_for(root, plan, log):
    if not plan.get('requirements') and not plan.get('package'):
        return sys.executable
    # Environments belong to this project path and dependency declaration. Never
    # import packages from another scanned project or the user's global Python.
    version = plan.get('python_version', '3.12' if plan['kind'] == 'jira' else sys.executable)
    declaration = dict(root=str(root.resolve()), python=version, schema=2)
    for field in ('requirements', 'package'):
        if plan.get(field):
            path = Path(plan[field])
            source = path / 'pyproject.toml' if field == 'package' else path
            declaration[field] = str(path.resolve())
            declaration[field + '_contents'] = source.read_text(encoding='utf-8')
    signature = hashlib.sha256(json.dumps(declaration, sort_keys=True).encode()).hexdigest()
    identity = root.name + '-' + hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12]
    environment = BASE / '.venvs' / identity
    python = environment / 'bin/python'
    marker = environment / '.skills-hub-ready'
    if python.exists() and marker.exists() and marker.read_text() == signature:
        return str(python)
    uv = ensure_uv(log)
    env = os.environ.copy()
    if setting('SKILLS_HUB_PYPI_INDEX'):
        env['UV_DEFAULT_INDEX'] = setting('SKILLS_HUB_PYPI_INDEX')
    subprocess.run([uv, 'venv', '--allow-existing', '--python', version, str(environment)], check=True, stdout=log, stderr=log, env=env, timeout=240)
    install = [uv, 'pip', 'install', '--python', str(python)]
    if plan.get('package'):
        install += ['-e', str(plan['package'])]
    else:
        install += ['-r', str(plan['requirements'])]
    subprocess.run(install, check=True, stdout=log, stderr=log, env=env, timeout=240)
    marker.write_text(signature)
    return str(python)


def ready(url):
    try:
        with urllib.request.urlopen(url, timeout=1):
            return True
    except urllib.error.HTTPError as error:
        return error.code in {401, 403}
    except OSError:
        return False


def start(root, page):
    plan = recipe(root, page)
    if not plan:
        return None
    key = str(plan['entry'])
    existing = RUNNING.get(key)
    if existing and existing['process'].poll() is None and ready(existing['url']):
        return existing['url']
    folder = BASE / '.state/runtime'
    folder.mkdir(parents=True, exist_ok=True)
    identity = root.name + '-' + hashlib.sha256(key.encode()).hexdigest()[:8]
    logfile = folder / (identity + '.log')
    record = folder / (identity + '.json')
    try:
        previous = json.loads(record.read_text())
        ticks = Path('/proc/' + str(previous['pid']) + '/stat').read_text().split()[21]
        if ticks == previous['ticks'] and previous['url'].startswith('http://127.0.0.1:') and ready(previous['url'] + ('health' if plan['kind'] == 'lthr' else '')):
            return '' if plan['kind'] == 'lthr' else previous['url']
    except (OSError, ValueError, KeyError, IndexError):
        pass
    port = plan.get('port') or free_port()
    url = 'http://127.0.0.1:' + str(port) + '/'
    if plan['kind'] == 'lthr' and ready(url + 'health'):
        return ''
    env = os.environ.copy()
    env.update(PORT=str(port), HOST='127.0.0.1', JA_PORT=str(port), JA_HOST='127.0.0.1', FLASK_DEBUG='0', PYTHONUNBUFFERED='1')
    if plan.get('source'):
        env['PYTHONPATH'] = str(plan['source'])
    try:
        with logfile.open('a') as log:
            if plan['kind'] == 'node':
                if not (root / 'node_modules').is_dir():
                    command = ['npm', 'ci']
                    if setting('SKILLS_HUB_NPM_REGISTRY'):
                        command += ['--registry', setting('SKILLS_HUB_NPM_REGISTRY')]
                    subprocess.run(command, cwd=str(root), check=True, stdout=log, stderr=log, timeout=240)
                state = folder / (identity + '-state')
                subprocess.run(['node', str(plan['entry']), '--state', str(state), 'setup', '--workspace', str(root), '--port', str(port)], cwd=str(root), check=True, stdout=log, stderr=log, timeout=60)
                command = ['node', str(plan['entry']), '--state', str(state), 'serve']
            else:
                python = python_for(root, plan, log)
                if plan['kind'] == 'flask':
                    command = [python, '-m', 'flask', '--app', str(plan['entry']), 'run', '--host', '127.0.0.1', '--port', str(port), '--no-reload']
                elif plan['kind'] == 'record':
                    command = [python, '-c', "import runpy; m=runpy.run_path('web_app.py'); m['HTTPServer'](('127.0.0.1', " + str(port) + "), m['Handler']).serve_forever()"]
                elif plan['kind'] == 'module':
                    command = [python, '-m', plan['entry'], '--host', '127.0.0.1', '--port', str(port)]
                elif plan['kind'] == 'jira':
                    # Use the service's existing configuration and installed CLI.
                    command = [python, '-c', 'from jira_service.app import main; main()']
                else:
                    command = [python, str(plan['entry'])] + plan.get('args', [])
                    if plan['kind'] != 'lthr':
                        command += ['--port', str(port)]
                env['PATH'] = str(Path(python).parent) + os.pathsep + env.get('PATH', '')
            process = subprocess.Popen(command, cwd=str(plan['cwd']), env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        for _ in range(150):
            if process.poll() is not None:
                break
            if ready(url + ('health' if plan['kind'] == 'lthr' else '')):
                RUNNING[key] = dict(process=process, url=url)
                ticks = Path('/proc/' + str(process.pid) + '/stat').read_text().split()[21]
                record.write_text(json.dumps(dict(pid=process.pid, ticks=ticks, url=url)))
                return '' if plan['kind'] == 'lthr' else url
            time.sleep(.2)
        if process.poll() is None:
            process.terminate()
        raise RuntimeError('服务未就绪')
    except Exception as error:
        raise ValueError('项目启动失败：' + root.name + '；' + str(error) + '。日志：' + str(logfile)) from error
