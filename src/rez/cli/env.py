from rez.resolved_context import ResolvedContext
from rez.util import get_epoch_time_from_str, pretty_env_dict
from rez.settings import settings
import select
import sys


def command(opts, parser=None):
    if opts.input:
        rc = ResolvedContext.load(opts.input)
        rc.validate()
    else:
        t = get_epoch_time_from_str(opts.time) if opts.time else None
        pkg_paths = settings.nonlocal_packages_path if opts.no_local else None
        pkg_paths = [] if opts.bootstrap_only else pkg_paths

        rc = ResolvedContext(opts.PKG,
                             timestamp=t,
                             package_paths=pkg_paths,
                             add_implicit_packages=(not opts.no_implicit),
                             max_fails=opts.max_fails,
                             verbosity=opts.resolve_verbosity,
                             store_failure=bool(opts.output))
        if opts.output:
            if not opts.quiet:
                rc.print_info()
            rc.save(opts.output)
            sys.exit(0 if rc.success else 1)

    # generally shells will behave as though the '-s' flag was not present, if
    # no stdin is available. So here we replicate this behaviour.
    if opts.stdin and not select.select([sys.stdin,],[],[],0.0)[0]:
        opts.stdin = False

    returncode,_,_ = rc.execute_shell(shell=opts.shell,
                                      rcfile=opts.rcfile,
                                      norc=opts.norc,
                                      command=opts.command,
                                      stdin=opts.stdin,
                                      quiet=opts.quiet,
                                      block=True)
    sys.exit(returncode)
