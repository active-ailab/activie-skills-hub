import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('launcher', Path(__file__).parents[1] / 'launch.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTest(unittest.TestCase):
    def test_repeated_open_waits_for_windows_handoff(self):
        with patch.object(launcher.subprocess, 'run') as run:
            launcher.open_browser()
            launcher.open_browser()
        self.assertEqual(run.call_count, 2)
        args, kwargs = run.call_args
        self.assertEqual(args[0][0], 'powershell.exe')
        self.assertIn(launcher.URL, args[0][-1])
        self.assertTrue(kwargs['check'])
        self.assertEqual(kwargs['timeout'], 30)

    def test_windows_failure_is_reported(self):
        with patch.object(launcher.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'powershell.exe')):
            with self.assertRaises(subprocess.CalledProcessError):
                launcher.open_browser()
