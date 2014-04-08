import os
import yaml
from rez.util import OrderedDict
from contextlib import contextmanager

class quoted(str):
    """
    wrap a string in this class to force a quoted representation when passed
    to `yaml.dump`.
    """
    pass

class literal(str):
    """
    wrap a string in this class to force a (multi-line) representation
    when passed to `yaml.dump`.
    """
    pass

# create a shortcut that is more rez-friendly
rex = literal

def quoted_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
yaml.add_representer(quoted, quoted_presenter)

def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
yaml.add_representer(literal, literal_presenter)

def ordered_dict_presenter(dumper, data):
    return dumper.represent_dict(data.items())
yaml.add_representer(OrderedDict, ordered_dict_presenter)


def _entab(text, spaces=4):
    '\n'.join([(' ' * 4) + t for t in text.split('\n')])

def make_version_directory(path, metadata):
    name = metadata['name']

    if 'version' in metadata:
        basedir = os.path.join(path, name, metadata['version'])
    else:
        basedir = os.path.join(path, name)

    os.makedirs(basedir)

    if 'variants' in metadata:
        for variant in metadata['variants']:
            os.makedirs(os.path.join(basedir, *variant))
    return basedir

def _get_metadata(name):
    metadata = OrderedDict()
    metadata['config_version'] = 0  # note that even if this value is overridden, it will appear first
    parts = name.split('-')
    if len(parts) == 1:
        metadata['name'] = name
    else:
        metadata['name'], metadata['version'] = parts
    return metadata

def write_package_yaml(metafile, metadata):
    with open(metafile, 'w') as f:
        yaml.dump(metadata, f)

def write_package_py(metafile, metadata):
    with open(metafile, 'w') as f:
        for key, value in metadata.iteritems():
            if isinstance(value, rex):
                text = 'def %s():\n%s\n' % (key, _entab(value))
            else:
                text = '%s = %r\n' % (key, value)
            f.write(text)

@contextmanager
def make_package_yaml(name, path):
    """
    Context manager to create a package.yaml file::

        with make_package_yaml('python-2.7.4', local_path) as pkg:
            pkg['variants'] = [['platform-linux'],
                               ['platform-darwin']]
        with make_package_yaml('platform-linux', local_path) as pkg:
            pass
    """
    metadata = _get_metadata(name)

    yield metadata

    basedir = make_version_directory(path, metadata)

    metafile = os.path.join(basedir, 'package.yaml')
    write_package_yaml(metafile, metadata)

@contextmanager
def make_package_py(name, path):
    """
    Context manager to create a package.yaml file::

        with make_package_py('python-2.7.4', local_path) as pkg:
            pkg['variants'] = [['platform-linux'],
                               ['platform-darwin']]
        with make_package_py('platform-linux', local_path) as pkg:
            pass
    """
    metadata = _get_metadata(name)

    yield metadata

    # post-with-block:
    basedir = make_version_directory(path, metadata)

    metafile = os.path.join(basedir, 'package.py')
    write_package_py(metafile, metadata)

class PackageMaker(object):
    """
    Class-based approach to creating packages::

        maker = PackageMaker(local_path)

        pkg = maker.add_package('python-2.7.4')
        pkg['variants'] = [['platform-linux'],
                           ['platform-darwin']]

        maker.add_package('platform-linux')

        maker.write_packages()

    """
    def __init__(self, path, default_ext='yaml'):
        self.path = path
        self.default_ext = default_ext
        self.packages = []

    def add_package(self, name, ext=None):
        metadata = _get_metadata(name)
        self.packages[name] = (metadata, ext)
        return metadata

    def write_packages(self):
        for name, (metadata, ext) in self.packages.iteritems():
            ext = ext if ext else self.default_ext
            if ext == 'py':
                writer = write_package_py
            else:
                writer = write_package_yaml

        basedir = make_version_directory(self.path, metadata)
        metafile = os.path.join(basedir, 'package.' + ext)
        writer(name, metafile)
