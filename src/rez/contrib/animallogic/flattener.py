from rez.platform_ import platform_
from rez.util import print_debug
import os.path


class Flattener(object):

    def __init__(self, paths, base_target):
        """
        Args:
            path (list of str): the paths to be flattened.
            base_target (str): where the contents should be flattened too.
        """
        self._paths = paths
        self._base_target = base_target
        self._indent = 0

    def flatten(self):
        """Flatten each path individually..

        Returns:
            A list of paths that should be retained in the resulting
            environment variable.  (Generally this will nearly always be an
            empty list, however special files (such as Python egg files)
            require this functionality).
        """
        paths_to_retain_in_variable = []

        for path in self._paths:
            self._indent = 2

            if not path.strip():
                self._debug("+ '%s' - skipping, null value detected." % path)
                continue

            if os.path.exists(path):
                self._debug("+ %s" % path)

                for path in self._flatten_path(path):
                    if path not in paths_to_retain_in_variable:
                        paths_to_retain_in_variable.append(path)

            else:
                self._debug("+ %s - skipping, does not exist to flatten." % path)

        return paths_to_retain_in_variable

    def _flatten_path(self, path):
        """Flatten the contents of a specific path.

        Args:
            path (str): The path to flatten.

        Returns:
            A list of paths that should be retained in the resulting
            environment variable.  (Generally this will nearly always be an
            empty list, however special files (such as Python egg files)
            require this functionality).
        """
        raise NotImplemented

    def symlink(self, source, target):
        item = os.path.basename(source)

        if os.path.exists(target):
            self._debug("- %s - skipping, already seen in %s" % (item, os.readlink(target)))
            return False

        else:
            self._debug("- %s -> %s" % (item, target))
            platform_.symlink(source, target)
            return True

    def _debug(self, s):
        print_debug("%s%s" % (" " * self._indent, s), module="flatten_env")


class DefaultFlattener(Flattener):

    def _flatten_path(self, path):
        self._indent = 4

        if os.path.isdir(path):
            contents = os.listdir(path)

            if not contents:
                self._debug("- skipping, is empty.")
                return []

            for item in contents:
                source = os.path.join(path, item)
                target = os.path.join(self._base_target, item)

                self.symlink(source, target)

        else:
            basename = os.path.basename(path)
            target = os.path.join(self._base_target, basename)

            self.symlink(path, target)

            self._debug("~ retaining %s in variable." % target)
            return [target]

        return []


class PythonPathFlattener(DefaultFlattener):
    """
    If the path is a directory we have a couple of choices:

        1. If the directory ends in .egg then it is most likely an egg file 
           that has already been extracted.  This means they probably contain
           EGG-INFO folders etc that might clash with other similar directories
           in the PYTHONPATH.  In these we create the symlink to the original
           .egg directory (rather than it's contents) and ensure that this
           directory remains in the PYTHONPATH.
        2. If the directory contains an .egg file which is not listed
           explicitly in the PYTHONPATH then chances are it is being loaded
           using some .pth and site.py magic.  To avoid multiple instances of
           these files we ignore *.pth and site.py files, create symlinks for
           everything else, and ensure that the .egg file is explicitly added
           back into the PYTHONPATH.
        3. If the directory contains other directories, it is possible these
           provide a namespace using the pkg_resources mechanism.  As there is
           no easy way to detect this, we must merge all subdirectories
           together into one local flattened structure.
        4. For anything else that might be contained in the directory, we treat
           it as a normal file.  We assume that these are standard .py files as
           so create symlinks back to the original source.  Even if they are
           not, there is not much else we can do.

    If the path is a file then there is a high chance it is an egg file (a zip
    archive).  Even if it's not an egg file, there's little else we can do
    here.  In these cases we create a symlink as usual and ensure that the file
    being pointed to remains in the final PYTHONPATH variable by passing it
    back to the caller.

    In all cases, when making a symlink we only create the link if it doesn't
    already exists.  This means if foo.py is encountered twice in the
    PYTHONPATH only the first occurence wins, which is the same behaviour
    Python itself would use if we had not modified the PYTHONPATH at all.
    """

    EGG_SUFFIX = ".egg"
    PTH_SUFFIX = ".pth"
    SITE_FILE = "site.py"
    SITE_FILE_COMPILED = "site.pyc"

    def makedirs(self, target):

        if not os.path.isdir(target):
            self._debug("- %s mkdir" % (target))
            os.makedirs(target)

    def _flatten_path(self, path):
        self._indent = 4

        if os.path.isdir(path):
            if path.endswith(self.EGG_SUFFIX):
                # The current path is a .egg file (scenario 1 in the class
                # docstring).  In this case we create a symlink and ensure it
                # remains in the PYTHONPATH.
                return self._flatten_egg(path)

            contents = os.listdir(path)

            # Otherwise check to see if it contains one or more egg files that
            # are not already in the PYTHONPATH (scenario 2 in the docstring
            # for this class).
            eggs = filter(lambda x: x.endswith(self.EGG_SUFFIX), contents)
            paths_to_retain, contents = self._filter_eggs_from_contents(path, eggs, contents)

            for item in contents:
                self._indent = 4

                if os.path.isdir(os.path.join(path, item)):
                    # It's a directory.  Because of Python's namespace magic,
                    # it is possible to have multiple directories with the same
                    # name in the PYTHONPATH, each providing the same top level
                    # namespace (and different child namespaces).  As a result
                    # we must merge all directories that we come across to
                    # ensure we pick up all the potential namespaces.  The
                    # easiest way to do this without assuming anything about
                    # the structure of the python code is to flatten the folder
                    # structure locally, with symlinks off to the actualy files
                    # underneath.  As expected, the first occurence of a file
                    # wins.
                    self._flatten_subfolder(path, item)

                else:
                    # Files can just be linked in normally.
                    self._flatten_file(path, item)

            return paths_to_retain

        else:
            # This is a file, which means it must be an egg archive.  We can
            # make a link to this as usual, however the path must remain in the
            # resulting PYTHONPATH variable to ensure it is importable.  This
            # is scenario 4 in the docstring.
            return self._flatten_egg(path)

    def _flatten_egg(self, path):
        basename = os.path.basename(path)
        target = os.path.join(self._base_target, basename)

        self.symlink(path, target)

        self._debug("~ retaining %s in PYTHONPATH." % target)
        return [target]

    def _flatten_file(self, path, item):
        source = os.path.join(path, item)
        target = os.path.join(self._base_target, item)

        self.symlink(source, target)

    def _flatten_subfolder(self, path, item):
        subfolder = os.path.join(path, item)
        target = os.path.join(self._base_target, item)
        self.makedirs(target)

        for root, dirs, files in os.walk(subfolder):
            relative = os.path.relpath(root, path)
            depth = relative.count(os.path.sep) + 1
            self._indent = 4 + (depth * 2)

            for file_ in files:
                source = os.path.join(root, file_)
                target = os.path.join(self._base_target, relative, file_)

                self.symlink(source, target)

            for dir_ in dirs:
                target = os.path.join(self._base_target, relative, dir_)

                self.makedirs(target)

    def _filter_eggs_from_contents(self, path, eggs, contents):
        paths_to_retain = []

        for egg in eggs:
            source = os.path.join(path, egg)
            target = os.path.join(self._base_target, egg)

            if source in self._paths:
                # The egg is already in the PYTHONPATH, it will be dealt
                # with on another iteration, so we can ignore it.
                # (scenario 4 in the docstring for this class).
                self._debug("- %s - skipping, already in PYTHONPATH" % (egg))
                contents.remove(egg)

            else:
                # The egg isn't in the PYTHONPATH so a .pth and site.py
                # file must be loading it.  Technically we only need to do
                # this once, no makker how many eggs we discover in the
                # path.  However to preserve the clarity of the flattening
                # logic we do it on each iteration.
                for file_ in (self.SITE_FILE, self.SITE_FILE_COMPILED):
                    if file_ in contents:
                        contents.remove(file_)
                contents = filter(lambda x: not x.endswith(self.PTH_SUFFIX), contents)

                self._debug("~ retaining %s in PYTHONPATH." % target)
                paths_to_retain.append(target)

        return paths_to_retain, contents


def get_flattener_for_variable(variable):
    if variable == "PYTHONPATH":
        return PythonPathFlattener

    return DefaultFlattener
