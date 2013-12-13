'''
Invoke a shell based on a configuration request.
'''

import argparse
import sys
import os
import textwrap
from rez.cli import error, output
from . import config as rez_cli_config

# _g_usage = "rez-env [options] pkg1 pkg2 ... pkgN"


# class OptionParser2(optparse.OptionParser):
#     def exit(self, status=0, msg=None):
#         if msg:
#             sys.stderr.write(msg)
#         sys.exit(1)

# autowrapper constants:
_g_context_filename = 'package.context'
_g_packages_filename = 'packages.txt'
_g_dot_filename = _g_context_filename + '.dot'
_g_tools_filename = _g_context_filename + '.tools'
_g_wrapper_pkg_prefix = '__wrapper_'

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
            break
    return tools

def _contains_autowrappers(pkglist):
    return any([pkg for pkg in pkglist if '(' in pkg])

def resolve(opts, pkg_list, dot_file):
    import rez.config as dc
    resolver = dc.Resolver(opts.mode,
                           quiet=opts.quiet,
                           max_fails=opts.view_fail,
                           time_epoch=opts.time,
                           build_requires=opts.buildreqs,
                           assume_dt=not opts.no_assume_dt,
                           caching=not opts.no_cache)

    result = resolver.guarded_resolve(pkg_list, opts.no_os,
                                      dot_file=dot_file,
                                      meta_vars=['tools'],
                                      shallow_meta_vars=['tools'])

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
            if os.path.exists(opts.tmpdir):
                os.removedirs(opts.tmpdir)
    return result

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

#     (opts, args) = p.parse_args(sys.argv[2:])

    pkgs_str = str(' ').join(opts.pkg).strip()

    if opts.no_local:
        import rez.util
        rez.util.hide_local_packages()

    base_pkgs, subshells = rpr.parse_request(pkgs_str)
    all_pkgs = base_pkgs[:]

    if not opts.quiet and not opts.stdin:
        print 'Building into ' + opts.tmpdir + '...'

    # make a copy of rcfile, if specified. We need to propagate this into the subshells
    rcfile_copy = None
    if opts.rcfile and opts.prop_rcfile and os.path.isfile(opts.rcfile):
        rcfile_copy = os.path.join(opts.tmpdir, "rcfile.sh")
        shutil.copy(opts.rcfile, rcfile_copy)

    # create the local subshell packages
    for name, d in subshells.iteritems():
        s = name
        if d['prefix']:
            s += '(prefix:%s)' % d['prefix']
        if d['suffix']:
            s += '(suffix:%s)' % d['suffix']
        if not opts.stdin:
            print "Building subshell: " + s + ': ' + ' '.join(d['pkgs'])

        pkgname = _g_wrapper_pkg_prefix + name
        pkgdir = os.path.join(opts.tmpdir, pkgname)
        os.mkdir(pkgdir)

        # do the resolve, creates the context and dot files
        context_file = os.path.join(pkgdir, _g_context_filename)
        dot_file = os.path.join(pkgdir, _g_dot_filename)

        result = resolve(opts, d['pkgs'], dot_file)

        commands = result[1]
        commands.append(rex.Setenv("REZ_CONTEXT_FILE", context_file))

        # add wrapper stuff
        commands.append(rex.Setenv('REZ_IN_WRAPPER', '1'))
        # NOTE: the purpose of REZ_WRAPPER_PATH is to circumvent the resetting
        # of the PATH variable that occurs with each new subshell.
        # 1. The user enters a subshell
        #    1a. the package.yaml for each tool adds its root directory to both
        #        PATH and REZ_WRAPPER_PATH. This ensures that the wrapper scripts are
        #        accessible.
        # 2. The user runs the tool wrapper script
        #    2a. the context file for that tool is sourced, which begins by
        #        resetting the PATH
        #    2b. the last line in the context file *appends* REZ_WRAPPER_PATH to
        #        the PATH. Appending ensures that the wrapper scripts are found
        #        *after* the real tools that they wrap.
        # TODO: try getting rid of REZ_WRAPPER_PATH altogether. Instead, add
        # the wrapper packages themselves to each resolve to ensure
        # the PATH is setup. ex.
        #    rez-env (maya foo) (nuke bar) would yield these sub-resolves:
        #        maya: maya-2014 foo-1 __wrapper_maya __wrapper_nuke
        #        nuke: nuke-7.0.1 bar-2 __wrapper_maya __wrapper_nuke
        commands.append(rex.Appendenv('PATH', '$REZ_WRAPPER_PATH'))

        script = rex.interpret(commands, shell=opts.shell)

        with open(context_file, 'w') as f:
            f.write(script)

        write_shell_resource(pkgdir, '.bashrc',
                             context_file, rcfile_copy, quiet=True)
        write_shell_resource(pkgdir, '.bash_profile',
                             context_file, rcfile_copy, quiet=True)

        # extract the tools from the context file, create the alias scripts
        tools = get_tools_from_commands(commands)

        seen = set([])
        for tool in tools:
            alias = d["prefix"] + tool + d["suffix"]
            if alias in seen:
                continue  # early bird wins

            seen.add(alias)
            aliasfile = os.path.join(pkgdir, alias)

            write_tool_wrapper_script(name, tool, aliasfile)

        # create the package.yaml that will put the tool wrappers on the PATH.
        # the package will resolved immediately following return of this function.
        with open(os.path.join(pkgdir, 'package.yaml'), 'w') as f:
            f.write(
                'config_version : 0\n'
                'name: ' + pkgname + '\n'
                'commands: |\n'
                '  PATH.append("{root}")\n'
                '  REZ_WRAPPER_PATH.append("{root}")\n')

            if tools:
                f.write("tools:\n")
                for tool in tools:
                    alias = d["prefix"] + tool + d["suffix"]
                    f.write("- %s\n" % alias)
        # add to list of packages to resolve
        all_pkgs.append(pkgname)

    # FIXME: originally this file was used to pass results between rez-env-autowrappers
    # and rez-env bash scripts.  now that things are converted to python
    # I don't think it is needed anymore.
    fpath = os.path.join(opts.tmpdir, _g_packages_filename)
    with open(fpath, 'w') as f:
        f.write(' '.join(all_pkgs))

    return all_pkgs

def command(opts):
    import tempfile
    import rez.parse_request as rpr
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

    if not opts.tmpdir:
        opts.tmpdir = tempfile.mkdtemp()

    ##############################################################################
    # switch to auto-wrapper rez-env if bracket syntax is detected
    # TODO patching of wrapper envs is not yet supported.
    ##############################################################################
    if autowrappers:
        # resolve_autowrappers() replaces any subshells in the package requests
        # with a newly created temporary package wrapping the packages in that subshell.
        # ex. ['maya', '(nuke bar)'] --> ['maya', '__wrapper_nuke']
        packages = resolve_autowrappers(opts)

        # make rez.config aware of the location of our new packages
        # FIXME: provide a way to pass paths to resolve()
        filesys._g_syspaths.insert(0, opts.tmpdir)
        filesys._g_syspaths_nolocal.insert(0, opts.tmpdir)
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
    dot_file = os.path.join(opts.tmpdir, _g_dot_filename)
    context_file = os.path.join(opts.tmpdir, _g_context_filename)

    result = resolve(opts, pkg_list, dot_file)

    commands = result[1]

    if autowrappers:
        # cleanup: remove tempdir from REZ_PACKAGES_PATH
        filesys._g_syspaths = filesys._g_syspaths[1:]
        filesys._g_syspaths_nolocal = filesys._g_syspaths_nolocal[1:]
    else:
        commands = [rex.Setenv('REZ_IN_WRAPPER', ''),
                    rex.Setenv('REZ_WRAPPER_PATH', '')] + commands

    script = rex.interpret(commands, shell=opts.shell)
    with open(context_file, 'w') as f:
        f.write(script)

    recorder = rex.CommandRecorder()

    # FIXME: can these be added to the context file like it is for autowrappers?
    # this gets set *prior* to spawining the subshell and relies on the fact that
    # the env will be inhereted by the subshell.
    recorder.setenv('REZ_CONTEXT_FILE', context_file)
    recorder.setenv('REZ_ENV_PROMPT', '${REZ_ENV_PROMPT}%s' % opts.prompt)

    spawn_child_shell(recorder, opts.tmpdir, context_file, opts.stdin, opts.rcfile)
    recorder.command("rm -rf %s" % opts.tmpdir)

    cmd = rex.interpret(recorder, shell=opts.shell, output_style='eval')
    output(cmd)

# bash utilities
# TODO: Add to an appropriate base-class
def write_tool_wrapper_script(pkg_name, tool_name, filepath):
    """
    write an executable shell script which wraps a "tool" (any executable registered
    by a package).
    By default, the wrapper script will source a rez context file and then run
    the tool.
    """
    import stat
    script = textwrap.dedent("""\
        #!/bin/bash

        export REZ_WRAPPER_NAME='%(pkg_name)s'
        export REZ_WRAPPER_ALIAS='%(tool_name)s'
        context_file=`dirname $0`/%(context_file)s

        source $REZ_PATH/init.sh

        if [ "${!#}" == "---i" ]; then
            # interactive mode: drop into a new shell
            export REZ_ENV_PROMPT="${REZ_ENV_PROMPT}%(pkg_name)s>"
            export HOME=`dirname $0`
            /bin/bash
            exit $?
        fi

        source $context_file

        if [ "${!#}" == "---s" ]; then
            /bin/bash -s
            exit $?
        else
            # run the actual tool
            %(tool_name)s $*
            exit $?
        fi
        """ % {'pkg_name': pkg_name,
               'tool_name': tool_name,
               'context_file': _g_context_filename})

    with open(filepath, 'w') as f:
        f.write(script)

    os.chmod(filepath, stat.S_IXUSR | stat.S_IXGRP | stat.S_IRUSR | stat.S_IRGRP)

def write_shell_resource(tmpdir, filename, context_file, rcfile=None, quiet=False):
    """
    Write a shell script which should get sourced on initialization of a new shell
    and perform the necessary steps to setup the rez environment.

    The script must be named after an automatically sourced resource file for
    this shell (e.g. .bashrc, .bash_profile, .tcshrc, etc)

    Before spawn_child_resource() creates the new shell, it should set $HOME
    to the directory where this script resides. This should ensure that the
    shell will source it.  The script will restore the $HOME variable, and call
    the real resource script after which it was named.
    """
    script = textwrap.dedent("""\
        # reset HOME directory
        export HOME=%(home)s

        # source overridden script
        [[ -f ~/%(filename)s ]] && source ~/%(filename)s

        # source rez context file
        source %(context_file)s

        source $REZ_PATH/init.sh
        source $REZ_PATH/bin/_complete

        PS1="\[\e[1m\]$REZ_ENV_PROMPT\[\e[0m\] $PS1"
        """ % {'home': os.environ['HOME'],
               'filename': filename,
               'context_file': context_file})

    if rcfile:
        script += "source %s\n" % rcfile

    if not quiet:
        script += "echo\n"
        script += "echo You are now in a new environment.\n"
        script += "rez-context-info\n"

    fullpath = os.path.join(tmpdir, filename)
    with open(fullpath, 'w') as f:
        f.write(script)
    return fullpath

def spawn_child_shell(recorder, tmpdir, context_file, stdin=False, rcfile=None,
                      quiet=False):
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
        write_shell_resource(tmpdir, '.bashrc',
                             context_file, rcfile, quiet=quiet)
        write_shell_resource(tmpdir, '.bash_profile',
                             context_file, rcfile, quiet=quiet)

        recorder.setenv("HOME", tmpdir)
        # (bash-specific):
        recorder.command("bash")


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
