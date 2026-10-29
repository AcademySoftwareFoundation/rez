# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test the rez.pip _cmd helper
"""
import unittest
from unittest import mock

from rez.exceptions import BuildError
from rez.pip import _cmd


class TestPipCmd(unittest.TestCase):
    def test_no_context_waits_and_succeeds(self) -> None:
        fake_popen = mock.MagicMock()
        fake_popen.returncode = 0
        fake_popen.__enter__.return_value = fake_popen
        fake_popen.__exit__.return_value = False

        with mock.patch("rez.pip.Popen", return_value=fake_popen) as popen_cls:
            _cmd(None, ["some", "command"])

        popen_cls.assert_called_once_with(["some", "command"])
        fake_popen.wait.assert_called_once()

    def test_no_context_raises_on_nonzero_returncode(self) -> None:
        fake_popen = mock.MagicMock()
        fake_popen.returncode = 1
        fake_popen.__enter__.return_value = fake_popen
        fake_popen.__exit__.return_value = False

        with mock.patch("rez.pip.Popen", return_value=fake_popen):
            self.assertRaises(BuildError, _cmd, None, ["some", "command"])

    def test_context_blocks_on_execute_shell(self) -> None:
        context = mock.MagicMock()
        context.execute_shell.return_value = (0, "stdout", "stderr")

        _cmd(context, ["some", "command"])

        context.execute_shell.assert_called_once_with(
            command=["some", "command"], block=True
        )

    def test_context_raises_on_nonzero_returncode(self) -> None:
        context = mock.MagicMock()
        context.execute_shell.return_value = (1, "stdout", "stderr")

        self.assertRaises(BuildError, _cmd, context, ["some", "command"])


if __name__ == '__main__':
    unittest.main()
