from rez.utils.data_utils import SourceCode
from rez.vendor import yaml
from rez.vendor.yaml.dumper import SafeDumper
from rez.vendor.yaml.nodes import ScalarNode, MappingNode
from rez.vendor.version.version import Version
from rez.vendor.version.requirement import Requirement
from types import FunctionType
from inspect import getsourcelines
from textwrap import dedent


class _Dumper(SafeDumper):
    """Dumper which can serialise custom types such as Version, and keeps
    long strings nicely formatted in >/| block-style format.
    """
    # modified from yaml.representer.SafeRepresenter.represent_str()
    def represent_str(self, data):
        tag = None

        if '\n' in data:
            style = '|'
        elif len(data) > 80:
            style = '>'
        else:
            style = None

        try:
            data = unicode(data, 'ascii')
            tag = u'tag:yaml.org,2002:str'
        except UnicodeDecodeError:
            try:
                data = unicode(data, 'utf-8')
                tag = u'tag:yaml.org,2002:str'
            except UnicodeDecodeError:
                data = data.encode('base64')
                tag = u'tag:yaml.org,2002:binary'
                style = '|'
        return self.represent_scalar(tag, data, style=style)

    def represent_as_str(self, data):
        return self.represent_str(str(data))

    def represent_function(self, data):
        loc = getsourcelines(data)[0][1:]
        code = dedent(''.join(loc))
        return self.represent_str(code)

    def represent_sourcecode(self, data):
        code = data.source
        return self.represent_str(code)


_Dumper.add_representer(str, _Dumper.represent_str)
_Dumper.add_representer(Version, _Dumper.represent_as_str)
_Dumper.add_representer(Requirement, _Dumper.represent_as_str)
_Dumper.add_representer(FunctionType, _Dumper.represent_function)
_Dumper.add_representer(SourceCode, _Dumper.represent_sourcecode)


"""
class OrderedDumper(_Dumper):
    order = None

    # modified from yaml.representer.BaseRepresenter.represent_mapping()
    def represent_dict(self, data):
        mapping = data
        value = []
        node = MappingNode(u'tag:yaml.org,2002:map', value, flow_style=None)
        if self.alias_key is not None:
            self.represented_objects[self.alias_key] = node
        best_style = True
        if hasattr(mapping, 'items'):
            mapping = self._sort_mapping(mapping)
        for item_key, item_value in mapping:
            node_key = self.represent_data(item_key)
            node_value = self.represent_data(item_value)
            if not (isinstance(node_key, ScalarNode) and not node_key.style):
                best_style = False
            if not (isinstance(node_value, ScalarNode) and not node_value.style):
                best_style = False
            value.append((node_key, node_value))
        if self.default_flow_style is not None:
            node.flow_style = self.default_flow_style
        else:
            node.flow_style = best_style
        return node

    def _sort_mapping(self, mapping):
        mapping = mapping.copy()
        new_mapping = []
        for key in (self.order or []):
            if key in mapping:
                item = (key, mapping[key])
                new_mapping.append(item)
                del mapping[key]
        new_mapping.extend(sorted(mapping.items()))
        return new_mapping


OrderedDumper.add_representer(dict, OrderedDumper.represent_dict)
"""

def dump_yaml(data, Dumper=_Dumper, default_flow_style=False):
    """Returns data as yaml-formatted string."""
    content = yaml.dump(data,
                        default_flow_style=default_flow_style,
                        Dumper=Dumper)
    return content.strip()


def load_yaml(filepath):
    """Convenience function for loading yaml-encoded data from disk."""
    with open(filepath) as f:
        txt = f.read()
    return yaml.load(txt)
