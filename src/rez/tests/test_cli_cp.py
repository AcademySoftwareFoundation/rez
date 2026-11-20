# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Test the `rez cp` CLI command (`rez.cli.cp`).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
from unittest.mock import MagicMock, patch

from rez.cli._complete_util import PackageCompleter
from rez.cli._main import _add_common_args
from rez.cli.cp import command, setup_parser
from rez.tests.util import TestBase
from rez.version import Version


def _make_mock_pkg(name="foo", version="1.0.0", num_variants=0, uri=None):
    pkg = MagicMock()
    pkg.name = name
    pkg.version = Version(version)
    pkg.qualified_name = "%s-%s" % (name, version)
    pkg.num_variants = num_variants
    pkg.uri = uri or ("/src_repo/%s/%s/package.py" % (name, version))
    pkg.repository = MagicMock()
    return pkg


def _make_mock_variant(index=0, parent=None, uri=None):
    variant = MagicMock()
    variant.index = index
    variant.parent = parent or _make_mock_pkg()
    variant.uri = uri or ("%s[%d]" % (variant.parent.uri, index))
    return variant


class TestCliCp(TestBase):
    def _parse(self, args, completions=False):
        parser = argparse.ArgumentParser(prog="rez cp")
        setup_parser(parser, completions=completions)
        _add_common_args(parser)
        opts = parser.parse_args(args)
        return opts, parser

    def _run(self, args):
        opts, parser = self._parse(args)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with contextlib.redirect_stderr(stderr):
                command(opts, parser)
        return stdout.getvalue(), stderr.getvalue()

    def test_setup_parser_completions(self) -> None:
        parser_no_comp = argparse.ArgumentParser(prog="rez cp")
        setup_parser(parser_no_comp, completions=False)
        pkg_action_no_comp = next(
            a for a in parser_no_comp._actions if a.dest == "PKG"
        )
        self.assertFalse(hasattr(pkg_action_no_comp, "completer"))

        parser_comp = argparse.ArgumentParser(prog="rez cp")
        setup_parser(parser_comp, completions=True)
        pkg_action_comp = next(
            a for a in parser_comp._actions if a.dest == "PKG"
        )
        self.assertIs(pkg_action_comp.completer, PackageCompleter)

    def test_error_both_pkg_and_variant_uri(self) -> None:
        opts, parser = self._parse(
            ["--dest-path", "/dest", "--variant-uri", "uri://v", "foo"]
        )
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("Supply PKG or --variant-uri, not both.", stderr.getvalue())

    def test_error_neither_pkg_nor_variant_uri(self) -> None:
        opts, parser = self._parse(["--dest-path", "/dest"])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("Expected PKG.", stderr.getvalue())

    def test_error_missing_dest_path_without_rename_or_reversion(self) -> None:
        opts, parser = self._parse(["foo"])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)
        self.assertIn(
            "--dest-path must be specified unless --rename or --reversion are used.",
            stderr.getvalue(),
        )

    def test_variant_uri_unknown(self) -> None:
        with patch("rez.packages.get_variant_from_uri", return_value=None) as mock_get:
            opts, parser = self._parse(
                ["--dest-path", "/dest", "--variant-uri", "missing://0"]
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        mock_get.assert_called_once_with("missing://0")
        self.assertIn("Unknown variant: missing://0", stderr.getvalue())

    def test_variant_uri_success(self) -> None:
        src_pkg = _make_mock_pkg(num_variants=3)
        src_variant = _make_mock_variant(index=2, parent=src_pkg)
        dest_pkg = _make_mock_pkg(uri="/dest/foo/1.0.0/package.py")
        dest_variant = _make_mock_variant(index=0, parent=dest_pkg)

        dest_repo = MagicMock()
        dest_repo.is_empty.return_value = False

        with patch("rez.packages.get_variant_from_uri", return_value=src_variant):
            with patch(
                "rez.package_repository.package_repository_manager.get_repository",
                return_value=dest_repo,
            ):
                with patch(
                    "rez.package_copy.copy_package",
                    return_value={"copied": [(src_variant, dest_variant)], "skipped": []},
                ) as mock_copy:
                    stdout, stderr = self._run(
                        ["--dest-path", "/dest", "--variant-uri", "foo/1.0.0/2"]
                    )

        self.assertEqual(stderr, "")
        mock_copy.assert_called_once()
        self.assertEqual(mock_copy.call_args.kwargs["package"], src_pkg)
        self.assertEqual(mock_copy.call_args.kwargs["variants"], [2])
        self.assertIn("1 variants were copied:", stdout)

    def test_pkg_paths_and_no_local_selection(self) -> None:
        self.update_settings({
            "packages_path": ["/local/repo", "/nonlocal/repo"],
            "local_packages_path": "/local/repo",
        })
        src_pkg = _make_mock_pkg(num_variants=0)
        dest_pkg = _make_mock_pkg(uri="/dest/foo/1.0.0/package.py")
        src_v = _make_mock_variant(parent=src_pkg)
        dest_v = _make_mock_variant(parent=dest_pkg)

        dest_repo = MagicMock()
        dest_repo.is_empty.return_value = False

        cases = [
            (["--dest-path", "/dest", "--paths", os.pathsep.join(["/a", "", "/b"]), "foo"], ["/a", "/b"]),
            (["--dest-path", "/dest", "--no-local", "foo"], ["/nonlocal/repo"]),
            (["--dest-path", "/dest", "foo"], None),
        ]

        for args, expected_paths in cases:
            with self.subTest(args=args):
                with patch(
                    "rez.packages.iter_packages",
                    side_effect=lambda **kwargs: iter([src_pkg]),
                ) as mock_iter:
                    with patch(
                        "rez.package_repository.package_repository_manager.get_repository",
                        return_value=dest_repo,
                    ):
                        with patch(
                            "rez.package_copy.copy_package",
                            return_value={"copied": [(src_v, dest_v)], "skipped": []},
                        ):
                            self._run(args)
                self.assertEqual(mock_iter.call_args.kwargs["paths"], expected_paths)

    def test_pkg_not_found(self) -> None:
        with patch("rez.packages.iter_packages", return_value=iter([])):
            opts, parser = self._parse(["--dest-path", "/dest", "missing_pkg==1.0"])
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("No matching packages found.", stderr.getvalue())

    def test_pkg_multiple_matches(self) -> None:
        pkg2 = _make_mock_pkg(name="foo", version="2.0.0")
        pkg1 = _make_mock_pkg(name="foo", version="1.0.0")

        with patch("rez.packages.iter_packages", return_value=iter([pkg2, pkg1])):
            opts, parser = self._parse(["--dest-path", "/dest", "foo"])
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        err_text = stderr.getvalue()
        self.assertIn("More than one package matches, please choose:", err_text)
        self.assertLess(err_text.index("foo-1.0.0"), err_text.index("foo-2.0.0"))

    def test_dest_path_empty_repo_rejected_and_allowed(self) -> None:
        src_pkg = _make_mock_pkg(num_variants=0)
        dest_pkg = _make_mock_pkg(uri="/dest/foo/1.0.0/package.py")
        src_v = _make_mock_variant(parent=src_pkg)
        dest_v = _make_mock_variant(parent=dest_pkg)

        empty_repo = MagicMock()
        empty_repo.is_empty.return_value = True

        with patch("rez.packages.iter_packages", return_value=iter([src_pkg])):
            with patch(
                "rez.package_repository.package_repository_manager.get_repository",
                return_value=empty_repo,
            ):
                opts, parser = self._parse(["--dest-path", "/empty_dest", "foo"])
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    with self.assertRaises(SystemExit) as cm:
                        command(opts, parser)
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("EMPTY repository", stderr.getvalue())

        with patch("rez.packages.iter_packages", return_value=iter([src_pkg])):
            with patch(
                "rez.package_repository.package_repository_manager.get_repository",
                return_value=empty_repo,
            ):
                with patch(
                    "rez.package_copy.copy_package",
                    return_value={"copied": [(src_v, dest_v)], "skipped": []},
                ) as mock_copy:
                    stdout, _ = self._run(
                        ["--dest-path", "/empty_dest", "--allow-empty", "foo"]
                    )
        mock_copy.assert_called_once()
        self.assertIn("Copied", stdout)

    def test_same_repo_with_rename_or_reversion(self) -> None:
        src_pkg = _make_mock_pkg(num_variants=0)
        dest_pkg = _make_mock_pkg(name="bar", version="1.0.0", uri="/src_repo/bar/1.0.0/package.py")
        src_v = _make_mock_variant(parent=src_pkg)
        dest_v = _make_mock_variant(parent=dest_pkg)

        with patch("rez.packages.iter_packages", return_value=iter([src_pkg])):
            with patch(
                "rez.package_copy.copy_package",
                return_value={"copied": [(src_v, dest_v)], "skipped": []},
            ) as mock_copy:
                self._run(["--rename", "bar", "foo"])

        self.assertIs(mock_copy.call_args.kwargs["dest_repository"], src_pkg.repository)
        self.assertEqual(mock_copy.call_args.kwargs["dest_name"], "bar")
        self.assertIsNone(mock_copy.call_args.kwargs["dest_version"])

    def test_all_copy_options_forwarded(self) -> None:
        src_pkg = _make_mock_pkg(num_variants=0)
        dest_pkg = _make_mock_pkg(name="bar", version="2.0.0", uri="/dest/bar/2.0.0/package.py")
        src_v = _make_mock_variant(parent=src_pkg)
        dest_v = _make_mock_variant(parent=dest_pkg)

        dest_repo = MagicMock()
        dest_repo.is_empty.return_value = False

        with patch("rez.packages.iter_packages", return_value=iter([src_pkg])):
            with patch(
                "rez.package_repository.package_repository_manager.get_repository",
                return_value=dest_repo,
            ):
                with patch(
                    "rez.package_copy.copy_package",
                    return_value={"copied": [(src_v, dest_v)], "skipped": []},
                ) as mock_copy:
                    self._run([
                        "--dest-path", "/dest",
                        "--rename", "bar",
                        "--reversion", "2.0.0",
                        "-o", "-s", "--follow-symlinks", "-k", "-f",
                        "--variants", "0", "2",
                        "-vv",
                        "foo",
                    ])

        self.assertEqual(
            mock_copy.call_args.kwargs,
            {
                "package": src_pkg,
                "dest_repository": dest_repo,
                "dest_name": "bar",
                "dest_version": "2.0.0",
                "variants": [0, 2],
                "overwrite": True,
                "shallow": True,
                "follow_symlinks": True,
                "keep_timestamp": True,
                "force": True,
                "verbose": 2,
                "dry_run": False,
            },
        )

    def test_output_non_varianted_copied_and_skipped(self) -> None:
        src_pkg = _make_mock_pkg(num_variants=0)
        dest_pkg = _make_mock_pkg(uri="/dest/foo/1.0.0/package.py")
        src_v = _make_mock_variant(parent=src_pkg)
        dest_v = _make_mock_variant(parent=dest_pkg)

        dest_repo = MagicMock()
        dest_repo.is_empty.return_value = False

        with patch("rez.packages.iter_packages", side_effect=lambda **kwargs: iter([src_pkg])):
            with patch(
                "rez.package_repository.package_repository_manager.get_repository",
                return_value=dest_repo,
            ):
                with patch(
                    "rez.package_copy.copy_package",
                    return_value={"copied": [(src_v, dest_v)], "skipped": []},
                ):
                    stdout, _ = self._run(["--dest-path", "/dest", "foo"])
                self.assertIn("Copied %s to %s" % (src_pkg.uri, dest_pkg.uri), stdout)

                with patch(
                    "rez.package_copy.copy_package",
                    return_value={"copied": [], "skipped": [(src_v, dest_v)]},
                ):
                    stdout, _ = self._run(["--dest-path", "/dest", "foo"])
                self.assertIn(
                    "Target package already exists: %s. Use 'overwrite' to replace it."
                    % dest_pkg.uri,
                    stdout,
                )

    def test_output_varianted_copied_and_skipped(self) -> None:
        src_pkg = _make_mock_pkg(num_variants=2)
        sv0 = _make_mock_variant(index=0, parent=src_pkg, uri="src/0")
        sv1 = _make_mock_variant(index=1, parent=src_pkg, uri="src/1")
        dv0 = _make_mock_variant(index=0, uri="dest/0")
        dv1 = _make_mock_variant(index=1, uri="dest/1")

        dest_repo = MagicMock()
        dest_repo.is_empty.return_value = False

        with patch("rez.packages.iter_packages", side_effect=lambda **kwargs: iter([src_pkg])):
            with patch(
                "rez.package_repository.package_repository_manager.get_repository",
                return_value=dest_repo,
            ):
                with patch(
                    "rez.package_copy.copy_package",
                    return_value={"copied": [(sv0, dv0)], "skipped": [(sv1, dv1)]},
                ):
                    stdout, _ = self._run(["--dest-path", "/dest", "foo"])

        self.assertIn("1 variants were copied:", stdout)
        self.assertIn("  src/0 -> dest/0", stdout)
        self.assertIn("1 variants were skipped (target exists):", stdout)
        self.assertIn("  src/1 !-> dest/1", stdout)

    def test_output_varianted_all_skipped(self) -> None:
        src_pkg = _make_mock_pkg(num_variants=1)
        sv0 = _make_mock_variant(index=0, parent=src_pkg, uri="src/0")
        dv0 = _make_mock_variant(index=0, uri="dest/0")

        dest_repo = MagicMock()
        dest_repo.is_empty.return_value = False

        with patch("rez.packages.iter_packages", return_value=iter([src_pkg])):
            with patch(
                "rez.package_repository.package_repository_manager.get_repository",
                return_value=dest_repo,
            ):
                with patch(
                    "rez.package_copy.copy_package",
                    return_value={"copied": [], "skipped": [(sv0, dv0)]},
                ):
                    stdout, _ = self._run(["--dest-path", "/dest", "foo"])

        self.assertNotIn("copied:", stdout)
        self.assertIn("1 variants were skipped (target exists):", stdout)
        self.assertIn("  src/0 !-> dest/0", stdout)

    def test_output_varianted_dry_run(self) -> None:
        src_pkg = _make_mock_pkg(num_variants=1)
        sv0 = _make_mock_variant(index=0, parent=src_pkg, uri="src/0")

        dest_repo = MagicMock()
        dest_repo.is_empty.return_value = False
        dest_repo.get_package_payload_path.return_value = "/dest/foo/1.0.0"

        with patch("rez.packages.iter_packages", return_value=iter([src_pkg])):
            with patch(
                "rez.package_repository.package_repository_manager.get_repository",
                return_value=dest_repo,
            ):
                with patch(
                    "rez.package_copy.copy_package",
                    return_value={"copied": [(sv0, None)], "skipped": []},
                ):
                    stdout, _ = self._run(["--dest-path", "/dest", "--dry-run", "foo"])

        dest_repo.get_package_payload_path.assert_called_once_with(
            package_name="foo",
            package_version=Version("1.0.0"),
        )
        self.assertIn("1 variants would be copied:", stdout)
        self.assertIn("  src/0 -> /dest/foo/1.0.0/?", stdout)
