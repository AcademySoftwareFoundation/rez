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
# One last thing: each subshell has a name, by default this name is the pre/postfixed version of the
# first pkg in the shell, so eg 'fx_maya' from above. To set this manually, do this:
#
# ]$ rez-env fx_(mayafx: maya mfx-4.3)
#

import os
import os.path
import sys
import optparse
import tempfile
import rez_config as rc

_g_alias_context_filename = os.getenv('REZ_PATH') + '/template/wrapper.sh'
_g_context_filename     = 'package.context'
_g_dot_filename         = _g_context_filename + '.dot'
_g_tools_filename       = _g_context_filename + '.tools'


# split pkgs string into separate subshells
def parse_pkg_args(s):
    d = {}
    base_pkgs = []
    subshell = None
    toks = s.replace('(', '( ').replace(')', '  )').replace(':', ': ').split()

    for tok in toks:
        if tok.endswith('('):
            if subshell:
                raise Exception('Syntax error')
            subshell = {'pkgs':[]}
            prefix = tok[:-1]
            subshell['prefix'] = prefix
        elif tok.startswith(')'):
            if not subshell or not subshell['pkgs']:
                raise Exception('Syntax error')
            suffix = tok[1:]
            subshell['suffix'] = suffix
            if 'name' in subshell:
                name = subshell['name']
            else:
                first_pkg_fam = subshell['pkgs'][0].split('-')[0]
                name = subshell['prefix'] + first_pkg_fam + subshell['suffix']
            base_name = name
            i = 1
            while name in d:
                i = i + 1
                name = base_name + str(i)
            d[name] = subshell
            subshell = None
        else:
            if subshell:
                if tok.endswith(':'):
                    subshell['name'] = tok[:-1]
                else:
                    subshell['pkgs'].append(tok)
            else:
                base_pkgs.append(tok)

    return (base_pkgs, d)



# main
if __name__ == '__main__':

    # parse args
    usage = "usage: %prog [options] [[prefix](pkg1 pkg2 ... pkgN)[suffix]]+"
    p = optparse.OptionParser(usage=usage)

    p.add_option("-q", "--quiet", dest="quiet", action="store_true", default=False, \
        help="suppress unnecessary output [default = %default]")

    (opts, args) = p.parse_args()
    pkgs_str = str(' ').join(args).strip()
    if not pkgs_str:
        p.parse_args(['-h'])
        sys.exit(1)

    base_pkgs, subshells = parse_pkg_args(pkgs_str)
    if not opts.quiet:
        print 'master shell: ' + str(' ').join(base_pkgs)
        for name,d in subshells.iteritems():
            s = name
            if d['prefix']:     s += '(prefix:' + d['prefix'] + ')'
            if d['suffix']:     s += '(suffix:' + d['suffix'] + ')'
            print s + ': ' + str(' ').join(d['pkgs'])


    # create and save subshell pkgs using rez-config. Yes going via system call is hacky, but all
    # this client-side code needs reworking anyway, if I ever get the time :/
    subshell_pkgs = []

    tmpdir = tempfile.mkdtemp(suffix='.rez')
    if not opts.quiet:
        print
        print 'Building into ' + tmpdir + '...'

    for name,d in subshells.iteritems():
        if not opts.quiet:
            print
            print 'Building subshell ' + name + '...'

        pkgname = '__' + name
        subshell_pkgs.append(pkgname)
        pkgdir = os.path.join(tmpdir, pkgname)
        os.mkdir(pkgdir)

        f = open(os.path.join(pkgdir, 'package.yaml'), 'w')
        f.write( \
            'config_version : 0\n' \
            'name: ' + pkgname + '\n' \
            'commands:\n' \
            '- export PATH=$PATH:!ROOT!\n' \
            '- export REZ_WRAPPER_PATH=$REZ_WRAPPER_PATH:!ROOT!\n')
        f.close()

        contextfile = os.path.join(pkgdir, _g_context_filename)
        dotfile = os.path.join(pkgdir, _g_dot_filename)
        pkgs_str = str(' ').join(d['pkgs'])
        cmd = 'rez-config --print-env --wrapper --dot-file=%s --meta-info=tools %s > %s' % \
            (dotfile, pkgs_str, contextfile)
        errnum = os.system(cmd)
        if errnum != 0:
            sys.exit(errnum)

        tools = open(toolsfile, 'r').read().strip().split('\n')
        for tool in tools:
            alias = d['prefix'] + tool + d['suffix']
            aliasfile = os.path.join(pkgdir, alias)
            cmd = \
                'cat %s ' \
                ' | sed -e "s/#CONTEXT#/%s/g"' \
                ' -e "s/#CONTEXTNAME#/%s/g"' \
                ' -e "s/#ALIAS#/%s/g" > %s' % \
                (_g_alias_context_filename, _g_context_filename, name, tool, aliasfile)




#		COMMAND cat $ENV{REZ_PATH}/template/wrapper.sh
# | sed -e "s/#CONTEXT#/${instwrp_context_target}/g"
# -e "s/#CONTEXTNAME#/${instwrp_context_name}/g"
# -e "s/#ALIAS#/${alias}/g" > ${INSTWRP_dest_dir}/${wrapper_script}


    # run rez-env, pick up local subshell packages





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




















