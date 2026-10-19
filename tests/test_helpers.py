import unittest
from unittest.mock import Mock, patch
from brother_ql.backends.helpers import get_status, send
from test_reader import packet


class HelperTests(unittest.TestCase):
    def test_status_accepts_fragments(self):
        printer = Mock()
        data = packet()
        printer.read.side_effect = [data[:10], data[10:]]
        self.assertEqual(get_status(printer)['status_code'], 0)
        printer.write.assert_called_once_with(b'\x1biS')

    def test_malformed_status_preserves_parse_error(self):
        printer = Mock()
        printer.read.return_value = bytes(32)
        with self.assertRaises(ValueError):
            get_status(printer)

    def test_target_status_mismatch_is_an_error(self):
        printer = Mock()
        printer.read.return_value = packet(**{'18': 5})
        with self.assertRaisesRegex(ValueError, 'instead of'):
            get_status(printer, receive_only=True, target_status=0)
        printer.write.assert_not_called()

    def test_send_disposes_on_success_nonblocking_network_and_exception(self):
        for backend, blocking, fail in [('pyusb', True, False),
                                        ('pyusb', False, False),
                                        ('network', True, False),
                                        ('pyusb', True, True)]:
            with self.subTest(backend=backend, blocking=blocking, fail=fail):
                printer = Mock()
                printer.read.return_value = packet(**{'18': 1}) + packet(**{'18': 6})
                if fail:
                    printer.write.side_effect = IOError('disconnected')
                with patch('brother_ql.backends.helpers.backend_factory', return_value={
                    'backend_class': Mock(return_value=printer),
                    'list_available_devices': Mock(),
                }):
                    if fail:
                        with self.assertRaises(IOError):
                            send(b'job', 'test', backend, blocking)
                    else:
                        result = send(b'job', 'test', backend, blocking)
                        self.assertEqual(result['did_print'], backend == 'pyusb' and blocking)
                    printer.dispose.assert_called_once()
