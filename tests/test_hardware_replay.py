"""Replay replies captured from synthetic prints; never access real hardware."""
import json
import unittest
from pathlib import Path
from collections import deque
from unittest.mock import Mock

from brother_ql.print_queue import BrotherPrintQueue
from brother_ql.reader import interpret_response
from test_queue import Transport


class HardwareReplayTests(unittest.TestCase):
    def test_captured_ql800_and_ql1110_two_page_sequences(self):
        for path in Path(__file__).with_name('fixtures').glob('*.json'):
            fixture = json.loads(path.read_text())
            replies = [bytes.fromhex(h) for h in fixture['replies']]
            for raw in replies:
                result = interpret_response(raw)
                self.assertEqual(result['model'], fixture['model'])
                self.assertEqual(result['errors'], [])
            # First reply belongs to the probe's preflight, then queue init,
            # two page cycles, and the probe's final status query.
            for fragmented in (False, True):
                with self.subTest(model=fixture['model'], fragmented=fragmented):
                    data = replies[1:-1]
                    if fragmented:
                        data = [part for raw in data for part in (raw[:9], raw[9:])]
                    transport = Transport(data)
                    queue = BrotherPrintQueue(transport, Mock(data=b'init'))
                    queue._print_queue = deque([b'page1', b'page2'])
                    self.assertTrue(queue.submit())
                    self.assertFalse(queue.uncertain)
                    self.assertTrue(queue.ready)
                    self.assertEqual(transport.writes.count(b'page1'), 1)
                    self.assertEqual(transport.writes.count(b'page2'), 1)

    def test_timeout_settings_are_explicit_and_validated(self):
        for value in (0, -1, float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                BrotherPrintQueue(Mock(), Mock(), completion_timeout=value)
        queue = BrotherPrintQueue(Transport([bytes.fromhex(json.loads(
            Path(__file__).with_name('fixtures').joinpath('QL-800.json').read_text()
        )['replies'][0])]), Mock(data=b'init'), completion_timeout=45)
        queue._print_queue.append(b'page')
        queue._validate_status = Mock(side_effect=[True, True])
        self.assertTrue(queue.submit())
        self.assertEqual(queue._validate_status.call_args_list[0].kwargs['timeout'], 45)
