"""Loopback-only Skills reader. No file copies or external dependencies."""
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import project_runtime
import usage_guides
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, quote, unquote

BASE = Path(__file__).resolve().parent
STATE = BASE / '.state'
CONFIG = STATE / 'local-workspace.json'
TOKEN = secrets.token_urlsafe(32)
IGNORED = {'.git', '.repo', 'node_modules', '__pycache__', '.venv', '.venvs', '.state', 'vendor', 'dist', 'build'}
FILES = {}
CACHE = {}
LOCK = threading.Lock()
PREVIEWS = {}


class PreviewHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        relative = unquote(urlsplit(path).path).lstrip('/')
        target = (self.server.project_root / relative).resolve()
        if target != self.server.project_root and self.server.project_root not in target.parents:
            return str(self.server.project_root / '.preview-forbidden')
        return str(target)

    def do_GET(self):
        return self.serve_preview()

    def do_HEAD(self):
        return self.serve_preview(head=True)

    def serve_preview(self, head=False):
        if self.headers.get('Host') != '127.0.0.1:' + str(self.server.server_port):
            self.send_error(403)
            return
        target = Path(self.translate_path(self.path))
        if (target != self.server.project_root and self.server.project_root not in target.parents) or any(part in IGNORED or part.startswith('.') for part in target.relative_to(self.server.project_root).parts):
            self.send_error(403)
            return
        if target.is_dir() and not (target / 'index.html').is_file():
            self.send_error(403, 'Directory listing disabled')
            return
        if head:
            super().do_HEAD()
        else:
            super().do_GET()


def open_preview(name):
    file = FILES.get(name)
    if not file or file.suffix.lower() not in {'.html', '.htm'} or file.resolve() != file:
        raise ValueError('请选择已读取的 HTML 网页')
    workspace = json.loads(CONFIG.read_text(encoding='utf-8'))
    roots = [Path(item['path']) for item in workspace['skills'] if name in item['files']]
    roots = [root for root in roots if root in file.parents]
    if not roots:
        raise ValueError('网页不在已读取的项目中')
    root = max(roots, key=lambda value: len(value.parts)).resolve()
    runtime_url = project_runtime.start(root, file)
    if runtime_url:
        if project_runtime.recipe(root, file)['kind'] == 'node' and file.name == 'serial.html':
            runtime_url += 'serial.html'
        return {'url': runtime_url}
    if root not in PREVIEWS:
        server = ThreadingHTTPServer(('127.0.0.1', 8000 if runtime_url == '' else 0), PreviewHandler)
        server.project_root = root
        threading.Thread(target=server.serve_forever, daemon=True).start()
        PREVIEWS[root] = server
    server = PREVIEWS[root]
    return {'url': 'http://127.0.0.1:' + str(server.server_port) + '/' + quote(file.relative_to(root).as_posix())}



def normalize(value):
    value = value.strip().strip('"')
    if re.match(r'^[A-Za-z]:[\\/]', value):
        value = subprocess.check_output(['wslpath', '-u', value], text=True).strip()
    return Path(os.path.expandvars(value)).expanduser().resolve()


def scan(paths, mode='projects'):
    started = time.monotonic()
    result, errors, mapping = [], [], {}
    labels = json.loads((BASE / 'static/chinese_names.json').read_text())
    seen = set()
    for value in paths:
        root = normalize(value)
        if not root.is_dir():
            errors.append('目录不存在：' + str(root))
            continue
        inventory = []
        def visit(folder):
            try:
                with os.scandir(str(folder)) as iterator:
                    for entry in iterator:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name not in IGNORED:
                                visit(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            inventory.append(Path(entry.path))
            except OSError as error:
                errors.append(str(error))
        visit(root)
        if mode == 'skills':
            groups = sorted({p.parent for p in inventory if p.name == 'SKILL.md'})
        elif (root / 'SKILL.md').exists() or (root / 'README.md').exists():
            groups = [root]
        else:
            groups = sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and p.name not in IGNORED and not p.name.startswith('.')) or [root]
        for group in groups:
            if str(group) in seen:
                continue
            seen.add(str(group))
            prefix = str(group) + os.sep
            entries = [p for p in inventory if str(p).startswith(prefix)]
            sources = sorted((p for p in entries if p.name.lower() in {'readme.md', 'skill.md'}), key=lambda p: (len(p.parts), str(p)))
            signature = [(str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in sources]
            key = str(group)
            cached = CACHE.get(key)
            if cached and cached['signature'] == signature:
                item = dict(cached['item'])
            else:
                texts = [(p, p.read_text(encoding='utf-8', errors='replace')) for p in sources]
                primary = next((body for p, body in texts if p.name.lower() == 'readme.md'), texts[0][1] if texts else '')
                heading = re.search(r'^#\s+(.+)$', primary, re.M)
                title = heading.group(1).strip('*` ') if heading else ''
                description = re.search(r'^description:\s*(.+)$', primary, re.M)
                desc = description.group(1).strip('"\'') if description else next((line.strip()[:240] for line in primary.splitlines() if line.strip() and not re.match(r'^(#|---|```|name:|[!\[])', line)), '打开查看说明与文件。')
                body = '\n\n'.join('## 来源：' + str(p.relative_to(group)) + '\n\n' + text for p, text in texts) or '未发现 README.md 或 SKILL.md，可查看项目文件。'
                item = dict(id=hashlib.sha256(key.encode()).hexdigest()[:24], path=key, name=group.name, chineseName=title if re.search('[\u4e00-\u9fff]', title) and len(title) <= 40 else labels.get(group.name, group.name), description=desc, body=body, sources=[str(p) for p in sources], kind='project', skillCount=sum(p.name == 'SKILL.md' for p in sources))
                item['documentHashes'] = {str(p.relative_to(group)): hashlib.sha256(text.encode('utf-8')).hexdigest() for p, text in texts}
                CACHE[key] = dict(signature=signature, item=dict(item))
            item.update(files=[str(p) for p in entries], pages=[str(p) for p in entries if p.suffix.lower() in {'.html', '.htm'}], scripts=[str(p) for p in entries if p.suffix.lower() in {'.py', '.sh', '.js', '.mjs'}])
            usage_guides.attach(item)
            mapping.update((str(p), p) for p in entries)
            result.append(item)
    FILES.clear()
    FILES.update(mapping)
    snapshot = dict(paths=paths, mode=mode, skills=result, errors=errors, elapsed=round(time.monotonic() - started, 3), count=len(mapping))
    STATE.mkdir(exist_ok=True)
    temporary = CONFIG.with_suffix('.tmp')
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False), encoding='utf-8')
    temporary.replace(CONFIG)
    return snapshot


class Handler(BaseHTTPRequestHandler):
    def respond(self, value, code=200):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get('Host') in {'127.0.0.1:8765', 'localhost:8765'}

    def do_GET(self):
        if not self.valid_host():
            return self.respond({'error': 'Invalid host'}, 403)
        route = urlsplit(self.path)
        if route.path == '/api/session':
            return self.respond({'token': TOKEN})
        if route.path == '/api/workspace':
            try:
                value = json.loads(CONFIG.read_text(encoding='utf-8'))
                with LOCK:
                    for item in value['skills']:
                        for name in item['files']:
                            p = Path(name)
                            if Path(item['path']) in p.parents:
                                FILES[name] = p
                return self.respond(value)
            except (OSError, ValueError, KeyError):
                return self.respond({'skills': [], 'paths': [], 'count': 0})
        if route.path == '/api/file':
            if self.headers.get('X-Skills-Token') != TOKEN:
                return self.respond({'error': 'Invalid token'}, 403)
            name = parse_qs(route.query).get('path', [''])[0]
            file = FILES.get(name)
            # Only indexed paths; reject later symlink replacements as well.
            if not file or file.is_symlink() or file.resolve() != file:
                return self.respond({'error': 'File not indexed'}, 403)
        else:
            name = route.path.lstrip('/') or 'index.html'
            file = (BASE / 'static' / name).resolve()
            if file.parent != (BASE / 'static').resolve():
                return self.respond({'error': 'Forbidden'}, 403)
        try:
            data = file.read_bytes()
        except OSError:
            return self.respond({'error': 'File unavailable'}, 404)
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.valid_host() or self.headers.get('X-Skills-Token') != TOKEN or (origin and origin not in {'http://127.0.0.1:8765', 'http://localhost:8765'}):
            return self.respond({'error': 'Forbidden'}, 403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size > 65536:
                raise ValueError('请求过大')
            data = json.loads(self.rfile.read(size) or '{}')
            with LOCK:
                if self.path == '/api/preview':
                    return self.respond(open_preview(data.get('path', '')))
                if self.path == '/api/scan':
                    paths = data.get('paths', [])
                    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p.strip() for p in paths):
                        raise ValueError('请填写要读取的目录')
                    return self.respond(scan(paths, data.get('mode', 'projects')))
                if self.path == '/api/clear':
                    FILES.clear()
                    CACHE.clear()
                    CONFIG.unlink(missing_ok=True)
                    return self.respond({'ok': True})
            return self.respond({'error': 'Unknown endpoint'}, 404)
        except Exception as error:
            return self.respond({'error': str(error)}, 400)


def main():
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()


if __name__ == '__main__':
    main()
