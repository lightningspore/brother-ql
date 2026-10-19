import unittest
from unittest.mock import Mock

import packbits
from PIL import Image
from brother_ql.conversion import convert
from brother_ql import create_label
from brother_ql.print_queue import BrotherPrintQueue
from brother_ql.raster import BrotherQLRaster
from brother_ql.reader import chunker
from test_reader import packet


def media_instructions(data):
    return [instruction for instruction in chunker(data, raise_exception=True)
            if instruction.startswith(b'\x1biz')]


class ConversionTests(unittest.TestCase):
    def test_ql800_and_ql1110_generate_complete_raster_pages(self):
        for model, label, width in [('QL-800', '29x90', 306),
                                    ('QL-1110NWB', '102', 1164)]:
            for compress in (False, True):
                with self.subTest(model=model, compress=compress):
                    image = Image.new('RGB', (width, 991 if label == '29x90' else 200), 'white')
                    image.paste('black', (10, 10, 100, 100))
                    data = convert(BrotherQLRaster(model), [image], label,
                                   compress=compress)
                    self.assertTrue(data.endswith(b'\x1a'))
                    headers = media_instructions(data)
                    self.assertEqual(len(headers), 1)
                    self.assertEqual(headers[0][-2], 0)  # first page flag

    def test_queue_marks_first_and_subsequent_pages_correctly(self):
        printer = Mock()
        printer.read.return_value = packet()
        queue = BrotherPrintQueue(printer, BrotherQLRaster('QL-800'))
        image = Image.new('RGB', (306, 991), 'white')
        queue.queue_image(images=[image], label='29x90')
        queue.queue_image(images=[image], label='29x90')
        pages = list(queue._print_queue)
        self.assertEqual([media_instructions(p)[0][-2] for p in pages], [0, 1])
        self.assertEqual(queue.page_count, 2)

    def test_compression_preserves_every_raster_row_for_both_models(self):
        for model, label, width, height in [('QL-800', '29x90', 306, 991),
                                           ('QL-1110NWB', '102', 1164, 200)]:
            image = Image.new('RGB', (width, height), 'white')
            image.paste('black', (7, 11, 150, 100))
            rows = []
            for compress in (False, True):
                raster = BrotherQLRaster(model)
                data = convert(raster, [image], label, compress=compress)
                payloads = [p[3:] for p in chunker(data, raise_exception=True)
                            if p.startswith(b'\x67\x00')]
                rows.append([packbits.decode(p) if compress and raster.compression_support else p for p in payloads])
            self.assertTrue(rows[0] == rows[1], f"Raster pixels changed: {model}")
            self.assertEqual(len(rows[0]), height)

    def test_legacy_create_label_populates_raster_buffer(self):
        for model, label, size in [('QL-800', '29x90', (306, 991)),
                                    ('QL-1110NWB', '102', (1164, 708))]:
            with self.subTest(model=model):
                image = Image.new('RGB', size, 'white')
                raster = BrotherQLRaster(model)
                create_label(raster, image, label, compress=True)
                expected = convert(BrotherQLRaster(model), [image], label, compress=True)
                self.assertEqual(len(raster.data), len(expected))
                self.assertTrue(raster.data == expected)
                self.assertTrue(raster.data.endswith(b'\x1a'))
