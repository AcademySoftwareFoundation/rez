"""
TMA's rez package handler

Usage example:
    rez pkg-handler python-3.9.13 --arg1 --arg2
"""
import os
import json
from rez.command import Command

command_behavior = {
    'hidden': False,  # show in `rez --help`
    'arg_mode': None,  # None | "passthrough" | "grouped"
}

def setup_parser(parser, completions=False):
    parser.add_argument(
        'PKG', type=str, nargs='?',
        help='[package]-[version] to handle. Version must be exact (exist on locally)')
    parser.add_argument(
        '-r', '--pkg-root', dest='pkg_root', type=str,
        default=None,
        help='Package Root to look for package')
    parser.add_argument(
        '--add-variant', dest='to_add', type=str,
        default=[], action='append',
        help='variants to add, path separated by forward slashes')
    parser.add_argument(
        '--remove-variant', dest='to_remove', type=str,
        default=[], action='append',
        help='variants to remove, path separated by forward slashes')
    parser.add_argument(
        '--fetch-variants', dest='fetch_variants', action='store_true',
        help='variants to add, path separated by forward slashes')
    parser.add_argument(
        '-d', '--dry-run', dest='dry_run', action='store_true',
        help='Dry run, do not save anything')
    
def get_pkg_name_version(pkg):
    name = '-'.join(pkg.split('-')[0:-1])
    version = pkg.split('-')[-1]
    return name, version

def variant_subpath_to_list(variant_subpath):
    return variant_subpath.rstrip('"').lstrip('"').split('/')

def command(opts, parser=None, extra_arg_groups=None):
    from rez.config import config
    from rez.package_hander import PackageHandler

    def _validate_pkg_root():
        if not opts.pkg_root:
            return False
        local_roots = [os.path.normpath(r) for r in config.packages_path]
        if not opts.pkg_root in local_roots:
            return False
        return True
    
    def _validate_package():
        if not opts.PKG:
            return False
        if len(opts.PKG.split('-')) < 2:
            return False
        name, version = get_pkg_name_version(opts.PKG)
        pkg_path = os.path.join(pkg_root, name, version)
        if not os.path.isdir(pkg_path):
            return False
        return True
        
    if not _validate_pkg_root():
        parser.error('"-r/--pkg-root must be defined and be configured in rez\'s config (with proper casing)')
    pkg_root = os.path.normpath(opts.pkg_root)
    if not _validate_package():
        parser.error('package must be provided with a full version (mypackage-2.3.0), and found in the provided "-r/--pkg-root"')
    name, version = get_pkg_name_version(opts.PKG)
    
    pkg_handler = PackageHandler(pkg_root=pkg_root, name=name, version=version)
    
    if opts.to_add:
        for variant in opts.to_add:
            variant_list = variant_subpath_to_list(variant)
            added = pkg_handler.add_variant(variant=variant_list)
            if added:
                print('Variant "{}" successfully added'.format(variant))
            else:
                print('WARNING: Variant "{}" already exists'.format(variant))

    if opts.to_remove:
        for variant in opts.to_remove:
            variant_list = variant_subpath_to_list(variant)
            removed = pkg_handler.remove_variant(variant=variant_list)
            if removed:
                print('Variant "{}" successfully removed'.format(variant))
            else:
                print('WARNING: Variant "{}" not found in package'.format(variant))

    if opts.fetch_variants:
        result = {'variants': pkg_handler.fetch_variants()}
        print(json.dumps(result))
        

class CommandPkgHandler(Command):
    @classmethod
    def name(cls):
        return 'pkg-handler'

def register_plugin():
    return CommandPkgHandler
