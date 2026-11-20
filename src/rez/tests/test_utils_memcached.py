# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test rez.utils.memcached
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from rez.tests.util import TestBase
from rez.utils.memcached import (
    Client,
    DoNotCache,
    cache_interface_version,
    memcache_client_version,
    memcached,
    memcached_client,
    pool_memcached_connections,
    scoped_instance_manager,
)
from rez.vendor.memcache.memcache import SERVER_MAX_KEY_LENGTH


class _FakeMemcacheBackend:
    """In-memory stand-in for a memcached server's storage and stats."""

    def __init__(self) -> None:
        self.store: dict[str, object] = {}
        self.flushed_count = 0
        self.reset_stats_count = 0
        self.disconnect_count = 0


class _FakeMemcacheClient:
    """In-memory stand-in for ``rez.vendor.memcache.memcache.Client``."""

    def __init__(self, servers, backends: dict[tuple[str, ...], _FakeMemcacheBackend] | None = None):
        self.servers = list(servers)
        self.key = tuple(self.servers)
        if backends is not None:
            self.backend = backends.setdefault(self.key, _FakeMemcacheBackend())
        else:
            self.backend = _FakeMemcacheBackend()
        self.set_calls: list[tuple[str, object, int, int]] = []
        self.get_calls: list[str] = []
        self.delete_calls: list[str] = []

    def set(self, key: str, val: object, time: int = 0, min_compress_len: int = 0) -> int:
        self.set_calls.append((key, val, time, min_compress_len))
        self.backend.store[key] = val
        return 1

    def get(self, key: str) -> object:
        self.get_calls.append(key)
        return self.backend.store.get(key)

    def delete(self, key: str) -> int:
        self.delete_calls.append(key)
        self.backend.store.pop(key, None)
        return 1

    def flush_all(self) -> None:
        self.backend.store.clear()
        self.backend.flushed_count += 1

    def get_stats(self, stat_args=None) -> list[tuple]:
        if stat_args == "reset":
            self.backend.reset_stats_count += 1
            return []
        return [(s, {"curr_items": str(len(self.backend.store))}) for s in self.servers]

    def disconnect_all(self) -> None:
        self.backend.disconnect_count += 1


class TestClient(TestBase):
    def _make_backend_factory(self):
        backends: dict[tuple[str, ...], _FakeMemcacheBackend] = {}

        def factory(servers):
            return _FakeMemcacheClient(servers, backends=backends)

        return backends, factory

    def test_miss_sentinel_is_falsy(self) -> None:
        self.assertFalse(bool(Client.miss))
        self.assertIsNotNone(Client.miss)

    def test_init_and_bool(self) -> None:
        c_str = Client("127.0.0.1:11211")
        self.assertEqual(c_str.servers, ["127.0.0.1:11211"])
        self.assertTrue(bool(c_str))
        self.assertEqual(c_str.key_hasher, c_str._key_hash)

        c_debug = Client(["127.0.0.1:11211"], debug=True)
        self.assertEqual(c_debug.key_hasher, c_debug._debug_key_hash)

        c_empty = Client([])
        self.assertFalse(bool(c_empty))

        c_none = Client(None)  # type: ignore[arg-type]
        self.assertFalse(bool(c_none))

    def test_client_property_caches_native_instance(self) -> None:
        _, factory = self._make_backend_factory()
        with patch("rez.utils.memcached.Client_", side_effect=factory) as mock_cls:
            client = Client(["127.0.0.1:11211"])
            self.assertIsNone(client._client)
            native1 = client.client
            native2 = client.client

        self.assertIs(native1, native2)
        mock_cls.assert_called_once_with(["127.0.0.1:11211"])

    def test_test_servers(self) -> None:
        def factory(servers):
            fake = _FakeMemcacheClient(servers)
            if servers == ["bad:11211"]:
                fake.get = lambda key: None  # type: ignore[method-assign]
            return fake

        with patch("rez.utils.memcached.Client_", side_effect=factory):
            client = Client(["good1:11211", "bad:11211", "good2:11211"])
            responders = client.test_servers()

        self.assertEqual(responders, {"good1:11211", "good2:11211"})

        with patch("rez.utils.memcached.Client_", side_effect=factory):
            self.assertEqual(Client([]).test_servers(), set())

    def test_set_get_delete_with_no_servers_are_noops(self) -> None:
        with patch("rez.utils.memcached.Client_") as mock_cls:
            client = Client([])
            client.set("k", "v")
            self.assertIs(client.get("k"), client.miss)
            client.delete("k")
            client.flush()
            client.disconnect()

        mock_cls.assert_not_called()

    def test_set_get_delete_roundtrip_and_none_value(self) -> None:
        _, factory = self._make_backend_factory()
        with patch("rez.utils.memcached.Client_", side_effect=factory):
            client = Client(["127.0.0.1:11211"])
            self.assertIs(client.get("missing"), client.miss)

            client.set("str_key", "hello", time=60, min_compress_len=128)
            self.assertEqual(client.get("str_key"), "hello")

            # Ability to cache None distinctly from a cache miss
            client.set("none_key", None)
            self.assertIsNone(client.get("none_key"))

            native = client.client
            self.assertEqual(native.set_calls[0][2:], (60, 128))  # type: ignore[attr-defined]

            client.delete("str_key")
            self.assertIs(client.get("str_key"), client.miss)

    def test_get_rejects_malformed_or_colliding_entries(self) -> None:
        _, factory = self._make_backend_factory()
        with patch("rez.utils.memcached.Client_", side_effect=factory):
            client = Client(["127.0.0.1:11211"])
            qkey = client._qualified_key("target")
            hkey = client.key_hasher(qkey)

            # Non-tuple entry
            client.client.backend.store[hkey] = "corrupt"  # type: ignore[attr-defined]
            self.assertIs(client.get("target"), client.miss)

            # Wrong-length tuple
            client.client.backend.store[hkey] = ("only_one",)  # type: ignore[attr-defined]
            self.assertIs(client.get("target"), client.miss)

            # Hash collision: different qualified key stored under same hashed key
            client.client.backend.store[hkey] = ("other:key", "wrong_val")  # type: ignore[attr-defined]
            self.assertIs(client.get("target"), client.miss)

    def test_flush_soft_and_hard(self) -> None:
        backends, factory = self._make_backend_factory()
        with patch("rez.utils.memcached.Client_", side_effect=factory):
            client = Client(["127.0.0.1:11211"], debug=False)
            client.set("k", "v1")
            self.assertEqual(client.get("k"), "v1")

            # Soft flush updates self.current without clearing backend
            client.flush(hard=False)
            self.assertNotEqual(client.current, "")
            self.assertFalse(client.current.startswith("flushed"))
            self.assertIs(client.get("k"), client.miss)
            backend = backends[("127.0.0.1:11211",)]
            self.assertEqual(backend.flushed_count, 0)

            # Debug soft flush prefixes tag with 'flushed'
            debug_client = Client(["127.0.0.1:11211"], debug=True)
            debug_client.flush(hard=False)
            self.assertTrue(debug_client.current.startswith("flushed"))

            # Hard flush clears server and resets stats
            client.flush(hard=True)
            self.assertEqual(backend.flushed_count, 1)
            self.assertEqual(backend.reset_stats_count, 1)
            self.assertEqual(backend.store, {})

    def test_get_stats_and_reset_stats(self) -> None:
        backends, factory = self._make_backend_factory()
        with patch("rez.utils.memcached.Client_", side_effect=factory):
            client = Client(["127.0.0.1:11211"])
            client.set("a", 1)
            stats = client.get_stats()
            self.assertEqual(stats, [("127.0.0.1:11211", {"curr_items": "1"})])

            client.reset_stats()
            self.assertEqual(backends[("127.0.0.1:11211",)].reset_stats_count, 1)

    def test_disconnect_only_when_servers_and_client_present(self) -> None:
        backends, factory = self._make_backend_factory()
        with patch("rez.utils.memcached.Client_", side_effect=factory):
            # Never accessed .client -> disconnect is a no-op
            c1 = Client(["127.0.0.1:11211"])
            c1.disconnect()
            self.assertEqual(backends, {})

            # Accessed .client -> disconnect calls disconnect_all
            c2 = Client(["127.0.0.1:11211"])
            _ = c2.client
            c2.disconnect()
            self.assertEqual(backends[("127.0.0.1:11211",)].disconnect_count, 1)

    def test_key_qualification_and_hashing(self) -> None:
        client = Client(["127.0.0.1:11211"])
        client.current = "tag1"
        qkey = client._qualified_key("mykey")
        self.assertEqual(
            qkey,
            f"{memcache_client_version}:{cache_interface_version}:tag1:mykey",
        )

        hashed = Client._key_hash(qkey)
        self.assertEqual(len(hashed), 32)

        debug_hashed = Client._debug_key_hash("a:b c/d!" + "x" * SERVER_MAX_KEY_LENGTH)
        self.assertLessEqual(len(debug_hashed), SERVER_MAX_KEY_LENGTH)
        self.assertRegex(debug_hashed, r"^[0-9a-zA-Z_]+$")


class TestScopedInstanceAndPooling(TestBase):
    def test_memcached_client_shares_across_nested_scopes(self) -> None:
        backends: dict[tuple[str, ...], _FakeMemcacheBackend] = {}

        def factory(servers):
            return _FakeMemcacheClient(servers, backends=backends)

        with patch("rez.utils.memcached.Client_", side_effect=factory):
            with memcached_client(["127.0.0.1:11211"], debug=False) as outer:
                _ = outer.client
                with memcached_client(["127.0.0.1:11211"], debug=False) as inner:
                    self.assertIs(outer, inner)
                # Inner exit must not disconnect yet
                self.assertEqual(backends[("127.0.0.1:11211",)].disconnect_count, 0)
            # Outer exit disconnects
            self.assertEqual(backends[("127.0.0.1:11211",)].disconnect_count, 1)

    def test_memcached_client_handles_acquire_exception(self) -> None:
        with patch.object(scoped_instance_manager, "acquire", side_effect=RuntimeError("boom")):
            with patch.object(scoped_instance_manager, "release") as mock_release:
                with self.assertRaises(RuntimeError):
                    with memcached_client(["127.0.0.1:11211"]):
                        pass
                mock_release.assert_not_called()

    def test_scoped_instance_manager_is_thread_local(self) -> None:
        results: list[Client] = []

        def worker():
            with memcached_client(["127.0.0.1:11211"]) as c:
                results.append(c)

        with memcached_client(["127.0.0.1:11211"]) as main_client:
            t = threading.Thread(target=worker)
            t.start()
            t.join()
            self.assertEqual(len(results), 1)
            self.assertIsNot(results[0], main_client)

    def test_pool_memcached_connections_regular_and_generator(self) -> None:
        mock_cm = MagicMock()
        enter_count = 0
        exit_count = 0

        class _CountingCM:
            def __enter__(self):
                nonlocal enter_count
                enter_count += 1
                return mock_cm

            def __exit__(self, *args):
                nonlocal exit_count
                exit_count += 1

        with patch("rez.utils.memcached.memcached_client", return_value=_CountingCM()):
            @pool_memcached_connections
            def add(a, b):
                """Add two numbers."""
                return a + b

            self.assertEqual(add.__name__, "add")
            self.assertEqual(add.__doc__, "Add two numbers.")
            self.assertEqual(add(2, 3), 5)
            self.assertEqual((enter_count, exit_count), (1, 1))

            @pool_memcached_connections
            def gen(n):
                """Yield range."""
                for i in range(n):
                    yield i

            self.assertEqual(gen.__name__, "gen")
            g = gen(3)
            self.assertEqual((enter_count, exit_count), (1, 1))
            self.assertEqual(next(g), 0)
            self.assertEqual((enter_count, exit_count), (2, 1))
            self.assertEqual(list(g), [1, 2])
            self.assertEqual((enter_count, exit_count), (2, 2))


class TestMemcachedDecorator(TestBase):
    def _make_factory(self):
        backends: dict[tuple[str, ...], _FakeMemcacheBackend] = {}

        def factory(servers):
            return _FakeMemcacheClient(servers, backends=backends)

        return backends, factory

    def test_disabled_when_no_servers(self) -> None:
        calls = 0

        @memcached(None)
        def fn(x):
            nonlocal calls
            calls += 1
            if x < 0:
                return DoNotCache("neg")
            return x * 2

        self.assertEqual(fn(3), 6)
        self.assertEqual(fn(3), 6)
        self.assertEqual(calls, 2)
        self.assertEqual(fn(-1), "neg")

        # forget() is still callable when disabled
        fn.forget()

    def test_caches_function_hits_misses_and_forget(self) -> None:
        _, factory = self._make_factory()
        calls = 0

        with patch("rez.utils.memcached.Client_", side_effect=factory):
            @memcached(["127.0.0.1:11211"])
            def compute(x, y=10):
                """Compute sum."""
                nonlocal calls
                calls += 1
                return x + y

            self.assertEqual(compute.__name__, "compute")
            self.assertEqual(compute.__doc__, "Compute sum.")
            self.assertTrue(callable(compute.__wrapped__))

            self.assertEqual(compute(1, y=2), 3)
            self.assertEqual(compute(1, y=2), 3)
            self.assertEqual(calls, 1)

            self.assertEqual(compute(1, y=3), 4)
            self.assertEqual(calls, 2)

            compute.forget()
            # Outside a memcached_client scope, soft-flush is discarded on exit;
            # inside a shared scope, the flushed tag persists for subsequent calls.
            with memcached_client(["127.0.0.1:11211"]):
                self.assertEqual(compute(1, y=2), 3)
                self.assertEqual(calls, 2)
                compute.forget()
                self.assertEqual(compute(1, y=2), 3)
                self.assertEqual(calls, 3)

    def test_zero_arg_function_default_key(self) -> None:
        _, factory = self._make_factory()
        calls = 0

        with patch("rez.utils.memcached.Client_", side_effect=factory):
            @memcached(["127.0.0.1:11211"])
            def get_constant():
                nonlocal calls
                calls += 1
                return 42

            self.assertEqual(get_constant(), 42)
            self.assertEqual(get_constant(), 42)
            self.assertEqual(calls, 1)

    def test_caches_none_and_respects_do_not_cache(self) -> None:
        _, factory = self._make_factory()
        calls = 0

        with patch("rez.utils.memcached.Client_", side_effect=factory):
            @memcached(["127.0.0.1:11211"])
            def maybe(flag):
                nonlocal calls
                calls += 1
                if flag == "skip":
                    return DoNotCache("uncached")
                return None

            self.assertIsNone(maybe("none"))
            self.assertIsNone(maybe("none"))
            self.assertEqual(calls, 1)

            self.assertEqual(maybe("skip"), "uncached")
            self.assertEqual(maybe("skip"), "uncached")
            self.assertEqual(calls, 3)

    def test_custom_key_and_translators_and_storage_args(self) -> None:
        backends, factory = self._make_factory()
        clients: list[_FakeMemcacheClient] = []

        def capturing_factory(servers):
            client = factory(servers)
            clients.append(client)
            return client

        with patch("rez.utils.memcached.Client_", side_effect=capturing_factory):
            @memcached(
                ["127.0.0.1:11211"],
                key=lambda x: f"custom:{x}",
                to_cache=lambda val, x: f"encoded:{val}:{x}",
                from_cache=lambda val, x: f"decoded:{val}:{x}",
                time=30,
                min_compress_len=64,
            )
            def get_val(x):
                return x * 10

            # Miss returns raw result
            self.assertEqual(get_val(2), 20)
            # Hit passes cached value through from_cache
            self.assertEqual(get_val(2), "decoded:encoded:20:2:2")

            backend = backends[("127.0.0.1:11211",)]
            self.assertEqual(len(backend.store), 1)
            self.assertEqual(len(clients[0].set_calls), 1)
            _, stored_pair, set_time, set_min_compress = clients[0].set_calls[0]
            self.assertEqual(set_time, 30)
            self.assertEqual(set_min_compress, 64)
            qkey, _ = stored_pair  # type: ignore[misc]
            self.assertTrue(qkey.endswith(":custom:2"))

    def test_default_key_handles_methods_and_classmethods(self) -> None:
        _, factory = self._make_factory()

        class Widget:
            calls = 0

            @memcached(["127.0.0.1:11211"])
            def method(self, x):
                Widget.calls += 1
                return x + 1

            @classmethod
            @memcached(["127.0.0.1:11211"])
            def clsmethod(cls, x):
                Widget.calls += 1
                return x + 2

        with patch("rez.utils.memcached.Client_", side_effect=factory):
            w1 = Widget()
            w2 = Widget()
            # `self` is stripped from default_key, so w1 and w2 share cache entry
            self.assertEqual(w1.method(5), 6)
            self.assertEqual(w2.method(5), 6)
            self.assertEqual(Widget.calls, 1)

            self.assertEqual(Widget.clsmethod(5), 7)
            self.assertEqual(Widget.clsmethod(5), 7)
            self.assertEqual(Widget.calls, 2)

    def test_default_key_raises_on_unhashable_args(self) -> None:
        _, factory = self._make_factory()

        with patch("rez.utils.memcached.Client_", side_effect=factory):
            @memcached(["127.0.0.1:11211"])
            def fn(items):
                return len(items)

            with self.assertRaises(TypeError):
                fn([1, 2, 3])
