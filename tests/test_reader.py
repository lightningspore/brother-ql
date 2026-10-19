import unittest
from brother_ql.reader import interpret_response, chunker, match_opcode
from brother_ql.models import ModelsManager


def packet(**fields):
    data = bytearray(32)
    data[:5] = b'\x80\x20\x42\x30\x4f'
    data[10], data[11], data[17] = 29, 0x0b, 90
    for key, value in fields.items():
        data[int(key)] = value
    return bytes(data)


class ReaderTests(unittest.TestCase):
    def test_known_ql_status_stays_compatible(self):
        result = interpret_response(packet())
        self.assertEqual(result['media_type'], 'Die-cut labels')
        self.assertEqual(result['media_width'], 29)
        self.assertEqual(result['media_length'], 90)
        self.assertEqual(result['status_type'], 'Reply to status request')
        self.assertEqual(result['phase_type'], 'Waiting to receive')

    def test_unknown_codes_preserve_numeric_values_without_crashing(self):
        result = interpret_response(packet(**{'11': 0xfe, '18': 0xfe, '19': 0xfe}))
        for name in ('media', 'status', 'phase'):
            self.assertEqual(result[name + '_code'], 0xfe)
            self.assertEqual(result[name + '_type'], 'Unknown (0xFE)')

    def test_all_media_status_and_phase_codes_are_decodable(self):
        for offset in (11, 18, 19):
            for code in range(256):
                with self.subTest(offset=offset, code=code):
                    interpret_response(packet(**{str(offset): code}))

    def test_invalid_packets_raise_value_error(self):
        for data in (b'', bytes(31), bytes(32)):
            with self.subTest(data=data), self.assertRaises(ValueError):
                interpret_response(data)

    def test_unknown_opcode_obeys_strict_and_permissive_modes(self):
        with self.assertRaises(KeyError):
            match_opcode(b'\xff')
        with self.assertRaises(ValueError):
            list(chunker(b'\xff', raise_exception=True))
        self.assertEqual(list(chunker(b'\xff\x1a')), [b'\x1a'])

    def test_truncated_commands_are_not_returned_as_valid(self):
        for data in (b'\x67', b'\x67\x00', b'\x67\x00\x04ab',
                     b'\x47\x04\x00ab', b'\x1biz\x80'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                list(chunker(data, raise_exception=True))

    def test_unknown_pt_color_codes_do_not_crash(self):
        model = next(m for m in ModelsManager().iter_elements()
                     if m.identifier.startswith('PT'))
        data = bytearray(packet())
        data[3], data[4] = model.series_code, model.model_code
        data[24], data[25] = 0xfe, 0xfe
        result = interpret_response(data)
        self.assertEqual(result['tape_color'], 'Unknown (0xFE)')
        self.assertEqual(result['text_color'], 'Unknown (0xFE)')
