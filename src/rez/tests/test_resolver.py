# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rez.resolver (Resolver and ResolverStatus).
"""

from contextlib import contextmanager
import os
import shutil
import unittest
from unittest.mock import patch

from rez.package_filter import GlobRule, PackageFilter, PackageFilterList
from rez.package_order import PackageOrderList, SortedOrder
from rez.plugin_managers import plugin_manager
from rez.resolved_context import ResolvedContext
from rez.resolver import Resolver, ResolverStatus
from rez.solver import SolverCallbackReturn
from rez.tests.util import TempdirMixin, TestBase
from rez.version import Requirement


class _FakeMemcacheClient:
    """In-memory stand-in for rez.utils.memcached.Client."""

    def __init__(self, store):
        self.store = store
        self.deleted_keys = []
        self.set_keys = []

    def get(self, key):
        return self.store.get(key)

    def set(self, key, val):
        self.store[key] = val
        self.set_keys.append(key)

    def delete(self, key):
        self.store.pop(key, None)
        self.deleted_keys.append(key)


def _write_pkg(repo_root, name, version, requires=None):
    pkg_dir = os.path.join(repo_root, name, version)
    os.makedirs(pkg_dir, exist_ok=True)
    req_line = f"requires = {requires!r}\n" if requires else ""
    pkg_py = os.path.join(pkg_dir, "package.py")
    with open(pkg_py, "w") as f:
        f.write(
            f"name = {name!r}\n"
            f"version = {version!r}\n"
            f"{req_line}"
        )
    return pkg_py


class TestResolver(TestBase, TempdirMixin):
    """Tests for Resolver solving, status, filters, orderers, and caching."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()
        cls.solver_packages_path = cls.data_path("solver", "packages")
        cls.settings = dict(
            packages_path=[cls.solver_packages_path],
            package_filter=None,
            resolve_caching=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _make_context(self, package_requests, **kwargs):
        return ResolvedContext(
            package_requests=package_requests,
            caching=False,
            **kwargs,
        )

    def test_status_enum_descriptions(self):
        self.assertTrue(ResolverStatus.pending.description)
        self.assertTrue(ResolverStatus.solved.description)
        self.assertTrue(ResolverStatus.failed.description)
        self.assertTrue(ResolverStatus.aborted.description)

    def test_pending_state_before_solve(self):
        reqs = [Requirement("nada")]
        ctx = self._make_context(reqs)
        resolver = Resolver(
            context=ctx,
            package_requests=reqs,
            package_paths=[self.solver_packages_path],
            caching=False,
        )
        self.assertEqual(resolver.status, ResolverStatus.pending)
        self.assertIsNone(resolver.resolved_packages)
        self.assertIsNone(resolver.resolved_ephemerals)
        self.assertIsNone(resolver.graph)
        self.assertFalse(resolver.from_cache)

    def test_solve_success_and_ephemerals(self):
        reqs = [Requirement("nada"), Requirement(".foo-1")]
        ctx = self._make_context(reqs)
        resolver = Resolver(
            context=ctx,
            package_requests=reqs,
            package_paths=[self.solver_packages_path],
            caching=False,
        )
        resolver.solve()

        self.assertEqual(resolver.status, ResolverStatus.solved)
        self.assertFalse(resolver.from_cache)
        self.assertIsNotNone(resolver.graph)
        self.assertEqual([v.name for v in resolver.resolved_packages], ["nada"])
        self.assertEqual([str(e) for e in resolver.resolved_ephemerals], [".foo-1"])

    def test_solve_failed_does_not_cache(self):
        ctx = self._make_context([Requirement("nada")])
        reqs = [Requirement("nada"), Requirement("!nada")]
        store = {}
        fake_client = _FakeMemcacheClient(store)

        @contextmanager
        def fake_mc(*args, **kwargs):
            yield fake_client

        self.update_settings({
            "resolve_caching": True,
            "memcached_uri": ["127.0.0.1:11211"],
        })

        with patch("rez.resolver.memcached_client", side_effect=fake_mc):
            resolver = Resolver(
                context=ctx,
                package_requests=reqs,
                package_paths=[self.solver_packages_path],
                caching=True,
            )
            resolver.solve()

        self.assertEqual(resolver.status, ResolverStatus.failed)
        self.assertIsNotNone(resolver.failure_description)
        self.assertIsNone(resolver.resolved_packages)
        self.assertIsNone(resolver.resolved_ephemerals)
        self.assertEqual(store, {})

    def test_solve_aborted_via_callback(self):
        reqs = [Requirement("pyfoo")]
        ctx = self._make_context(reqs)

        def abort_cb(state):
            return SolverCallbackReturn.abort, "stopped by test"

        resolver = Resolver(
            context=ctx,
            package_requests=reqs,
            package_paths=[self.solver_packages_path],
            callback=abort_cb,
            caching=False,
        )
        resolver.solve()

        self.assertEqual(resolver.status, ResolverStatus.aborted)
        self.assertEqual(resolver.failure_description, "stopped by test")
        self.assertIsNone(resolver.resolved_packages)

    def test_package_filter_and_orderers_without_and_with_timestamp(self):
        fltr = PackageFilterList()
        f = PackageFilter()
        f.add_exclusion(GlobRule("nada-99"))
        fltr.add_filter(f)
        orderers = PackageOrderList([SortedOrder(descending=True)])

        reqs = [Requirement("nada")]
        ctx = self._make_context(reqs)

        r_no_ts = Resolver(
            context=ctx,
            package_requests=reqs,
            package_paths=[self.solver_packages_path],
            package_filter=fltr,
            package_orderers=orderers,
            timestamp=0,
            caching=False,
        )
        self.assertEqual(r_no_ts.package_filter_hash, fltr.sha1)
        self.assertTrue(r_no_ts.package_orderers_hash)
        self.assertIs(r_no_ts.package_filter, fltr)

        r_with_ts = Resolver(
            context=ctx,
            package_requests=reqs,
            package_paths=[self.solver_packages_path],
            package_filter=fltr,
            package_orderers=orderers,
            timestamp=1000,
            caching=False,
        )
        self.assertEqual(r_with_ts.package_filter_hash, fltr.sha1)
        self.assertIsNot(r_with_ts.package_filter, fltr)
        r_with_ts.solve()
        self.assertEqual(r_with_ts.status, ResolverStatus.solved)

    def test_memcache_disabled_when_release_time_zero(self):
        store = {}
        fake_client = _FakeMemcacheClient(store)

        @contextmanager
        def fake_mc(*args, **kwargs):
            yield fake_client

        self.update_settings({
            "resolve_caching": True,
            "memcached_uri": ["127.0.0.1:11211"],
        })

        reqs = [Requirement("nada")]
        ctx = self._make_context(reqs)

        with patch("rez.resolver.memcached_client", side_effect=fake_mc), patch(
            "rez.resolver.get_last_release_time", return_value=0
        ):
            resolver = Resolver(
                context=ctx,
                package_requests=reqs,
                package_paths=[self.solver_packages_path],
                caching=True,
            )
            resolver.solve()

        self.assertEqual(resolver.status, ResolverStatus.solved)
        self.assertFalse(resolver.from_cache)
        self.assertEqual(store, {})

    def test_memcache_non_timestamped_hit_and_invalidation(self):
        repo_dir = os.path.join(self.root, "repo_non_ts")
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
        _write_pkg(repo_dir, "alpha", "1.0.0")

        store = {}
        fake_client = _FakeMemcacheClient(store)

        @contextmanager
        def fake_mc(*args, **kwargs):
            yield fake_client

        self.update_settings({
            "packages_path": [repo_dir],
            "resolve_caching": True,
            "memcached_uri": ["127.0.0.1:11211"],
        })

        reqs = [Requirement("alpha")]
        ctx = self._make_context(reqs, package_paths=[repo_dir])

        with patch("rez.resolver.memcached_client", side_effect=fake_mc):
            # 1. Miss -> solve -> store
            r1 = Resolver(
                context=ctx,
                package_requests=reqs,
                package_paths=[repo_dir],
                caching=True,
            )
            r1.solve()
            self.assertEqual(r1.status, ResolverStatus.solved)
            self.assertFalse(r1.from_cache)
            self.assertEqual(len(store), 1)

            # 2. Hit from cache
            r2 = Resolver(
                context=ctx,
                package_requests=reqs,
                package_paths=[repo_dir],
                caching=True,
            )
            r2.solve()
            self.assertEqual(r2.status, ResolverStatus.solved)
            self.assertTrue(r2.from_cache)
            self.assertEqual([v.name for v in r2.resolved_packages], ["alpha"])

            # 3. Newer release since solve -> _releases_since_solve deletes entry
            with patch("rez.resolver.get_last_release_time", return_value=9999999999):
                r3 = Resolver(
                    context=ctx,
                    package_requests=reqs,
                    package_paths=[repo_dir],
                    caching=True,
                )
                r3.solve()
            self.assertFalse(r3.from_cache)
            self.assertTrue(fake_client.deleted_keys)

            # 4. Modify variant state -> _packages_changed returns True
            fake_client.deleted_keys.clear()
            fs_repo_cls = plugin_manager.get_plugin_class(
                "package_repository", "filesystem"
            )
            with patch.object(
                fs_repo_cls,
                "get_variant_state_handle",
                return_value="modified-state",
            ):
                r4 = Resolver(
                    context=ctx,
                    package_requests=reqs,
                    package_paths=[repo_dir],
                    caching=True,
                )
                r4.solve()
            self.assertFalse(r4.from_cache)
            self.assertTrue(fake_client.deleted_keys)

            # 5. IOError/OSError in get_variant_state_handle -> _packages_changed returns True
            fake_client.deleted_keys.clear()
            with patch.object(
                fs_repo_cls,
                "get_variant_state_handle",
                side_effect=[OSError("gone"), "recovered-state"],
            ):
                r5 = Resolver(
                    context=ctx,
                    package_requests=reqs,
                    package_paths=[repo_dir],
                    caching=True,
                )
                r5.solve()
            self.assertFalse(r5.from_cache)
            self.assertTrue(fake_client.deleted_keys)

    def test_memcache_timestamped_paths(self):
        repo_dir = os.path.join(self.root, "repo_ts")
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
        _write_pkg(repo_dir, "beta", "1.0.0")

        store = {}
        fake_client = _FakeMemcacheClient(store)

        @contextmanager
        def fake_mc(*args, **kwargs):
            yield fake_client

        self.update_settings({
            "packages_path": [repo_dir],
            "resolve_caching": True,
            "memcached_uri": ["127.0.0.1:11211"],
        })

        reqs = [Requirement("beta")]
        ctx = self._make_context(reqs, package_paths=[repo_dir])

        with patch("rez.resolver.memcached_client", side_effect=fake_mc):
            # Case A: release time (100) <= timestamp (200) -> stored under non-timestamped key
            with patch("rez.resolver.get_last_release_time", return_value=100):
                r1 = Resolver(
                    context=ctx,
                    package_requests=reqs,
                    package_paths=[repo_dir],
                    timestamp=200,
                    caching=True,
                )
                r1.solve()
                self.assertFalse(r1.from_cache)
                self.assertEqual(len(store), 1)
                non_ts_key = r1._memcache_key(timestamped=False)
                self.assertIn(non_ts_key, store)

                # Reuses non-timestamped entry via elif not _timestamp_is_earlier
                r2 = Resolver(
                    context=ctx,
                    package_requests=reqs,
                    package_paths=[repo_dir],
                    timestamp=200,
                    caching=True,
                )
                r2.solve()
                self.assertTrue(r2.from_cache)

            # Case B: release time (500) > timestamp (200)
            # Non-timestamped entry has release_time=100 != 500 -> _releases_since_solve deletes it,
            # then _retrieve(True) misses, solves, and stores under timestamped key.
            with patch("rez.resolver.get_last_release_time", return_value=500):
                r3 = Resolver(
                    context=ctx,
                    package_requests=reqs,
                    package_paths=[repo_dir],
                    timestamp=200,
                    caching=True,
                )
                r3.solve()
                self.assertFalse(r3.from_cache)
                ts_key = r3._memcache_key(timestamped=True)
                self.assertIn(ts_key, store)
                self.assertNotIn(non_ts_key, store)

                # Now store a non-timestamped entry with release_time=500 too,
                # so _timestamp_is_earlier (200 < 500) triggers and falls through to ts_key hit.
                r_non_ts = Resolver(
                    context=ctx,
                    package_requests=reqs,
                    package_paths=[repo_dir],
                    timestamp=0,
                    caching=True,
                )
                r_non_ts.solve()
                self.assertIn(non_ts_key, store)

                r4 = Resolver(
                    context=ctx,
                    package_requests=reqs,
                    package_paths=[repo_dir],
                    timestamp=200,
                    caching=True,
                )
                r4.solve()
                self.assertTrue(r4.from_cache)

                # Modify variant state: non-timestamped entry deleted, and _packages_changed
                # on ts_key deletes ts_key and misses.
                fake_client.deleted_keys.clear()
                fs_repo_cls = plugin_manager.get_plugin_class(
                    "package_repository", "filesystem"
                )
                with patch.object(
                    fs_repo_cls,
                    "get_variant_state_handle",
                    return_value="modified-ts-state",
                ):
                    r5 = Resolver(
                        context=ctx,
                        package_requests=reqs,
                        package_paths=[repo_dir],
                        timestamp=200,
                        caching=True,
                    )
                    r5.solve()
                self.assertFalse(r5.from_cache)
                self.assertIn(ts_key, fake_client.deleted_keys)


if __name__ == "__main__":
    unittest.main()
