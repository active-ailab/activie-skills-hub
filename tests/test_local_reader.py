import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('reader', Path(__file__).parents[1] / 'local_server.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ReaderTest(unittest.TestCase):
    def test_scan_skips_binary_contents_and_reuses_unchanged_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'Library'
            project = root / 'tool'
            project.mkdir(parents=True)
            (project / 'SKILL.md').write_text('# 工具\n\n说明内容')
            (project / 'huge.bin').write_bytes(b'\x00' * 10000)
            ignored = root / 'node_modules'
            ignored.mkdir()
            (ignored / 'SKILL.md').write_text('# 忽略')
            with patch.object(reader, 'CONFIG', Path(tmp) / 'snapshot.json'):
                first = reader.scan([str(root)])
                self.assertEqual(len(first['skills']), 1)
                self.assertEqual(first['count'], 2)
                with patch.object(Path, 'read_text', autospec=True, side_effect=lambda p, **kw: '{}' if p.name == 'chinese_names.json' else self.fail('Unchanged doc reread')):
                    second = reader.scan([str(root)])
                self.assertEqual(first['skills'], second['skills'])
                (project / 'SKILL.md').write_text('# 工具\n\n新的说明内容')
                third = reader.scan([str(root)])
                self.assertIn('新的说明', third['skills'][0]['body'])

    def test_symlinks_cannot_expand_scan_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'tool'
            root.mkdir()
            (root / 'SKILL.md').write_text('# Test')
            (root / 'outside').symlink_to('/etc', target_is_directory=True)
            (root / 'secret').symlink_to('/etc/passwd')
            with patch.object(reader, 'CONFIG', Path(tmp) / 'snapshot.json'):
                result = reader.scan([str(root)])
            self.assertEqual(result['count'], 1)


if __name__ == '__main__':
    unittest.main()
