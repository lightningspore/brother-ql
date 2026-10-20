"""Selected January 2026 pklaus changes, retaining InvenTree compatibility."""
import contextlib
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from brother_ql.labels import LabelsManager
from brother_ql.models import ModelsManager
from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.devicedependent import label_type_specs, models
from brother_ql.output_helpers import textual_label_description
from brother_ql.brother_ql_create import main as create_main
from brother_ql.brother_ql_info import main as info_main


class UpstreamTests(unittest.TestCase):
    def test_lookup_and_unknown_identifier_errors(self):
        self.assertEqual(ModelsManager().get_model_by_identifier('QL-1110NWB').product_id, 0x20a8)
        self.assertEqual(LabelsManager().get_label_by_identifier('29x90').dots_printable, (306, 991))
        for manager, method, kind in [(ModelsManager(), 'get_model_by_identifier', 'model'),
                                      (LabelsManager(), 'get_label_by_identifier', 'label')]:
            with self.assertRaisesRegex(ValueError, 'Unknown '+kind+': missing'):
                getattr(manager, method)('missing')

    def test_restricted_labels_use_their_actual_model_list(self):
        label = LabelsManager().get_label_by_identifier('102')
        self.assertTrue(label.works_with_model('QL-1110NWB'))
        self.assertFalse(label.works_with_model('QL-800'))
        self.assertTrue(LabelsManager().get_label_by_identifier('29x90').works_with_model('QL-800'))

    def test_103_compatibility_extends_to_all_wide_ql_models(self):
        label = LabelsManager().get_label_by_identifier('103')
        for model in ('QL-1050','QL-1060N','QL-1100','QL-1110NWB','QL-1115NWB'):
            self.assertTrue(label.works_with_model(model))
            self.assertIn(model, label_type_specs['103']['restrict_printers'])
        self.assertFalse(label.works_with_model('QL-800'))

    def test_legacy_api_and_extra_inventree_entries_survive(self):
        self.assertTrue({'104','12+17','54x29','pt12','pt18','pt36'} <= label_type_specs.keys())
        self.assertIn('QL-600', models)
        self.assertIn('PT-P950NW', models)
        qlr = BrotherQLRaster('QL-800')
        qlr.add_invalidate()
        self.assertEqual(qlr.data, bytes(400))

    def test_legacy_cli_invalid_inputs_are_clean_errors(self):
        for args, message in [(['--model','not-a-model'], 'Unknown model'),
                               (['--label-size','not-a-label'], 'Unknown label_size')]:
            with tempfile.TemporaryDirectory() as directory:
                argv=['create','nonexistent.png',*args]
                with patch('sys.argv',argv), self.assertRaisesRegex(SystemExit,message):
                    create_main()

    def test_ptouch_label_descriptions_have_dimensions(self):
        self.assertNotIn('unknown',textual_label_description(['pt12','pt18','pt24','pt36']))
        with patch('sys.argv',['info','list-label-sizes']), contextlib.redirect_stdout(io.StringIO()) as output:
            info_main()
        self.assertIn('P-touch endless',output.getvalue())

    def test_validated_ql_raster_bytes_are_unchanged(self):
        cases=[('QL-800','29x90',(306,991),'da2901ed48ed51c6e5b5a43496222ff65956e3f2df0aa8634d5c7619c9274856'),
               ('QL-1110NWB','102',(1164,708),'87c3232af530fc32998bf93b74ee69da2ceb405f3740f8830cbc1baeefc7d05f')]
        for model,label,size,expected in cases:
            image=Image.new('RGB',size,'white');image.paste('black',(16,16,180,150))
            data=convert(BrotherQLRaster(model),[image],label,compress=True)
            self.assertEqual(hashlib.sha256(data).hexdigest(),expected)
