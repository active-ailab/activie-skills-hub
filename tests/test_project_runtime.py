import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import local_server as reader
import project_runtime as runtime


class RuntimeTest(unittest.TestCase):
    def test_static_pages_keep_relative_resources_and_cannot_escape_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            (root / 'assets').mkdir(parents=True)
            page = root / 'index.html'
            page.write_text('<script type="module" src="assets/tool.js"></script>')
            (root / 'assets/tool.js').write_text('export const value = 42;')
            (root / '.env').write_text('private')
            (root / 'outside').symlink_to('/etc/passwd')
            config = Path(tmp) / 'workspace.json'
            config.write_text(json.dumps({'skills': [{'path': str(root), 'files': [str(page)]}]}))
            with patch.object(reader, 'CONFIG', config), patch.dict(reader.FILES, {str(page): page}):
                url = reader.open_preview(str(page))['url']
                self.assertEqual(reader.open_preview(str(page))['url'], url)
                with urllib.request.urlopen(url.replace('index.html', 'assets/tool.js')) as response:
                    self.assertIn(b'value = 42', response.read())
                for path in ['.env', 'outside', '../workspace.json', 'assets/']:
                    with self.assertRaises(urllib.error.HTTPError):
                        urllib.request.urlopen(url.replace('index.html', path))
            server = reader.PREVIEWS.pop(root)
            server.shutdown()
            server.server_close()

    def test_backend_starts_once_and_serves_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'web').mkdir()
            page = root / 'web/index.html'
            page.write_text('<h1>Tool</h1>')
            entry = root / 'server.py'
            entry.write_text('''import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
p=argparse.ArgumentParser();p.add_argument('--host');p.add_argument('--port',type=int);a=p.parse_args()
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(b'{"result":42}')
HTTPServer((a.host,a.port), Handler).serve_forever()
''')
            with patch.object(runtime, 'BASE', root):
                try:
                    url = runtime.start(root, page)
                    self.assertEqual(runtime.start(root, page), url)
                    with urllib.request.urlopen(url + 'api/compute') as response:
                        self.assertEqual(json.load(response), {'result': 42})
                finally:
                    process = runtime.RUNNING.pop(str(entry))['process']
                    process.terminate()
                    process.wait(timeout=5)

    def test_unindexed_page_cannot_start_a_project(self):
        with self.assertRaises(ValueError):
            reader.open_preview('/etc/index.html')

class PortableBundleTest(unittest.TestCase):
    def test_bundle_contains_runtime_but_no_machine_state(self):
        import package_local
        from zipfile import ZipFile
        with tempfile.TemporaryDirectory() as tmp:
            archive = package_local.build(Path(tmp) / 'local.zip')
            with ZipFile(archive) as bundle:
                names = bundle.namelist()
                for name in ['launch.py', 'local_server.py', 'project_runtime.py', 'README.md', 'static/app.js']:
                    self.assertIn('skills-hub/' + name, names)
                self.assertFalse(any('/.state/' in name or '/.venvs/' in name or '/.git/' in name for name in names))

    def test_clean_projects_get_separate_environments_and_dependency_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            roots = [base / 'first/tool', base / 'second/tool']
            for root in roots:
                root.mkdir(parents=True)
                (root / 'requirements.txt').write_text('Flask>=3.0\n')
            calls = []
            def run(command, **kwargs):
                calls.append(command)
                if command[1] == 'venv':
                    python = Path(command[-1]) / 'bin/python'
                    python.parent.mkdir(parents=True, exist_ok=True)
                    python.touch()
                return None
            with patch.object(runtime, 'BASE', base / 'clean-hub'), patch.object(runtime, 'ensure_uv', return_value='uv'), patch.object(runtime.subprocess, 'run', side_effect=run):
                def prepare(root):
                    return runtime.python_for(root, {'kind': 'flask', 'requirements': root / 'requirements.txt'}, None)
                first = prepare(roots[0])
                self.assertEqual(prepare(roots[0]), first)
                self.assertEqual(len(calls), 2)
                second = prepare(roots[1])
                self.assertNotEqual(first, second)
                (roots[0] / 'requirements.txt').write_text('Flask>=3.1\n')
                prepare(roots[0])
                self.assertEqual(len(calls), 6)
                self.assertFalse(any('--system-site-packages' in command for command in calls))
