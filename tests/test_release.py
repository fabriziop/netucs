"""Release validation tests using disposable Git repositories."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'release.py'


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Release Test')
        self.git('config', 'user.email', 'test@example.invalid')
        shutil.copy2(SCRIPT, self.root / 'release.py')
        self.set_version('0.10.0')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def set_version(self, version):
        (self.root / 'VERSION').write_text(version + '\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Release changes')

    def run_release(self, *args, success=True):
        result = subprocess.run(['python3', str(self.root / 'release.py'), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return result

    def test_numeric_order_and_annotated_tag(self):
        self.git('tag', '0.9.0')
        self.run_release()
        self.assertEqual(self.git('cat-file', '-t', 'refs/tags/v0.10.0'), 'tag')
        self.assertEqual(self.git('rev-parse', 'v0.10.0^{}'), self.git('rev-parse', 'HEAD'))

    def test_check_does_not_tag(self):
        self.run_release('--check')
        self.assertEqual(self.git('tag'), '')

    def test_duplicate_and_downgrade(self):
        for tag in ('0.10.0', 'v0.10.0', 'v1.0.0'):
            with self.subTest(tag=tag):
                self.git('tag', tag)
                self.run_release(success=False)
                self.git('tag', '-d', tag)

    def test_dirty_and_untracked(self):
        (self.root / 'VERSION').write_text('1.0.0\n')
        self.run_release(success=False)
        self.git('checkout', '--', 'VERSION')
        (self.root / 'extra').write_text('untracked')
        self.run_release(success=False)

    def test_invalid_version(self):
        for version in ('', '01.2.3', '1.2', 'v1.2.3', '1.2.3\n4.5.6'):
            self.set_version(version)
            self.run_release(success=False)

    def test_tag_ci_validation(self):
        self.run_release()
        self.run_release('--check-tag', 'v0.10.0')
        self.run_release('--check-tag', 'v0.11.0', success=False)
        self.set_version('0.11.0')
        self.git('tag', 'v0.11.0', 'HEAD~1')
        self.run_release('--check-tag', 'v0.11.0', success=False)

    def test_missing_and_uncommitted_version(self):
        (self.root / 'VERSION').unlink()
        self.git('add', '-u')
        self.git('commit', '-qm', 'Remove VERSION')
        self.run_release(success=False)
        self.git('config', 'core.excludesfile', str(self.root / '.git' / 'ignored'))
        (self.root / '.git' / 'ignored').write_text('VERSION\n')
        (self.root / 'VERSION').write_text('0.11.0\n')
        self.run_release(success=False)

    def test_existing_legacy_tag_ci(self):
        self.git('tag', '0.10.0')
        self.run_release('--check-tag', '0.10.0')


if __name__ == '__main__':
    unittest.main()
