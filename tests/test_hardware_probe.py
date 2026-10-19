import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools.hardware_probe import main


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / 'report.json'
        fixture = json.loads(Path(__file__).with_name('fixtures').joinpath('QL-800.json').read_text())
        self.status = bytes.fromhex(fixture['replies'][0])
        self.backend = Mock()
        self.backend.read.return_value = self.status

    def run_probe(self, *extra):
        argv = ['hardware_probe', '--model', 'QL-800', '--identifier', 'usb://test',
                '--output', str(self.output), *extra]
        with patch('sys.argv', argv), patch('tools.hardware_probe.backend_factory',
                return_value={'backend_class': Mock(return_value=self.backend)}), \
                patch('builtins.print'):
            main()

    def test_default_only_queries_status_and_disposes_transport(self):
        self.run_probe()
        self.assertFalse(json.loads(self.output.read_text())['printed'])
        self.assertEqual([c.args[0] for c in self.backend.write.call_args_list],
                         [b'\x1biS', b'\x1biS'])
        self.backend.dispose.assert_called_once()
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    def test_wrong_stock_never_sends_raster_even_with_print_flag(self):
        raw = bytearray(self.status)
        raw[10] = 62
        self.backend.read.return_value = bytes(raw)
        with self.assertRaisesRegex(RuntimeError, 'Unexpected stock'):
            self.run_probe('--print')
        self.backend.write.assert_called_once_with(b'\x1biS')
        self.assertIn('Unexpected stock', json.loads(self.output.read_text())['error'])
        self.backend.dispose.assert_called_once()

    def test_existing_report_refuses_any_device_access(self):
        self.output.write_text('previous experiment')
        with self.assertRaises(FileExistsError):
            self.run_probe('--print')
        self.backend.write.assert_not_called()
        self.assertEqual(self.output.read_text(), 'previous experiment')

    def test_unconfirmed_print_is_reported_and_not_retried(self):
        queue = Mock(uncertain=True, last_error=[])
        queue.submit.return_value = False
        with patch('tools.hardware_probe.BrotherPrintQueue', return_value=queue):
            with self.assertRaisesRegex(RuntimeError, 'do not retry'):
                self.run_probe('--print')
        queue.submit.assert_called_once()
        self.assertTrue(json.loads(self.output.read_text())['uncertain'])
        self.backend.dispose.assert_called_once()
