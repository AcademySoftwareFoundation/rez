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

# autowrapper constants:
_g_alias_context_filename = os.getenv('REZ_PATH') + '/template/wrapper.sh'
_g_context_filename = 'package.context'
_g_packages_filename = 'packages.txt'
_g_dot_filename = _g_context_filename + '.dot'
_g_tools_filename = _g_context_filename + '.tools'

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

def get_tools_from_commands(commands):
    '''
    REZ_META_ is formatted like so:
        pkgname1:val1,va2 pkgname2:val1,val2
    '''
    tools = []
    for cmd in commands:
        # FIXME: search through the metadata on resolved packages instead of parsing strings
        if cmd.name == 'setenv' and cmd.key == 'REZ_META_SHALLOW_TOOLS':
            toks = cmd.value.split()
            for tok in toks:
                values = tok.split(':', 1)[1]
                aliases = values.split(',')
                tools.extend(aliases)
            return tools

def _contains_autowrappers(pkglist):
    return any([pkg for pkg in pkglist if '(' in pkg])

def resolve_autowrappers(opts):
    '''
    Create rez-env wrappers on the fly.

    Rez-env automatically switches to this mode if it detects the syntax
    described below... Consider the following invocation of rez-env:

    ]$ rez-env (maya mutils-1.4) (houdini-11 hutils-3.2.2 mysops-5)

    Each one of the sections in parentheses becomes its own subshell. Any
    package in that subshell that has executables listed in a 'tools' section of
    its package.yaml file, will have those executables exposed as 'alias'
    scripts. For example, after running the above command, running 'maya' would
    actually jump into the first subshell and then execute maya inside of it.
    Now consider:

    ]$ rez-env fx_(maya mfx-4.3) (maya manim-2.2)_anim

    Here, one subshell is given a prefix, and another a suffix. After running
    the above command, we would expect the executables "fx_maya" and "maya_anim"
    to exist. The prefix/suffix is applied to all tools found within that
    subshell.

    Each subshell has a name, by default this name is the pre/postfixed version
    of the first pkg in the shell, so eg 'fx_maya' from above. To set this
    manually, do this:

    ]$ rez-env fx_(mayafx: maya mfx-4.3)

    Rez can also take a list of separate requests and 'merge' them together, use
    the pipe operator to do this. Later requests override earlier ones. For
    example, consider:

    rez-env (maya foo-1) | (maya foo-2)  # ==> becomes (maya foo-2)

    Here, the user was asking for 'foo-1' initially, but this was then overriden
    to 'foo-2' in the second request. This functionality is provided for two
    reasons - (a) it's used internally when using patching; (b) it can be
    utilised by rez users, who want to implement their own environment
    management system, and have a need to create a working environment based on
    a heirarchical series of overriding config files.

    Lastly, the '^' operator can be used to *remove* packages from the request, eg:

    rez-env (maya foo-1) | (maya ^foo)  # ==> becomes (maya)
    '''
    import stat
    import os.path
    import shutil
    import pyparsing as pp
    import rez.parse_request as rpr
    import rez.rex as rex
    import rez.config as dc

#     (opts, args) = p.parse_args(sys.argv[2:])

    pkgs_str = str(' ').join(opts.pkg).strip()

    if opts.no_local:
        import rez.util
        rez.util.hide_local_packages()


    base_pkgs, subshells = rpr.parse_request(pkgs_str)
    all_pkgs = base_pkgs[:]

    tmpdir = opts.tmpdir
    if not opts.quiet and not opts.stdin:
        print 'Building into ' + tmpdir + '...'

    # make a copy of rcfile, if specified. We need to propagate this into the subshells
    rcfile_copy = None
    if opts.rcfile and opts.prop_rcfile and os.path.isfile(opts.rcfile):
        rcfile_copy = os.path.join(tmpdir, "rcfile.sh")
        shutil.copy(opts.rcfile, rcfile_copy)

    with open(_g_alias_context_filename, 'r') as f:
        wrapper_template_src = f.read()

    # create the local subshell packages
    for name, d in subshells.iteritems():
        s = name
        if d['prefix']:
            s += '(prefix:' + d['prefix'] + ')'
        if d['suffix']:
            s += '(suffix:' + d['suffix'] + ')'
        if not opts.stdin:
            print "Building subshell: " + s + ': ' + str(' ').join(d['pkgs'])

        pkgname = '__wrapper_' + name
        pkgdir = os.path.join(tmpdir, pkgname)
        os.mkdir(pkgdir)
        all_pkgs.append(pkgname)

        # do the resolve, creates the context and dot files
        contextfile = os.path.join(pkgdir, _g_context_filename)
        dot_file = os.path.join(pkgdir, _g_dot_filename)

        resolver = dc.Resolver(opts.mode,
                               quiet=opts.quiet,
                               time_epoch=opts.time,
                               build_requires=opts.buildreqs,
                               assume_dt=not opts.no_assume_dt,
                               caching=not opts.no_cache)

        result = resolver.guarded_resolve(d['pkgs'],
                                          no_os=opts.no_os,
                                          is_wrapper=True,
                                          meta_vars=["tools"],
                                          shallow_meta_vars=["tools"],
                                          dot_file=dot_file)

        if not result:
            sys.exit(1)

        commands = result[1]
        commands.append(rex.Setenv("REZ_CONTEXT_FILE", contextfile))

        # TODO: support other shells
        script = rex.interpret(commands, shell=opts.shell)

        with open(contextfile, 'w') as f:
            f.write(script)

        # extract the tools from the context file, create the alias scripts
        tools = get_tools_from_commands(commands)

        seen = set([])
        for tool in tools:
            alias = d["prefix"] + tool + d["suffix"]
            if alias in seen:
                continue  # early bird wins
            seen.add(alias)
            aliasfile = os.path.join(pkgdir, alias)
            src = wrapper_template_src.replace("#CONTEXT#", _g_context_filename)
            src = src.replace("#CONTEXTNAME#", name)
            src = src.replace("#ALIAS#", tool)

            if rcfile_copy:
                src = src.replace("#RCFILE#", "../rcfile.sh")

            with open(aliasfile, 'w') as f:
                f.write(src)

            os.chmod(aliasfile, stat.S_IXUSR | stat.S_IXGRP | stat.S_IRUSR | stat.S_IRGRP)

        # create the package.yaml
        with open(os.path.join(pkgdir, 'package.yaml'), 'w') as f:
            f.write(
                'config_version : 0\n'
                'name: ' + pkgname + '\n'
                'commands:\n'
                '- export PATH=$PATH:!ROOT!\n'
                '- export REZ_WRAPPER_PATH=$REZ_WRAPPER_PATH:!ROOT!\n')

            if tools:
                f.write("tools:\n")
                for tool in tools:
                    alias = d["prefix"] + tool + d["suffix"]
                    f.write("- %s\n" % alias)

    fpath = os.path.join(tmpdir, _g_packages_filename)
    with open(fpath, 'w') as f:
        f.write(' '.join(all_pkgs))
    return all_pkgs

def command(opts):
    import tempfile
    import rez.parse_request as rpr
    import rez.config as dc
    import rez.rex as rex
    import rez.filesys as filesys

    # TODO: support other shells
    opts.shell = 'bash'

    autowrappers = _contains_autowrappers(opts.pkg)
    raw_request = os.getenv('REZ_RAW_REQUEST', '')
    if opts.add_loose or opts.add_strict:
        if autowrappers:
            error("Patching of auto-wrapper environments is not yet supported.")
            sys.exit(1)

        if _contains_autowrappers(raw_request.split()):
            error("Patching from auto-wrapper environments is not yet supported.")
            sys.exit(1)

    ##############################################################################
    # switch to auto-wrapper rez-env if bracket syntax is detected
    # TODO patching of wrapper envs is not yet supported.
    ##############################################################################
    if autowrappers:
        if not opts.tmpdir:
            opts.tmpdir = tempfile.mkdtemp()

        packages = resolve_autowrappers(opts)

        # make rez.config aware of the location of our new packages
        # FIXME: provide a way to pass paths to resolve()
        filesys._g_syspaths.insert(1, opts.tmpdir)
        filesys._g_syspaths_nolocal.insert(1, opts.tmpdir)
        opts.no_cache = True
    else:
        packages = opts.pkg

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
        base_pkgs, subshells = rpr.parse_request(ctxt_pkg_list + " | " + ' '.join(packages))
        pkg_list = rpr.encode_request(base_pkgs, subshells).split()

    if print_pkgs and not opts.quiet:
        quotedpkgs = ["'%s'" % pkg for pkg in pkg_list]
        print "request: %s" % ' '.join(quotedpkgs)

    ##############################################################################
    # call rez-config, and write env into bake file
    ##############################################################################
    context_file = tempfile.mktemp(dir=opts.tmpdir, prefix='.rez-context.')
    dot_file = context_file + ".dot"

    # # setup args for rez-config
    # # TODO: convert to use rez.config directly
    # kwargs = dict(verbosity=0,
    #               version=False,
    #               print_env=False,
    #               print_dot=False,
    #               meta_info='tools',
    #               meta_info_shallow='tools',
    #               env_file=context_file,
    #               dot_file=dot_file,
    #               max_fails=opts.view_fail,
    #               wrapper=False,
    #               no_catch=False,
    #               no_path_append=False,
    #               print_pkgs=False)
    # # copy settings that are the same between rez-env and rez-config
    # kwargs.update(vars(opts))
    # # override values that differ
    # kwargs['quiet'] = True
    # kwargs['pkg'] = pkg_list.split()

    # config_opts = argparse.Namespace(**kwargs)
    # try:
    #     rez_cli_config.command(config_opts)
    # except Exception, err:
    #     error(err)
    #     try:
    #         # TODO: change cli convention so that commands do not call sys.exit
    #         # and we can actually catch this exception
    #         if opts.view_fail != "-1":
    #             from . import dot as rez_cli_dot
    #             dot_opts = argparse.Namespace(conflict_only=True,
    #                                           package="",
    #                                           dot_file=dot_file)
    #             rez_cli_dot.command(dot_opts)
    #         sys.exit(1)
    #     finally:
    #         if os.path.exists(context_file):
    #             os.remove(context_file)
    #         if os.path.exists(dot_file):
    #             os.remove(dot_file)

    resolver = dc.Resolver(opts.mode, True, 0, opts.view_fail,
                           opts.time, opts.buildreqs, not opts.no_assume_dt,
                           not opts.no_cache)

    result = resolver.guarded_resolve(pkg_list, opts.no_os,
                                      dot_file=dot_file,
                                      meta_vars=['tools'],
                                      shallow_meta_vars=['tools'])

    if autowrappers:
        # remove tempdir
        filesys._g_syspaths = filesys._g_syspaths[1:]
        filesys._g_syspaths_nolocal = filesys._g_syspaths_nolocal[1:]

    if not result:
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

    pkg_ress, commands, dot_graph, num_fails = result

    pkgs_str = ' '.join(packages)

    if autowrappers:
        # override REZ_RAW_REQUEST set in the context file with result from resolve_autowrappers()
        # FIXME: i think this should be the same was what's already in the context file...
        # the value in packages is passed to the resolver above (via `pkg_list`) 
        commands.append(rex.Setenv('REZ_RAW_REQUEST', pkgs_str))

    script = rex.interpret(commands, shell=opts.shell)
    with open(context_file, 'w') as f:
        f.write(script)

    recorder = rex.CommandRecorder()

    if not raw_request:
        # is this necessary? REZ_RAW_REQUEST is set in the context file...
        recorder.setenv('REZ_RAW_REQUEST', pkgs_str)

    # FIXME: can these be added to the context file like it is for autowrappers?
    # this gets set *prior* to spawining the subshell and relies on the fact that
    # the env will be inhereted by the subshell.
    recorder.setenv('REZ_CONTEXT_FILE', context_file)
    recorder.setenv('REZ_ENV_PROMPT', '${REZ_ENV_PROMPT}%s' % opts.prompt)

    spawn_subshell(recorder, context_file, opts.stdin, opts.rcfile)
    cmd = rex.interpret(recorder, shell=opts.shell, output_style='eval')
    output(cmd)

def spawn_subshell(recorder, context_file, stdin=False, rcfile=None, quiet=False):
    """
    spawn the new shell, sourcing the bake file
    """
    if stdin:
        recorder.command("source %s" % context_file)
        if not rcfile:
            # (bash-specific):
            if os.path.exists(os.path.expanduser('~/.bashrc')):
                recorder.command("source ~/.bashrc &> /dev/null")
        else:
            recorder.command("source %s" % rcfile)

        # ensure that rez-config is available no matter what (eg .bashrc might not exist,
        # rcfile might not source rez-config)
        # (bash-specific):
        recorder.command("source $REZ_PATH/init.sh")
        recorder.command("bash -s")

    else:
        source_file = context_file + ".source"
        with open(source_file, 'w') as f:
            f.write("source %s\n" % context_file)
            if rcfile:
                f.write("source %s\n" % rcfile)

            # (bash-specific):
            f.write("source rez-env-bashrc\n")
            if not quiet:
                f.write("echo\n")
                f.write("echo You are now in a new environment.\n")
                f.write("rez-context-info\n")

        # (bash-specific):
        recorder.command("bash --rcfile %s" % source_file)

    recorder.command("rm -f %s*" % context_file)

    # print "exit $ret;"


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
