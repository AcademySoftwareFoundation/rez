# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Test package repository plugin.
"""
import unittest
import unittest.mock
from contextlib import contextmanager

from rezplugins.package_repository import filesystem
from rez.exceptions import ResourceError
from rez.packages import create_package
from rez.tests.util import TestBase, TempdirMixin
from rez.utils.platform_ import platform_
from rez.utils.resources import ResourceHandle
from rez.version import Version


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


class TestFilesystemRepoUriCaseSensitivity(TestBase, TempdirMixin):
    """get_package_from_uri and get_variant_from_uri must find packages when
    the package name or version contains uppercase letters.

    Root cause: get_package_from_uri applies os.path.normcase to the entire URI
    before slicing out pkg_name and pkg_ver_str. Windows normcase lowercases
    the whole string, so '1.0B' becomes '1.0b' and 'FooBar' becomes 'foobar'.
    The subsequent get_package call (version equality check) and _get_family
    case-guard then both return None.
    """

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()
        cls.settings = {}

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def _make_repo(self):
        pool = filesystem.ResourcePool(cache_size=None)
        return filesystem.FileSystemPackageRepository(self.root, pool)

    def _install(self, repo, name, version_str):
        data = {"version": version_str} if version_str else {}
        package = create_package(name, data=data)
        variant = next(package.iter_variants())
        return repo._create_variant(variant, overrides={})

    def test_get_package_from_uri_uppercase_version(self):
        """get_package_from_uri finds a package whose version contains uppercase letters."""
        repo = self._make_repo()
        installed = self._install(repo, "foo", "1.0B")
        pkg_uri = installed.parent.uri

        result = repo.get_package_from_uri(pkg_uri)
        self.assertIsNotNone(
            result,
            "get_package_from_uri returned None for %r — "
            "version '1.0B' was normcased to '1.0b' before lookup" % pkg_uri,
        )
        self.assertEqual(result.version, Version("1.0B"))

    def test_get_package_from_uri_uppercase_name(self):
        """get_package_from_uri finds a package whose name contains uppercase letters."""
        repo = self._make_repo()
        installed = self._install(repo, "FooBar", "1.0")
        pkg_uri = installed.parent.uri

        result = repo.get_package_from_uri(pkg_uri)
        self.assertIsNotNone(
            result,
            "get_package_from_uri returned None for %r — "
            "name 'FooBar' was normcased to 'foobar' before lookup" % pkg_uri,
        )
        self.assertEqual(result.name, "FooBar")

    def test_get_variant_from_uri_uppercase_version(self):
        """get_variant_from_uri finds a variant whose version contains uppercase letters."""
        repo = self._make_repo()
        installed = self._install(repo, "foo", "1.0B")
        variant_uri = installed.uri

        result = repo.get_variant_from_uri(variant_uri)
        self.assertIsNotNone(
            result,
            "get_variant_from_uri returned None for %r — "
            "version '1.0B' was normcased to '1.0b' before lookup" % variant_uri,
        )
