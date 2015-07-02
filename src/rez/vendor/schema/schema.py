# REZ: added a .rez to version
__version__ = '0.3.0.rez'


class SchemaError(Exception):

    """Error during Schema validation."""

    def __init__(self, autos, errors):
        self.autos = autos if type(autos) is list else [autos]
        self.errors = errors if type(errors) is list else [errors]
        Exception.__init__(self, self.code)

    @property
    def code(self):
        def uniq(seq):
            seen = set()
            seen_add = seen.add
            return [x for x in seq if x not in seen and not seen_add(x)]
        a = uniq(i for i in self.autos if i is not None)
        e = uniq(i for i in self.errors if i is not None)
        if e:
            return '\n'.join(e)
        return '\n'.join(a)


class And(object):

    def __init__(self, *args, **kw):
        self._args = args
        assert list(kw) in (['error'], [])
        self._error = kw.get('error')

    def __repr__(self):
        # REZ: Switched to use a map operation instead of list comprehension.
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(map(repr, self._args)))

    def validate(self, data):
        for s in [Schema(s, error=self._error) for s in self._args]:
            data = s.validate(data)
        return data


class Or(And):

    def validate(self, data):
        x = SchemaError([], [])
        for s in [Schema(s, error=self._error) for s in self._args]:
            try:
                return s.validate(data)
            except SchemaError as _x:
                x = _x
        raise SchemaError(['%r did not validate %r' % (self, data)] + x.autos,
                          [self._error] + x.errors)


class Use(object):

    def __init__(self, callable_, error=None):
        assert callable(callable_)
        self._callable = callable_
        self._error = error

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._callable)

    def validate(self, data):
        try:
            return self._callable(data)
        except SchemaError as x:
            raise SchemaError([None] + x.autos, [self._error] + x.errors)
        except BaseException as x:
            f = self._callable.__name__
            raise SchemaError('%s(%r) raised %r' % (f, data, x), self._error)


def priority(s):
    """Return priority for a give object."""
    # REZ: Previously this value was calculated in place many times which is
    #      expensive.  Do it once early.
    # REZ: Changed this to output a list, so that can nicely sort "validate"
    #      items by the sub-priority of their schema
    type_of_s = type(s)
    if type_of_s in (list, tuple, set, frozenset):
        return [6]
    if type_of_s is dict:
        return [5]
    if hasattr(s, 'validate'):
        p = [4]
        if hasattr(s, "_schema"):
            p.extend(priority(s._schema))
        return p
    if type_of_s is type:
        return [3]
    if callable(s):
        return [2]
    else:
        return [1]


class Schema(object):

    def __init__(self, schema, error=None):
        self._schema = schema
        self._error = error

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._schema)

    def validate(self, data):
        s = self._schema
        # REZ: Previously this value was calculated in place many times which is
        #      expensive.  Do it once early.
        type_of_s = type(s)
        e = self._error
        if type_of_s in (list, tuple, set, frozenset):
            data = Schema(type_of_s, error=e).validate(data)
            return type_of_s(Or(*s, error=e).validate(d) for d in data)
        if type_of_s is dict:
            # REZ: Here we are validating that the data is an instance of the
            #      same type as the schema (a dict).  However creating a whole
            #      new instance of ourselves is wasteful.  Instead we inline
            #      the check that would have be undertaken.  The previous
            #      approach remains commented below.
#            data = Schema(dict, error=e).validate(data)
            if not isinstance(data, dict):
                raise SchemaError('%r should be instance of %r' % (data, s), e)
            new = type(data)()  # new - is a dict of the validated values
            x = None
            coverage = set()  # non-optional schema keys that were matched
            # REZ: For each key and value find a schema entry matching them,
            #      if any. As there is not a one-to-one mapping between keys
            #      in the dictionary being validated and the schema this
            #      section would attempt to find the correct section of the
            #      schema to use by calling itself. For example, to validate
            #      the following:
            #
            #      schema = Schema({
            #          Optional('foo'):int
            #          Optional(basestring):int
            #      })
            #
            #      data = {
            #          'foo':1,
            #          'bar':1,
            #      }
            #
            #      a prioritised list of keys from the schema are validated
            #      against the current key being validated from the data. If
            #      that validation passes then the value from the schema is
            #      used to validate the value of the current key. This is
            #      very inefficient as every key in data is (potentially)
            #      being compared against every key in schema. This is
            #      expensive. Now, we use the same approach as
            #      rez.util._LazyAttributeValidator and try and build a
            #      mapping between schema keys and data keys, resorting to
            #      the original approach only in the (very) few cases where
            #      this map is insufficient.
            sorted_skeys = None
            schema_key_map = {}
            for key in s:
                key_name = key
                while isinstance(key_name, Schema):
                    key_name = key_name._schema
                if isinstance(key_name, basestring):
                    schema_key_map[key_name] = key
            for key, value in data.items():
                nkey = None
                if key in schema_key_map:
                    nkey = key
                    svalue = s[schema_key_map[key]]
                    skey = schema_key_map[key]
                else:
                    if not sorted_skeys:
                        sorted_skeys = list(sorted(s, key=priority))
                    for skey in sorted_skeys:
                        svalue = s[skey]
                        try:
                            nkey = Schema(skey, error=e).validate(key)
                        except SchemaError:
                            pass
                if not nkey:
                    continue
                try:
                    nvalue = Schema(svalue, error=e).validate(value)
                except SchemaError as _x:
                    x = _x
                    raise
                else:
                    # Only add to the set if the type of skey is not
                    # Optional.  Previously this was done as a secondary
                    # step (which remains commented out below).
                    if type(skey) is not Optional:
                        coverage.add(skey)
                    valid = True
                    #break
                if valid:
                    new[nkey] = nvalue
                elif skey is not None:
                    if x is not None:
                        raise SchemaError(['invalid value for key %r' % key] +
                                          x.autos, [e] + x.errors)
            # REZ: we now check for Optional as we add to coverage
#            coverage = set(k for k in coverage if type(k) is not Optional)
            required = set(k for k in s if type(k) is not Optional)
            if coverage != required:
                raise SchemaError('missed keys %r' % (required - coverage), e)
            if len(new) != len(data):
                wrong_keys = set(data.keys()) - set(new.keys())
                s_wrong_keys = ', '.join('%r' % k for k in sorted(wrong_keys))
                raise SchemaError('wrong keys %s in %r' % (s_wrong_keys, data),
                                  e)
            return new
        if hasattr(s, 'validate'):
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%r.validate(%r) raised %r' % (s, data, x),
                                  self._error)
        if type_of_s is type:
            if isinstance(data, s):
                return data
            else:
                raise SchemaError('%r should be instance of %r' % (data, s), e)
        if callable(s):
            f = s.__name__
            try:
                if s(data):
                    return data
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%s(%r) raised %r' % (f, data, x),
                                  self._error)
            raise SchemaError('%s(%r) should evaluate to True' % (f, data), e)
        if s == data:
            return data
        else:
            raise SchemaError('%r does not match %r' % (s, data), e)


class Optional(Schema):

    """Marker for an optional part of Schema."""
