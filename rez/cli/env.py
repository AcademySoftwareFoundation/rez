from rez.resolved_context import ResolvedContext
from rez.util import get_epoch_time_from_str, pretty_env_dict
from rez.settings import settings
import sys


def command(opts, parser=None):
    if opts.rxt:
        rc = ResolvedContext.load(opts.rxt)
        rc.validate()
    else:
        t = get_epoch_time_from_str(opts.time) if opts.time else None
        pkg_paths = settings.nonlocal_packages_path if opts.no_local else None
        rc = ResolvedContext(opts.PKG,
                             timestamp=t,
                             package_paths=pkg_paths,
                             add_implicit_packages=(not opts.no_implicit),
                             max_fails=opts.max_fails,
                             store_failure=bool(opts.output))
        if opts.output:
            if not opts.quiet:
                rc.print_info()
            rc.save(opts.output)
            sys.exit(0 if rc.success else 1)

    if opts.print_:
        if opts.print_ == 'resolve':
            print ' '.join(x.short_name() for x in rc.resolved_packages)
        elif opts.print_ == 'context':
            rc.print_info(verbose=True)
        elif opts.print_ == 'script':
            print rc.get_shell_code(shell=opts.shell)
        elif opts.print_ == 'dict':
            env = rc.get_environ()
            print pretty_env_dict(env)
        print
        sys.exit(0)

    returncode,_,_ = rc.execute_shell(shell=opts.shell,
                                      rcfile=opts.rcfile,
                                      norc=opts.norc,
                                      command=opts.command,
                                      stdin=opts.stdin,
                                      quiet=opts.quiet,
                                      block=True)
    sys.exit(returncode)
