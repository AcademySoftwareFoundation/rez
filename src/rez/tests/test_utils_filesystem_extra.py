# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Additional unit tests for 'rez.utils.filesystem' module.
"""
import errno
import gc
import ntpath
import os
import os.path
import shutil
import stat
import sys
import unittest
import unittest.mock

from rez.tests.util import TempdirMixin, TestBase
from rez.utils import filesystem


class TestTempDirsExtra(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_clear_all_skips_collected_instances(self) -> None:
        """TempDirs.clear_all skips weakrefs whose instances were garbage collected."""
        manager = filesystem.TempDirs(self.root, prefix="gc_test_")
        d = manager.mkdtemp(cleanup=False)
        self.assertTrue(os.path.isdir(d))
        del manager
        gc.collect()
        # Should not raise even when dead weakrefs exist in TempDirs.instances
        filesystem.TempDirs.clear_all()
        self.assertTrue(os.path.isdir(d))

    def test_clear_empty_and_manual_clear(self) -> None:
        """TempDirs.clear removes managed dirs and is idempotent when empty."""
        manager = filesystem.TempDirs(self.root, prefix="manual_")
        d = manager.mkdtemp(cleanup=True)
        self.assertTrue(os.path.isdir(d))
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REZ_KEEP_TMPDIRS", None)
            manager.clear()
            self.assertFalse(os.path.exists(d))
            # Second clear hits early return when self.dirs is empty
            manager.clear()


class TestMakePathWritable(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_readonly_file_temporarily_writable(self) -> None:
        """make_path_writable adds write bit on read-only path and restores it."""
        path = os.path.join(self.root, "readonly.txt")
        with open(path, "w") as f:
            f.write("original")
        os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        orig_mode = os.stat(path).st_mode

        try:
            with filesystem.make_path_writable(path):
                self.assertTrue(os.access(path, os.W_OK))
                with open(path, "w") as f:
                    f.write("updated")

            self.assertEqual(os.stat(path).st_mode, orig_mode)
            with open(path) as f:
                self.assertEqual(f.read(), "updated")
        finally:
            os.chmod(path, orig_mode | stat.S_IWUSR)

    def test_already_writable_file_unchanged(self) -> None:
        """make_path_writable does not chmod when path is already writable."""
        path = os.path.join(self.root, "writable.txt")
        with open(path, "w") as f:
            f.write("data")

        with unittest.mock.patch("os.chmod") as mock_chmod:
            with filesystem.make_path_writable(path):
                pass
        mock_chmod.assert_not_called()

    def test_missing_path_ignored(self) -> None:
        """make_path_writable ignores OSError on nonexistent paths."""
        missing = os.path.join(self.root, "does_not_exist.txt")
        with filesystem.make_path_writable(missing):
            self.assertFalse(os.path.exists(missing))


class TestRetainCwd(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_restores_cwd_on_normal_exit_and_exception(self) -> None:
        """retain_cwd restores original working directory even on exception."""
        orig_cwd = os.getcwd()
        with filesystem.retain_cwd():
            os.chdir(self.root)
            self.assertEqual(os.path.realpath(os.getcwd()), os.path.realpath(self.root))
        self.assertEqual(os.getcwd(), orig_cwd)

        with self.assertRaises(RuntimeError):
            with filesystem.retain_cwd():
                os.chdir(self.root)
                raise RuntimeError("boom")
        self.assertEqual(os.getcwd(), orig_cwd)


class TestGetExistingPath(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_existing_and_parent_paths(self) -> None:
        """get_existing_path returns existing path or longest existing ancestor."""
        sub = os.path.join(self.root, "a", "b")
        os.makedirs(sub)
        self.assertEqual(filesystem.get_existing_path(sub), sub)
        self.assertEqual(
            filesystem.get_existing_path(os.path.join(sub, "c", "d")),
            sub,
        )

    def test_topmost_path_stops_search(self) -> None:
        """get_existing_path returns None when topmost_path is reached."""
        target = os.path.join(self.root, "missing_a", "missing_b")
        self.assertIsNone(filesystem.get_existing_path(target, topmost_path=self.root))

        topmost = os.path.join(self.root, "topmost")
        mid = os.path.join(topmost, "mid")
        os.makedirs(mid)
        missing = os.path.join(mid, "missing")
        self.assertEqual(filesystem.get_existing_path(missing, topmost_path=topmost), mid)
        self.assertIsNone(filesystem.get_existing_path(missing, topmost_path=mid))
        self.assertIsNone(
            filesystem.get_existing_path(os.path.join(missing, "leaf"), topmost_path=missing)
        )

    def test_no_existing_ancestor_returns_none(self) -> None:
        """get_existing_path returns None when relative path has no existing parent."""
        self.assertIsNone(filesystem.get_existing_path("nonexistent_rel_a/nonexistent_rel_b"))


class TestSafeListdirAndRemove(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_safe_listdir_variants(self) -> None:
        """safe_listdir handles existing dir, ENOENT, ENOTDIR, and re-raises other errors."""
        d = os.path.join(self.root, "listdir_test")
        os.makedirs(d)
        f = os.path.join(d, "file.txt")
        with open(f, "w") as fp:
            fp.write("hi")

        self.assertEqual(filesystem.safe_listdir(d), ["file.txt"])
        self.assertEqual(filesystem.safe_listdir(os.path.join(d, "missing")), [])
        self.assertEqual(filesystem.safe_listdir(f), [])

        err = OSError(errno.EACCES, "Permission denied")
        with unittest.mock.patch("os.listdir", side_effect=err):
            with self.assertRaises(OSError) as ctx:
                filesystem.safe_listdir(d)
            self.assertEqual(ctx.exception.errno, errno.EACCES)

    def test_safe_remove_missing_and_error_cases(self) -> None:
        """safe_remove handles missing path, raced removal, and persistent OSError."""
        missing = os.path.join(self.root, "no_such_file")
        filesystem.safe_remove(missing)

        f = os.path.join(self.root, "remove_me.txt")
        with open(f, "w") as fp:
            fp.write("x")

        # Raced removal: os.remove raises OSError, path no longer exists
        def _remove_and_raise(p):
            os.unlink(p)
            raise OSError(errno.ENOENT, "gone")

        with unittest.mock.patch("os.remove", side_effect=_remove_and_raise):
            filesystem.safe_remove(f)
        self.assertFalse(os.path.exists(f))

        # Persistent failure: os.remove raises OSError and path still exists
        f2 = os.path.join(self.root, "still_there.txt")
        with open(f2, "w") as fp:
            fp.write("y")

        with unittest.mock.patch("os.remove", side_effect=PermissionError(errno.EACCES, "denied")):
            with self.assertRaises(PermissionError):
                filesystem.safe_remove(f2)

    def test_safe_remove_symlink_to_dir(self) -> None:
        """safe_remove unlinks a symlink to a directory without removing the target."""
        target_dir = os.path.join(self.root, "sym_target_dir")
        os.makedirs(target_dir)
        sentinel = os.path.join(target_dir, "keep.txt")
        with open(sentinel, "w") as fp:
            fp.write("keep")

        link_path = os.path.join(self.root, "dir_link")
        try:
            os.symlink(target_dir, link_path)
        except OSError as exc:
            self.skipTest("symlinks unavailable: %s" % exc)

        filesystem.safe_remove(link_path)
        self.assertFalse(os.path.lexists(link_path))
        self.assertTrue(os.path.isdir(target_dir))
        self.assertTrue(os.path.isfile(sentinel))


class TestForcefulRmtree(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_forceful_rmtree_removes_readonly_tree(self) -> None:
        """forceful_rmtree removes a tree containing read-only files and dirs."""
        tree = os.path.join(self.root, "ro_tree")
        sub = os.path.join(tree, "sub")
        os.makedirs(sub)
        ro_file = os.path.join(sub, "ro.txt")
        with open(ro_file, "w") as fp:
            fp.write("locked")

        os.chmod(ro_file, stat.S_IRUSR)
        if sys.platform != "win32":
            # Windows os.access(dir, os.W_OK) ignores read-only attribute while os.rmdir fails with WinError 5
            os.chmod(sub, stat.S_IRUSR | stat.S_IXUSR)
        try:
            filesystem.forceful_rmtree(tree)
            self.assertFalse(os.path.exists(tree))
        finally:
            if os.path.exists(sub):
                os.chmod(sub, stat.S_IRWXU)
            if os.path.exists(ro_file):
                os.chmod(ro_file, stat.S_IRWXU)

    def test_forceful_rmtree_mac_appledouble_ignored(self) -> None:
        """forceful_rmtree ignores FileNotFoundError for AppleDouble ._ files on macOS."""
        def _fake_rmtree(path, onerror=None):
            try:
                raise FileNotFoundError(errno.ENOENT, "not found")
            except FileNotFoundError:
                onerror(os.unlink, os.path.join(path, "._resource"), sys.exc_info())

        with unittest.mock.patch("rez.utils.filesystem.is_mac", True), \
             unittest.mock.patch("shutil.rmtree", side_effect=_fake_rmtree):
            filesystem.forceful_rmtree(os.path.join(self.root, "mac_tree"))

    def test_forceful_rmtree_windows_long_path_and_chmod_fallback(self) -> None:
        """forceful_rmtree invokes windows_long_path on Windows and handles stat errors."""
        called = []

        def _fake_func(p):
            called.append(p)

        def _fake_rmtree(path, onerror=None):
            try:
                raise PermissionError(errno.EACCES, "denied")
            except PermissionError:
                onerror(_fake_func, path, sys.exc_info())

        wlp_patch = unittest.mock.patch(
            "rez.utils.filesystem.windows_long_path",
            return_value="\\\\?\\C:\\long",
        )
        with unittest.mock.patch("rez.utils.filesystem.is_mac", False), \
             unittest.mock.patch("rez.utils.filesystem.is_windows", True), \
             wlp_patch as mock_wlp, \
             unittest.mock.patch("os.access", return_value=False), \
             unittest.mock.patch("os.stat", side_effect=OSError("stat failed")), \
             unittest.mock.patch("shutil.rmtree", side_effect=_fake_rmtree):
            filesystem.forceful_rmtree("C:\\long")

        mock_wlp.assert_called_once_with("C:\\long")
        self.assertEqual(called, ["\\\\?\\C:\\long"])


class TestReplacingAndCopyHelpers(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    @unittest.skipIf(sys.platform == "win32", "Symlinks require privileges on Windows")
    def test_replacing_symlink(self) -> None:
        """replacing_symlink creates a symlink and overwrites an existing target."""
        target1 = os.path.join(self.root, "sym_t1")
        target2 = os.path.join(self.root, "sym_t2")
        os.makedirs(target1)
        os.makedirs(target2)
        link = os.path.join(self.root, "my_link")

        filesystem.replacing_symlink(target1, link)
        self.assertEqual(os.readlink(link), target1)

        filesystem.replacing_symlink(target2, link)
        self.assertEqual(os.readlink(link), target2)

    def test_replacing_copy_file_dir_and_symlink(self) -> None:
        """replacing_copy overwrites existing files, directories, and symlinks."""
        src_file = os.path.join(self.root, "src.txt")
        with open(src_file, "w") as fp:
            fp.write("new_content")

        dest_file = os.path.join(self.root, "dest.txt")
        with open(dest_file, "w") as fp:
            fp.write("old_content")

        filesystem.replacing_copy(src_file, dest_file)
        with open(dest_file) as fp:
            self.assertEqual(fp.read(), "new_content")

        src_dir = os.path.join(self.root, "rc_src_dir")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "a.txt"), "w") as fp:
            fp.write("dir_content")

        dest_dir = os.path.join(self.root, "rc_dest_dir")
        os.makedirs(dest_dir)
        with open(os.path.join(dest_dir, "stale.txt"), "w") as fp:
            fp.write("stale")

        filesystem.replacing_copy(src_dir, dest_dir)
        self.assertTrue(os.path.isfile(os.path.join(dest_dir, "a.txt")))
        self.assertFalse(os.path.exists(os.path.join(dest_dir, "stale.txt")))

        if sys.platform != "win32":
            link_src = os.path.join(self.root, "rc_link_src")
            link_dst = os.path.join(self.root, "rc_link_dst")
            os.symlink(src_file, link_src)
            filesystem.replacing_copy(link_src, link_dst, follow_symlinks=False)
            self.assertTrue(os.path.islink(link_dst))
            self.assertEqual(os.readlink(link_dst), src_file)

    def test_replace_file_or_dir_error_and_fallback(self) -> None:
        """replace_file_or_dir re-raises on missing dest error and falls back when atomic fails."""
        src = os.path.join(self.root, "rfd_src.txt")
        dst = os.path.join(self.root, "rfd_dst.txt")
        with open(src, "w") as fp:
            fp.write("src")

        # rename raises and dst still doesn't exist -> re-raises
        with unittest.mock.patch("rez.utils.filesystem.rename", side_effect=OSError("fail")):
            with self.assertRaises(OSError):
                filesystem.replace_file_or_dir(dst, src)

        # rename raises because another process created dst in the meantime -> falls through to replace_atomic
        def _race_create_dst(s, d):
            with open(d, "w") as fp:
                fp.write("raced")
            raise OSError("exists")

        with unittest.mock.patch("rez.utils.filesystem.rename", side_effect=_race_create_dst):
            filesystem.replace_file_or_dir(dst, src)
        with open(dst) as fp:
            self.assertEqual(fp.read(), "src")

        # dst exists, replace_atomic raises -> falls back to make_tmp_name + rename
        with open(src, "w") as fp:
            fp.write("src2")
        with open(dst, "w") as fp:
            fp.write("dst")
        with unittest.mock.patch("rez.vendor.atomicwrites.replace_atomic", side_effect=OSError("atomic fail")):
            filesystem.replace_file_or_dir(dst, src)
        with open(dst) as fp:
            self.assertEqual(fp.read(), "src2")

    def test_additive_copytree(self) -> None:
        """additive_copytree merges nested directories into an existing destination."""
        src = os.path.join(self.root, "add_src")
        dst = os.path.join(self.root, "add_dst")
        os.makedirs(os.path.join(src, "sub"))
        os.makedirs(os.path.join(dst, "sub"))

        with open(os.path.join(src, "sub", "new.txt"), "w") as fp:
            fp.write("new")
        with open(os.path.join(dst, "sub", "existing.txt"), "w") as fp:
            fp.write("existing")

        filesystem.additive_copytree(src, dst)
        self.assertTrue(os.path.isfile(os.path.join(dst, "sub", "new.txt")))
        self.assertTrue(os.path.isfile(os.path.join(dst, "sub", "existing.txt")))

    def test_is_subdirectory_different_mounts_returns_false(self) -> None:
        """is_subdirectory returns False when os.path.relpath raises ValueError."""
        with unittest.mock.patch("os.path.relpath", side_effect=ValueError("different mounts")):
            self.assertFalse(filesystem.is_subdirectory(self.root, self.root))

    @unittest.skipIf(sys.platform == "win32", "Symlinks require privileges on Windows")
    def test_find_matching_symlink(self) -> None:
        """find_matching_symlink finds matching relative/absolute symlinks and ignores non-links."""
        base = os.path.join(self.root, "sym_search")
        target = os.path.join(self.root, "sym_target")
        other = os.path.join(self.root, "sym_other")
        os.makedirs(base)
        os.makedirs(target)
        os.makedirs(other)

        with open(os.path.join(base, "regular_file"), "w") as fp:
            fp.write("not a link")
        os.symlink(other, os.path.join(base, "wrong_link"))
        os.symlink(os.path.join("..", "sym_target"), os.path.join(base, "rel_match"))

        self.assertEqual(filesystem.find_matching_symlink(base, target), "rel_match")
        self.assertEqual(
            filesystem.find_matching_symlink(base, os.path.join("..", "sym_target")),
            "rel_match",
        )
        self.assertIsNone(filesystem.find_matching_symlink(base, os.path.join(self.root, "missing")))

    def test_copy_or_replace(self) -> None:
        """copy_or_replace handles normal copy, EPERM fallback, dir dst, and non-EPERM errors."""
        src = os.path.join(self.root, "cor_src.txt")
        dst = os.path.join(self.root, "cor_dst.txt")
        with open(src, "w") as fp:
            fp.write("hello")

        # Normal copy
        filesystem.copy_or_replace(src, dst)
        with open(dst) as fp:
            self.assertEqual(fp.read(), "hello")

        # Non-EPERM error re-raises
        with unittest.mock.patch("shutil.copy", side_effect=OSError(errno.ENOENT, "missing")):
            with self.assertRaises(OSError) as ctx:
                filesystem.copy_or_replace(src, dst)
            self.assertEqual(ctx.exception.errno, errno.ENOENT)

        # EPERM fallback with directory dst
        dst_dir = os.path.join(self.root, "cor_dir")
        os.makedirs(dst_dir)
        dir_target = os.path.join(dst_dir, "cor_src.txt")
        with open(dir_target, "w") as fp:
            fp.write("old")

        real_copy = shutil.copy
        call_count = [0]

        def _eperm_once(s, d):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError(errno.EPERM, "eperm")
            return real_copy(s, d)

        with unittest.mock.patch("shutil.copy", side_effect=_eperm_once):
            filesystem.copy_or_replace(src, dst_dir)
        with open(dir_target) as fp:
            self.assertEqual(fp.read(), "hello")

        # EPERM fallback when temp file missing after copy raises RuntimeError
        with unittest.mock.patch("shutil.copy", side_effect=[OSError(errno.EPERM, "eperm"), None]), \
             unittest.mock.patch("os.path.isfile", return_value=False):
            with self.assertRaises(RuntimeError):
                filesystem.copy_or_replace(src, dst)


class TestCopytreeAndMovetree(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_copytree_basic_ignore_and_hardlinks(self) -> None:
        """copytree copies nested dirs, honors ignore, and supports hardlinks + fallback."""
        src = os.path.join(self.root, "ct_src")
        sub = os.path.join(src, "sub")
        os.makedirs(sub)
        f1 = os.path.join(src, "a.txt")
        f2 = os.path.join(sub, "b.txt")
        f_ign = os.path.join(src, "skip.tmp")
        for p, content in ((f1, "a"), (f2, "b"), (f_ign, "skip")):
            with open(p, "w") as fp:
                fp.write(content)

        if sys.platform != "win32":
            os.symlink(f1, os.path.join(src, "link_a"))

        dst = os.path.join(self.root, "ct_dst")
        filesystem.copytree(
            src,
            dst,
            symlinks=(sys.platform != "win32"),
            ignore=shutil.ignore_patterns("*.tmp"),
            hardlinks=True,
        )
        self.assertTrue(os.path.isfile(os.path.join(dst, "a.txt")))
        self.assertTrue(os.path.isfile(os.path.join(dst, "sub", "b.txt")))
        self.assertFalse(os.path.exists(os.path.join(dst, "skip.tmp")))
        if sys.platform != "win32":
            self.assertEqual(os.stat(f1).st_ino, os.stat(os.path.join(dst, "a.txt")).st_ino)
            self.assertTrue(os.path.islink(os.path.join(dst, "link_a")))

        # Hardlinks fallback to copy2 when os.link raises OSError
        dst_fb = os.path.join(self.root, "ct_dst_fb")
        with unittest.mock.patch("os.link", side_effect=OSError(errno.EXDEV, "cross-device")):
            filesystem.copytree(src, dst_fb, hardlinks=True)
        self.assertTrue(os.path.isfile(os.path.join(dst_fb, "a.txt")))

    def test_copytree_error_collection_and_copystat(self) -> None:
        """copytree collects IOError/shutil.Error and ignores WindowsError on copystat."""
        src = os.path.join(self.root, "ct_err_src")
        sub = os.path.join(src, "sub")
        os.makedirs(sub)
        with open(os.path.join(sub, "bad.txt"), "w") as fp:
            fp.write("bad")

        # copy2 OSError is collected into shutil.Error
        dst1 = os.path.join(self.root, "ct_err_dst1")
        with unittest.mock.patch("shutil.copy2", side_effect=OSError("copy failed")):
            with self.assertRaises(shutil.Error) as ctx:
                filesystem.copytree(src, dst1)
            self.assertEqual(len(ctx.exception.args[0]), 1)

        if hasattr(shutil, "WindowsError"):
            # WindowsError on copystat is ignored
            dst2 = os.path.join(self.root, "ct_err_dst2")
            with unittest.mock.patch("shutil.copystat", side_effect=shutil.WindowsError("win")):
                filesystem.copytree(src, dst2)

    @unittest.expectedFailure
    def test_copytree_copystat_oserror_fallback(self) -> None:
        """Non-WindowsError OSError on copystat is appended to errors (src/rez/utils/filesystem.py:487)."""
        src = os.path.join(self.root, "ct_stat_err_src")
        os.makedirs(src)
        with open(os.path.join(src, "ok.txt"), "w") as fp:
            fp.write("ok")

        dst = os.path.join(self.root, "ct_stat_err_dst")
        with unittest.mock.patch("shutil.copystat", side_effect=OSError("stat failed")):
            with self.assertRaises(shutil.Error) as ctx:
                filesystem.copytree(src, dst)
            self.assertTrue(len(ctx.exception.args[0]) >= 1)

    def test_movetree_normal_and_fallback(self) -> None:
        """movetree uses shutil.move and falls back to copytree + safe_rmtree on failure."""
        src = os.path.join(self.root, "mt_src")
        os.makedirs(src)
        with open(os.path.join(src, "f.txt"), "w") as fp:
            fp.write("mv")

        dst1 = os.path.join(self.root, "mt_dst1")
        filesystem.movetree(src, dst1)
        self.assertFalse(os.path.exists(src))
        self.assertTrue(os.path.isfile(os.path.join(dst1, "f.txt")))

        dst2 = os.path.join(self.root, "mt_dst2")
        with unittest.mock.patch("shutil.move", side_effect=OSError("exdev")):
            filesystem.movetree(dst1, dst2)
        self.assertFalse(os.path.exists(dst1))
        self.assertTrue(os.path.isfile(os.path.join(dst2, "f.txt")))


class TestPathAndChmodHelpers(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    @unittest.skipIf(sys.platform == "win32", "POSIX mode bits are not preserved on Windows")
    def test_safe_chmod(self) -> None:
        """safe_chmod only calls os.chmod when the mode differs."""
        f = os.path.join(self.root, "chmod.txt")
        with open(f, "w") as fp:
            fp.write("c")
        os.chmod(f, 0o644)

        with unittest.mock.patch("os.chmod") as mock_chmod:
            filesystem.safe_chmod(f, 0o644)
        mock_chmod.assert_not_called()

        filesystem.safe_chmod(f, 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(f).st_mode), 0o600)

    def test_path_conversion_helpers(self) -> None:
        """to_nativepath, to_ntpath, and to_posixpath convert separators as expected."""
        self.assertEqual(filesystem.to_ntpath("a/b/c"), "a\\b\\c")
        self.assertEqual(filesystem.to_posixpath("a\\b\\c"), "a/b/c")
        self.assertEqual(filesystem.to_nativepath("a\\b/c"), os.path.join("a", "b", "c"))

    def test_windows_long_path(self) -> None:
        """windows_long_path adds \\\\?\\ or \\\\?\\UNC\\ unless already prefixed."""
        with unittest.mock.patch("os.path.abspath", side_effect=lambda p: p):
            self.assertEqual(
                filesystem.windows_long_path("\\\\?\\C:\\foo"),
                "\\\\?\\C:\\foo",
            )
            self.assertEqual(
                filesystem.windows_long_path("\\\\server\\share\\foo"),
                "\\\\?\\UNC\\server\\share\\foo",
            )
            self.assertEqual(
                filesystem.windows_long_path("C:\\foo"),
                "\\\\?\\C:\\foo",
            )

    @unittest.skipIf(sys.platform == "win32", "Mocks Windows internals on non-Windows")
    def test_windows_realpath_root_relative_inherits_drive_os_sep(self) -> None:
        """_windows_realpath inherits link drive for root-relative target matching os.sep."""
        link_path = "N:/links/link"
        target_path = "/targets/pkg"

        p_islink = unittest.mock.patch("os.path.islink", side_effect=lambda p: p == link_path)
        p_readlink = unittest.mock.patch("os.readlink", return_value=target_path)
        p_abspath = unittest.mock.patch("os.path.abspath", side_effect=os.path.normpath)
        p_isabs = unittest.mock.patch(
            "os.path.isabs", side_effect=lambda p: p == target_path or ntpath.isabs(p)
        )
        p_splitdrive = unittest.mock.patch("os.path.splitdrive", side_effect=ntpath.splitdrive)
        with p_islink, p_readlink as mock_readlink, p_abspath, p_isabs, p_splitdrive:
            result = filesystem._windows_realpath(link_path)

        mock_readlink.assert_called_once_with(link_path)
        self.assertEqual(result, "N:/targets/pkg")

    def test_walk_up_dirs(self) -> None:
        """walk_up_dirs yields path and all ancestors up to root."""
        nested = os.path.join(self.root, "w1", "w2")
        os.makedirs(nested)
        walked = list(filesystem.walk_up_dirs(nested))
        self.assertEqual(walked[0], os.path.abspath(nested))
        self.assertIn(os.path.abspath(self.root), walked)
        self.assertEqual(walked[-1], os.path.dirname(walked[-2]))
