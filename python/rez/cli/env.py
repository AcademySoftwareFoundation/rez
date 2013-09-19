'''
Invoke a shell based on a configuration request.
'''

import argparse
import sys
import os
from rez.cli import error, output
from . import config as rez_cli_config

# _g_usage = "rez-env [options] pkg1 pkg2 ... pkgN"


# class OptionParser2(optparse.OptionParser):
#     def exit(self, status=0, msg=None):
#         if msg:
#             sys.stderr.write(msg)
#         sys.exit(1)

def setup_parser(parser):

    parser.add_argument("pkg", nargs='+',
                        help='list of package names')

    # settings shared with `rez config`
    rez_cli_config.setup_shared_parser(parser)

    # settings unique to `rez env`
    parser.add_argument("-p", "--prompt", dest="prompt", type=str,
                        default=">",
                        help="Set the prompt decorator [default=%(default)s]")
    parser.add_argument("-r", "--rcfile", dest="rcfile", type=str,
                        default='',
                        help="Source this file after the new shell is invoked")
    parser.add_argument("--tmpdir", dest="tmpdir", type=str,
                        default=None,
                        help="Set the temp directory manually, /tmp otherwise")
    parser.add_argument("--propogate-rcfile", dest="prop_rcfile",
                        action="store_true", default=False,
                        help="Propogate rcfile into subshells")
    parser.add_argument("-s", "--stdin", dest="stdin",
                        action="store_true", default=False,
                        help="Read commands from stdin, rather than starting an interactive shell")
    parser.add_argument("-a", "--add-loose",
                        # FIXME: remove this option:
                        "--add_loose",
                        dest="add_loose",
                        action="store_true", default=False,
                        help="Add mode (loose). Packages will override or add to the existing request list")
    parser.add_argument("-t", "--add-strict",
                        # FIXME: remove this option:
                        "--add_strict",
                        dest="add_strict",
                        action="store_true", default=False,
                        help="Add mode (strict). Packages will override or add to the existing resolve list")
    parser.add_argument("-f", "--view-fail", "--view_fail", dest="view_fail", type=int,
                        default=-1,
                        help="View the dotgraph for the Nth failed config attempt")

def _autowrappers(pkglist):
    return any([pkg for pkg in pkglist if '(' in pkg])

def command(opts):
    import tempfile
    autowrappers = _autowrappers(opts.pkg)
    raw_request = os.getenv('REZ_RAW_REQUEST', '')
    if opts.add_loose or opts.add_strict:
        if autowrappers:
            error("Patching of auto-wrapper environments is not yet supported.")
            sys.exit(1)

        if _autowrappers(raw_request.split()):
            error("Patching from auto-wrapper environments is not yet supported.")
            sys.exit(1)

    ##############################################################################
    # switch to auto-wrapper rez-env if bracket syntax is detected
    # TODO patching of wrapper envs is not yet supported.
    ##############################################################################
    if autowrappers:
        if not opts.tmpdir:
            opts.tmpdir = tempfile.mkdtemp()

        os.environ['REZ_TMP_DIR'] = opts.tmpdir

        import rez.cli.env_autowrappers
        rez.cli.env_autowrappers.command(opts)

        os.environ['REZ_PACKAGES_PATH'] = opts.tmpdir + ':' + os.environ['REZ_PACKAGES_PATH']
        packages_file = os.path.join(opts.tmpdir, 'packages.txt')
        with open(packages_file, 'r') as f:
            packages = f.read()
#         unset _REZ_ENV_OPT_ADD_LOOSE
#         unset _REZ_ENV_OPT_ADD_STRICT
        opts.no_cache = True
    else:
        packages = ' '.join(opts.pkg)

    ##############################################################################
    # apply patching, if any
    ##############################################################################

    if opts.add_loose:
        ctxt_pkg_list = os.environ['REZ_REQUEST']
        print_pkgs = True
    elif opts.add_strict:
        ctxt_pkg_list = os.environ['REZ_RESOLVE']
        print_pkgs = True
    else:
        ctxt_pkg_list = None
        print_pkgs = False

    if not ctxt_pkg_list:
        pkg_list = packages
    else:
        import rez.rez_parse_request as rpr
        base_pkgs, subshells = rpr.parse_request(ctxt_pkg_list + " | " + packages)
        pkg_list = rpr.encode_request(base_pkgs, subshells)

    if print_pkgs and not opts.quiet:
        quotedpkgs = ["'%s'" % pkg for pkg in pkg_list.split()]
        print "request: %s" % ' '.join(quotedpkgs)


    ##############################################################################
    # call rez-config, and write env into bake file
    ##############################################################################

    context_file = tempfile.mktemp(dir=opts.tmpdir, prefix='.rez-context.')
    source_file = context_file + ".source"
    dot_file = context_file + ".dot"

    # setup args for rez-config
    # TODO: provide a util which reads defaults for the cli function
    kwargs = dict(verbosity=0,
                  version=False,
                  print_env=False,
                  print_dot=False,
                  meta_info='tools',
                  meta_info_shallow='tools',
                  env_file=context_file,
                  dot_file=dot_file,
                  max_fails=opts.view_fail,
                  wrapper=False,
                  no_catch=False,
                  no_path_append=False,
                  print_pkgs=False)
    # copy settings that are the same between rez-env and rez-config
    kwargs.update(vars(opts))
    # override values that differ
    kwargs['quiet'] = True
    kwargs['pkg'] = pkg_list.split()

    config_opts = argparse.Namespace(**kwargs)
    try:
        rez_cli_config.command(config_opts)
    except Exception, err:
        error(err)
        try:
            # TODO: change cli convention so that commands do not call sys.exit
            # and we can actually catch this exception
            if opts.view_fail != "-1":
                from . import dot as rez_cli_dot
                dot_opts = argparse.Namespace(conflict_only=True,
                                              package="",
                                              dotfile=dot_file)
                rez_cli_dot.command(dot_opts)
            sys.exit(1)
        finally:
            if os.path.exists(context_file):
                os.remove(context_file)
            if os.path.exists(dot_file):
                os.remove(dot_file)

    if autowrappers:
        with open(context_file, 'w') as f:
            f.write("export REZ_RAW_REQUEST='%s'\n" % packages)

    ##############################################################################
    # spawn the new shell, sourcing the bake file
    ##############################################################################

    cmd = ''
    if not raw_request:
        cmd += "export REZ_RAW_REQUEST='%s';" % packages

    cmd += "export REZ_CONTEXT_FILE=%s;" % context_file
    cmd += 'export REZ_ENV_PROMPT="%s";' % (os.getenv('REZ_ENV_PROMPT', '') + opts.prompt)
 
    if opts.stdin:
        cmd += "source %s;" % context_file
        if not opts.rcfile:
            if os.path.exists(os.path.expanduser('~/.bashrc')):
                cmd += "source ~/.bashrc &> /dev/null;"
        else:
            cmd += "source %s;" % opts.rcfile
#                 if [ $? -ne 0 ]; then
#                     exit 1
#                 fi
 
        # ensure that rez-config is available no matter what (eg .bashrc might not exist,
        # rcfile might not source rez-config)
        cmd += "source $REZ_PATH/init.sh;"
        cmd += "bash -s;"
        cmd += "ret=$?;"
    else:
        with open(source_file, 'w') as f:
            f.write("source %s\n" % context_file)
            if opts.rcfile:
                f.write("source %s\n" % opts.rcfile)

            f.write("source rez-env-bashrc\n")
            if not opts.quiet:
                f.write("echo\n")
                f.write("echo You are now in a new environment.\n")
                f.write("rez-context-info\n")
 
        cmd += "bash --rcfile %s;" % source_file
        cmd += "ret=$?;"
        cmd += "rm -f %s;" % source_file

    cmd += "rm -f %s;" % context_file
    cmd += "rm -f %s;" % dot_file
    output(cmd)
    #print "exit $ret;"


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
