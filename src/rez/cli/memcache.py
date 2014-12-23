"""
Manage and query memcache server(s).
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--flush", action="store_true",
        help="flush all cache entries")
    parser.add_argument(
        "--reset-stats", action="store_true",
        help="reset statistics")


def command(opts, parser, extra_arg_groups=None):
    from rez.memcache import memcache_client
    from rez.utils.yaml import dump_yaml

    if opts.flush:
        memcache_client.flush(hard=True)
        print "memcached servers are flushed."
        return

    if opts.reset_stats:
        memcache_client.reset_stats()
        print "memcached servers are stat reset."
        return

    data = memcache_client.get_stats()
    if data:
        txt = dump_yaml(data)
        print txt
