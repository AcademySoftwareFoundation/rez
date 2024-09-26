# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'rez.utils.filesystem' module
"""
import os.path
import tempfile

from rez.tests.util import TestBase
from rez.tests.util import TempdirMixin
from rez.utils import filesystem
from rez.utils.platform_ import platform_
import unittest


class TestFileSystem(TestBase, TempdirMixin):

    def __init__(self, *nargs, **kwargs):
        super().__init__(*nargs, **kwargs)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        TempdirMixin.tearDownClass()

    def test_windows_rename_fallback_to_robocopy(self):
        if platform_.name != 'windows':
            self.skipTest('Robocopy is only available on windows.')
        src = tempfile.mkdtemp(dir=self.root)
        dst = tempfile.mkdtemp(dir=self.root)
        with unittest.mock.patch("os.rename") as mock_rename:
            mock_rename.side_effect = PermissionError("Permission denied")
            filesystem.rename(src, dst)
            self.assertTrue(os.path.exists(dst))
            self.assertFalse(os.path.exists(src))

    def test_windows_robocopy_failed(self):
        if platform_.name != 'windows':
            self.skipTest('Robocopy is only available on windows.')
        src = tempfile.mkdtemp(dir=self.root)
        dst = tempfile.mkdtemp(dir=self.root)
        with unittest.mock.patch("os.rename") as mock_rename:
            mock_rename.side_effect = PermissionError("Permission denied")
            with unittest.mock.patch("rez.utils.filesystem.Popen") as mock_subprocess:
                mock_subprocess.return_value = unittest.mock.Mock(returncode=9)
                with self.assertRaises(OSError) as err:
                    filesystem.rename(src, dst)
                self.assertEqual(str(err.exception), "Rename {} to {} failed.".format(src, dst))

    def test_rename_folder_with_permission_error_and_no_robocopy(self):
        src = tempfile.mkdtemp(dir=self.root)
        dst = tempfile.mkdtemp(dir=self.root)
        with unittest.mock.patch("os.rename") as mock_rename:
            mock_rename.side_effect = PermissionError("Permission denied")
            with unittest.mock.patch("rez.utils.filesystem.which") as mock_which:
                mock_which.return_value = False
                with self.assertRaises(PermissionError) as err:
                    filesystem.rename(src, dst)
                self.assertEqual(str(err.exception), "Permission denied")

    def test_rename_folder_with_permission_error_and_src_is_file(self):
        src = tempfile.mktemp(dir=self.root)
        dst = tempfile.mktemp(dir=self.root)
        with open(src, "w") as file_:
            file_.write("content.")
        with unittest.mock.patch("os.rename") as mock_rename:
            mock_rename.side_effect = PermissionError("Permission denied")
            with self.assertRaises(PermissionError) as err:
                filesystem.rename(src, dst)
            self.assertEqual(str(err.exception), "Permission denied")
        self.assertFalse(os.path.exists(dst))
        self.assertTrue(os.path.exists(src))

    def test_rename_file(self):
        src = tempfile.mktemp(dir=self.root)
        dst = tempfile.mktemp(dir=self.root)
        with open(src, "w") as file_:
            file_.write("content.")
        filesystem.rename(src, dst)
        self.assertTrue(os.path.exists(dst))
        self.assertFalse(os.path.exists(src))
