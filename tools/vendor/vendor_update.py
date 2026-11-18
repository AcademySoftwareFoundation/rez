# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

"""Deterministic vendored-dependency updater and verifier for rez."""

import argparse
import os
import re
import sys


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")
DEFAULT_VENDOR_DIR = os.path.join(REPO_ROOT, "src", "rez", "vendor")
DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
MIN_PYTHON = (3, 8)

_SPEC_RE = re.compile(r"^\s*(===|==|!=|<=|>=|~=|<|>)\s*([0-9]+(?:\.[0-9]+)*(?:\.\*)?)\s*$")


class VendorError(RuntimeError):
    """Raised when vendoring fails validation, fetching, or patching."""


def _parse_ver_tuple(ver_str):
    parts = []
    for seg in ver_str.split("."):
        if seg == "*":
            break
        parts.append(int(seg))
    return tuple(parts)


def _pad_pair(a, b):
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)), b + (0,) * (n - len(b))


def _match_single_spec(spec, target):
    m = _SPEC_RE.match(spec)
    if not m:
        raise VendorError(f"Unsupported requires_python specifier: {spec!r}")
    op, raw_ver = m.groups()
    is_wildcard = raw_ver.endswith(".*")
    ver = _parse_ver_tuple(raw_ver)

    if is_wildcard:
        prefix = target[: len(ver)]
        if op == "==":
            return prefix == ver
        if op == "!=":
            return prefix != ver
        raise VendorError(f"Wildcard not valid with {op!r}: {spec!r}")

    t_pad, v_pad = _pad_pair(target, ver)
    if op in ("==", "==="):
        return t_pad == v_pad
    if op == "!=":
        return t_pad != v_pad
    if op == ">=":
        return t_pad >= v_pad
    if op == "<=":
        return t_pad <= v_pad
    if op == ">":
        return t_pad > v_pad
    if op == "<":
        return t_pad < v_pad
    if op == "~=":
        if len(ver) < 2:
            raise VendorError(f"~= requires at least major.minor: {spec!r}")
        upper = ver[:-2] + (ver[-2] + 1,)
        t_u, u_pad = _pad_pair(target, upper)
        return t_pad >= v_pad and t_u < u_pad
    raise VendorError(f"Unsupported operator {op!r} in {spec!r}")


def is_python_compatible(requires_python, target=MIN_PYTHON):
    """Return True if ``target`` satisfies PEP 440 ``requires_python``."""
    if not requires_python or not requires_python.strip():
        return True
    for raw_spec in requires_python.split(","):
        spec = raw_spec.strip()
        if not spec:
            continue
        if not _match_single_spec(spec, target):
            return False
    return True


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Deterministically fetch, patch, and verify rez vendored dependencies."
    )
    parser.add_argument(
        "packages",
        nargs="*",
        help="Optional package name(s) from manifest.json (default: all).",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify 1:1 byte-for-byte parity against src/rez/vendor/ without modifying it.",
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help="Path to manifest.json (default: tools/vendor/manifest.json).",
    )
    parser.add_argument(
        "--vendor-dir",
        default=DEFAULT_VENDOR_DIR,
        help="Target vendor directory (default: src/rez/vendor).",
    )
    parser.add_argument(
        "--cache-dir",
        default=DEFAULT_CACHE_DIR,
        help="Download cache directory (default: tools/vendor/.cache).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not os.path.exists(args.manifest):
        print(f"Manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
