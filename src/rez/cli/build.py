'''
Build a package from source.
'''
import os


def setup_parser_common(parser):
    """Parser setup common to both rez-build and rez-release."""
    from rez.build_process_ import get_build_process_types
    from rez.build_system import get_valid_build_systems

    process_types = get_build_process_types()
    parser.add_argument(
        "--process", type=str, choices=process_types, default="local",
        help="the build process to use (default: %(default)s).")

    # add build system option only if one build system is associated with cwd
    clss = get_valid_build_systems(os.getcwd())
    if len(clss) == 1:
        cls = clss[0]
        cls.bind_cli(parser)
    elif clss:
        types = [x.name() for x in clss]
        parser.add_argument(
            "-b", "--build-system", dest="buildsys", type=str, choices=types,
            help="the build system to use.")

    parser.add_argument(
        "--variants", nargs='+', type=int, metavar="INDEX",
        help="select variants to build (zero-indexed).")
    parser.add_argument(
        "--ba", "--build-args", dest="build_args", type=str, metavar="ARGS",
        help="arguments to pass to the build system. Alternatively, list these "
        "after a '--'")
    parser.add_argument(
        "--cba", "--child-build-args", dest="child_build_args", type=str,
        metavar="ARGS",
        help="arguments to pass to the child build system, if any. "
        "Alternatively, list these after a second '--'.")


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-c", "--clean", action="store_true",
        help="clear the current build before rebuilding.")
    parser.add_argument(
        "-i", "--install", action="store_true",
        help="install the build to the local packages path. Use --prefix to "
        "choose a custom install path.")
    parser.add_argument(
        "-p", "--prefix", type=str, metavar='PATH',
        help="install to a custom path.")
    parser.add_argument(
        "--fail-graph", action="store_true",
        help="if the build environment fails to resolve due to a conflict, "
        "display the resolve graph as an image.")
    parser.add_argument(
        "-s", "--scripts", action="store_true",
        help="create build scripts rather than performing the full build. "
        "Running these scripts will place you into a build environment, where "
        "you can invoke the build system directly.")
    parser.add_argument(
        "--view-pre", action="store_true",
        help="just view the preprocessed package definition, and exit.")
    setup_parser_common(parser)


def get_build_args(opts, parser, extra_arg_groups):
    attrs = ["build_args", "child_build_args"]
    groups = (extra_arg_groups or [[]]) + [[]]
    result_groups = []

    for attr, group in zip(attrs, groups):
        cli_attr = "--%s" % attr.replace("_", "-")
        option = getattr(opts, attr, None)
        if option:
            if group:
                parser.error("argument %s: not allowed with arguments after '--'"
                             % cli_attr)
            group = option.strip().split()

        result_groups.append(group)
    return result_groups[0], result_groups[1]


def command(opts, parser, extra_arg_groups=None):
    from rez.exceptions import BuildContextResolveError
    from rez.packages_ import get_developer_package
    from rez.build_process_ import create_build_process
    from rez.build_system import create_build_system
    from rez.serialise import FileFormat
    import sys

    # load package
    working_dir = os.getcwd()
    package = get_developer_package(working_dir)

    if opts.view_pre:
        package.print_info(format_=FileFormat.py, skip_attributes=["preprocess"])
        sys.exit(0)

    # create build system
    build_args, child_build_args = get_build_args(opts, parser, extra_arg_groups)
    buildsys_type = opts.buildsys if ("buildsys" in opts) else None

    buildsys = create_build_system(working_dir,
                                   package=package,
                                   buildsys_type=buildsys_type,
                                   opts=opts,
                                   write_build_scripts=opts.scripts,
                                   verbose=True,
                                   build_args=build_args,
                                   child_build_args=child_build_args)

    # create and execute build process
    builder = create_build_process(opts.process,
                                   working_dir,
                                   package=package,
                                   build_system=buildsys,
                                   verbose=True)

    try:
        builder.build(install_path=opts.prefix,
                      clean=opts.clean,
                      install=opts.install,
                      variants=opts.variants)
    except BuildContextResolveError as e:
        print >> sys.stderr, str(e)

        if opts.fail_graph:
            if e.context.graph:
                from rez.utils.graph_utils import view_graph
                g = e.context.graph(as_dot=True)
                view_graph(g)
            else:
                print >> sys.stderr, \
                    "the failed resolve context did not generate a graph."
        sys.exit(1)


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
