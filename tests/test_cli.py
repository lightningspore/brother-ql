import unittest
from importlib.metadata import version
from click.testing import CliRunner
from brother_ql.cli import cli


class CLITests(unittest.TestCase):
    def test_version_uses_fork_metadata(self):
        result = CliRunner().invoke(cli, ['--version'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(version('brother-ql-sporeprint'), result.output)

    def test_environment_info_works_without_pkg_resources(self):
        result = CliRunner().invoke(cli, ['info', 'env'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(version('brother-ql-sporeprint'), result.output)

    def test_json_catalogs_have_complete_stable_records_without_hardware(self):
        import json
        from unittest.mock import patch
        from brother_ql.models import ALL_MODELS
        from brother_ql.labels import ALL_LABELS
        with patch('brother_ql.backends.helpers.get_printer', side_effect=AssertionError('USB accessed')):
            for command, expected in [('models', ALL_MODELS), ('labels', ALL_LABELS)]:
                result = CliRunner().invoke(cli, ['info', command, '--json'])
                self.assertEqual(result.exit_code, 0, result.output)
                records = json.loads(result.output)
                self.assertEqual([r['identifier'] for r in records], [r.identifier for r in expected])
                if command == 'models':
                    model = next(r for r in records if r['identifier'] == 'QL-1110NWB')
                    self.assertEqual(model['min_max_length_dots'], [301, 35434])
                    self.assertIs(model['compression_support'], True)
                else:
                    label = next(r for r in records if r['identifier'] == '102')
                    self.assertEqual(label['dots_printable'], [1164, 0])
                    self.assertEqual(label['form_factor'], 'ENDLESS')
                    self.assertEqual(label['color'], 'BLACK_WHITE')
                    self.assertIn('QL-1110NWB', label['restricted_to_models'])
                    self.assertNotIn('QL-800', label['restricted_to_models'])

    def test_catalog_text_remains_the_default(self):
        for command, heading in [('models', 'Supported models:'), ('labels', '29x90')]:
            result = CliRunner().invoke(cli, ['info', command])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn(heading, result.output)
            self.assertFalse(result.output.startswith('['))
