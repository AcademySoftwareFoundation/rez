from rez.resolved_context import ResolvedContext
from rez.util import get_epoch_time_from_str, pretty_env_dict
from rez.settings import settings
import select
import sys
import os


def command(opts, parser=None):
    if opts.input:
        rc = ResolvedContext.load(opts.input)
        rc.validate()
    else:
        t = get_epoch_time_from_str(opts.time) if opts.time else None

        if opts.paths is None:
            pkg_paths = settings.nonlocal_packages_path if opts.no_local else None
        else:
            pkg_paths = (opts.paths or "").split(os.pathsep)
            pkg_paths = [x for x in pkg_paths if x]

        rc = ResolvedContext(opts.PKG,
                             timestamp=t,
                             package_paths=pkg_paths,
                             add_implicit_packages=(not opts.no_implicit),
                             add_bootstrap_path=(not opts.no_bootstrap),
                             verbosity=opts.verbose)

    success = (rc.status == "solved")
    if not success:
        rc.print_info(buf=sys.stderr)

    if opts.output:
        rc.save(opts.output)
        sys.exit(0 if success else 1)

    # generally shells will behave as though the '-s' flag was not present when
    # no stdin is available. So here we replicate this behaviour.
    if opts.stdin and not select.select([sys.stdin,],[],[],0.0)[0]:
        opts.stdin = False

    quiet = opts.quiet or bool(opts.command)

    returncode,_,_ = rc.execute_shell(shell=opts.shell,
                                      rcfile=opts.rcfile,
                                      norc=opts.norc,
                                      command=opts.command,
                                      stdin=opts.stdin,
                                      quiet=quiet,
                                      block=True)
    sys.exit(returncode)
