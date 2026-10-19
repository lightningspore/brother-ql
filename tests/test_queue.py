import time
import unittest
from collections import deque
from unittest.mock import Mock
from brother_ql.print_queue import BrotherPrintQueue
from brother_ql.reader import StatusReader
from test_reader import packet


class Transport:
    def __init__(self, replies):
        self.replies = deque(replies)
        self.writes = []

    def read(self, length=32):
        return self.replies.popleft() if self.replies else b''

    def write(self, data):
        self.writes.append(data)


def queue(replies):
    printer = Transport([packet()] + replies)
    raster = Mock(data=b'init')
    q = BrotherPrintQueue(printer, raster)
    q._print_queue.extend([b'page1', b'page2'])
    return q, printer


class QueueTests(unittest.TestCase):
    def test_framing_preserves_fragmented_and_combined_packets(self):
        first, second = packet(), packet(**{'18': 1})
        reader = StatusReader(Transport([first[:7], first[7:] + second]))
        deadline = time.monotonic() + 1
        self.assertEqual(reader.read(deadline)['status_code'], 0)
        self.assertEqual(reader.read(deadline)['status_code'], 1)

    def test_truncated_reply_times_out(self):
        reader = StatusReader(Transport([packet()[:5]]))
        with self.assertRaises(TimeoutError):
            reader.read(time.monotonic() + 0.01)

    def test_notifications_and_fast_completion_do_not_lose_pages(self):
        completion = packet(**{'18': 1, '19': 1})
        ready = packet(**{'18': 6})
        q, printer = queue([packet(**{'18': 5}) + completion + ready,
                            completion + ready])
        self.assertTrue(q.submit())
        self.assertEqual(printer.writes.count(b'page1'), 1)
        self.assertEqual(printer.writes.count(b'page2'), 1)
        self.assertFalse(q.uncertain)
        self.assertFalse(q._printing)
        self.assertEqual(q.page_count, 0)

    def test_error_cannot_look_like_success_or_resend(self):
        q, printer = queue([packet(**{'18': 1, '8': 1})])
        self.assertFalse(q.submit())
        self.assertTrue(q.uncertain)
        self.assertEqual(q.page_count, 1)
        with self.assertRaises(RuntimeError):
            q.submit()
        with self.assertRaises(RuntimeError):
            q.initialize()
        self.assertEqual(printer.writes.count(b'page1'), 1)
        self.assertNotIn(b'page2', printer.writes)
        q.clear()
        self.assertFalse(q.uncertain)
        self.assertEqual(q.page_count, 0)

    def test_write_exception_leaves_queue_inspectable_and_not_printing(self):
        q, printer = queue([])
        printer.write = Mock(side_effect=IOError('unplugged mid-write'))
        with self.assertRaises(IOError):
            q.submit()
        self.assertFalse(q._printing)
        self.assertTrue(q.uncertain)
        self.assertEqual(q.page_count, 1)
        with self.assertRaises(RuntimeError):
            q.submit()

    def test_status_skips_notifications_and_rejects_error_reply(self):
        q, _ = queue([packet(**{'18': 5}) + packet()])
        self.assertTrue(q._validate_status(status=0, timeout=.1))
        q._responses = StatusReader(Transport([packet(**{'8': 1})]))
        self.assertFalse(q._validate_status(status=0, timeout=.1))

    def test_timeout_blocks_retry_even_when_no_more_pages_remain(self):
        q, printer = queue([])
        q._print_queue = deque([b'page1'])
        q._responses.read = Mock(side_effect=TimeoutError('no acknowledgement'))
        self.assertFalse(q.submit(clear_on_failure=True))
        self.assertEqual(q.page_count, 0)
        self.assertTrue(q.uncertain)
        with self.assertRaises(RuntimeError):
            q.submit()
        self.assertEqual(printer.writes.count(b'page1'), 1)

    def test_ready_before_completion_does_not_confirm_print(self):
        q, printer = queue([packet(**{'18': 6})])
        q._responses.read = Mock(side_effect=[
            {'status_code': 6, 'phase_code': 0, 'errors': []},
            TimeoutError('no completion')])
        self.assertFalse(q.submit())
        self.assertTrue(q.uncertain)
        self.assertFalse(q.ready)

    def test_failed_initial_readiness_never_sends_page(self):
        q, printer = queue([])
        q.ready = False
        q._responses.read = Mock(return_value={
            'status_code': 0, 'phase_code': 0, 'errors': ['Cover open']})
        self.assertFalse(q.submit())
        self.assertNotIn(b'page1', printer.writes)
        self.assertFalse(q.uncertain)
