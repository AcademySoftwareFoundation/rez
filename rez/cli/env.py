from rez.resolved_context import ResolvedContext
from rez.util import get_epoch_time_from_str
from rez.settings import settings
import sys



def command(opts, parser=None):
    if opts.rxt:
        rc = ResolvedContext.load(opts.rxt)
        if not opts.force_rxt:
            rc.validate()
    else:
        t = get_epoch_time_from_str(opts.time) if opts.time else None
        pkg_paths = settings.nonlocal_packages_path if opts.no_local else None
        rc = ResolvedContext(opts.PKG,
                             timestamp=t,
                             package_paths=pkg_paths,
                             add_implicit_packages=(not opts.no_implicit),
                             store_failure=bool(opts.output))
        if opts.output:
            if not opts.quiet:
                rc.print_info()
            rc.save(opts.output)
            sys.exit(0 if rc.success else 1)

    returncode,_,_ = rc.execute_shell(shell=opts.shell,
                                      rcfile=opts.rcfile,
                                      command=opts.command,
                                      stdin=opts.stdin,
                                      quiet=opts.quiet,
                                      block=True)
    sys.exit(returncode)
