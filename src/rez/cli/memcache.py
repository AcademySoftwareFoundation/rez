"""
Manage and query memcache server(s).
"""
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--flush", action="store_true",
        help="flush all cache entries")
    parser.add_argument(
        "--stats", action="store_true",
        help="list stats")
    parser.add_argument(
        "--reset-stats", action="store_true",
        help="reset statistics")
    parser.add_argument(
        "--poll", action="store_true",
        help="continually poll, showing get/sets per second")
    parser.add_argument(
        "--interval", type=float, metavar="SECS", default=1.0,
        help="interval (in seconds) used when polling (default: %(default)s)")
    parser.add_argument(
        "--warm", action="store_true",
        help="warm the cache server with visible packages")


def poll(client, interval):
    from rez.utils.memcached import Client
    import time

    prev_entry = None
    print("%-64s %-16s %-16s %-16s %-16s %-16s" \
        % ("SERVER", "CONNS", "GET/s", "SET/s", "TEST_GET", "TEST_SET"))

    while True:
        stats = dict(client.get_stats())
        entry = (time.time(), stats)

        if prev_entry:
            prev_t, prev_stats = prev_entry
            t, stats = entry

            dt = t - prev_t
            for instance, payload in stats.items():
                prev_payload = prev_stats.get(instance)
                if payload and prev_payload:
                    # stats
                    gets = int(payload["cmd_get"]) - int(prev_payload["cmd_get"])
                    sets = int(payload["cmd_set"]) - int(prev_payload["cmd_set"])
                    gets_per_sec = gets / dt
                    sets_per_sec = sets / dt

                    # test get/set
                    uri = instance.split()[0]
                    client = Client([uri], debug=True)
                    t1 = time.time()
                    client.set("__TEST__", 1)
                    t2 = time.time()
                    test_set = t2 - t1
                    client.get("__TEST__")
                    test_get = time.time() - t2

                    nconns = int(payload["curr_connections"])

                    print("%-64s %-16d %-16g %-16g %-16g %-16g" \
                        % (instance, nconns, gets_per_sec, sets_per_sec,
                           test_get, test_set))

        prev_entry = entry
        time.sleep(interval)


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.packages_ import iter_package_families, iter_packages
    from rez.utils.yaml import dump_yaml
    from rez.utils.memcached import Client
    from rez.utils.formatting import columnise, readable_time_duration, \
        readable_memory_size
    import sys

    memcache_client = Client(servers=config.memcached_uri,
                             debug=config.debug_memcache)

    if not memcache_client:
        print("memcaching is not enabled.", file=sys.stderr)
        sys.exit(1)

    if opts.poll:
        poll(memcache_client, opts.interval)
        return

    if opts.flush:
        memcache_client.flush(hard=True)
        print("memcached servers are flushed.")
        return

    if opts.warm:
        seen = set()
        paths = config.nonlocal_packages_path

        for family in iter_package_families(paths=paths):
            if family.name in seen:
                continue

            for package in iter_packages(family.name, paths=paths):
                if opts.verbose:
                    print("warming: %s" % package.qualified_name)

                # forces package definition load, which puts in memcache
                _ = package.data  # noqa

            seen.add(family.name)

        print("memcached servers are warmed.")
        return

    if opts.reset_stats:
        memcache_client.reset_stats()
        print("memcached servers are stat reset.")
        return

    def _fail():
        print("memcached servers are not responding.", file=sys.stderr)
        sys.exit(1)

    stats = memcache_client.get_stats()
    if opts.stats:
        if stats:
            txt = dump_yaml(stats)
            print(txt)
        else:
            _fail()
        return

    # print stats summary
    if not stats:
        _fail()

    rows = [["CACHE SERVER", "UPTIME", "HITS", "MISSES", "HIT RATIO", "MEMORY", "USED"],
            ["------------", "------", "----", "------", "---------", "------", "----"]]

    for server_id, stats_dict in stats:
        server_uri = server_id.split()[0]
        uptime = int(stats_dict.get("uptime", 0))
        hits = int(stats_dict.get("get_hits", 0))
        misses = int(stats_dict.get("get_misses", 0))
        memory = int(stats_dict.get("limit_maxbytes", 0))
        used = int(stats_dict.get("bytes", 0))

        hit_ratio = float(hits) / max(hits + misses, 1)
        hit_percent = int(hit_ratio * 100.0)
        used_ratio = float(used) / max(memory, 1)
        used_percent = int(used_ratio * 100.0)

        row = (server_uri,
               readable_time_duration(uptime),
               str(hits),
               str(misses),
               "%d%%" % hit_percent,
               readable_memory_size(memory),
               "%s (%d%%)" % (readable_memory_size(used), used_percent))

        rows.append(row)
    print('\n'.join(columnise(rows)))


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
