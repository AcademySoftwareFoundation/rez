"""
Manage and query memcache server(s).
"""


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


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.utils.memcached import Client
    from rez.utils.yaml import dump_yaml
    from rez.utils.formatting import columnise, readable_time_duration, \
        readable_memory_size
    import sys

    memcache_client = Client(servers=config.memcached_uri)

    if not memcache_client:
        print >> sys.stderr, "memcaching is not enabled."
        sys.exit(1)

    if opts.flush:
        memcache_client.flush(hard=True)
        print "memcached servers are flushed."
        return

    if opts.reset_stats:
        memcache_client.reset_stats()
        print "memcached servers are stat reset."
        return

    stats = memcache_client.get_stats()
    if opts.stats:
        if stats:
            txt = dump_yaml(stats)
            print txt
        return

    # print stats summary
    if not stats:
        print >> sys.stderr, "memcached servers are not responding."
        return

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
    print '\n'.join(columnise(rows))
