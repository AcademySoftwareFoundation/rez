'''
Install packages and manage formulae repositories.
'''
import os
import sys
import argparse
from rez.formulae_manager import formulae_manager
from rez.util import get_close_pkgs
from rez.cli import error


SEARCH_FUZZINESS = 0.4

def setup_parser(parser):
    parser.add_argument("pkg", metavar='PACKAGE', help="Package name", nargs='?')
    parser.add_argument("-s", "--search", action="store_true", default=False,
        help="Search for a package in the formulae repositories")
    parser.add_argument("-i", "--install", action="store_true", default=False,
        help="Install the package PACKAGE")
    parser.add_argument("--lp", "--list-pkgs", dest="list_pkgs", action="store_true",
        default=False, help="List packages in tracked repositories")
    parser.add_argument("--lr", "--list-repos", dest="list_repos", action="store_true",
        default=False, help="List tracked package repositories")
    parser.add_argument("--ur", "--update-repos", dest="update_repos", action="store_true",
        default=False, help="Update tracked package repositories")
    parser.add_argument("-r", "--repo", dest="repo", type=int,
        help="Select a particular repo (by index). Used by --lp and --ur.")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
        default=False, help="Dry run mode")


def command(opts, parser=None):
    def _print_header():
        print "REPO PACKAGE"
        print "---- -------"

    def _get_repos(ignore_select=False):
        urls = formulae_manager.get_urls()
        if ignore_select or opts.repo is None:
            return list(enumerate(urls))
        idx = opts.repo - 1
        if (idx < 0) or (idx >= len(urls)):
            error("Invalid repository index.")
            sys.exit(1)
        return [(idx, urls[idx])]

    def _search_pkgs(pkg, urls):
        matches = []
        for i,url in urls:
            pkgs = formulae_manager.get_packages(url)
            matches_ = get_close_pkgs(pkg, pkgs, fuzziness=SEARCH_FUZZINESS)
            if matches_:
                matches += [(x[0],x[1],i) for x in matches_]
        return sorted(matches, key=lambda x:-x[1])

    def _get_pkg(pkg):
        urls = _get_repos()
        matches = _search_pkgs(pkg, urls)

        if matches:
            pkgs = [x[0] for x in matches]
            if pkg in pkgs:
                idx = [x[2] for x in matches if x[0]==pkg][0]
                url = [x[1] for x in urls if x[0]==idx][0]
                return pkg,url
            elif len(pkgs) == 1:
                print "Did you mean %s?" % pkgs[0]
            else:
                print "Did you mean one of:"
                print '\n'.join(pkgs)
        else:
            print "Package '%s' not found." % pkg
        sys.exit(1)

    if opts.list_repos:
        # list formulae repositories
        urls = _get_repos(True)
        for i,url in urls:
            print "%-4d %s" % (i+1, url)

    elif opts.list_pkgs:
        # list packages in repositories
        _print_header()
        urls = _get_repos()
        for i,url in urls:
            pkgs = formulae_manager.get_packages(url)
            for pkg in pkgs:
                print "%-4d %s" % (i+1, pkg)

    elif opts.update_repos:
        # update the formulae repositories
        urls = _get_repos()
        new_pkgs = []

        for i,url in urls:
            print "Updating repository #%d (%s)..." % (i+1, url)
            if not opts.dry_run:
                new_pkgs_ = formulae_manager.update_repository(url)
                if new_pkgs_:
                    new_pkgs += [(i,x) for x in new_pkgs_]
        print
        if new_pkgs:
            print "Packages were added:"
            _print_header()
            for i,pkg in new_pkgs:
                print "%-4d %s" % (i+1, pkg)
        else:
            print "No new packages were added."

    elif opts.search:
        # search for a package
        if not opts.pkg:
            error("Must supply a search term")
            sys.exit(1)

        urls = _get_repos()
        matches = _search_pkgs(opts.pkg, urls)

        if matches:
            _print_header()
            for m in matches:
                print "%-4d %s" % (m[2]+1, m[0])
        else:
            print "No matches found."

    else:
        # install a package
        if not opts.pkg:
            error("Must supply a package")
            sys.exit(1)

        pkg,url = _get_pkg(opts.pkg)
        formulae_manager.install_package(url, pkg, dry_run=opts.dry_run)
