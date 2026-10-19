import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from brother_ql.backends.pyusb import BrotherQLBackendPyUSB
import usb.core


class USBTests(unittest.TestCase):
    def backend(self):
        backend = BrotherQLBackendPyUSB.__new__(BrotherQLBackendPyUSB)
        backend.dev = None
        backend.read_dev = Mock()
        backend.write_dev = Mock()
        backend.read_timeout = 10
        backend.write_timeout = 15000
        backend.strategy = 'try_twice'
        return backend

    def test_serial_selects_exact_device_with_same_product(self):
        devices = [SimpleNamespace(idVendor=0x04f9, idProduct=0x209b,
                                   iSerialNumber=3) for _ in range(2)]
        for dev in devices:
            dev.is_kernel_driver_active = Mock(return_value=False)
            dev.set_configuration = Mock()
            dev.get_active_configuration = Mock()
        discovered = [dict(identifier=f'usb://0x04f9:0x209b/{serial}', instance=dev)
                      for serial, dev in zip(('FIRST', 'SECOND'), devices)]
        with patch('brother_ql.backends.pyusb.list_available_devices', return_value=discovered), \
             patch('usb.util.find_descriptor', return_value=Mock()), \
             patch('usb.util.dispose_resources'):
            backend = BrotherQLBackendPyUSB('usb://0x04f9:0x209b/SECOND')
            self.assertIs(backend.dev, devices[1])
            backend.dispose()

    def test_missing_serial_does_not_fall_back_to_same_product(self):
        dev = SimpleNamespace(idVendor=0x04f9, idProduct=0x209b, iSerialNumber=3)
        with patch('brother_ql.backends.pyusb.list_available_devices', return_value=[
            dict(identifier='usb://0x04f9:0x209b/FIRST', instance=dev)
        ]):
            with self.assertRaises(ValueError):
                BrotherQLBackendPyUSB('usb://0x04f9:0x209b/MISSING')

    def test_timeout_returns_no_data_and_uses_explicit_timeout(self):
        backend = self.backend()
        backend.read_dev.read.side_effect = usb.core.USBTimeoutError('idle')
        self.assertEqual(backend.read(), b'')
        self.assertEqual(backend.read_dev.read.call_count, 2)
        backend.read_dev.read.assert_called_with(32, timeout=10)

    def test_disconnect_is_not_swallowed(self):
        backend = self.backend()
        backend.read_dev.read.side_effect = usb.core.USBError('disconnected')
        with self.assertRaises(usb.core.USBError):
            backend.read()

    def test_select_strategy_uses_bounded_usb_read(self):
        backend = self.backend()
        backend.strategy = 'select'
        backend.read_dev.read.return_value = b'reply'
        self.assertEqual(backend.read(), b'reply')
        backend.read_dev.read.assert_called_once_with(32, timeout=10)

    def test_partial_write_is_an_error_without_retry(self):
        backend = self.backend()
        backend.write_dev.write.return_value = 2
        with self.assertRaisesRegex(IOError, 'Short USB write'):
            backend.write(b'1234')
        backend.write_dev.write.assert_called_once()

    def test_initialization_failure_raises_and_reattaches(self):
        dev = Mock(spec=usb.core.Device)
        dev.is_kernel_driver_active.return_value = True
        dev.set_configuration.side_effect = usb.core.USBError('permission denied')
        with patch('usb.util.dispose_resources') as release:
            with self.assertRaises(usb.core.USBError):
                BrotherQLBackendPyUSB(dev)
            dev.attach_kernel_driver.assert_called_once_with(0)
            release.assert_called_once_with(dev)

    def test_cleanup_is_idempotent_even_if_release_fails(self):
        backend = self.backend()
        backend.dev = dev = Mock()
        backend.was_kernel_driver_active = True
        with patch('usb.util.dispose_resources', side_effect=usb.core.USBError('gone')) as release:
            backend.dispose()
            backend.dispose()
            release.assert_called_once_with(dev)
            dev.attach_kernel_driver.assert_called_once_with(0)
