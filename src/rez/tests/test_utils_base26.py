# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test rez.utils.base26
"""
import errno
import os.path
from unittest.mock import patch

from rez.utils.base26 import create_unique_base26_symlink, get_next_base26
from rez.tests.util import TestBase


class TestGetNextBase26(TestBase):
    def test_no_prev_returns_a(self) -> None:
        self.assertEqual(get_next_base26(None), 'a')
        self.assertEqual(get_next_base26(''), 'a')

    def test_increments_last_letter(self) -> None:
        self.assertEqual(get_next_base26('a'), 'b')
        self.assertEqual(get_next_base26('y'), 'z')
        self.assertEqual(get_next_base26('ab'), 'ac')

    def test_rolls_over_to_new_letter(self) -> None:
        self.assertEqual(get_next_base26('z'), 'aa')
        self.assertEqual(get_next_base26('az'), 'ba')
        self.assertEqual(get_next_base26('zz'), 'aaa')

    def test_rolls_over_multiple_letters(self) -> None:
        self.assertEqual(get_next_base26('azz'), 'baa')

    def test_invalid_input_raises(self) -> None:
        for bad in ('A', 'a1', 'a-b', ' a', 'a '):
            with self.assertRaises(ValueError):
                get_next_base26(bad)


class TestCreateUniqueBase26Symlink(TestBase):
    """These mock the filesystem boundary (os.listdir/os.path.islink/os.symlink)
    rather than creating real symlinks, since symlink creation requires elevated
    privileges on some platforms (e.g. Windows without Developer Mode).
    """

    def test_returns_existing_symlink_if_already_pointing_at_source(self) -> None:
        with patch(
            "rez.utils.base26.find_matching_symlink", return_value="c"
        ), patch("os.symlink") as symlink:
            result = create_unique_base26_symlink("/pkgs", "/source/1.0")

        self.assertEqual(result, os.path.join("/pkgs", "c"))
        symlink.assert_not_called()

    def test_creates_first_symlink_when_none_exist(self) -> None:
        with patch(
            "rez.utils.base26.find_matching_symlink", return_value=None
        ), patch("os.listdir", return_value=[]), patch(
            "os.symlink"
        ) as symlink:
            result = create_unique_base26_symlink("/pkgs", "/source/1.0")

        symlink.assert_called_once_with("/source/1.0", result)
        self.assertTrue(result.endswith('a'))

    def test_creates_symlink_after_highest_existing(self) -> None:
        with patch(
            "rez.utils.base26.find_matching_symlink", return_value=None
        ), patch(
            "os.listdir", return_value=['a', 'b', 'c']
        ), patch(
            "os.path.islink", return_value=True
        ), patch("os.symlink") as symlink:
            result = create_unique_base26_symlink("/pkgs", "/source/2.0")

        symlink.assert_called_once_with("/source/2.0", result)
        self.assertTrue(result.endswith('d'))

    def test_retries_on_race_condition_then_succeeds(self) -> None:
        exists_error = OSError(errno.EEXIST, "File exists")

        with patch(
            "rez.utils.base26.find_matching_symlink", return_value=None
        ), patch("os.listdir", return_value=[]), patch(
            "os.symlink", side_effect=[exists_error, None]
        ) as symlink:
            result = create_unique_base26_symlink("/pkgs", "/source/1.0")

        self.assertEqual(symlink.call_count, 2)
        self.assertTrue(result.endswith('a'))

    def test_reraises_non_eexist_oserror(self) -> None:
        other_error = OSError(errno.EACCES, "Permission denied")

        with patch(
            "rez.utils.base26.find_matching_symlink", return_value=None
        ), patch("os.listdir", return_value=[]), patch(
            "os.symlink", side_effect=other_error
        ):
            with self.assertRaises(OSError):
                create_unique_base26_symlink("/pkgs", "/source/1.0")

    def test_gives_up_after_too_much_contention(self) -> None:
        exists_error = OSError(errno.EEXIST, "File exists")

        with patch(
            "rez.utils.base26.find_matching_symlink", return_value=None
        ), patch("os.listdir", return_value=[]), patch(
            "os.symlink", side_effect=exists_error
        ):
            with self.assertRaises(RuntimeError):
                create_unique_base26_symlink("/pkgs", "/source/1.0")
