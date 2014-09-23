import unittest
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.replacer import Replacer
from rez.contrib.animallogic.launcher.tests.stubs import StubPresetProxy, StubToolsetProxy

__author__ = 'federicon'
__docformat__ = 'epytext'


class TestReplace(unittest.TestCase):

    def setUp(self):

        self.launcher_service = LauncherHessianService(StubPresetProxy(), StubToolsetProxy())
        self.replacer = Replacer(self.launcher_service)

    def test_valid_replace(self):

        destination_path = '/presets/root/path'
        reference_path = '/test/path/replace'
        old_ref_path_1 =  '/test/full/path'
        old_ref_path_2 = '/test/to/different/path/path'

        current_references = self.launcher_service.get_references_from_path(destination_path, 'username')

        for ref in current_references:
            full_path = self.launcher_service.get_preset_full_path(ref.get_preset_id_as_dict())
            self.assertTrue(full_path in [old_ref_path_1, old_ref_path_2])

        self.replacer.replace(reference_path, destination_path, 'nice description')

        current_references = self.launcher_service.get_references_from_path(destination_path, 'username')
        full_path = self.launcher_service.get_preset_full_path(current_references[0].get_preset_id_as_dict())
        self.assertEqual(full_path, reference_path)
