import unittest
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.updater import Updater
from rez.contrib.animallogic.launcher.tests.stubs import StubPresetProxy, StubToolsetProxy

__author__ = 'federicon'
__docformat__ = 'epytext'


class TestUpdate(unittest.TestCase):

    def setUp(self):

        self.launcher_service = LauncherHessianService(StubPresetProxy(), StubToolsetProxy())
        self.updater = Updater(self.launcher_service)

    def test_add_reference(self):
        target_preset_path = '/presets/root/path'
        reference_preset_path_list = ['/test/full/path']

        self.updater.update(target_preset_path, reference_preset_path_list, 'nice description')

        current_references = self.launcher_service.get_references_from_path(target_preset_path)
        full_path_list = [ self.launcher_service.get_preset_full_path(current_references[0].preset_id)]
        self.assertEqual(full_path_list, reference_preset_path_list)

    def test_remove_all_reference(self):

        target_preset_path = '/presets/root/path'

        self.updater.update(target_preset_path, [], 'nice description', remove_all_references=True)

        current_references = self.launcher_service.get_references_from_path(target_preset_path)
        self.assertEqual(len(current_references), 0)

    def test_update_reference(self):

        target_preset_path = '/presets/root/path'

        new_reference_path_list = ['/test/path/replace']
        old_references = ['/test/full/path', '/test/to/different/path/']

        current_references = self.launcher_service.get_references_from_path(target_preset_path)

        for ref in current_references:
            full_path_list = self.launcher_service.get_preset_full_path(ref.preset_id)
            self.assertTrue(full_path_list in old_references)

        self.updater.update(target_preset_path, new_reference_path_list,  'nice description', remove_all_references=True)

        current_references = self.launcher_service.get_references_from_path(target_preset_path)
        full_path_list = [self.launcher_service.get_preset_full_path(current_references[0].preset_id)]
        self.assertEqual(full_path_list, new_reference_path_list)
