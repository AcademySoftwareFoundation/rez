'''
Convert a package.yaml file to a package.py file.
'''
from rez.config import config
from rez.exceptions import ResourceError
from rez.packages import Package
from rez.package_maker_ import make_py_package
from rez.resources import iter_resources
import os
import shutil


def setup_parser(parser, completions=False):

    parser.add_argument("-f", "--force", dest="force", action="store_true",
        help="force the package.py file to be rewritten even if it already"
        "exists.")
    parser.add_argument("--path", type=str, default=None,
        help="convert all package.yaml files found in the provided search"
        "path. If not provided a 'developer package resource' will be loaded"
        "from the current directory.")


def command(opts, parser, extra_arg_groups=None):

    force = opts.force
    path = opts.path if opts.path else os.getcwd()

    if opts.path:
        resources = load_resources_from_path(path)
    else:
        resources = [load_developer_resources(path)]

    for yaml_resource, py_resource in resources:
        if py_resource and not force:
            raise ResourceError("package.py definition file already found "
                                "under %s. Use --force to overwrite." % path)

        if not yaml_resource:
            raise ResourceError("Unable to find package.yaml definition file "
                                "under %s." % path)

        package = convert_resource_to_package(yaml_resource)
        metafile = convert_package_to_py(package)

        shutil.copy(metafile, os.path.dirname(yaml_resource.path))


def convert_resource_to_package(resource):
    package = Package(resource)
    package.validate_data()
    return package


def convert_package_to_py(package):
    tmpdir = os.path.join(config.tmpdir, "yaml2py")

    with make_py_package(package.name, package.version, tmpdir) as py_package:
        py_package.set_uuid(package.uuid)
        py_package.set_description(package.description)
        py_package.set_authors(package.authors)
        py_package.set_help(package.help)

        if package.private_build_requires:
            py_package.set_private_build_requires(*map(str, package.private_build_requires))

        if package.build_requires:
            py_package.set_build_requires(*map(str, package.build_requires))

        if package.requires:
            py_package.set_requires(*map(str, package.requires))

        if package.variants:
            for variant in package.variants:
                py_package.add_variant(*map(str, variant))

        if package.commands:
            def _filter_func(command):
                return not command.startswith("comment")

            commands = package.commands.split("\n")
            py_package.set_commands(filter(_filter_func, commands))

        if "external" in package._data:
            custom = {"external": package._data.get("external")}
            py_package.set_custom(custom)

        return os.path.join(py_package.base_path, "package.py")


def load_developer_resources(path):
    it = iter_resources(
        resource_keys='package.*',
        search_path=path,
        root_resource_key="folder.dev_packages_root")
    resources = list(it)

    if not resources:
        raise ResourceError("No package definition file found under %s" % path)

    return _map_resources(resources)


def load_resources_from_path(path):

    consumed_resources = {}

    for resource in iter_resources(resource_keys='package.*',
                                   search_path=[path],
                                   root_resource_key="folder.packages_root",
                                   variables={}):

        handle = "%s-%s" % (resource.variables["name"],
                            resource.variables["version"])
        consumed_resources.setdefault(handle, []).append(resource)

    for handle, resources in consumed_resources.items():
        yield _map_resources(resources)


def _map_resources(resources):
    py_resource = None
    yaml_resource = None

    for resource in resources:
        if resource.variables["ext"] == "py":
            py_resource = resource
        elif resource.variables["ext"] == "yaml":
            yaml_resource = resource

    return yaml_resource, py_resource
