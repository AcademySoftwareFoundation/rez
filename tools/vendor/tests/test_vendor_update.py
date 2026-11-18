# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vendor_update


class TestVendorUpdateCLI(unittest.TestCase):
    def test_parse_args_defaults(self):
        args = vendor_update.parse_args([])
        self.assertEqual(args.packages, [])
        self.assertFalse(args.verify)

    def test_parse_args_packages_and_verify(self):
        args = vendor_update.parse_args(["--verify", "six", "schema"])
        self.assertEqual(args.packages, ["six", "schema"])
        self.assertTrue(args.verify)

    def test_requires_python_38_compatible(self):
        self.assertTrue(vendor_update.is_python_compatible(">=3.8", (3, 8)))
        self.assertTrue(vendor_update.is_python_compatible(">=3.7,<4", (3, 8)))
        self.assertTrue(vendor_update.is_python_compatible(None, (3, 8)))
        self.assertTrue(vendor_update.is_python_compatible("", (3, 8)))
        self.assertFalse(vendor_update.is_python_compatible(">=3.9", (3, 8)))
        self.assertFalse(vendor_update.is_python_compatible(">=3.10", (3, 8)))
        self.assertFalse(vendor_update.is_python_compatible("~=3.9", (3, 8)))
        self.assertTrue(vendor_update.is_python_compatible(">=2.7, !=3.0.*, !=3.1.*", (3, 8)))


def _make_tar_gz(entries):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in entries.items():
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


class TestSourceFetcherAndExtractor(unittest.TestCase):
    def test_verify_sha256_mismatch_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "pkg.tar.gz")
            with open(p, "wb") as f:
                f.write(b"hello")
            good = hashlib.sha256(b"hello").hexdigest()
            vendor_update.verify_sha256(p, good)
            with self.assertRaises(vendor_update.VendorError):
                vendor_update.verify_sha256(p, "0" * 64)

    def test_rejects_compiled_binary_unless_allowlisted(self):
        with tempfile.TemporaryDirectory() as td:
            arc_so = os.path.join(td, "bad.tar.gz")
            with open(arc_so, "wb") as f:
                f.write(_make_tar_gz({"pkg-1.0/pkg/__init__.py": b"", "pkg-1.0/pkg/ext.so": b"ELF"}))
            with self.assertRaises(vendor_update.VendorError):
                vendor_update.extract_source_archive(arc_so, os.path.join(td, "out1"), strip_prefix="pkg-1.0/pkg/")

            arc_exe = os.path.join(td, "distlib.tar.gz")
            with open(arc_exe, "wb") as f:
                f.write(
                    _make_tar_gz({"distlib-0.3.9/distlib/__init__.py": b"", "distlib-0.3.9/distlib/t64.exe": b"MZ"})
                )
            with self.assertRaises(vendor_update.VendorError):
                vendor_update.extract_source_archive(
                    arc_exe, os.path.join(td, "out2"), strip_prefix="distlib-0.3.9/distlib/"
                )
            out3 = os.path.join(td, "out3")
            vendor_update.extract_source_archive(
                arc_exe, out3, strip_prefix="distlib-0.3.9/distlib/", allow_binaries=["*.exe"]
            )
            self.assertTrue(os.path.exists(os.path.join(out3, "t64.exe")))

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            arc = os.path.join(td, "trav.tar.gz")
            with open(arc, "wb") as f:
                f.write(_make_tar_gz({"pkg-1.0/pkg/../../evil.py": b"x"}))
            with self.assertRaises(vendor_update.VendorError):
                vendor_update.extract_source_archive(arc, os.path.join(td, "out"), strip_prefix="pkg-1.0/pkg/")

    def test_extra_files_and_drop_globs(self):
        with tempfile.TemporaryDirectory() as td:
            arc = os.path.join(td, "pkg.tar.gz")
            with open(arc, "wb") as f:
                f.write(
                    _make_tar_gz(
                        {
                            "pkg-1.0/LICENSE": b"MIT",
                            "pkg-1.0/src/pkg/__init__.py": b"x = 1\n",
                            "pkg-1.0/src/pkg/tests/test_a.py": b"pass\n",
                        }
                    )
                )
            out = os.path.join(td, "out")
            vendor_update.extract_source_archive(
                arc,
                out,
                strip_prefix="pkg-1.0/src/pkg/",
                extra_files={"LICENSE": "pkg-1.0/LICENSE"},
                drop_globs=["tests/*"],
            )
            self.assertTrue(os.path.exists(os.path.join(out, "__init__.py")))
            self.assertTrue(os.path.exists(os.path.join(out, "LICENSE")))
            self.assertFalse(os.path.exists(os.path.join(out, "tests", "test_a.py")))

    def test_resolve_pypi_artifact_gates(self):
        meta_py39 = json.dumps(
            {
                "info": {"requires_python": ">=3.9"},
                "urls": [
                    {
                        "packagetype": "sdist",
                        "filename": "a-1.0.tar.gz",
                        "url": "https://x/a.tar.gz",
                        "digests": {"sha256": "abc"},
                    }
                ],
            }
        ).encode()
        with mock.patch.object(vendor_update, "fetch_bytes", return_value=meta_py39):
            with self.assertRaises(vendor_update.VendorError):
                vendor_update.resolve_pypi_artifact("a", "1.0", min_python=(3, 8))

        meta_bin_whl = json.dumps(
            {
                "info": {"requires_python": ">=3.8"},
                "urls": [
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "a-1.0-cp313-cp313-linux_x86_64.whl",
                        "url": "https://x/a.whl",
                        "digests": {"sha256": "abc"},
                    }
                ],
            }
        ).encode()
        with mock.patch.object(vendor_update, "fetch_bytes", return_value=meta_bin_whl):
            with self.assertRaises(vendor_update.VendorError):
                vendor_update.resolve_pypi_artifact("a", "1.0", min_python=(3, 8))

        meta_pure_whl = json.dumps(
            {
                "info": {"requires_python": ">=3.8"},
                "urls": [
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "a-1.0-py3-none-any.whl",
                        "url": "https://x/a.whl",
                        "digests": {"sha256": "def"},
                    }
                ],
            }
        ).encode()
        with mock.patch.object(vendor_update, "fetch_bytes", return_value=meta_pure_whl):
            url, sha = vendor_update.resolve_pypi_artifact("a", "1.0", min_python=(3, 8))
            self.assertEqual(url, "https://x/a.whl")
            self.assertEqual(sha, "def")


class TestImportRewriterAndLayout(unittest.TestCase):
    def test_rewrite_self_and_dotted_imports_with_attr_chains(self):
        src = (
            '"""Docstring mentioning import pika.spec."""\n'
            "import pika.exceptions\n"
            "import pika.spec\n"
            "from pika.adapters import base_connection\n"
            "import logging\n\n"
            "def f(x):\n"
            "    # comment: pika.exceptions\n"
            "    if isinstance(x, pika.spec.Basic.Return):\n"
            "        raise pika.exceptions.AMQPConnectionError()\n"
        )
        out = vendor_update.rewrite_python_imports(src, {"pika": "rez.vendor.pika"})
        self.assertIn('"""Docstring mentioning import pika.spec."""', out)
        self.assertIn("# comment: pika.exceptions", out)
        self.assertIn("import rez.vendor.pika.exceptions", out)
        self.assertIn("import rez.vendor.pika.spec", out)
        self.assertIn("from rez.vendor.pika.adapters import base_connection", out)
        self.assertIn("isinstance(x, rez.vendor.pika.spec.Basic.Return)", out)
        self.assertIn("raise rez.vendor.pika.exceptions.AMQPConnectionError()", out)
        self.assertIn("import logging", out)

    def test_rewrite_wrapped_single_module_and_bare_import(self):
        src = (
            "import six\n"
            "import zipp\n"
            "from six.moves.urllib import parse as urlparse\n"
            "from typing_extensions import Protocol\n"
        )
        rules = {
            "six": "rez.vendor.six.six",
            "zipp": "rez.vendor.zipp",
            "typing_extensions": "rez.vendor.typing_extensions.typing_extensions",
        }
        out = vendor_update.rewrite_python_imports(src, rules)
        self.assertIn("from rez.vendor.six import six", out)
        self.assertIn("from rez.vendor import zipp", out)
        self.assertIn("from rez.vendor.six.six.moves.urllib import parse as urlparse", out)
        self.assertIn("from rez.vendor.typing_extensions.typing_extensions import Protocol", out)

    def test_apply_layout_wrap_single_module(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "schema.py"), "w", encoding="utf-8") as f:
                f.write("class Schema: pass\n")
            vendor_update.apply_layout(td, {"wrap_single_module": True})
            self.assertTrue(os.path.exists(os.path.join(td, "__init__.py")))
            self.assertEqual(os.path.getsize(os.path.join(td, "__init__.py")), 0)
            self.assertTrue(os.path.exists(os.path.join(td, "schema.py")))


if __name__ == "__main__":
    unittest.main()
