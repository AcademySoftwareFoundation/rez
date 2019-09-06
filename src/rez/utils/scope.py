from __future__ import print_function

from rez.utils.formatting import StringFormatMixin, StringFormatType
import sys


class RecursiveAttribute(dict, StringFormatMixin):
    """An object that can have new attributes added recursively::

        >>> a = RecursiveAttribute()
        >>> a.foo.bah = 5
        >>> a.foo['eek'] = 'hey'
        >>> a.fee = 1

        >>> print(a.to_dict())
        {'foo': {'bah': 5, 'eek': 'hey'}, 'fee': 1}

    A recursive attribute can also be created from a dict, and made read-only::

        >>> d = {'fee': {'fi': {'fo': 'fum'}}, 'ho': 'hum'}
        >>> a = RecursiveAttribute(d, read_only=True)
        >>> print(str(a))
        {'fee': {'fi': {'fo': 'fum'}}, 'ho': 'hum'}
        >>> print(a.ho)
        hum
        >>> a.new = True
        AttributeError: 'RecursiveAttribute' object has no attribute 'new'
    """
    format_expand = StringFormatType.unchanged

    def __init__(self, data=None, read_only=False):
        self.__dict__.update(dict(data={}, read_only=read_only))
        self._update(data or {})

    def __getattr__(self, attr):
        def _noattrib():
            raise AttributeError("'%s' object has no attribute '%s'"
                                 % (self.__class__.__name__, attr))
        d = self.__dict__
        if attr.startswith('__') and attr.endswith('__'):
            try:
                return d[attr]
            except KeyError:
                _noattrib()
        if attr in d["data"]:
            return d["data"][attr]
        if d["read_only"]:
            _noattrib()

        # the new attrib isn't actually added to this instance until it's set
        # to something. This stops code like "print(instance.notexist)" from
        # adding empty attributes
        attr_ = self._create_child_attribute(attr)
        assert(isinstance(attr_, RecursiveAttribute))
        attr_.__dict__["pending"] = (attr, self)
        return attr_

    def __setattr__(self, attr, value):
        d = self.__dict__
        if d["read_only"]:
            if attr in d["data"]:
                raise AttributeError("'%s' object attribute '%s' is read-only"
                                     % (self.__class__.__name__, attr))
            else:
                raise AttributeError("'%s' object has no attribute '%s'"
                                     % (self.__class__.__name__, attr))
        elif attr.startswith('__') and attr.endswith('__'):
            d[attr] = value
        else:
            d["data"][attr] = value
            self._reparent()

    def __getitem__(self, attr):
        return getattr(self, attr)

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.to_dict())

    def _create_child_attribute(self, attr):
        """Override this method to create new child attributes.

        Returns:
            `RecursiveAttribute` instance.
        """
        return self.__class__()

    def to_dict(self):
        """Get an equivalent dict representation."""
        d = {}
        for k, v in self.__dict__["data"].items():
            if isinstance(v, RecursiveAttribute):
                d[k] = v.to_dict()
            else:
                d[k] = v
        return d

    def copy(self):
        return self.__class__(self.__dict__['data'].copy())

    def update(self, data):
        """Dict-like update operation."""
        if self.__dict__["read_only"]:
            raise AttributeError("read-only, cannot be updated")
        self._update(data)

    def _update(self, data):
        for k, v in data.items():
            if isinstance(v, dict):
                v = RecursiveAttribute(v)
            self.__dict__["data"][k] = v

    def _reparent(self):
        d = self.__dict__
        if "pending" in d:
            attr_, parent = d["pending"]
            parent._reparent()
            parent.__dict__["data"][attr_] = self
            del d["pending"]


class _Scope(RecursiveAttribute):
    def __init__(self, name=None, context=None):
        RecursiveAttribute.__init__(self)
        self.__dict__.update(dict(name=name,
                                  context=context,
                                  locals=None))

    def __enter__(self):
        locals_ = sys._getframe(1).f_locals
        self.__dict__["locals"] = locals_.copy()
        return self

    def __exit__(self, *args):
        # find what's changed
        updates = {}
        d = self.__dict__
        locals_ = sys._getframe(1).f_locals
        self_locals = d["locals"]
        for k, v in locals_.items():
            if not (k.startswith("__") and k.endswith("__")) \
                    and (k not in self_locals or v != self_locals[k]) \
                    and not isinstance(v, _Scope):
                updates[k] = v

        # merge updated local vars with attributes
        self.update(updates)

        # restore upper scope
        locals_.clear()
        locals_.update(self_locals)

        self_context = d["context"]
        if self_context:
            self_context._scope_exit(d["name"])

    def _create_child_attribute(self, attr):
        return RecursiveAttribute()


class ScopeContext(object):
    """A context manager for creating nested dictionaries::

        >>> scope = ScopeContext()
        >>>
        >>> with scope("animal"):
        >>>     count = 2
        >>>     with scope("cat"):
        >>>         friendly = False
        >>>     with scope("dog") as d:
        >>>         friendly = True
        >>>         d.num_legs = 4
        >>>         d.breed.sub_breed = 'yorkshire terrier'
        >>> with scope("animal"):
        >>>     count = 3
        >>>     with scope("cat"):
        >>>         num_legs = 4
        >>>     with scope("ostrich"):
        >>>         friendly = False
        >>>         num_legs = 2

    The dictionaries can then be retrieved::

        >>> print(pprint.pformat(scope.to_dict()))
        {'animal': {'count': 3,
                    'cat': {'friendly': False,
                            'num_legs': 4},
                    'dog': {'breed': {'sub_breed': 'yorkshire terrier'},
                            'friendly': True,
                            'num_legs': 4},
                    'ostrich': {'friendly': False,
                                'num_legs': 2}}}

    Note that scopes and recursive attributes can be referenced multiple times,
    and the assigned properties will be merged. If the same property is set
    multiple times, it will be overwritten.
    """
    def __init__(self):
        self.scopes = {}
        self.scope_stack = [_Scope()]

    def __call__(self, name):
        path = tuple([x.name for x in self.scope_stack[1:]] + [name])
        if path in self.scopes:
            scope = self.scopes[path]
        else:
            scope = _Scope(name, self)
            self.scopes[path] = scope

        self.scope_stack.append(scope)
        return scope

    def _scope_exit(self, name):
        scope = self.scope_stack.pop()
        assert(self.scope_stack)
        assert(name == scope.name)
        data = {scope.name: scope.to_dict()}
        self.scope_stack[-1].update(data)

    def to_dict(self):
        """Get an equivalent dict representation."""
        return self.scope_stack[-1].to_dict()

    def __str__(self):
        names = ('.'.join(y for y in x) for x in self.scopes.keys())
        return "%r" % (tuple(names),)


def scoped_formatter(**objects):
    """Format a string with respect to a set of objects' attributes.

    Use this rather than `scoped_format` when you need to reuse the formatter.
    """
    return RecursiveAttribute(objects, read_only=True)


def scoped_format(txt, **objects):
    """Format a string with respect to a set of objects' attributes.

    Example:

        >>> Class Foo(object):
        >>>     def __init__(self):
        >>>         self.name = "Dave"
        >>> print(scoped_format("hello {foo.name}", foo=Foo()))
        hello Dave

    Args:
        objects (dict): Dict of objects to format with. If a value is a dict,
            its values, and any further neted dicts, will also format with dot
            notation.
        pretty (bool): See `ObjectStringFormatter`.
        expand (bool): See `ObjectStringFormatter`.
    """
    pretty = objects.pop("pretty", RecursiveAttribute.format_pretty)
    expand = objects.pop("expand", RecursiveAttribute.format_expand)
    attr = RecursiveAttribute(objects, read_only=True)
    formatter = scoped_formatter(**objects)
    return formatter.format(txt, pretty=pretty, expand=expand)


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
