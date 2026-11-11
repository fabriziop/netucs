"""Exercise Debian build numbering in disposable repositories."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('dpkg-deb') and shutil.which('git'), 'requires Debian build tools')
class DebianCounterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        for name in ('build_deb.sh', 'README.md', 'LICENSE', '.gitignore'):
            shutil.copy2(SOURCE / name, self.repo / name)
        shutil.copytree(SOURCE / 'src', self.repo / 'src', ignore=shutil.ignore_patterns('__pycache__'))
        (self.repo / 'VERSION').write_text('0.6.0\n')
        self.git('init', '-q')
        self.git('config', 'user.name', 'Build Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('add', '.')
        self.git('commit', '-qm', 'Initial release')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def build(self, expected, env=None):
        result = subprocess.run(['bash', str(self.repo / 'build_deb.sh')],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        package = self.repo / f'python3-netucs_{expected}_all.deb'
        actual = subprocess.check_output(['dpkg-deb', '--field', str(package), 'Version'], text=True).strip()
        self.assertEqual(actual, expected)

    def test_counter_and_version_reset(self):
        self.build('0.6.0-1+build1')
        self.build('0.6.0-1+build2')
        (self.repo / 'VERSION').write_text('0.6.1\n')
        self.build('0.6.1-1+build1')
        self.assertEqual((self.repo / '.deb-build-counter').read_text(), '0.6.1 1\n')
        self.assertNotIn('.deb-build-counter', self.git('status', '--porcelain'))

    def test_release_dirty_tag_and_return_to_release(self):
        self.git('tag', 'v0.6.0')
        self.build('0.6.0-1')
        self.assertFalse((self.repo / '.deb-build-counter').exists())
        # Rebuilding a clean tag stays a release despite generated output.
        self.build('0.6.0-1')
        (self.repo / 'untracked').write_text('development change')
        self.build('0.6.0-1+build1')
        (self.repo / 'untracked').unlink()
        self.build('0.6.0-1')
        self.assertEqual((self.repo / '.deb-build-counter').read_text(), '0.6.0 1\n')

    def test_legacy_tag(self):
        self.git('tag', '0.6.0')
        self.build('0.6.0-1')

    def test_failed_build_keeps_counter(self):
        self.build('0.6.0-1+build1')
        fake_bin = self.repo / 'fake-bin'
        fake_bin.mkdir()
        fake_dpkg = fake_bin / 'dpkg-deb'
        fake_dpkg.write_text('#!/bin/sh\nexit 1\n')
        fake_dpkg.chmod(0o755)
        env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ['PATH'])
        result = subprocess.run(['bash', str(self.repo / 'build_deb.sh')], env=env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.repo / '.deb-build-counter').read_text(), '0.6.0 1\n')

    def test_version_order(self):
        for before, after in [('0.6.0-1', '0.6.0-1+build1'),
                              ('0.6.0-1+build2', '0.6.0-1+build10'),
                              ('0.6.0-1+build10', '0.6.1-1')]:
            subprocess.run(['dpkg', '--compare-versions', before, 'lt', after], check=True)


if __name__ == '__main__':
    unittest.main()
