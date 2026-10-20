"""Independently decode source images and reconstructed transmitted pixels."""
import unittest
from PIL import Image
from tools.barcode_labels import pattern,validate,raster_image


class BarcodeTests(unittest.TestCase):
    def test_both_formats_survive_rasterization_on_both_models(self):
        for model in ('QL-800','QL-1110NWB'):
            with self.subTest(model=model):
                image,expected=pattern(model)
                preview,report=validate(model,image)
                self.assertEqual(report['source_decoded'],expected)
                self.assertEqual(report['raster_decoded'],expected)
                self.assertEqual(preview.height,image.height)
                self.assertEqual(set(color for count,color in image.getcolors(maxcolors=3)),{(0,0,0),(255,255,255)})

    def test_missing_codes_fail_verification(self):
        with self.assertRaises(ValueError):
            validate('QL-800',Image.new('RGB',(306,991),'white'))

    def test_missing_or_inconsistent_raster_is_rejected(self):
        for data in (b'\x1a',b'g\x00\x01\xffg\x00\x02\xff\xff'):
            with self.subTest(data=data),self.assertRaises(ValueError):
                raster_image(data)
