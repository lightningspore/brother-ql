import unittest
from click.testing import CliRunner
from brother_ql.cli import cli


class CLITests(unittest.TestCase):
    def test_version_uses_fork_metadata(self):
        result = CliRunner().invoke(cli, ['--version'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('1.4a1', result.output)

    def test_environment_info_works_without_pkg_resources(self):
        result = CliRunner().invoke(cli, ['info', 'env'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('1.4a1', result.output)
