from rez.vendor.six import six
from rez.config import config
from rez.packages_ import Package
from rez.serialise import load_from_file, FileFormat, set_objects
from rez.packages_ import create_package
from rez.exceptions import PackageMetadataError, InvalidPackageError
from rez.utils.system import add_sys_paths
from rez.utils.sourcecode import SourceCode
from rez.utils.logging_ import print_info, print_error
from inspect import isfunction
import os.path
import stat


class DeveloperPackage(Package):
    """A developer package.

    This is a package in a source directory that is subsequently built or
    released.
    """
    def __init__(self, resource):
        super(DeveloperPackage, self).__init__(resource)
        self.filepath = None

        # include modules, derived from any present @include decorators
        self.includes = None

    @property
    def root(self):
        if self.filepath:
            return os.path.dirname(self.filepath)
        else:
            return None

    @classmethod
    def from_path(cls, path, format=None):
        """Load a developer package.

        A developer package may for example be a package.yaml or package.py in a
        user's source directory.

        Args:
            path: Directory containing the package definition file, or file
                path for the package file itself
            format: which FileFormat to use, or None to check both .py and .yaml

        Returns:
            `Package` object.
        """
        name = None
        data = None

        if format is None:
            formats = (FileFormat.py, FileFormat.yaml)
        else:
            formats = (format,)

        try:
            mode = os.stat(path).st_mode
        except (IOError, OSError):
            raise PackageMetadataError(
                "Path %r did not exist, or was not accessible" % path)
        is_dir = stat.S_ISDIR(mode)

        for name_ in config.plugins.package_repository.filesystem.package_filenames:
            for format_ in formats:
                if is_dir:
                    filepath = os.path.join(path, "%s.%s" % (name_,
                                                             format_.extension))
                    exists = os.path.isfile(filepath)
                else:
                    # if format was not specified, verify that it has the
                    # right extension before trying to load
                    if format is None:
                        if os.path.splitext(path)[1] != format_.extension:
                            continue
                    filepath = path
                    exists = True

                if exists:
                    data = load_from_file(filepath, format_, disable_memcache=True)
                    break
            if data:
                name = data.get("name")
                if name is not None or isinstance(name, six.string_types):
                    break

        if data is None:
            raise PackageMetadataError("No package definition file found at %s" % path)

        if name is None or not isinstance(name, six.string_types):
            raise PackageMetadataError(
                "Error in %r - missing or non-string field 'name'" % filepath)

        package = create_package(name, data, package_cls=cls)

        # preprocessing
        result = package._get_preprocessed(data)

        if result:
            package, data = result

        package.filepath = filepath

        # find all includes, this is needed at install time to copy the right
        # py sourcefiles into the package installation
        package.includes = set()

        def visit(d):
            for k, v in d.items():
                if isinstance(v, SourceCode):
                    package.includes |= (v.includes or set())
                elif isinstance(v, dict):
                    visit(v)

        visit(data)

        package._validate_includes()

        return package

    def get_reevaluated(self, objects):
        """Get a newly loaded and re-evaluated package.

        Values in `objects` are made available to early-bound package
        attributes. For example, a re-evaluated package might return a different
        value for an early-bound 'private_build_requires', depending on the
        variant currently being built.

        Args:
            objects (`dict`): Variables to expose to early-bound package attribs.

        Returns:
            `DeveloperPackage`: New package.
        """
        with set_objects(objects):
            return self.from_path(self.root)

    def _validate_includes(self):
        if not self.includes:
            return

        definition_python_path = self.config.package_definition_python_path

        if not definition_python_path:
            raise InvalidPackageError(
                "Package %s uses @include decorator, but no include path "
                "has been configured with the 'package_definition_python_path' "
                "setting." % self.filepath)

        for name in self.includes:
            filepath = os.path.join(definition_python_path, name)
            filepath += ".py"

            if not os.path.exists(filepath):
                raise InvalidPackageError(
                    "@include decorator requests module '%s', but the file "
                    "%s does not exist." % (name, filepath))

    def _get_preprocessed(self, data):
        """
        Returns:
            (DeveloperPackage, new_data) 2-tuple IFF the preprocess function
            changed the package; otherwise None.
        """
        from rez.serialise import process_python_objects
        from rez.utils.data_utils import get_dict_diff_str
        from copy import deepcopy

        with add_sys_paths(config.package_definition_build_python_paths):
            preprocess_func = getattr(self, "preprocess", None)
            funcname = None

            if preprocess_func:
                print_info("Applying preprocess from package.py")

            else:
                # load globally configured preprocess function
                dotted = self.config.package_preprocess_function

                if not dotted:
                    return None

                elif isfunction(dotted):
                    funcname = dotted.__name__
                    preprocess_func = dotted

                elif isinstance(dotted, six.string_types):
                    if '.' not in dotted:
                        print_error(
                            "Setting 'package_preprocess_function' must be of "
                            "form 'module[.module.module...].funcname'. "
                            "Package preprocessing has not been applied."
                        )
                        return None

                    name, funcname = dotted.rsplit('.', 1)

                    try:
                        module = __import__(name=name, fromlist=[funcname])
                    except Exception as e:
                        print_error(
                            "Failed to load preprocessing function '%s': %s"
                            % (dotted, str(e))
                        )

                        return None

                    setattr(module, "InvalidPackageError", InvalidPackageError)
                    preprocess_func = getattr(module, funcname)

                else:
                    print_error(
                        "Invalid package_preprocess_function: %s" % funcname
                    )
                    return None

            if not preprocess_func or not isfunction(preprocess_func):
                print_error("Function '%s' not found" % funcname)
                return None

            print_info("Applying preprocess function %s" % funcname)

            preprocessed_data = deepcopy(data)

            # apply preprocessing
            try:
                preprocess_func(this=self, data=preprocessed_data)
            except InvalidPackageError:
                raise
            except Exception as e:
                print_error("Failed to apply preprocess: %s: %s"
                            % (e.__class__.__name__, str(e)))
                return None

        # if preprocess added functions, these may need to be converted to
        # SourceCode instances
        preprocessed_data = process_python_objects(preprocessed_data)

        if preprocessed_data == data:
            return None

        # recreate package from modified package data
        package = create_package(self.name, preprocessed_data,
                                 package_cls=self.__class__)

        # print summary of changed package attributes
        txt = get_dict_diff_str(
            data,
            preprocessed_data,
            title="Package attributes were changed in preprocessing:"
        )
        print_info(txt)

        return package, preprocessed_data
