# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test running of all commandline tools (just -h on each)
"""
from rez.tests.util import TestBase
import os
import os.path
import subprocess
import sys
import unittest
from tempfile import TemporaryFile

from rez.system import system
from rez.cli._entry_points import get_specifications
from rez.cli._main import setup_parser
from rez.vendor.argcomplete import autocomplete


class TestImports(TestBase):
    def test_1(self) -> None:
        """run -h option on every cli tool"""

        # skip if cli not available
        if not system.rez_bin_path:
            self.skipTest("Not a production install")

        for toolname in get_specifications().keys():
            if toolname.startswith('_'):
                continue

            binfile = os.path.join(system.rez_bin_path, toolname)
            subprocess.check_output([binfile, "-h"])


class TestComplete(TestBase):
    """Test argcomplete-driven completion against the actual rez parser.

    Uses the in-process pattern from argcomplete's own test suite
    (https://github.com/kislyuk/argcomplete/blob/main/test/test.py): set
    COMP_LINE/COMP_POINT/_ARGCOMPLETE in the env, call ``autocomplete()``
    with an output_stream and exit_method, then split the captured output
    by IFS.
    """

    IFS = "\013"

    def setUp(self) -> None:
        super().setUp()
        self._saved_environ = os.environ.copy()
        os.environ["_ARGCOMPLETE"] = "1"
        os.environ["IFS"] = self.IFS
        os.environ["_ARGCOMPLETE_SHELL"] = "bash"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._saved_environ)
        super().tearDown()

    # Inspired by https://github.com/kislyuk/argcomplete/blob/8e5ad6a5a702e5529f61ae9a63f720beda68ffaf/test/test.py#L118-L143  # noqa
    def _run_completer(self, command, point=None):
        if point is None:
            point = len(command)
        os.environ["COMP_LINE"] = command
        os.environ["COMP_POINT"] = str(point)

        parser = setup_parser()
        with TemporaryFile(mode="w+") as t:
            with self.assertRaises(SystemExit) as cm:
                autocomplete(parser, output_stream=t, exit_method=sys.exit)
            self.assertEqual(cm.exception.code, 0)
            t.seek(0)
            return set(t.read().split(self.IFS))

    def test_subcommand_completion(self) -> None:
        """`rez <TAB>` should list subcommands."""
        completions = self._run_completer("rez ")
        self.assertIn("env", completions)
        self.assertIn("build", completions)

    def test_subcommand_prefix(self) -> None:
        """`rez bui<TAB>` should narrow to `build`."""
        completions = self._run_completer("rez bui")
        self.assertEqual(completions, {"build "})

    def test_subcommand_options(self) -> None:
        """`rez env --<TAB>` should list options for the env subcommand."""
        completions = self._run_completer("rez env --")
        # --help is on every parser, --input/--output are env-specific
        self.assertIn("--help", completions)
        self.assertIn("--input", completions)
        self.assertIn("--output", completions)


if __name__ == '__main__':
    unittest.main()
