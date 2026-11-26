# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

"""Deterministic vendored-dependency updater and verifier for rez."""

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")
DEFAULT_VENDOR_DIR = os.path.join(REPO_ROOT, "src", "rez", "vendor")
DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
MIN_PYTHON = (3, 8)
BANNED_BINARY_EXTS = {".so", ".pyd", ".dll", ".dylib", ".exe"}

_SPEC_RE = re.compile(r"^\s*(===|==|!=|<=|>=|~=|<|>)\s*([0-9]+(?:\.[0-9]+)*(?:\.\*)?)\s*$")
_ORIG_GETADDRINFO = socket.getaddrinfo


def _ipv4_getaddrinfo(*args, **kwargs):
    res = _ORIG_GETADDRINFO(*args, **kwargs)
    v4 = [r for r in res if r[0] == socket.AF_INET]
    return v4 if v4 else res


def fetch_bytes(url, timeout=30):
    """Fetch URL bytes, falling back to IPv4 if IPv6 stalls."""
    req = urllib.request.Request(url, headers={"User-Agent": "rez-vendor-update/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (TimeoutError, OSError):
        socket.getaddrinfo = _ipv4_getaddrinfo
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        finally:
            socket.getaddrinfo = _ORIG_GETADDRINFO


def fetch_cached(url, cache_dir, filename):
    """Return path to cached file for ``url``, downloading if absent."""
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, filename)
    if not os.path.exists(dest):
        data = fetch_bytes(url)
        with open(dest, "wb") as f:
            f.write(data)
    return dest


def verify_sha256(path, expected_sha256):
    """Verify file SHA256 matches ``expected_sha256``."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual.lower() != expected_sha256.lower():
        raise VendorError(f"SHA256 mismatch for {path}: expected {expected_sha256}, got {actual}")


def resolve_pypi_artifact(name, version, min_python=MIN_PYTHON, prefer="sdist"):
    """Resolve an sdist or pure-Python wheel from PyPI JSON metadata."""
    meta = json.loads(fetch_bytes(f"https://pypi.org/pypi/{name}/{version}/json"))
    req_py = meta.get("info", {}).get("requires_python")
    if not is_python_compatible(req_py, min_python):
        raise VendorError(
            f"{name}=={version} requires_python={req_py!r} is incompatible with {min_python[0]}.{min_python[1]}"
        )
    sdists = []
    pure_wheels = []
    for entry in meta.get("urls", []):
        pt = entry.get("packagetype")
        fn = entry.get("filename", "")
        if pt == "sdist":
            sdists.append((entry["url"], entry["digests"]["sha256"]))
        elif pt == "bdist_wheel" and fn.endswith("-none-any.whl"):
            pure_wheels.append((entry["url"], entry["digests"]["sha256"]))
    ordered = (sdists + pure_wheels) if prefer == "sdist" else (pure_wheels + sdists)
    if not ordered:
        raise VendorError(f"No sdist or pure-Python (*-none-any.whl) artifact found for {name}=={version}")
    return ordered[0]


def _is_safe_relpath(rel):
    if not rel or rel.startswith("/") or "\\" in rel:
        return False
    parts = rel.split("/")
    return all(p not in ("", ".", "..") for p in parts)


def _matches_any_glob(rel, globs):
    return any(fnmatch.fnmatch(rel, g) for g in (globs or ()))


def _iter_archive_entries(archive_path):
    if archive_path.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive_path, "r:gz") as tf:
            for m in tf.getmembers():
                if m.isfile():
                    yield m.name, tf.extractfile(m).read()
    elif archive_path.endswith((".zip", ".whl")):
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                if not info.is_dir():
                    yield info.filename, zf.read(info.filename)
    else:
        raise VendorError(f"Unsupported archive format: {archive_path}")


def extract_source_archive(
    archive_path,
    staging_dir,
    strip_prefix="",
    extra_files=None,
    drop_globs=(),
    allow_binaries=(),
):
    """Extract source-only/pure-Python files from archive into ``staging_dir``."""
    os.makedirs(staging_dir, exist_ok=True)
    extra_map = {v: k for k, v in (extra_files or {}).items()}
    entries = list(_iter_archive_entries(archive_path))

    for raw_name, data in entries:
        norm_name = raw_name.replace("\\", "/")
        if norm_name in extra_map:
            rel = extra_map[norm_name]
        elif strip_prefix:
            if not norm_name.startswith(strip_prefix):
                continue
            rel = norm_name[len(strip_prefix) :]
        else:
            rel = norm_name

        if not _is_safe_relpath(rel):
            raise VendorError(f"Unsafe archive member path: {raw_name!r}")
        if _matches_any_glob(rel, drop_globs):
            continue

        _, ext = os.path.splitext(rel)
        if ext.lower() in BANNED_BINARY_EXTS and not _matches_any_glob(rel, allow_binaries):
            raise VendorError(f"Disallowed binary artifact in {archive_path}: {rel}")

        dest = os.path.join(staging_dir, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)


def _line_byte_offsets(source_bytes):
    offsets = [0]
    for line in source_bytes.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def _node_byte_span(node, line_offsets):
    start = line_offsets[node.lineno - 1] + node.col_offset
    end = line_offsets[node.end_lineno - 1] + node.end_col_offset
    return start, end


def _match_rule(mod_name, rewrite_rules):
    if not mod_name:
        return None
    for src_pkg, dst_pkg in sorted(rewrite_rules.items(), key=lambda kv: len(kv[0]), reverse=True):
        if mod_name == src_pkg:
            return src_pkg, dst_pkg, ""
        if mod_name.startswith(src_pkg + "."):
            return src_pkg, dst_pkg, mod_name[len(src_pkg) :]
    return None


def rewrite_python_imports(source_text, rewrite_rules):
    """Dynamically rewrite imports (and dotted attribute chains) using ``ast``."""
    if not rewrite_rules:
        return source_text
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return source_text

    source_bytes = source_text.encode("utf-8")
    line_offsets = _line_byte_offsets(source_bytes)
    replacements = []
    dotted_imported_pkgs = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if len(node.names) != 1:
                # Handle multi-name imports only when all or individual parts match via text fallback
                continue
            alias = node.names[0]
            matched = _match_rule(alias.name, rewrite_rules)
            if not matched:
                continue
            src_pkg, dst_pkg, suffix = matched
            start, end = _node_byte_span(node, line_offsets)
            if not suffix:
                parent, _, leaf = dst_pkg.rpartition(".")
                as_part = f" as {alias.asname}" if alias.asname else ""
                new_stmt = f"from {parent} import {leaf}{as_part}" if parent else f"import {leaf}{as_part}"
            else:
                as_part = f" as {alias.asname}" if alias.asname else ""
                new_stmt = f"import {dst_pkg}{suffix}{as_part}"
                if not alias.asname:
                    dotted_imported_pkgs.add(src_pkg)
            replacements.append((start, end, new_stmt.encode("utf-8")))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            matched = _match_rule(node.module, rewrite_rules)
            if not matched:
                continue
            _, dst_pkg, suffix = matched
            start, end = _node_byte_span(node, line_offsets)
            stmt_bytes = source_bytes[start:end]
            old_mod_bytes = node.module.encode("utf-8")
            new_mod_bytes = f"{dst_pkg}{suffix}".encode("utf-8")
            idx = stmt_bytes.find(old_mod_bytes)
            if idx != -1:
                replacements.append((start + idx, start + idx + len(old_mod_bytes), new_mod_bytes))

    if dotted_imported_pkgs:
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                pkg = node.value.id
                if pkg in dotted_imported_pkgs and pkg in rewrite_rules:
                    s, e = _node_byte_span(node.value, line_offsets)
                    replacements.append((s, e, rewrite_rules[pkg].encode("utf-8")))

    if not replacements:
        return source_text

    # Sort descending and deduplicate overlapping spans
    replacements.sort(key=lambda r: (r[0], r[1]), reverse=True)
    buf = bytearray(source_bytes)
    last_start = len(buf) + 1
    for start, end, repl in replacements:
        if end <= last_start:
            buf[start:end] = repl
            last_start = start
    return buf.decode("utf-8")


def rewrite_directory_imports(staging_dir, rewrite_rules):
    """Apply ``rewrite_python_imports`` to all ``.py`` files in ``staging_dir``."""
    if not rewrite_rules:
        return
    for dp, _, fns in os.walk(staging_dir):
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(dp, fn)
            with open(fp, "r", encoding="utf-8", errors="surrogateescape") as f:
                orig = f.read()
            updated = rewrite_python_imports(orig, rewrite_rules)
            if updated != orig:
                with open(fp, "w", encoding="utf-8", errors="surrogateescape", newline="\n") as f:
                    f.write(updated)


def apply_layout(staging_dir, pkg_spec):
    """Apply ``file_map`` and ``wrap_single_module`` layout adjustments."""
    for src_rel, dst_rel in (pkg_spec.get("file_map") or {}).items():
        src = os.path.join(staging_dir, src_rel.replace("/", os.sep))
        dst = os.path.join(staging_dir, dst_rel.replace("/", os.sep))
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
    if pkg_spec.get("wrap_single_module"):
        init_path = os.path.join(staging_dir, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "wb") as f:
                f.write(b"")


def apply_overlays(staging_dir, overlay_dir):
    """Copy overlay files into ``staging_dir``, overwriting existing files."""
    if not overlay_dir or not os.path.isdir(overlay_dir):
        return
    for dp, _, fns in os.walk(overlay_dir):
        rel_dir = os.path.relpath(dp, overlay_dir)
        for fn in fns:
            src = os.path.join(dp, fn)
            dst_dir = staging_dir if rel_dir == "." else os.path.join(staging_dir, rel_dir)
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy2(src, os.path.join(dst_dir, fn))


def apply_patch(staging_dir, patch_path):
    """Apply a unified diff patch file inside ``staging_dir`` via ``git apply``."""
    if not patch_path or not os.path.isfile(patch_path):
        return
    res = subprocess.run(
        ["git", "apply", "--no-index", "--whitespace=nowarn", os.path.abspath(patch_path)],
        cwd=staging_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise VendorError(f"Patch failed ({patch_path}):\n{res.stderr or res.stdout}")


def replace_target_dir(staging_dir, target_dir):
    """Remove ``target_dir`` completely and replace it with ``staging_dir`` contents."""
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    shutil.copytree(staging_dir, target_dir)


def _snapshot_files(root_dir):
    out = {}
    if not os.path.isdir(root_dir):
        return out
    for dp, _, fns in os.walk(root_dir):
        if os.path.basename(dp) == "__pycache__":
            continue
        for fn in fns:
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, root_dir).replace(os.sep, "/")
            with open(fp, "rb") as f:
                out[rel] = f.read()
    return out


def compare_dirs(staging_dir, target_dir):
    """Return list of mismatch descriptions between ``staging_dir`` and ``target_dir``."""
    expected = _snapshot_files(staging_dir)
    actual = _snapshot_files(target_dir)
    diffs = []
    for k in sorted(set(expected) | set(actual)):
        if k not in actual:
            diffs.append(f"missing in target: {k}")
        elif k not in expected:
            diffs.append(f"extra in target: {k}")
        elif expected[k] != actual[k]:
            diffs.append(f"byte mismatch: {k} (staged={len(expected[k])}B, target={len(actual[k])}B)")
    return diffs


def process_package(name, spec, vendor_dir, cache_dir, tools_dir, verify=False):
    """Fetch, extract, transform, and either verify or replace ``vendor_dir/<name>``."""
    source_kind = spec.get("source", "pypi")
    if source_kind == "pypi":
        pypi_name = spec.get("pypi_name", name)
        version = spec["version"]
        url, expected_sha = resolve_pypi_artifact(
            pypi_name,
            version,
            min_python=MIN_PYTHON,
            prefer=spec.get("prefer", "sdist"),
        )
        if spec.get("sha256") and spec["sha256"].lower() != expected_sha.lower():
            raise VendorError(f"Manifest sha256 mismatch for {name}: {spec['sha256']} != {expected_sha}")
        filename = os.path.basename(url.split("?", 1)[0])
    elif source_kind == "url":
        url = spec["url"]
        expected_sha = spec["sha256"]
        filename = spec.get("filename") or os.path.basename(url.split("?", 1)[0])
    else:
        raise VendorError(f"Unknown source kind {source_kind!r} for {name}")

    archive_path = fetch_cached(url, cache_dir, filename)
    verify_sha256(archive_path, expected_sha)

    with tempfile.TemporaryDirectory() as td:
        staging = os.path.join(td, name)
        extract_source_archive(
            archive_path,
            staging,
            strip_prefix=spec.get("strip_prefix", ""),
            extra_files=spec.get("extra_files"),
            drop_globs=spec.get("drop", ()),
            allow_binaries=spec.get("allow_binaries", ()),
        )
        apply_layout(staging, spec)
        rewrite_directory_imports(staging, spec.get("rewrite_imports"))

        overlay_dir = os.path.join(tools_dir, "overlays", name)
        apply_overlays(staging, overlay_dir)

        patch_file = spec.get("patch")
        if patch_file:
            apply_patch(staging, os.path.join(tools_dir, patch_file))

        target_dir = os.path.join(vendor_dir, name)
        if verify:
            return compare_dirs(staging, target_dir)
        replace_target_dir(staging, target_dir)
        return []


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
    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    packages_map = manifest.get("packages", {})
    selected = args.packages or list(packages_map.keys())
    unknown = [p for p in selected if p not in packages_map]
    if unknown:
        print(f"Unknown package(s): {', '.join(unknown)}", file=sys.stderr)
        return 1

    tools_dir = os.path.dirname(os.path.abspath(__file__))
    failures = 0
    for name in selected:
        try:
            diffs = process_package(
                name,
                packages_map[name],
                args.vendor_dir,
                args.cache_dir,
                tools_dir,
                verify=args.verify,
            )
            if args.verify:
                if diffs:
                    failures += 1
                    print(f"FAIL {name}:")
                    for d in diffs:
                        print(f"  - {d}")
                else:
                    print(f"OK   {name}")
            else:
                print(f"UPDATED {name}")
        except VendorError as exc:
            failures += 1
            print(f"ERROR {name}: {exc}", file=sys.stderr)

    if args.verify and failures == 0:
        print(f"{len(selected)}/{len(selected)} packages verified: 1:1 byte-for-byte parity")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
