"""
Run the Rez GUI application.
"""


def setup_parser(parser, completions=False):
    FILE_action = parser.add_argument(
        "FILE", type=str, nargs='*',
        help="context files")

    if completions:
        from rez.cli._complete_util import FilesCompleter
        FILE_action.completer = FilesCompleter()


def command(opts, parser=None, extra_arg_groups=None):
    from rez.exceptions import RezGuiQTImportError

    try:
        from rezgui.app import run
        run(opts, parser)
    except RezGuiQTImportError as e:
        # In order for rez-gui to work, PyQt/PySide needs to be installed into
        # Rez's installation virtualenv. Many studios will already have PyQt/
        # PySide available as rez packages though, and installing them again is
        # a pain.
        #
        # An alternative approach is to use the 'rezgui' rez package, which can
        # be created using the 'rez-bind' tool. This circumvents the rez install,
        # by pulling in PyQt/PySide dependencies (and rez itself) as rez packages.
        # With this approach, you can run rez-gui like so:
        #
        # ]$ rez-env rezgui pyside -- rez-gui
        #
        # A studio will often wrap this into a script or function, or use a rez
        # suite, to provide this wrapped rez-gui binary instead. However, when
        # rez resolves an environment, it prefixes $PATH with its bin directory
        # once more, which can cause the native 'rez-gui' binary to become
        # visible once more (and that's us here in the file you're reading!).
        #
        # In order to fix this, we find the other rez-gui binary, move its path
        # to the front of PATH, and try again.
        import sys
        import os
        import os.path
        from rez.backport.shutilwhich import which

        binary_filepath = os.path.realpath(sys.argv[0])
        current_bin_path = os.path.dirname(binary_filepath)
        paths = os.environ.get("PATH", "").split(os.pathsep)

        # find other rez-gui
        reduced_paths = []
        for i, path in enumerate(paths):
            if path and (os.path.realpath(path) != current_bin_path):
                reduced_paths.append(path)

        env = os.environ.copy()
        env["PATH"] = os.pathsep.join(reduced_paths)
        executable = which("rez-gui", env=env)
        if not executable:
            raise e

        # run other gui (replaces current process)
        new_paths = [os.path.dirname(executable)] + paths
        env["PATH"] = os.pathsep.join(new_paths)
        executable = os.path.abspath(executable)
        os.execve(executable, sys.argv[1:], env)
