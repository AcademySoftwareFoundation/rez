"""
Install a pip-compatible python package, incl. dependencies, as rez packages.
"""

import time
import contextlib

quiet = False


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-i", "--install", nargs="+",
        help="Install the package")
    parser.add_argument(
        "-s", "--search", nargs="+",
        help="Search for the package on PyPi")
    parser.add_argument(
        "-r", "--release", action="store_true",
        help="Install as released package; if not set, package is installed "
        "locally only")
    parser.add_argument(
        "-va", "--variant", action="append",
        help="Install package as variant, may be called multiple times.")
    parser.add_argument(
        "-p", "--prefix", type=str, metavar="PATH",
        help="Install to a custom package repository path.")
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Pre-emptively answer the question to continue")
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Do not output anything to stdout, overridden with -vvv")

    # Additional pip-specific arguments
    parser.add_argument(
        "--no-deps", action="store_true", help="Do not install dependencies")
    parser.add_argument(
        "--index-url", default="https://pypi.org/simple",
        help="Provide a custom PyPI index")


def tell(msg, newlines=1):
    if quiet:
        return

    import sys
    sys.stdout.write("%s%s" % (msg, "\n" * newlines))


def error(msg, newlines=1):
    import sys
    sys.stderr.write("ERROR: %s\n" % msg)


def ask(msg):
    from rez.vendor.six.six.moves import input

    try:
        return input(msg).lower() in ("", "y", "yes", "ok")
    except EOFError:
        return True  # On just hitting enter
    except KeyboardInterrupt:
        return False


@contextlib.contextmanager
def stage(msg, timing=True):
    tell(msg, 0)
    t0 = time.time()

    try:
        yield
    except Exception:
        tell("fail")
        raise
    else:
        if timing:
            tell("ok - %.2fs" % (time.time() - t0))
        else:
            tell("ok")


def command(opts, parser, extra_arg_groups=None):
    import os
    import shutil
    import tempfile

    global quiet
    quiet = (opts.verbose < 2) and opts.quiet

    if opts.search:
        _search(opts)

    if opts.install:
        t0 = time.time()
        tmpdir = tempfile.mkdtemp(suffix="-rez", prefix="wheel-")
        tempdir = os.path.join(tmpdir, "rez_staging", "python")
        success = False

        try:
            _install(opts, tempdir)
            success = True

        finally:
            shutil.rmtree(tmpdir)

        tell(
            ("Completed in %.2fs" % (time.time() - t0))
            if success else "Failed"
        )


def _install(opts, tempdir):
    import os
    from rez import wheel
    from rez.config import config

    python_version = wheel.python_version()
    pip_version = wheel.pip_version()

    if not python_version:
        error("Python could not be found")
        exit(1)

    if not pip_version:
        error("pip could not be found")
        exit(1)

    if pip_version < "19.0.0":
        error("Requires pip>=19")
        exit(1)

    tell("Using python-%s" % python_version)
    tell("Using pip-%s" % pip_version)

    try:
        with stage("Reading package lists... "):
            distributions = wheel.download(
                opts.install,
                tempdir=tempdir,
                no_deps=opts.no_deps,
                index_url=opts.index_url,
            )
    except OSError as e:
        tell(e)
        exit(1)

    packagesdir = opts.prefix or (
        config.release_packages_path if opts.release
        else config.local_packages_path
    )

    with stage("Discovering existing packages... "):
        new, exists = list(), list()
        for dist in distributions:
            package = wheel.convert(dist, variants=opts.variant)

            if wheel.exists(package, packagesdir):
                exists.append(package)
            else:
                new.append(package)

    if not new:
        for package in exists:
            tell("%s-%s was already installed" % (
                package.name, package.version
            ))

        return tell("No new packages were installed")

    size = sum(
        os.path.getsize(os.path.join(dirpath, filename))
        for dirpath, dirnames, filenames in os.walk(tempdir)
        for filename in filenames
    ) / (10.0 ** 6)  # mb

    # Determine column width for upcoming printing
    all_ = new + exists
    max_name = max((i.name for i in all_), key=len)
    max_version = max((str(i.version) for i in all_), key=len)
    row_line = "  {:<%d}{:<%d}{}" % (len(max_name) + 4, len(max_version) + 2)

    def format_variants(package):
        return (
            "/".join(str(v) for v in package.variants[0])
            if package.variants else ""
        )

    tell("The following NEW packages will be installed:")
    for package in new:
        tell(row_line.format(
            package.name,
            package.version,
            format_variants(package)
        ))

    if exists:
        tell("The following packages will be SKIPPED:")
        for package in exists:
            tell(row_line.format(
                package.name,
                package.version,
                format_variants(package)
            ))

    tell("Packages will be installed to %s" % packagesdir)
    tell("After this operation, %.2f mb will be used." % size)

    if not opts.yes and not opts.quiet:
        if not ask("Do you want to continue? [Y/n] "):
            return

    for index, package in enumerate(new):
        msg = "(%d/%d) Installing %s-%s... " % (
            index + 1, len(new),
            package.name,
            package.version,
        )

        with stage(msg, timing=False):
            wheel.deploy(
                package,
                path=packagesdir
            )

    tell("%d installed, %d skipped" % (len(new), len(exists)))


def _search(opts):
    import subprocess
    subprocess.check_call([
        "python", "-m", "pip" "search"
    ] + opts.search).wait()


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
