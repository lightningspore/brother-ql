import unittest

from PIL import Image

from brother_ql import BrotherQLRasterError
from brother_ql.conversion import convert
from brother_ql.models import ALL_MODELS
from brother_ql.raster import BrotherQLRaster


class LengthTests(unittest.TestCase):
    def test_continuous_boundaries_for_every_model_and_resolution(self):
        for model in ALL_MODELS:
            for high_resolution in (False, True):
                minimum, maximum = [v * (2 if high_resolution else 1)
                                    for v in model.min_max_length_dots]
                for height in (minimum - 1, minimum, maximum, maximum + 1):
                    with self.subTest(model=model.identifier, dpi_600=high_resolution, height=height):
                        raster = BrotherQLRaster(model.identifier)
                        raster.dpi_600 = high_resolution
                        image = Image.new('1', (raster.get_pixel_width(), height))
                        if minimum <= height <= maximum:
                            raster.add_raster_data(image)
                            self.assertTrue(raster.data)
                        else:
                            with self.assertRaisesRegex(BrotherQLRasterError, 'Invalid raster length'):
                                raster.add_raster_data(image)
                            self.assertEqual(raster.data, b'')

    def test_converter_validates_after_width_resizing(self):
        # Width is halved, so height becomes 300: below the QL-1110 minimum.
        with self.assertRaisesRegex(BrotherQLRasterError, '300 rows'):
            convert(BrotherQLRaster('QL-1110NWB'),
                    [Image.new('RGB', (2328, 600), 'white')], '102')

    def test_converter_resolution_scales_continuous_limits(self):
        for high_resolution, height, valid in [(False, 150, True),
                                               (True, 299, False),
                                               (True, 300, True)]:
            with self.subTest(dpi_600=high_resolution, height=height):
                image = Image.new('RGB', (1392 if high_resolution else 696, height), 'white')
                if valid:
                    self.assertTrue(convert(BrotherQLRaster('QL-800'), [image], '62', dpi_600=high_resolution))
                else:
                    with self.assertRaises(BrotherQLRasterError):
                        convert(BrotherQLRaster('QL-800'), [image], '62', dpi_600=high_resolution)

    def test_small_fixed_labels_keep_their_own_dimensions(self):
        for model, label, size in [('QL-800', 'd12', (94, 94)),
                                   ('QL-500', '23x23', (202, 202))]:
            for high_resolution in (False, True):
                with self.subTest(model=model, dpi_600=high_resolution):
                    scaled = tuple(v * (2 if high_resolution else 1) for v in size)
                    self.assertTrue(convert(BrotherQLRaster(model),
                                            [Image.new('RGB', scaled, 'white')], label,
                                            dpi_600=high_resolution))
        with self.assertRaisesRegex(ValueError, 'Bad image dimensions'):
            convert(BrotherQLRaster('QL-800'), [Image.new('RGB', (94, 95))], 'd12')
