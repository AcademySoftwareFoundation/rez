#!!REZ_PYTHON_BINARY!

#
# rez-env-autowrappers
#
# Like rez-env, but is able to create wrappers on the fly. Rez-env automatically switches to this
# mode if it detects the syntax described below...
# Consider the following invocation of rez-env:
#
# ]$ rez-env (maya mutils-1.4) (houdini-11 hutils-3.2.2 mysops-5)
#
# Each one of the bracketed sections becomes its own subshell. Any package in that subshell that has
# executables listed in a 'tools' section of its package.yaml file, will have those executables
# exposed as 'alias' scripts. For example, after running the above command, running 'maya' would
# actually jump into the first subshell and then execute maya inside of it. Now consider:
#
# ]$ rez-env fx_(maya mfx-4.3) (maya manim-2.2)_anim
#
# Here, one subshell is given a prefix, and another a suffix. After running the above command, we
# would expect the executables "fx_maya" and "maya_anim" to exist. The prefix/suffix is applied to
# all tools found within that subshell.
#
# Each subshell has a name, by default this name is the pre/postfixed version of the first pkg in 
# the shell, so eg 'fx_maya' from above. To set this manually, do this:
#
# ]$ rez-env fx_(mayafx: maya mfx-4.3)
#
# Rez can also take a list of separate requests and 'merge' them together, use the pipe operator to
# do this. Later requests override earlier ones. For example, consider:
#
# rez-env (maya foo-1) | (maya foo-2)  # ==> becomes (maya foo-2)
#
# Here, the user was asking for 'foo-1' initially, but this was then overriden to 'foo-2' in the 
# second request. This functionality is provided for two reasons - (a) it's used internally when
# using patching in combination with auto-generated subshells; (b) it can be utilised by rez users,
# who want to implement their own environment management system, and have a need to create a
# working environment based on a heirarchical series of overriding config files.
#
# Lastly, the '^' operator can be used to *remove* packages from the request, eg:
#
# rez-env (maya foo-1) | (maya ^foo)  # ==> becomes (maya)
#

import os
import stat
import os.path
import sys
import subprocess
import tempfile
import rez_config as rc
import pyparsing as pp
import rez_env_cmdlin as rec
import rez_parse_request as rpr

_g_alias_context_filename = os.getenv('REZ_PATH') + '/template/wrapper.sh'
_g_context_filename     = 'package.context'
_g_packages_filename    = 'packages.txt'
_g_dot_filename         = _g_context_filename + '.dot'
_g_tools_filename       = _g_context_filename + '.tools'


# main
if __name__ == '__main__':

    # parse args
    p = rec.get_cmdlin_parser()

    (opts, args) = p.parse_args(sys.argv[2:])
    pkgs_str = str(' ').join(args).strip()
    if not pkgs_str:
        p.parse_args(['-h'])
        sys.exit(1)

    base_pkgs, subshells = rpr.parse_request(pkgs_str)
    all_pkgs = base_pkgs[:]

    # create the local subshell packages
    tmpdir = sys.argv[1]
    if not opts.quiet:
        print 'Building into ' + tmpdir + '...'

    f = open(_g_alias_context_filename, 'r')
    wrapper_template_src = f.read()
    f.close()

    for name,d in subshells.iteritems():
        if not opts.quiet:
            s = name
            if d['prefix']:     s += '(prefix:' + d['prefix'] + ')'
            if d['suffix']:     s += '(suffix:' + d['suffix'] + ')'
            print "Building subshell: " + s + ': ' + str(' ').join(d['pkgs'])

        pkgname = '__wrapper_' + name
        pkgdir = os.path.join(tmpdir, pkgname)
        os.mkdir(pkgdir)
        all_pkgs.append(pkgname)

        # do the resolve, creates the context and dot files
        # Invoking rez-config as a subproc sucks... but I'd have to reorganise a bunch of code to
        # fix this. I'd rather just do it properly in certus (aka 2nd-gen rez).
        contextfile = os.path.join(pkgdir, _g_context_filename)
        dotfile = os.path.join(pkgdir, _g_dot_filename)
        pkgs_str = str(' ').join(d['pkgs'])

        cmd = ('rez-config --print-env --wrapper --dot-file=%s --meta-info=tools ' + \
            '--meta-info-shallow=tools') % dotfile

        # forward opts onto rez-config invocation
        if opts.quiet:              cmd += " --quiet"
        if opts.build:              cmd += " --build-requires"
        if opts.no_os:              cmd += " --no-os"
        if opts.ignore_blacklist:   cmd += " --ignore-blacklist"
        if opts.ignore_archiving:   cmd += " --ignore-archiving"
        if opts.no_assume_dt:       cmd += " --no-assume-dt"
        if opts.time:               cmd += " --time=" + str(opts.time)
        cmd += " '" + pkgs_str + "'"

        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        commands,err_ = p.communicate()
        if p.returncode != 0:
            sys.exit(p.returncode)

        commands = [x.strip() for x in commands.strip().split('\n')]
        commands.append("export REZ_CONTEXT_FILE=%s" % contextfile)

        f = open(contextfile, 'w')
        f.write(str('\n').join(commands))
        f.close()

        # extract the tools from the context file, create the alias scripts
        tools = []
        f = open(contextfile, 'r')
        lines = f.read().strip().split('\n')
        for l in lines:
            if l.startswith("export REZ_META_SHALLOW_TOOLS="):
                toks = l.strip().split("'")[1].split()
                for tok in toks:
                    toks2 = tok.split(':')
                    aliases = toks2[1].split(',')
                    tools.extend(aliases)
                break

        for tool in tools:
            alias = d["prefix"] + tool + d["suffix"]
            aliasfile = os.path.join(pkgdir, alias)
            src = wrapper_template_src.replace("#CONTEXT#", _g_context_filename)
            src = src.replace("#CONTEXTNAME#", name)
            src = src.replace("#ALIAS#", tool)
            
            f = open(aliasfile, 'w')
            f.write(src)
            f.close()
            os.chmod(aliasfile, stat.S_IXUSR|stat.S_IXGRP|stat.S_IRUSR|stat.S_IRGRP)

        # create the package.yaml
        f = open(os.path.join(pkgdir, 'package.yaml'), 'w')
        f.write( \
            'config_version : 0\n' \
            'name: ' + pkgname + '\n' \
            'commands:\n' \
            '- export PATH=$PATH:!ROOT!\n' \
            '- export REZ_WRAPPER_PATH=$REZ_WRAPPER_PATH:!ROOT!\n')

        if tools:
            f.write("tools:\n")
            for tool in tools:
                alias = d["prefix"] + tool + d["suffix"]
                f.write("- %s\n" % alias)
        f.close()

    fpath = os.path.join(tmpdir, _g_packages_filename)
    f = open(fpath, 'w')
    f.write(str(' ').join(all_pkgs))
    f.close()



#    Copyright 2012 Allan Johns
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




















