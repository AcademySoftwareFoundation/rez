# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test rez.package_help
"""
import contextlib
import io
import os
from unittest.mock import MagicMock, patch

from rez.config import config
from rez.package_help import PackageHelp
from rez.tests.util import TempdirMixin, TestBase
from rez.version import VersionRange


class TestPackageHelp(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()
        cls.settings = {}

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _write_package(
        self,
        name: str,
        version: str,
        help_entry=None,
        variants=None,
    ) -> str:
        pkg_dir = os.path.join(self.root, name, version)
        os.makedirs(pkg_dir, exist_ok=True)
        lines = [
            "name = %r" % name,
            "version = %r" % version,
        ]
        if help_entry is not None:
            lines.append("help = %r" % (help_entry,))
        if variants is not None:
            lines.append("variants = %r" % (variants,))
            for variant in variants:
                vdir = os.path.join(pkg_dir, *variant)
                os.makedirs(vdir, exist_ok=True)
        with open(os.path.join(pkg_dir, "package.py"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return pkg_dir

    def test_no_package_found(self) -> None:
        """PackageHelp reports failure when no matching package exists."""
        self.update_settings({"packages_path": [self.root]})
        pkg_help = PackageHelp("nonexistent")
        self.assertIsNone(pkg_help.package)
        self.assertFalse(pkg_help.success)
        self.assertEqual(pkg_help.sections, [])

    def test_package_without_help_verbose(self) -> None:
        """PackageHelp skips packages without help and logs when verbose."""
        self._write_package("nohelp", "1.0.0")
        self.update_settings({"packages_path": [self.root]})

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pkg_help = PackageHelp("nohelp", verbose=True)

        self.assertIsNone(pkg_help.package)
        self.assertFalse(pkg_help.success)
        self.assertEqual(pkg_help.sections, [])
        self.assertIn("searching for help in", buf.getvalue())

    def test_selects_latest_package_with_help_and_version_range(self) -> None:
        """PackageHelp picks the latest version in range that defines help."""
        self._write_package("multi", "1.0.0", help_entry="https://example.com/1.0")
        self._write_package("multi", "1.5.0", help_entry="https://example.com/1.5")
        self._write_package("multi", "2.0.0")  # no help
        self._write_package("multi", "3.0.0", help_entry="https://example.com/3.0")
        self.update_settings({"packages_path": [self.root]})

        # Without range: 3.0.0 is latest with help
        pkg_help = PackageHelp("multi")
        self.assertTrue(pkg_help.success)
        self.assertEqual(str(pkg_help.package.version), "3.0.0")
        self.assertEqual(pkg_help.sections, [["Help", "https://example.com/3.0"]])

        # With range <3.0: 2.0.0 has no help so 1.5.0 is chosen
        pkg_help_ranged = PackageHelp("multi", version_range=VersionRange("<3.0"))
        self.assertTrue(pkg_help_ranged.success)
        self.assertEqual(str(pkg_help_ranged.package.version), "1.5.0")
        self.assertEqual(pkg_help_ranged.sections, [["Help", "https://example.com/1.5"]])

    def test_help_string_and_list_formatting(self) -> None:
        """Help entries expand old tokens, strip $BROWSER, and format scope vars."""
        self._write_package(
            "strpkg",
            "1.2.3",
            help_entry="$BROWSER https://example.com/{version}/!ROOT!",
        )
        self._write_package(
            "listpkg",
            "2.0.0",
            help_entry=[
                ["Manual", "{base}/manual.html"],
                ["API", "$BROWSER {root}/api.html"],
            ],
        )
        self.update_settings({"packages_path": [self.root]})

        str_help = PackageHelp("strpkg")
        self.assertTrue(str_help.success)
        self.assertEqual(
            str_help.sections,
            [["Help", "https://example.com/1.2.3/%s" % str_help.package.base]],
        )

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            list_help = PackageHelp("listpkg", verbose=True)

        self.assertTrue(list_help.success)
        self.assertEqual(
            list_help.sections,
            [
                ["Manual", "%s/manual.html" % list_help.package.base],
                ["API", "%s/api.html" % list_help.package.base],
            ],
        )
        self.assertIn("found 2 help entries in", buf.getvalue())

    def test_package_with_variants_uses_variant_base_and_root(self) -> None:
        """Packages with variants resolve {base} and {root} from variant 0."""
        self._write_package(
            "varpkg",
            "1.0.0",
            help_entry=[["Docs", "{base}|{root}"]],
            variants=[["linux"]],
        )
        self.update_settings({"packages_path": [self.root]})

        pkg_help = PackageHelp("varpkg")
        self.assertTrue(pkg_help.success)
        variant = pkg_help.package.get_variant(0)
        self.assertEqual(
            pkg_help.sections,
            [["Docs", "%s|%s" % (variant.base, variant.root)]],
        )

    def test_print_info_to_buffer_and_stdout(self) -> None:
        """print_info writes formatted sections to a buffer or sys.stdout."""
        self._write_package(
            "infopkg",
            "1.0.0",
            help_entry=[
                ["Home", "https://example.com"],
                ["Guide", "https://example.com/guide"],
            ],
        )
        self.update_settings({"packages_path": [self.root]})
        pkg_help = PackageHelp("infopkg")

        buf = io.StringIO()
        pkg_help.print_info(buf=buf)
        expected = (
            "Sections:\n"
            "  1:\tHome (https://example.com)\n"
            "  2:\tGuide (https://example.com/guide)\n"
        )
        self.assertEqual(buf.getvalue(), expected)

        stdout_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf):
            pkg_help.print_info()
        self.assertEqual(stdout_buf.getvalue(), expected)

    def test_open_url_with_default_webbrowser(self) -> None:
        """open() launches a single-token URL via webbrowser when browser is unset."""
        self._write_package("web", "1.0.0", help_entry="https://example.com/docs")
        self.update_settings({"packages_path": [self.root], "browser": "", "quiet": False})
        pkg_help = PackageHelp("web")

        buf = io.StringIO()
        with patch("rez.package_help.webbrowser.open_new") as mock_open, \
             contextlib.redirect_stdout(buf):
            pkg_help.open()

        mock_open.assert_called_once_with("https://example.com/docs")
        self.assertIn("opening URL in browser: https://example.com/docs", buf.getvalue())

    def test_open_url_with_configured_browser(self) -> None:
        """open() invokes configured browser via Popen when config.browser is set."""
        self._write_package(
            "browserpkg",
            "1.0.0",
            help_entry=[
                ["First", "https://example.com/1"],
                ["Second", "https://example.com/2"],
            ],
        )
        self.update_settings({
            "packages_path": [self.root],
            "browser": "custom-browser",
            "quiet": False,
        })
        pkg_help = PackageHelp("browserpkg")

        mock_proc = MagicMock()
        buf = io.StringIO()
        with patch("rez.package_help.Popen", return_value=mock_proc) as mock_popen, \
             contextlib.redirect_stdout(buf):
            pkg_help.open(section_index=1)

        mock_popen.assert_called_once_with(["custom-browser", "https://example.com/2"])
        mock_proc.communicate.assert_called_once_with()
        self.assertIn(
            "running command: custom-browser https://example.com/2",
            buf.getvalue(),
        )

        # With quiet=True, nothing is printed
        self.update_settings({
            "packages_path": [self.root],
            "browser": "custom-browser",
            "quiet": True,
        })
        mock_proc_quiet = MagicMock()
        quiet_buf = io.StringIO()
        with patch("rez.package_help.Popen", return_value=mock_proc_quiet), \
             contextlib.redirect_stdout(quiet_buf):
            pkg_help.open(section_index=0)
        self.assertEqual(quiet_buf.getvalue(), "")

    def test_open_command_runs_popen_shell(self) -> None:
        """open() executes multi-word help entries via Popen(shell=True)."""
        self._write_package("cmdpkg", "1.0.0", help_entry="viewer /tmp/docs.pdf")
        self.update_settings({"packages_path": [self.root]})
        pkg_help = PackageHelp("cmdpkg", verbose=True)

        mock_proc = MagicMock()
        mock_proc.__enter__.return_value = mock_proc
        buf = io.StringIO()
        with patch("rez.package_help.Popen", return_value=mock_proc) as mock_popen, \
             contextlib.redirect_stdout(buf):
            pkg_help.open()

        mock_popen.assert_called_once_with("viewer /tmp/docs.pdf", shell=True)
        mock_proc.wait.assert_called_once_with()
        self.assertIn("running command: viewer /tmp/docs.pdf", buf.getvalue())

        # With verbose=False, nothing is printed
        pkg_help_quiet = PackageHelp("cmdpkg", verbose=False)
        mock_proc_quiet = MagicMock()
        mock_proc_quiet.__enter__.return_value = mock_proc_quiet
        quiet_buf = io.StringIO()
        with patch("rez.package_help.Popen", return_value=mock_proc_quiet) as mock_popen, \
             contextlib.redirect_stdout(quiet_buf):
            pkg_help_quiet.open()
        mock_popen.assert_called_once_with("viewer /tmp/docs.pdf", shell=True)
        self.assertEqual(quiet_buf.getvalue(), "")

    def test_open_rez_manual(self) -> None:
        """open_rez_manual() opens config.documentation_url."""
        self.update_settings({"browser": "", "quiet": True})
        with patch("rez.package_help.webbrowser.open_new") as mock_open:
            PackageHelp.open_rez_manual()

        mock_open.assert_called_once_with(config.documentation_url)
