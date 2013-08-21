'''
Install a python egg as a Rez package.
'''

import optparse
import sys
import os
import re
import stat
import time
import os.path
import shutil
import tempfile
import subprocess as sp


_g_r_stat = stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH
_g_x_stat = stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH

_g_rez_egg_api_version  = 0
_g_rez_path             = os.getenv("REZ_PATH", "UNKNOWN_REZ_PATH")
_g_pkginfo_key_re       = re.compile("^[A-Z][a-z_-]+:")
_g_yaml_prettify_re     = re.compile("^([^: \\n]+):", re.MULTILINE)


# this is because rez doesn't have alphanumeric version support. It will have though, when
# ported to Certus. Just not yet. :(
def _convert_version(txt):
    txt = txt.lower()
    txt = txt.replace('alpha','a')
    txt = txt.replace('beta','b')
    txt = txt.replace("python",'p')
    txt = txt.replace("py",'p')    
    ver = ''

    for ch in txt:
        if ch>='0' and ch<='9':
            ver += ch
        elif ch>='a' and ch<='z':
            ver += ".%s." % ch
        elif ch=='.' or ch=='-':
            ver += '.'
        elif ch=='_':
            pass
        else:
            ver += ".%d." % ord(ch)

    ver = ver.replace("..",".")
    ver = ver.strip('.')
    return ver


def _convert_pkg_name(name, pkg_remappings):
    name2 = pkg_remappings.get(name)
    if name2:
        name = _convert_pkg_name(name2, {})
    return name.replace('-','_')


def _convert_requirement(req, pkg_remappings):
    pkg_name = _convert_pkg_name(req.project_name, pkg_remappings)
    if not req.specs:
        return [pkg_name]

    rezreqs = []
    for spec in req.specs:
        op,ver = spec
        rezver = _convert_version(ver)
        if op == "<":
            r = "%s-0+<%s" % (pkg_name, rezver)
            rezreqs.append(r)
        elif op == "<=":
            r = "%s-0+<%s|%s" % (pkg_name, rezver, rezver)
            rezreqs.append(r)
        elif op == "==":
            r = "%s-%s" % (pkg_name, rezver)
            rezreqs.append(r)
        elif op == ">=":
            r = "%s-%s+" % (pkg_name, rezver)
            rezreqs.append(r)
        elif op == ">":
            r1 = "%s-%s+" % (pkg_name, rezver)
            r2 = "!%s-%s" % (pkg_name, rezver)
            rezreqs.append(r1)
            rezreqs.append(r2)
        elif op == "!=":
            r = "!%s-%s" % (pkg_name, rezver)
            rezreqs.append(r)
        else:
            print >> sys.stderr, \
                "Warning: Can't understand op '%s', just depending on unversioned package..." % op
            rezreqs.append(pkg_name)

    return rezreqs


# some pkg-infos appear to be screwed
def _repair_pkg_info(s):
    s2 = ''
    lines = s2.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('[') and not line.endswith(']'):
            line += ']'
        s2 += line + '\n'
    return s2


def _convert_metadata(distr):
    meta = {}
    if distr.has_metadata("PKG-INFO"):
        s = distr.get_metadata("PKG-INFO")
        s = _repair_pkg_info(s)
        sections = pkg_r.split_sections(s)
        print sections
        for section in sections:
            entries = section[1]
            for e in entries:
                if _g_pkginfo_key_re.match(e):
                    toks = e.split(':',1)
                    k = toks[0].strip()
                    v = toks[1].strip()
                    meta[k] = v
    return meta



#########################################################################################
# cmdlin
####################################################################################

def setup_parser(parser):
    
#     usage = "usage: rez-egg-install [options] <package_name> [-- <easy_install args>]\n\n" + \
#         "  Rez-egg-install installs Python eggs as Rez packages, using the standard\n" + \
#         "  'easy_install' python module installation tool. For example:\n" + \
#         "  rez-egg-install pylint\n" + \
#         "  If you need to use specific easy_install options, include the second\n" + \
#         "  set of args - in this case you need to make sure that <package_name>\n" + \
#         "  matches the egg that you're installing, for example:\n" + \
#         "  rez-egg-install MyPackage -- http://somewhere/MyPackage-1.0.tgz\n" + \
#         "  Rez will install the package into the current release path, set in\n" + \
#         "  $REZ_EGG_PACKAGES_PATH, which is currently:\n" + \
#         "  " + (os.getenv("REZ_EGG_PACKAGES_PATH") or "UNSET!")
#     p = optparse.OptionParser(usage=usage)

    rez_egg_remapping_file = os.getenv("REZ_EGG_MAPPING_FILE") or \
        ("%s/template/egg_remap.yaml" % _g_rez_path)
    
    
    parser.add_argument("--verbose", dest="verbose", action="store_true", default=False,
        help="print out extra information")
    parser.add_argument("--mapping-file", dest="mapping_file", type=str, default=rez_egg_remapping_file,
        help="yaml file that remaps package names. Set $REZ_EGG_MAPPING_FILE to change the default " +
        "[default = %(default)s]")
    parser.add_argument("--force-platform", dest="force_platform", type=str,
        help="ignore egg platform and force packages (comma-separated). Eg: Linux,x86_64,centos-6.3")
    parser.add_argument("--use-non-eggs", dest="use_non_eggs", default=False,
        help="allow use of rez packages that already exist, but " +
            "were not created by rez-egg-install")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=False,
        help="perform a dry run")
    parser.add_argument("--local", dest="local", action="store_true", default=False,
        help="install to local packages directory instead")
    parser.add_argument("--no-clean", dest="no_clean", action="store_true", default=False,
        help="don't delete temporary egg files afterwards")

# TODO: handle this:

# help_args = set(["--help","-help","-h","--h"]) & set(sys.argv)
# if help_args:
#     p.parse_args()

# rez_args = None
# easy_install_args = None
# 
# if "--" in sys.argv:
#     i = sys.argv.index("--")
#     rez_args = sys.argv[1:i]
#     easy_install_args = sys.argv[i+1:]
# else:
#     rez_args = sys.argv[1:]
# 
# (opts, args) = p.parse_args(rez_args)
# if len(args) != 1:
#     p.error("Expected package name")

def command(opts):
    import yaml

    pkg_name = args[0]
    
    if not easy_install_args:
        easy_install_args = [pkg_name]
    
    install_evar = "REZ_EGG_PACKAGES_PATH"
    if opts.local:
        install_evar = "REZ_LOCAL_PACKAGES_PATH"
    
    install_path = os.getenv(install_evar)
    if not install_path:
        print >> sys.stderr, "Expected $%s to be set." % install_evar
        sys.exit(1)
    
    
    remappings = {}
    if opts.mapping_file:
        with open(opts.mapping_file, 'r') as f:
            s = f.read()
        remappings = yaml.load(s)
    package_remappings = remappings.get("package_mappings") or {}
    
    platre = remappings.get("platform_mappings") or {}
    platform_remappings = {}
    for k,v in platre.iteritems():
        platform_remappings[k.lower()] = v
    
    safe_pkg_name = _convert_pkg_name(pkg_name, package_remappings)
    
    
    #########################################################################################
    # run easy_install
    #########################################################################################
    
    # find easy_install
    proc = sp.Popen("which easy_install", shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    proc.communicate()
    if proc.returncode:
        print >> sys.stderr, "could not find easy_install."
        sys.exit(1)
    
    # install the egg to a temp dir
    eggs_path = tempfile.mkdtemp(prefix="rez-egg-download-")
    print "INSTALLING EGG FOR PACKAGE '%s' TO %s..." % (pkg_name, eggs_path)
    
    def _clean():
        if not opts.no_clean:
            print
            print "DELETING %s..." % eggs_path
            shutil.rmtree(eggs_path)
    
    cmd = "export PYTHONPATH=$PYTHONPATH:%s" % eggs_path
    cmd += " ; easy_install --always-copy --install-dir=%s %s" % \
        (eggs_path, str(' ').join(easy_install_args))
    
    print "Running: %s" % cmd
    proc = sp.Popen(cmd, shell=True)
    proc.wait()
    if proc.returncode:
        _clean()
        print
        print >> sys.stderr, "A problem occurred running easy_install, the command was:\n%s" % cmd
        sys.exit(proc.returncode)
    
    
    
    #########################################################################################
    # extract info from eggs
    #########################################################################################
    
    # find tools, if any
    eggs_tools = set()
    names = os.listdir(eggs_path)
    for name in names:
        fpath = os.path.join(eggs_path, name)
        if not os.path.isfile(fpath):
            continue
        m = os.stat(fpath).st_mode
        if m & _g_x_stat:
            eggs_tools.add(name)
    
    # add eggs to python path
    sys.path = [eggs_path] + sys.path
    try:
        import pkg_resources as pkg_r
    except ImportError:
        print >> sys.stderr, "couldn't import pkg_resources. You probably need to install " + \
            "the python setuptools package, you can get it at http://pypi.python.org/pypi/setuptools."
        sys.exit(1)
    
    distrs = pkg_r.find_distributions(eggs_path)
    eggs = {}
    
    # iterate over eggs
    for distr in distrs:
        print
        print "EXTRACTING DATA FROM %s..." % distr.location
    
        name = _convert_pkg_name(distr.project_name, package_remappings)
        ver = _convert_version(distr.version)
        pyver = _convert_version(distr.py_version)
    
        d = {
            "config_version":   0,
            "name":             name,
            "unsafe_name":      distr.project_name,
            "version":          ver,
            "unsafe_version":   distr.version,
            "requires":         ["python-%s+" % pyver]
        }
    
        pkg_d = _convert_metadata(distr)
        d["EGG-INFO"] = pkg_d
        
        v = pkg_d.get("Summary")
        v2 = pkg_d.get("Description")
        if v:
            d["description"] = v
        elif v2:
            d["description"] = v2
    
        v = pkg_d.get("Author")
        if v:
            d["author"] = v
    
        v = pkg_d.get("Home-page")
        if v:
            d["help"] = "$BROWSER %s" % v
    
        reqs = distr.requires()
        for req in reqs:
            rezreqs = _convert_requirement(req, package_remappings)
            d["requires"] += rezreqs
    
        if opts.force_platform is None:
            v = pkg_d.get("Platform")
            if v:
                platform_pkgs = platform_remappings.get(v.lower())
                if platform_pkgs is None:
                    print >> sys.stderr, ("No remappings are present for the platform '%s'. " + \
                        "Please use the --mapping-file option to provide the remapping, or " + \
                        "use the --force-platform option.") % v
                    sys.exit(1)
                else:
                    if platform_pkgs:
                        d["variants"] = platform_pkgs
        else:
            toks = opts.force_platform.replace(',',' ').strip().split()
            if toks:
                d["variants"] = toks
    
        eggs[name] = (distr, d)
    
    
    # iterate over tools and assign to eggs. There doesn't seem to be consistency in how eggs specify
    # their scripts (if at all), so we work it out by looking for the egg name in the script sources.
    if eggs and eggs_tools:
        for tool in eggs_tools:
            with open(os.path.join(eggs_path, tool), 'r') as f:
                s = f.read()
            
            count_d = {}
            for egg_name,v in eggs.iteritems():
                distr, d = v
                n = s.count(d["unsafe_name"])
                count_d[n] = egg_name
    
            counts = count_d.keys()
            counts.sort()
            n = counts[-1]
            script_egg = count_d[n]
    
            d = eggs[script_egg][1]
            if "tools" not in d:
                d["tools"] = []
            d["tools"].append(tool)
    
    
    if eggs:
        print
        print "FOUND EGGS: %s" % str(", ").join(eggs.keys())
        if eggs_tools:
            print "FOUND PROGRAMS: %s" % str(", ").join(eggs_tools)
    
    
    
    #########################################################################################
    # convert eggs to rez packages
    #########################################################################################
    destdirs = []
    
    def _mkdir(path, make_ro=True):
        if not os.path.exists(path):
            if opts.verbose:
                print "creating %s..." % path
            if not opts.dry_run:
                os.makedirs(path)
                if make_ro:
                    destdirs.append(path)
    
    def _cpfile(filepath, destdir, make_ro=True, make_x=False):
        if opts.verbose:
            print "copying %s to %s..." % (filepath, destdir+'/')
        if not opts.dry_run:
            shutil.copy(filepath, destdir)
            if make_ro or make_x:
                st = 0
                if make_ro: st |= _g_r_stat
                if make_x:  st |= _g_x_stat
                destfile = os.path.join(destdir, os.path.basename(filepath))
                os.chmod(destfile, st)
    
    
    if not opts.use_non_eggs:
        nnoneggs = 0
        for egg_name, v in eggs.iteritems():
            distr, d = v
            pkg_path = os.path.join(install_path, egg_name, d["version"])
            meta_path = os.path.join(pkg_path, ".metadata")    
            rezeggfile = os.path.join(meta_path, "rez_egg_info.txt")
    
            if os.path.exists(pkg_path) and not os.path.exists(rezeggfile):
                print
                print >> sys.stderr, ("package '%s' already exists, but was not created by " + \
                    "rez-egg-install. Use the --use-non-eggs option to skip this error, but note " + \
                    "that rez doesn't know if this package is properly configured." % egg_name)
                nnoneggs += 1
        if nnoneggs:
            sys.exit(1)
    
    
    added_pkgs = []
    updated_pkgs = []
    existing_pkgs = []
    
    for egg_name, v in eggs.iteritems():
        print
        print "BUILDING REZ PACKAGE FOR '%s'..." % egg_name
    
        variants = d.get("variants") or []
        distr, d = v
        egg_path = distr.location
        egg_dir = os.path.basename(egg_path)
        egg_path = os.path.split(egg_path)[0]
        
        pkg_path = os.path.join(install_path, egg_name, d["version"])
        meta_path = os.path.join(pkg_path, ".metadata")    
        variant_path = os.path.join(pkg_path, *(variants))
        bin_path = os.path.join(variant_path, "bin")
        rezeggfile = os.path.join(meta_path, "rez_egg_info.txt")
    
        if os.path.exists(variant_path):
            print ("skipping installation of '%s', the current variant appears to exist already " + \
                "- %s already exists. Delete this directory to force a reinstall.") % \
                (egg_name, variant_path)
            existing_pkgs.append(egg_name)
            continue
    
        _mkdir(meta_path, False)
        _mkdir(variant_path, bool(variants))
    
        # copy files
        for root, dirs, files in os.walk(egg_path):
            subpath = root[len(egg_path):].strip('/')
            dest_root = os.path.join(variant_path, egg_dir, subpath)
            _mkdir(dest_root)
    
            for name in dirs:
                _mkdir(os.path.join(dest_root, name))
    
            for name in files:
                if not name.endswith(".pyc"):
                    _cpfile(os.path.join(root, name), dest_root)
    
        tools = d.get("tools")
        if tools:
            _mkdir(bin_path)
            for tool in tools:
                _cpfile(os.path.join(eggs_path, tool), bin_path, make_ro=True, make_x=True)
    
        for path in reversed(destdirs):
            os.chmod(path, _g_r_stat|_g_x_stat)
    
        # create/update yaml
        print
        pkg_d = {}
        yaml_path = os.path.join(pkg_path, "package.yaml")
        if os.path.exists(yaml_path):
            print "UPDATING %s..." % yaml_path
            with open(yaml_path, 'r') as f:
                s = f.read()
            pkg_d = yaml.load(s) or {}
            updated_pkgs.append(egg_name)
        else:
            print "CREATING %s..." % yaml_path
            added_pkgs.append(egg_name)
    
        for k,v in d.iteritems():
            if k == "variants":
                continue
            if k not in pkg_d:
                pkg_d[k] = v
    
        if variants:
            if "variants" not in pkg_d:
                pkg_d["variants"] = []
            pkg_d["variants"].append(variants)
        
        if "commands" not in pkg_d:
            pkg_d["commands"] = []
    
        cmd = "export PYTHONPATH=$PYTHONPATH:!ROOT!/%s" % egg_dir
        if cmd not in pkg_d["commands"]:
            pkg_d["commands"].append(cmd)
    
        if tools:
            cmd = "export PATH=$PATH:!ROOT!/bin"
            if cmd not in pkg_d["commands"]:
                pkg_d["commands"].append(cmd)        
    
        s = yaml.dump(pkg_d, default_flow_style=False)
        pretty_s = re.sub(_g_yaml_prettify_re, "\\n\\1:", s).strip() + '\n'
    
        if opts.dry_run:
            print
            print "CONTENTS OF %s WOULD BE:" % yaml_path
            print pretty_s
        else:
            with open(yaml_path, 'w') as f:
                f.write(pretty_s)
    
            # timestamp
            timefile = os.path.join(meta_path, "release_time.txt")
            if not os.path.exists(timefile):
                with open(timefile, 'w') as f:
                    f.write(str(int(time.time())))
    
            if not os.path.exists(rezeggfile):
                with open(rezeggfile, 'w') as f:
                    f.write(str(_g_rez_egg_api_version))
    
    _clean()
    
    print
    print "Success! %d packages were installed, %d were updated." % (len(added_pkgs), len(updated_pkgs))
    if not opts.dry_run:
        if added_pkgs:
            print "Newly installed packages: %s" % str(", ").join(added_pkgs)
        if updated_pkgs:
            print "Updated packages: %s" % str(", ").join(updated_pkgs)
        if existing_pkgs:
            print "Pre-existing packages: %s" % str(", ").join(existing_pkgs)



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
