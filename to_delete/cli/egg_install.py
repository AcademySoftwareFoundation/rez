'''
Install a python egg as a Rez package.
TODO replace with pip-based implementation.
'''
from __future__ import with_statement
import sys
import os
import os.path
import re
import stat
import time
import os.path
import shutil
import tempfile
import subprocess as sp
import textwrap
from rez import module_root_path
from rez.system import system
from rez.settings import settings
from rez.cli import error, output
from rez.util import copytree


_g_r_stat = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
_g_w_stat = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
_g_x_stat = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH

_g_rez_egg_api_version = 0
_g_pkginfo_key_re = re.compile("^[A-Z][a-z_-]+:")
_g_yaml_prettify_re = re.compile("^([^: \\n]+):", re.MULTILINE)
_g_hash_re = re.compile("[a-z0-9]{8,40}")

# TODO remove once proper alphanumeric version support is added
def _convert_version(txt):
    txt = txt.lower()

    txt = txt.replace('alpha', 'a')
    txt = txt.replace('beta', 'b')
    txt = txt.replace("python", 'p')
    txt = txt.replace("py", 'p')

    # remove any hash added to the version. this is done when building from source.
    txt = _g_hash_re.sub('', txt)

    ver = ''

    for ch in txt:
        if ch >= '0' and ch <= '9':
            ver += ch
        elif ch >= 'a' and ch <= 'z':
            ver += ".%s." % ch
        elif ch == '.' or ch == '-':
            ver += '.'
        elif ch == '_':
            pass
        else:
            ver += ".%d." % ord(ch)

    ver = ver.replace("..", ".")
    ver = ver.strip('.')
    return ver


def _convert_pkg_name(name, pkg_remappings):
    name2 = pkg_remappings.get(name)
    if name2:
        name = _convert_pkg_name(name2, {})
    return name.replace('-', '_')


def _convert_requirement(req, pkg_remappings):
    pkg_name = _convert_pkg_name(req.project_name, pkg_remappings)
    if not req.specs:
        return [pkg_name]

    rezreqs = []
    for spec in req.specs:
        op, ver = spec
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
    lines = s.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('[') and not line.endswith(']'):
            line += ']'
        s2 += line + '\n'
    return s2

def _convert_metadata(distr):
    import pkg_resources as pkg_r
    meta = {}
    if distr.has_metadata("PKG-INFO"):
        s = distr.get_metadata("PKG-INFO")
        s = _repair_pkg_info(s)
        sections = pkg_r.split_sections(s)
        for section in sections:
            entries = section[1]
            for e in entries:
                if _g_pkginfo_key_re.match(e):
                    toks = e.split(':', 1)
                    k = toks[0].strip()
                    v = toks[1].strip()
                    meta[k] = v
    return meta

def _is_native_library(distr):
    if distr.has_metadata('native_libs.txt'):
        return True
    elif distr.has_metadata('installed-files.txt'):
        exts = ['.so', '.a', '.dll', '.lib']
        if any(os.path.splitext(p)[1] in exts for p in distr.get_metadata_lines('installed-files.txt')):
            return True
    return False

def _get_package_data_from_dist(distr, force_platform, package_remappings,
                                platform_remappings):
    name = _convert_pkg_name(distr.project_name, package_remappings)
    ver = _convert_version(distr.version)
    pyver = _convert_version(distr.py_version)

    d = {
        "config_version": 0,
        "name": name,
        "unsafe_name": distr.project_name,
        "version": ver,
        "unsafe_version": distr.version,
    }
    requires = []
    variant = []

    if _is_native_library(distr):
        # if the package has native libs, then python must be a variant
        native = True
        variant.append("python-%s" % pyver)
    else:
        native = False
        requires.append("python-%s+" % pyver)

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
        requires += rezreqs

    if force_platform is None:
        v = pkg_d.get("Platform")
        if native and v.lower() == 'unknown':
            # cannot allow native lib to be unknown
            import rez.filesys
            variant = ["platform-"+system.platform] + variant
        elif v:
            platform_pkgs = platform_remappings.get(v.lower())
            if platform_pkgs is None:
                error(("No remappings are present for the platform '%s'. " +
                       "Please use the --mapping-file option to provide the remapping, or " +
                       "use the --force-platform option.") % v)
                sys.exit(1)
            else:
                if platform_pkgs:
                    variant = platform_pkgs + variant
    else:
        toks = force_platform.replace(',', ' ').strip().split()
        if toks:
            variant = toks + variant

    if variant:
        # add our variant
        d["variants"] = [variant]
    if requires:
        d["requires"] = requires
    return name, d

def _update_package_yaml(yaml_path, data, dry_run):
    """
    Convert the dictionary of data to yaml. Read existing data from `yaml_path`,
    if it exists.

    Returns a tuple contain the yaml string and a bool for whether the data was
    updated from disk.
    """
    import yaml
    pkg_d = {}

    if os.path.exists(yaml_path):
        print "UPDATING %s..." % yaml_path
        with open(yaml_path, 'r') as f:
            s = f.read()
        pkg_d = yaml.load(s) or {}
        updated = True
    else:
        print "CREATING %s..." % yaml_path
        updated = False

    for k, v in data.iteritems():
        if k == "variants":
            continue
        if k not in pkg_d:
            pkg_d[k] = v

    variants = data.get("variants")
    if variants:
        if "variants" not in pkg_d:
            pkg_d["variants"] = []
        pkg_d["variants"].extend(variants)

    if "commands" not in pkg_d:
        pkg_d["commands"] = []

    cmd = "export PYTHONPATH=$PYTHONPATH:!ROOT!/lib"
    if cmd not in pkg_d["commands"]:
        pkg_d["commands"].append(cmd)

    tools = data.get("tools")
    if tools:
        cmd = "export PATH=$PATH:!ROOT!/bin"
        if cmd not in pkg_d["commands"]:
            pkg_d["commands"].append(cmd)

    s = yaml.dump(pkg_d, default_flow_style=False)
    pretty_s = re.sub(_g_yaml_prettify_re, "\\n\\1:", s).strip() + '\n'

    if dry_run:
        print
        print "CONTENTS OF %s WOULD BE:" % yaml_path
        print pretty_s
    else:
        with open(yaml_path, 'w') as f:
            f.write(pretty_s)

    return updated

def _get_safe_pythonpath(pkg_name, pypath):
    """
    Filter out unsafe paths from the PYTHONPATH.
    Paths that might contain other copies of the package being
    installed, will cause easy_install to skip installation.
    """
    safe_paths = []
    for path in pypath:
        for pkg_path in settings.packages_path:
            # allow rez packages that are not this one: because they contain a
            # single application/library, there is little chance they
            # will contain the python module being installed, and might even
            # be required by the package being installed
            if path.startswith(pkg_path) and \
                    pkg_name not in path.replace(pkg_path, '').split(os.path.sep):
                safe_paths.append(path)
                break
    return safe_paths

def _sandbox_eggs(tempdir, eggs):
    '''
    Copy setuptools egg into its own temp directory
    '''
    import pkg_resources as pkg_r
    sandboxed = []
    for egg in eggs:
        distr = pkg_r.get_distribution(egg)
        location = distr.location
        if location.endswith('.egg'):
            paths = [location]
            sandboxed.append(os.path.join('.', os.path.basename(location)))
            # easy-install-style egg
            # print list(distr.get_metadata("installed-files.txt"))
            print "sandboxing %s: copying %s to %s" % (egg, location, tempdir)
            basename = os.path.basename(location)
            if os.path.isfile(location):
                shutil.copy(location, tempdir)
            else:
                copytree(location, os.path.join(tempdir, basename))
        else:
            info = os.path.join(location, distr.egg_name() + '.egg-info')
            # pip style
            for file in distr.get_metadata_lines("installed-files.txt"):
                srcpath = os.path.abspath(os.path.join(info, file))
                destpath = os.path.relpath(srcpath, location)
                # can't install files that are above the lib dir, but we
                # don't need them anyway
                if destpath.split(os.path.sep)[0] == '..':
                    continue
                destpath = os.path.join(tempdir, destpath)
                if os.path.isdir(srcpath):
                    os.mkdir(destpath)
                else:
                    print "sandboxing %s: copying %s to %s" % (egg, srcpath, tempdir)
                    destdir = os.path.dirname(destpath)
                    if not os.path.exists(destdir):
                        os.makedirs(destdir)
                    shutil.copy(srcpath, destdir)
#             sys.exit(1)

    pthfile = os.path.join(tempdir, 'easy_instal.pth')
    with open(pthfile, 'w') as f:
        f.write(textwrap.dedent("""\
            import sys; sys.__plen = len(sys.path)
            %s
            import sys; new=sys.path[sys.__plen:]; del sys.path[sys.__plen:]; p=getattr(sys,'__egginsert',0); sys.path[p:p]=new; sys.__egginsert = p+len(new)
            """) % '\n'.join(sandboxed))

    sitefile = os.path.join(tempdir, 'site.py')
    with open(sitefile, 'w') as f:
        f.write(textwrap.dedent("""\
            def __boot():
                import sys, os, os.path
                PYTHONPATH = os.environ.get('PYTHONPATH')
                if PYTHONPATH is None or (sys.platform=='win32' and not PYTHONPATH):
                    PYTHONPATH = []
                else:
                    PYTHONPATH = PYTHONPATH.split(os.pathsep)

                pic = getattr(sys,'path_importer_cache',{})
                stdpath = sys.path[len(PYTHONPATH):]
                mydir = os.path.dirname(__file__)
                #print "searching",stdpath,sys.path

                for item in stdpath:
                    if item==mydir or not item:
                        continue    # skip if current dir. on Windows, or my own directory
                    importer = pic.get(item)
                    if importer is not None:
                        loader = importer.find_module('site')
                        if loader is not None:
                            # This should actually reload the current module
                            loader.load_module('site')
                            break
                    else:
                        try:
                            import imp # Avoid import loop in Python >= 3.3
                            stream, path, descr = imp.find_module('site',[item])
                        except ImportError:
                            continue
                        if stream is None:
                            continue
                        try:
                            # This should actually reload the current module
                            imp.load_module('site',stream,path,descr)
                        finally:
                            stream.close()
                        break
                else:
                    raise ImportError("Couldn't find the real 'site' module")

                #print "loaded", __file__

                known_paths = dict([(makepath(item)[1],1) for item in sys.path]) # 2.2 comp

                oldpos = getattr(sys,'__egginsert',0)   # save old insertion position
                sys.__egginsert = 0                     # and reset the current one

                for item in PYTHONPATH:
                    addsitedir(item)

                sys.__egginsert += oldpos           # restore effective old position

                d,nd = makepath(stdpath[0])
                insert_at = None
                new_path = []

                for item in sys.path:
                    p,np = makepath(item)

                    if np==nd and insert_at is None:
                        # We've hit the first 'system' path entry, so added entries go here
                        insert_at = len(new_path)

                    if np in known_paths or insert_at is None:
                        new_path.append(item)
                    else:
                        # new path after the insert point, back-insert it
                        new_path.insert(insert_at, item)
                        insert_at += 1

                sys.path[:] = new_path

            if __name__=='site':
                __boot()
                del __boot"""))


def install_egg(opts, pkg_name, install_cmd, install_path, setuptools_path,
                package_remappings, platform_remappings):
    import pkg_resources as pkg_r

    # install the egg to a temp dir
    tmpdir = tempfile.mkdtemp(prefix="rez-egg-download-")
    print "INSTALLING EGG FOR PACKAGE '%s' TO %s..." % (pkg_name, tmpdir)
    eggs_path = os.path.join(tmpdir, 'lib')
    bin_path = os.path.join(tmpdir, 'bin')
    os.makedirs(eggs_path)

    # old style required double dash as separator
    easy_install_args = [x for x in opts.extra_args if x != '--' and x.startswith('-')]
    easy_install_args.append(pkg_name)

    # Giant try/finally block to ensure that we get a chance to cleanup
    try:
        environ = dict(os.environ)
        pypath = environ.pop('REZ_ORIG_PYTHONPATH').split(os.path.pathsep)
        pypath = [setuptools_path, eggs_path] + _get_safe_pythonpath(pkg_name, pypath)
        environ['PYTHONPATH'] = os.path.pathsep.join(pypath)

        install_cmd = install_cmd % (tmpdir)
        install_cmd += ' '.join(easy_install_args)
        print "Running: %s" % install_cmd
        proc = sp.Popen(install_cmd, shell=True, env=environ)
        proc.wait()
        if proc.returncode:
            print
            error("A problem occurred running easy_install, the command was:\n%s" % install_cmd)
            sys.exit(proc.returncode)

        #########################################################################################
        # extract info from eggs
        #########################################################################################

        # add eggs to python path
        sys.path = [eggs_path] + sys.path
        distrs = list(pkg_r.find_distributions(eggs_path))

        if not distrs:
            error("easy_install failed to install the package")
            sys.exit(1)
        if len(distrs) != 1:
            error("should have only found one package in install directory")
            sys.exit(1)
        distr = distrs[0]

        print
        print "EXTRACTING DATA FROM %s..." % distr.location
        egg_name, d = _get_package_data_from_dist(distr, opts.force_platform,
                                                  package_remappings,
                                                  platform_remappings)

        tools = os.listdir(bin_path)
        if tools:
            d['tools'] = tools

        print
        print "FOUND EGG: %s" % egg_name
        if tools:
            print "FOUND PROGRAMS: %s" % ", ".join(tools)

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

        def _cpfile(filepath, destdir, make_ro=True):
            if opts.verbose:
                print "copying %s to %s..." % (filepath, destdir + '/')
            if not opts.dry_run:
                shutil.copy(filepath, destdir)
                if make_ro:
                    destfile = os.path.join(destdir, os.path.basename(filepath))
                    st = os.stat(destfile).st_mode
                    if make_ro:
                        # remove write
                        st ^= _g_w_stat
                    os.chmod(destfile, st)

        added_pkgs = []
        updated_pkgs = []
        existing_pkgs = []

        print
        print "BUILDING REZ PACKAGE FOR '%s'..." % egg_name

        # NOTE: variants is a list of lists, though at this point, there should
        # never be more than one entry
        variants = d.get("variants", [[]])

        pkg_path = os.path.join(install_path, egg_name, d["version"])
        meta_path = os.path.join(pkg_path, ".metadata")
        variant_path = os.path.join(pkg_path, *(variants[0]))
#             bin_path = os.path.join(variant_path, "bin")
        rezeggfile = os.path.join(meta_path, "rez_egg_info.txt")

        if os.path.exists(variant_path):
            if not opts.use_non_eggs and os.path.exists(pkg_path) and not os.path.exists(rezeggfile):
                print
                error(("package '%s' already exists, but was not created by "
                      "rez-egg-install. Use the --use-non-eggs option to skip this error, but note "
                      "that rez doesn't know if this package is properly configured.") % egg_name)

                sys.exit(1)

        if os.path.exists(variant_path):
            print ("skipping installation of '%s', the current variant appears to exist already " +
                   "- %s already exists. Delete this directory to force a reinstall.") % \
                (egg_name, variant_path)
            existing_pkgs.append(egg_name)
        else:
#             copytree(tmpdir, variant_path)
            _mkdir(meta_path, False)
            _mkdir(variant_path, bool(variants))

            # copy files
            for root, dirs, files in os.walk(tmpdir):
                subpath = root[len(tmpdir):].strip('/')
                dest_root = os.path.join(variant_path, subpath)
                _mkdir(dest_root)

                for name in dirs:
                    _mkdir(os.path.join(dest_root, name))

                # FIXME: for native libs we probably don't want to remove pyc files
                for name in files:
                    if not name.endswith(".pyc"):
                        _cpfile(os.path.join(root, name), dest_root)

            for path in reversed(destdirs):
                os.chmod(path, _g_r_stat | _g_x_stat)

            # create/update yaml
            print
            yaml_path = os.path.join(pkg_path, "package.yaml")
            updated = _update_package_yaml(yaml_path, d, opts.dry_run)
            if updated:
                updated_pkgs.append(egg_name)
            else:
                added_pkgs.append(egg_name)

            if not opts.dry_run:
                # timestamp
                timefile = os.path.join(meta_path, "release_time.txt")
                if not os.path.exists(timefile):
                    with open(timefile, 'w') as f:
                        f.write(str(int(time.time())))

                if not os.path.exists(rezeggfile):
                    with open(rezeggfile, 'w') as f:
                        f.write(str(_g_rez_egg_api_version))
    finally:
        if not opts.no_clean:
            print
            print "DELETING %s..." % eggs_path
            shutil.rmtree(tmpdir)

    for req in distr.requires():
        install_egg(opts, str(req), install_path, setuptools_path,
                    package_remappings, platform_remappings)

def _get_pip_install_cmd():
    proc = sp.Popen("pip --version", shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    out, err = proc.communicate()
    if proc.returncode:
        error("could not find pip: %s" % err)
        return
    # do not install any dependencies. we will recursively install them
    cmd = "pip install --no-deps "
    cmd += "--install-option='--install-base=""' "
    cmd += "--install-option='--install-purelib=lib' "
    cmd += "--install-option='--install-platlib=lib' "
    cmd += "--install-option='--install-scripts=bin' "
    cmd += "--install-option='--install-data=data' "
    cmd += " --root='%s' "
    return cmd

def _get_easy_install_cmd():
    # find easy_install
    proc = sp.Popen("easy_install --version", shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    out, err = proc.communicate()
    if proc.returncode:
        error("could not find easy_install.")
        return
    if out.split()[1] < '1.1.0':
        error("requires setuptools 1.1 or higher")
        return
    # do not install any dependencies. we will recursively install them
    cmd = "easy_install --no-deps "
    cmd += "--install-dir='%s/lib' "
    cmd += "--script-dir=bin "
    return cmd

#########################################################################################
# cmdlin
####################################################################################

def setup_parser(parser):
    import argparse

    rez_egg_remapping_file = os.getenv("REZ_EGG_MAPPING_FILE") or \
        ("%s/template/egg_remap.yaml" % module_root_path)

    parser.add_argument("pkg", metavar='PACKAGE', help="package name")
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
    parser.add_argument('extra_args', nargs=argparse.REMAINDER,
                        help="remaining arguments are passed to easy_install")

def command(opts, parser=None):
    try:
        import yaml
    except ImportError:
        # TODO: save the yaml path gathered on install and import yaml.py directly
        error("rez-egg-install uses the python binary found on the PATH instead of "
              "REZ_PYTHON_BINARY. Ensure that this python has yaml installed.")
        sys.exit(1)
        # This is required to successfully inspect modules, particularly "compiled extensions.

    print "Using python interpreter: %s" % sys.executable

#     pkg_name = opts.pkg

    install_evar = "REZ_EGG_PACKAGES_PATH"
    if opts.local:
        install_evar = "REZ_LOCAL_PACKAGES_PATH"

    install_path = os.getenv(install_evar)
    if not install_path:
        error("Expected $%s to be set." % install_evar)
        sys.exit(1)

    remappings = {}
    if opts.mapping_file:
        with open(opts.mapping_file, 'r') as f:
            s = f.read()
        remappings = yaml.load(s)
    package_remappings = remappings.get("package_mappings", {})

    platre = remappings.get("platform_mappings", {})
    platform_remappings = {}
    for k, v in platre.iteritems():
        platform_remappings[k.lower()] = v

    setuptools = ['setuptools']
    # find pip
    install_cmd = _get_pip_install_cmd()
    if not install_cmd:
        install_cmd = _get_easy_install_cmd()
        if not install_cmd:
            sys.exit(1)
    else:
        setuptools.append('pip')

    try:
        import pkg_resources as pkg_r
    except ImportError:
        error("couldn't import pkg_resources. You probably need to install "
              "the python setuptools package, you can get it at http://pypi.python.org/pypi/setuptools.")
        sys.exit(1)

    setuptools_path = tempfile.mkdtemp(prefix="rez-egg-setuptools-")

    print "Found pkg_resources: %s" % pkg_r.__file__

    try:
        _sandbox_eggs(setuptools_path, setuptools)

        install_egg(opts, opts.pkg, install_cmd, install_path, setuptools_path,
                    package_remappings, platform_remappings)
    finally:
        if not opts.no_clean:
            print
            print "DELETING %s..." % setuptools_path
            shutil.rmtree(setuptools_path)

#     print "Success! %d packages were installed, %d were updated." % (len(added_pkgs), len(updated_pkgs))
#     if not opts.dry_run:
#         if added_pkgs:
#             print "Newly installed packages: %s" % str(", ").join(added_pkgs)
#         if updated_pkgs:
#             print "Updated packages: %s" % str(", ").join(updated_pkgs)
#         if existing_pkgs:
#             print "Pre-existing packages: %s" % str(", ").join(existing_pkgs)



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
