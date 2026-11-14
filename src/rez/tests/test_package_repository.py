# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Test package repository plugin.
"""
import os
import sys
import unittest
import unittest.mock
from contextlib import contextmanager

from rezplugins.package_repository import filesystem, memory
from rez.exceptions import ResourceError
from rez.package_repository import package_repository_manager
from rez.packages import create_package
from rez.tests.util import TestBase, TempdirMixin
from rez.utils.platform_ import platform_
from rez.utils.resources import ResourceHandle


class TestFilesystemPackageRepository(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.settings = dict()

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    @unittest.skipIf(platform_.name != "windows",
                     "Skipping because this issue only affects case-insensitive platforms.")
    def test_mismatching_case(self):
        """Test that we get a caught PackageRepositoryError on case-insensitive platforms."""
        pool = filesystem.ResourcePool(cache_size=None)
        pkg_repository = filesystem.FileSystemPackageRepository(self.root, pool)

        package = create_package("myTestPackage", data={})
        variant = next(package.iter_variants())
        case_mismatch_package = create_package("MyTestPackage", data={})
        case_mismatch_variant = next(case_mismatch_package.iter_variants())

        pkg_repository._create_variant(variant, overrides={})
        with self.assertRaises(filesystem.PackageRepositoryError):
            pkg_repository._create_variant(case_mismatch_variant, overrides={})


# ---------------------------------------------------------------------------
# Helpers shared by the Windows path-form tests below.
# ---------------------------------------------------------------------------

_MOCK_DRIVE_TO_UNC = {"n": "\\\\nas\\studio"}


def _unc_expanding_realpath(path: str) -> str:
    """Simulate py3.8+ Windows os.path.realpath: N:\\ expansion to \\\\nas\\studio\\."""
    norm = path.replace("/", "\\")
    if len(norm) >= 2 and norm[1] == ":":
        drive = norm[0].lower()
        rest = norm[2:]
        if drive in _MOCK_DRIVE_TO_UNC:
            return _MOCK_DRIVE_TO_UNC[drive] + rest
    return path


@contextmanager
def _simulate_py38_unc_expansion():
    """Patch os.path.realpath and the filesystem plugin's platform_ reference
    to reproduce the py3.8+ Windows drive-letter -> UNC expansion bug."""
    mock_plat = unittest.mock.Mock(spec=["has_case_sensitive_filesystem", "name"])
    mock_plat.has_case_sensitive_filesystem = False
    mock_plat.name = "windows"
    with unittest.mock.patch("os.path.realpath", side_effect=_unc_expanding_realpath):
        with unittest.mock.patch.object(filesystem, "platform_", mock_plat):
            yield


@unittest.skipIf(
    platform_.name != "windows",
    "Windows drive-letter / UNC path-consistency tests are Windows-only.",
)
class TestFilesystemRepoWindowsPathForms(TestBase, TempdirMixin):
    """Verify that drive-letter and UNC path styles are preserved throughout
    the repository lifecycle.

    Root cause of bugs #1438 / #2045: With os.path.realpath from py3.8 onward,
    Windows silently converts mapped drive letters to a UNC equivalent.
    canonical_path calls realpath, so FileSystemPackageRepository.__init__
    stores a UNC self.location even when the caller supplied a drive-letter
    path. Subsequent make_resource_handle / get_resource_from_handle calls
    that carry the original drive-letter path cause a ResourceError, due to
    the apparent location mismatch.
    """

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()
        cls.settings = {}

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    # ------------------------------------------------------------------
    # FileSystemPackageRepository.__init__ - self.location form
    # ------------------------------------------------------------------

    def test_repo_init_preserves_drive_letter_location(self):
        """repo.location must maintain drive-letter input path to drive-letter output path.

        With the original realpath call, __init__ calls canonical_path,
        converting N:\\ to \\\\nas\\studio\\. After the fix, canonical_path
        on Windows must use abspath or configurably resolve symlinks, so
        self.location stays as the caller supplied it.
        """
        pool = filesystem.ResourcePool(cache_size=None)
        with _simulate_py38_unc_expansion():
            repo = filesystem.FileSystemPackageRepository("N:\\packages", pool)

        self.assertFalse(
            repo.location.startswith("\\\\"),
            f"repo.location was unexpectedly expanded to UNC: {repo.location!r}",
        )
        self.assertTrue(
            repo.location.lower().startswith("n:\\"),
            f"Expected drive-letter location starting with 'n:\\', got: {repo.location!r}",
        )

    def test_repo_init_preserves_unc_location(self):
        """repo.location must maintain UNC input path to UNC output path."""
        pool = filesystem.ResourcePool(cache_size=None)
        unc = "\\\\nas\\studio\\packages"
        with _simulate_py38_unc_expansion():
            repo = filesystem.FileSystemPackageRepository(unc, pool)

        self.assertTrue(
            repo.location.startswith("\\\\"),
            f"UNC repo.location lost its UNC form: {repo.location!r}",
        )

    # ------------------------------------------------------------------
    # make_resource_handle - location comparison (base-class code path)
    # ------------------------------------------------------------------

    def test_make_resource_handle_drive_letter_no_mismatch(self):
        """make_resource_handle must not raise when both the repo and the caller
        use consistent drive-letter paths.

        __init__ used to UNC-expand self.location via realpath, so the base-class
        make_resource_handle compared the caller's 'N:\\packages' against the
        stored '\\\\nas\\studio\\packages' and raised ResourceError.
        """
        pool = filesystem.ResourcePool(cache_size=None)
        with _simulate_py38_unc_expansion():
            repo = filesystem.FileSystemPackageRepository("N:\\packages", pool)
            try:
                repo.make_resource_handle(
                    "filesystem.family",
                    location="N:\\packages",
                    name="mypkg",
                )
            except ResourceError as exc:
                self.fail(
                    f"make_resource_handle raised ResourceError for matching "
                    f"drive-letter paths: {exc}"
                )

    def test_make_resource_handle_unc_no_mismatch(self):
        """make_resource_handle must not raise when both repo and caller use
        consistent UNC paths."""
        pool = filesystem.ResourcePool(cache_size=None)
        unc = "\\\\nas\\studio\\packages"
        with _simulate_py38_unc_expansion():
            repo = filesystem.FileSystemPackageRepository(unc, pool)
            try:
                repo.make_resource_handle(
                    "filesystem.family",
                    location=unc,
                    name="mypkg",
                )
            except ResourceError as exc:
                self.fail(
                    f"make_resource_handle raised ResourceError for matching "
                    f"UNC paths: {exc}"
                )

    # ------------------------------------------------------------------
    # get_resource_from_handle - filesystem-plugin code path
    # ------------------------------------------------------------------

    def test_get_resource_from_handle_drive_letter_no_mismatch(self):
        """get_resource_from_handle must not raise ResourceError when both
        the handle and the repo use drive-letter pathing.

        The filesystem plugin overrides get_resource_from_handle and applies
        canonical_path as a bridge for maintaining path-style consistency -
        but that bridge cannot work if canonical_path itself expands the
        drive-letter to UNC (making both sides UNC when the repo was created
        with a drive-letter path, or vice-versa).
        """
        pool = filesystem.ResourcePool(cache_size=None)
        drive_letter_path = "N:\\packages"

        with _simulate_py38_unc_expansion():
            repo = filesystem.FileSystemPackageRepository(drive_letter_path, pool)
            handle = ResourceHandle(
                "filesystem.family",
                {
                    "repository_type": "filesystem",
                    "location": drive_letter_path,
                    "name": "mypkg",
                },
            )
            # Mock the pool's own get_resource_from_handle so we do not need
            # actual packages on disk - we only want to exercise the location
            # verification logic, not the resource loading.
            with unittest.mock.patch.object(
                repo.pool, "get_resource_from_handle", return_value=unittest.mock.Mock()
            ):
                try:
                    repo.get_resource_from_handle(handle, verify_repo=True)
                except ResourceError as exc:
                    self.fail(
                        f"get_resource_from_handle raised ResourceError for a "
                        f"drive-letter handle against a drive-letter repo: {exc}"
                    )

    def test_get_resource_from_handle_unc_no_mismatch(self):
        """get_resource_from_handle must not raise ResourceError when both
        handle and repo both use UNC paths."""
        pool = filesystem.ResourcePool(cache_size=None)
        unc = "\\\\nas\\studio\\packages"

        with _simulate_py38_unc_expansion():
            repo = filesystem.FileSystemPackageRepository(unc, pool)
            handle = ResourceHandle(
                "filesystem.family",
                {
                    "repository_type": "filesystem",
                    "location": unc,
                    "name": "mypkg",
                },
            )
            with unittest.mock.patch.object(
                repo.pool, "get_resource_from_handle", return_value=unittest.mock.Mock()
            ):
                try:
                    repo.get_resource_from_handle(handle, verify_repo=True)
                except ResourceError as exc:
                    self.fail(
                        f"get_resource_from_handle raised ResourceError for a "
                        f"UNC handle against a UNC repo: {exc}"
                    )


@unittest.skipIf(
    sys.platform == "win32",
    "Test creates real symlinks; Windows requires admin or developer mode",
)
class TestGetResourceFromHandleSamefileFallback(TestBase, TempdirMixin):
    """Test that get_resource_from_handle uses samefile() as a final
    fallback when canonical_path can't bridge drive-letter vs UNC form."""

    def test_samefile_fallback_allows_mixed_forms(self):
        """A handle with a UNC location should match a repo with a
        drive-letter location when they refer to the same physical path."""

        # Create a real temp dir to use as the repo location
        repo_path = os.path.join(self.root, "repo")
        os.makedirs(repo_path)

        # Get a real repo to extract its variables
        repo = package_repository_manager.get_repository(repo_path)

        # Simulate a handle with a different path form that refers to
        # the same location
        fake_handle = unittest.mock.Mock()
        fake_handle.variables = {
            "repository_type": "filesystem",
            "location": repo_path + "_alias",  # different string
        }

        # Patch samefile to return True (simulating same physical path)
        with unittest.mock.patch("os.path.exists", return_value=True), \
             unittest.mock.patch("os.path.samefile", return_value=True):
            # The location-mismatch guard should pass via the samefile
            # fallback. A ResourceError with "location mismatch" means the
            # fallback failed. Other ResourceErrors (e.g. "Unknown resource
            # type" from the pool lookup) mean the guard passed but the mock
            # handle couldn't complete the full resource resolution -- that's
            # fine, we're only testing the location guard.
            try:
                repo.get_resource_from_handle(fake_handle)
            except ResourceError as e:
                if "location mismatch" in str(e):
                    self.fail(
                        "get_resource_from_handle raised location-mismatch "
                        "ResourceError despite samefile() returning True: %s" % e
                    )
            except Exception:
                pass


class TestFilesystemRepoCopyVariant(TestBase, TempdirMixin):
    """copy_variant_payload will copy a variants payload to dest path,

    Test that it will copy data that is in its payload, fail where required
    """

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()
        cls.settings = {}

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_copy_variant_payload(self):
        '''Test copy_variant_payload copies a variant payload to path'''
        repo_path = os.path.join(self.root, 'repo')
        copy_target = os.path.join(self.root, 'copy_target')

        pool = filesystem.ResourcePool(cache_size=None)
        pkg_repository = filesystem.FileSystemPackageRepository(repo_path, pool)

        package = create_package("copy_test1", data={})
        variant = next(package.iter_variants())

        fs_variant = variant.install(repo_path)
        with open(os.path.join(fs_variant.root, 'payload.txt'), 'w'):
            pass

        pkg_repository.copy_variant_payload(fs_variant.resource, copy_target)

        assert os.path.isfile(os.path.join(copy_target, 'payload.txt'))

    def test_copy_variant_payload_wrong_resource(self):
        '''Test copy_variant_payload failure
        when a different repo variant resource is passed
        '''
        repo_path = os.path.join(self.root, 'repo')
        copy_target = os.path.join(self.root, 'copy_target')

        pool = filesystem.ResourcePool(cache_size=None)
        pkg_repository = filesystem.FileSystemPackageRepository(repo_path, pool)

        mem_package = create_package("copy_test2", data={})
        mem_variant = next(mem_package.iter_variants())

        with self.assertRaises(filesystem.PackageRepositoryError):
            pkg_repository.copy_variant_payload(mem_variant.resource, copy_target)

    def test_copy_variant_payload_missing_root(self):
        '''Test copy_variant_payload failure when a variant has missing root'''
        repo_path = os.path.join(self.root, 'repo')
        copy_target = os.path.join(self.root, 'copy_target')

        pool = filesystem.ResourcePool(cache_size=None)
        pkg_repository = filesystem.FileSystemPackageRepository(repo_path, pool)

        package = create_package("copy_test3", data={'variants': [['python']]})
        variant = next(package.iter_variants())

        fs_variant = variant.install(repo_path)

        with self.assertRaises(filesystem.PackageRepositoryError):
            pkg_repository.copy_variant_payload(fs_variant.resource, copy_target)


class TestMemoryRepoCopyVariantAbstract(unittest.TestCase):
    """copy_variant_payload is abstract by default - a memory repository that doesn't
    wont implement it, test it raises NotImplementedError.
    """

    def test_memory_repository_raises_not_implemented(self):
        repo = memory.MemoryPackageRepository.create_repository({})
        with self.assertRaises(NotImplementedError):
            repo.copy_variant_payload(None, "/some/path")
