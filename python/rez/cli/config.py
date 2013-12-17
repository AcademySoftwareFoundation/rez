'''
Resolve a configuration request.

Output from this util can be used to setup said configuration (rez-env does this).
'''
import os
import sys
from rez.cli import error, output

def setup_shared_parser(parser):
    '''
    options shared by config and env
    '''
    import rez.public_enums as enums
    # also shared by rez-build:
    parser.add_argument("-m", "--mode", dest="mode",
                        default=enums.RESOLVE_MODE_LATEST,
                        choices=[enums.RESOLVE_MODE_LATEST,
                                 enums.RESOLVE_MODE_EARLIEST,
                                 enums.RESOLVE_MODE_NONE],
                        help="set resolution mode")
    parser.add_argument("-q", "--quiet", dest="quiet",
                        action="store_true", default=False,
                        help="Suppress unnecessary output")
    parser.add_argument("-o", "--no-os", dest="no_os",
                        action="store_true", default=False,
                        help="stop rez from implicitly requesting the operating system package")
    parser.add_argument("-b", "--build", "--build-requires", dest="buildreqs",
                        action="store_true", default=False,
                        help="include build-only package requirements")
    parser.add_argument("--no-cache", dest="no_cache",
                        action="store_true", default=False,
                        help="disable caching")
    # also shared by rez-build:
    parser.add_argument("-g", "--ignore-archiving", dest="ignore_archiving",
                        action="store_true", default=False,
                        help="silently ignore packages that have been archived")
    # also shared by rez-build:
    parser.add_argument("-u", "--ignore-blacklist", dest="ignore_blacklist",
                        action="store_true", default=False,
                        help="include packages that are blacklisted")
    # also shared by rez-build:
    parser.add_argument("-d", "--no-assume-dt", dest="no_assume_dt",
                        action="store_true", default=False,
                        help="do not assume dependency transitivity")
    # also shared by rez-build (with -t instead of -i):
    parser.add_argument("-i", "--time", dest="time", type=int,
                        default=0,
                        help="ignore packages newer than the given epoch time [default = current time]")
    parser.add_argument("--no-local", dest="no_local",
                        action="store_true", default=False,
                        help="don't load local packages")

def setup_parser(parser):
    # usage = "usage: %prog [options] pkg1 pkg2 ... pkgN"
    parser.add_argument("pkg", nargs='+',
                        help='list of package names')
    parser.add_argument("-v", "--verbosity", dest="verbosity", type=int,
                        default=0, choices=[0, 1, 2],
                        help="set verbosity")
    parser.add_argument("--version", dest="version", action="store_true",
                        default=False,
                        help="print the rez version number and exit")
    parser.add_argument("--max-fails", dest="max_fails", type=int,
                        default=-1,
                        help="exit when the number of failed configuration attempts exceeds N [default = no limit]")
    parser.add_argument("--dot-file", dest="dot_file", type=str,
                        default="",
                        help="write the dot-graph to the file specified (dot, gif, jpg, png, pdf supported). "
                        "Note that if resolution fails, the last failed attempt will still produce an image. "
                        "You can use --dot-file in combination with --max-fails to debug resolution failures.")
    parser.add_argument("--env-file", dest="env_file", type=str,
                        default="",
                        help="write commands which, if run, would produce the configured environment")
    parser.add_argument("--print-env", dest="print_env", action="store_true",
                        default=False,
                        help="print commands which, if run, would produce the configured environment")
    parser.add_argument("--print-packages", dest="print_pkgs", action="store_true",
                        default=False,
                        help="print resolved packages for this configuration")
    parser.add_argument("--print-dot", dest="print_dot", action="store_true",
                        default=False,
                        help="output a dot-graph representation of the configuration resolution")
    parser.add_argument("--meta-info", dest="meta_info", type=str,
                        help="Bake metadata into env-vars. Eg: --meta-info=tools,priority")
    parser.add_argument("--meta-info-shallow", dest="meta_info_shallow", type=str,
                        help="Same as --meta-info, but only bakes data for directly requested packages.")
    parser.add_argument("--wrapper", dest="wrapper", action="store_true",
                        default=False,
                        help="set to true if creating a wrapper environment")
    parser.add_argument("--no-catch", dest="no_catch", action="store_true",
                        default=False,
                        help="debugging option, turn on to see python exception on error")
    parser.add_argument("--no-path-append", dest="no_path_append", action="store_true",
                        default=False,
                        help="don't append system-specific paths to PATH")

    # settings shared with rez-env
    setup_shared_parser(parser)

    return parser

def command(opts):

    if opts.version:
        output(os.getenv("REZ_VERSION"))
        sys.exit(0)

    # force quiet with some options
    do_quiet = opts.quiet or opts.print_env or opts.print_pkgs or opts.print_dot

    # validate time
    time_epoch = opts.time

    # parse out meta bake
    meta_vars = (opts.meta_info or '').replace(',', ' ').strip().split()
    shallow_meta_vars = (opts.meta_info_shallow or '').replace(',', ' ').strip().split()

    # hide local pkgs
    if opts.no_local:
        import rez.util
        rez.util.hide_local_packages()

    import rez.config as dc
    ##########################################################################################
    # construct package request
    ##########################################################################################
    resolver = dc.Resolver(opts.mode, do_quiet, opts.verbosity, opts.max_fails,
                           time_epoch, opts.buildreqs, not opts.no_assume_dt,
                           not opts.no_cache)

    if opts.no_catch:
        result = resolver.resolve(opts.pkg, opts.no_os,
                                  opts.no_path_append, opts.wrapper,
                                  meta_vars, shallow_meta_vars)
    else:
        result = resolver.guarded_resolve(opts.pkg, opts.no_os,
                                          opts.no_path_append, opts.wrapper,
                                          meta_vars, shallow_meta_vars,
                                          opts.dot_file, opts.print_dot)

        if not result:
            sys.exit(1)

    pkg_ress, commands, dot_graph, num_fails = result

    ##########################################################################################
    # print result
    ##########################################################################################

    if not do_quiet:
        print "\nsuccessful configuration found after " + str(num_fails) + " failed attempts."

    if opts.print_env or opts.env_file:
        import rez.rex as rex
        # TODO: support other shells
        script = rex.interpret(commands, shell='bash')

    if opts.print_env:
        for env_cmd in script.split('\n'):
            output(env_cmd)

    if opts.print_pkgs:
        for pkg_res in pkg_ress:
            output(pkg_res.short_name())

    if opts.env_file:
        with open(opts.env_file, 'w') as f:
            f.write(script)



#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
