#
# Hessian protocol implementation
# This file contains serialization/deserialization code.
#
# Protocol specification can be found here
# http://www.caucho.com/resin-3.0/protocols/hessian-1.0-spec.xtp
#
# Copyright 2005, 2006 Petr Gladkikh (batyi at sourceforge net)
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
from struct import pack, unpack
import UTF8

__revision__ = "$Rev: 9356 $"

import logging
from datetime import datetime
logger = logging.getLogger(__name__)



types = []
CODE_MAP = {}
TYPE_MAP = {}


class HessianError(Exception):
    "This exception indicates a runtime error in 'hessian' module"
    pass


class ValueStreamer:
    "Describes contract for value serializers"

    codes = None # type code list
    ptype = None # Python type of value (or type name string if it is class)

    def read(self, stream):
        "Init value from Stream"
        assert False # abstract

    def write(self, stream, value):
        "Write value from Stream"
        assert False # abstract


def readObject(ctx):
    prefix = ctx.read(1)
    return readObjectByPrefix(ctx, prefix)


def readObjectByPrefix(ctx, prefix):
    codeMapKey = CODE_MAP.get(prefix, None)

    if codeMapKey:
#        if hasattr(codeMapKey, "ptype"):
#            logger.debug ('readObjectByPrefix %s %s' %(prefix, codeMapKey.ptype))
#        else:
#            logger.debug ('readObjectByPrefix %s' %(prefix))
        return ctx.post(CODE_MAP[prefix].read(ctx, prefix))
    else:
        raise 'dont support object type %s deserialisation' %(prefix)


def writeObject(ctx, value, htype):
    "Write value with specified type"
    value = ctx.pre(value)
    if htype is None: # then autodetect type
        if hasattr(value, "__class__"):
            htype = TYPE_MAP[value.__class__]
        else:
            htype = TYPE_MAP[type(value)]
    assert not htype is None
    htype.write(ctx, value)


def readShort(stream):
    return unpack('>H', stream.read(2))[0]


def writeShort(stream, value):
    stream.write(pack(">H", value))


def readVersion(stream):
    (major, minor) = unpack("BB", stream.read(2))
    if  (major, minor) != (1, 0):
        raise HessianError("Unsupported protocol version " + `major` + "." + `minor`)


def writeVersion(stream):
    stream.write("\x01\x00")


class SimpleValue:
    "Single valued types (e.g. None)"
    def read(self, ctx, prefix):
        assert prefix in self.codes
        return self.value

    def write(self, ctx, value):
        assert value == self.value
        ctx.write(self.codes[0])


class Null(SimpleValue):
    codes = ["N"]
    ptype = type(None)
    value = None
types.append(Null)





class Bool:
    codes = ["F", "T"]
    ptype = bool

    def read(self, ctx, prefix):
        assert prefix in self.codes
        return prefix == self.codes[1]

    def write(self, ctx, value):
        assert type(value) == bool
        k = 0
        if value: k = 1
        ctx.write(self.codes[k])
types.append(Bool)


class BasicInt:
    codes = []

    def read(self, ctx, prefix):
        assert prefix in self.codes
        dat = ctx.read(4)
        assert len(dat) == 4
        return unpack(">l", dat)[0]

    def write(self, ctx, value):
        ctx.write(self.codes[0])
        ctx.write(pack(">l", value))


class Int(BasicInt):
    codes = ["I"]
    ptype = int
types.append(Int)


class Long:
    codes = ["L"]
    ptype = long

    def read(self, ctx, prefix):
        assert prefix in self.codes
        return unpack('>q', ctx.read(8))[0]

    def write(self, ctx, value):
        ctx.write(self.codes[0])
        ctx.write(pack(">q", value))
types.append(Long)


class Double:
    codes = ["D"]
    ptype = float

    def read(self, ctx, prefix):
        assert prefix in self.codes
        return unpack('>d', ctx.read(8))[0]

    def write(self, ctx, value):
        ctx.write(self.codes[0])
        ctx.write(pack(">d", value))
types.append(Double)


class DateTime(object):
    codes = ["d"]
    ptype = datetime

    def read(self, ctx, prefix):
        assert prefix in self.codes
        chunk =  unpack('>q', ctx.read(8))[0]
        return int(chunk)

    def write(self, ctx, value):
        import time
        ctx.write(self.codes[0])
        ctx.write(pack(">q", int(time.mktime(value.timetuple())) * 1000))
types.append(DateTime)


class ShortSequence:
    codes = []

    def read(self, ctx, prefix):
        count = readShort(ctx)
        return ctx.read(count)

    def write(self, ctx, value):
        ctx.write(self.codes[0])
        writeShort(ctx, len(value))
        ctx.write(value)


class Chunked(ShortSequence):
    """'codes' mean following: codes[1] starts all chunks but last;
    codes[0] starts last chunk."""

    readChunk = ShortSequence.read # shortcut

    chunk_size = 2**12 # 4KiB

    def read(self, ctx, prefix):
        result = "";
        while (prefix == self.codes[1]):
            result += self.readChunk(ctx, self.codes[1])
            prefix = ctx.read(1)
        assert prefix == self.codes[0]
        result += self.readChunk(ctx, prefix)
        return result

    def write(self, ctx, value):
        length = len(value)
        pos = 0
        while pos < length - Chunked.chunk_size:
            ctx.write(self.codes[1])
            writeShort(ctx, self.chunk_size)
            ctx.write(value[pos : pos + Chunked.chunk_size])
            pos += Chunked.chunk_size
        # write last chunk
        ctx.write(self.codes[0])
        writeShort(ctx, length - pos)
        ctx.write(value[pos : ])


class UTF8Sequence(Chunked):
    """We can not use Chunked as base as Chunked counts octets in stream while
    UTF8 based sequences count lengths in symbols.
    """

    def readChunk(self, ctx, prefix):
        result = u""
        count = readShort(ctx)
        for ci in range(count):
            result += unichr(UTF8.readSymbol(ctx.read))
        return result

    def read(self, ctx, prefix):
        result = "";
        while (prefix == self.codes[1]):
            result += self.readChunk(ctx, prefix)
            prefix = ctx.read(1)
        assert prefix == self.codes[0]
        result += self.readChunk(ctx, prefix)
        return result

    def writeChunk(self, ctx, val):
        length = len(val)
        writeShort(ctx, length)
        for k in range(length):
            for byte in UTF8.symbolToUTF8(ord(val[k])):
                ctx.write(byte)

    def write(self, ctx, value):
        length = len(value)
        pos = 0
        # TODO write symbol-by symbol here
        # How do we calculate chunk sizes here
        while pos < length - Chunked.chunk_size:
            ctx.write(self.codes[1])
            self.writeChunk(ctx, value[pos : pos + Chunked.chunk_size])
            pos += Chunked.chunk_size
        # write last chunk
        ctx.write(self.codes[0])
        self.writeChunk(ctx, value[pos : ])


class String(UTF8Sequence):
    codes = ["S", "s"]
    ptype = str
types.append(String)


class UnicodeString(String):
    ptype = unicode
types.append(UnicodeString)


class Xml(UTF8Sequence):
    codes = ["X", "x"]
types.append(Xml)


class Binary(Chunked):
    codes = ["B", "b"]
types.append(Binary)


class TypeName(ShortSequence):
    codes = ["t"]
types.append(TypeName)


class Length(BasicInt):
    codes = ["l"]
types.append(Length)


def writeReferenced(stream, writeMethod, obj):
    """Write reference if object has been met before.
    Else write object itself."""

    objId = stream.getRefId(obj)
    if objId != -1:
        Ref().write(stream, objId)
    else:
        writeMethod(stream, obj)


class Array:
    codes = ["V"]
    ptype = list

    type_streamer = TypeName()
    length_streamer = Length()

    def read(self, ctx, prefix):
        assert prefix == "V"
        prefix = ctx.read(1)
        if prefix in self.type_streamer.codes:
            self.type_streamer.read(ctx, prefix)
            prefix = ctx.read(1)
        count = self.length_streamer.read(ctx, prefix)
        prefix = ctx.read(1)
        result = []
        ctx.referencedObjects.append(result)
        while prefix != "z":
            result.append(readObjectByPrefix(ctx, prefix))
            prefix = ctx.read(1)
        assert count == len(result)
        assert prefix == "z"
        return result

    def _write(self, ctx, value):
        ctx.write(self.codes[0])

        # we'll not write type marker because we may only guess it
        # self.type_streamer.write(stream, "something")

        self.length_streamer.write(ctx, len(value))
        for o in value:
            writeObject(ctx, o, None)
        ctx.write("z")

    def write(self, ctx, value):
        writeReferenced(ctx, self._write, value)
types.append(Array)


class Tuple(Array):
    "This class serialises tuples. They are always read as arrays"
    codes = ["V"]
    ptype = tuple
types.append(Tuple)


class Map:
    codes = ["M"]
    ptype = dict

    type_streamer = TypeName()

    def read(self, ctx, prefix):

#        logger.debug('read %s'%(self.__class__.__name__))
        assert prefix in self.codes
        prefix = ctx.read(1)
        if prefix in TypeName.codes:
            self.type_streamer.read(ctx, prefix)
            prefix = ctx.read(1)
        result = {}
        ctx.referencedObjects.append(result)
        while prefix != "z":
            key = readObjectByPrefix(ctx, prefix)
            value = readObject(ctx)
            result[key] = value
            prefix = ctx.read(1)
        return result

    def _write(self, ctx, mapping):
        ctx.write(self.codes[0])
        for k, v in mapping.items():
            writeObject(ctx, k, None)
            writeObject(ctx, v, None)
        ctx.write("z")

    def write(self, ctx, value):
        writeReferenced(ctx, self._write, value)
types.append(Map)


class Ref(BasicInt):
    """ Reference to a previously occured object
    (allows sharing objects in a map or a list) """
    codes = ["R"]

    def read(self, ctx, prefix):
        refId = BasicInt.read(self, ctx, prefix)
        return ctx.referencedObjects[refId]

    def write(self, ctx, objId):
        BasicInt.write(self, ctx, objId)
types.append(Ref)


class Header:
    "A (name, value) pair"
    codes = ["H"]

    title_streamer = ShortSequence()
    title_streamer.codes = codes

    def read(self, ctx, prefix):
        assert prefix in self.codes
        # read header title
        title = self.title_streamer.read(ctx, prefix)
        assert len(title) > 0
        # read header value
        value = readObject(ctx)
        return (title, value)

    def write(self, ctx, header):
        title, value = header
        # write title
        self.title_streamer.write(ctx, title)
        # write value
        writeObject(ctx, value, None)
types.append(Header)


class Method(ShortSequence):
    codes = ["m"]
types.append(Method)


class Call:
    "Represents request to a remote interface."
    codes = ["c"]

    method_streamer = Method()
    header_streamer = Header()

    def read(self, ctx, prefix):
        assert prefix == self.codes[0]
        readVersion(ctx)
        prefix = ctx.read(1)

        # read headers
        headers = []
        while prefix == self.header_streamer.codes[0]:
            headers.append(self.header_streamer.read(ctx, prefix))
            prefix = ctx.read(1)

        # read method
        method = self.method_streamer.read(ctx, prefix)
        prefix = ctx.read(1)

        # read params
        params = []
        while prefix != "z":
            params.append(readObjectByPrefix(ctx, prefix))
            prefix = ctx.read(1)

        return (method, headers, params)

    def write(self, ctx, value):
        # headers can be None or map of headers (header title->value)
        method, headers, params = value
        ctx.write(self.codes[0])
        writeVersion(ctx)

        # write headers
        if headers != None:
            for h in headers:
                self.header_streamer.write(ctx, h)

        # write method
        self.method_streamer.write(ctx, method)

        # write params
        if params != None:
            for v in params:
                writeObject(ctx, v, None)

        ctx.write("z");
types.append(Call)


class Fault:
    "Remote_call error_description."
    codes = ["f"]

    def read(self, ctx, prefix):
        assert prefix in self.codes
        result = {}
        prefix = ctx.read(1)
        while prefix != "z":
            k = readObjectByPrefix(ctx, prefix)
            prefix = ctx.read(1)
            v = readObjectByPrefix(ctx, prefix)
            prefix = ctx.read(1)
            result[k] = v
        return result

    def write(self, ctx, fault):
        ctx.write(self.codes[0])
        for k, v in fault.items():
            writeObject(ctx, k, None)
            writeObject(ctx, v, None)
types.append(Fault)


class Reply:
    "Result of remote call."

    """Note "Remote" code clashes with "Reply" code
    and Reply is always read explicitly.
    Thus do not register it in global type map. """
    autoRegister = False

    codes = ["r"]

    header_streamer = Header()
    fault_streamer = Fault()

    def read(self, ctx, prefix):
        assert prefix in self.codes[0]
        # parse header 'r' x01 x00 ... 'z'
        readVersion(ctx)
        prefix = ctx.read(1)
        # parse headers
        headers = []
        while prefix in self.header_streamer.codes:
            headers.append(self.header_streamer.read())
            prefix = ctx.read(1)

        succseeded = not prefix in self.fault_streamer.codes

        if succseeded:
            result = readObjectByPrefix(ctx, prefix)
            prefix = ctx.read(1)
            if prefix != 'z':
                raise "No closing marker in reply"
        else:
            result = self.fault_streamer.read(ctx, prefix)
            # closing "z" is already read by Fault.read

        return (headers, succseeded, result)

    def write(self, ctx, reply):
        (headers, succeeded, result) = reply
        ctx.write(self.codes[0])
        writeVersion(ctx)
        for h in headers:
            self.header_streamer.write(ctx, h)
        if succeeded:
            writeObject(ctx, result, None)
        else:
            self.fault_streamer.write(ctx, result)
        ctx.write("z")
types.append(Reply)


class RemoteReference:

    def __init__(self, url):
        self.url = url

    def __eq__(self, other):
        return self.url == other.url


class Remote:
    """Reference to a remote interface.
    TODO: We could read and write interface types if necessary
    (add interface type name string to RemoteInterface).
    This feaure is ignored for now."""

    codes = ["r"]
    ptype = RemoteReference

    typename_streamer = TypeName()
    url_streamer = String()

    def read(self, ctx, prefix):
        assert prefix in self.codes
        # just skip typeName of remote interface (see comments for the class)
        typeName = self.typename_streamer.read(ctx, ctx.read(1))
        # read url
        url = self.url_streamer.read(ctx, ctx.read(1))
        return RemoteReference(url)

    def write(self, ctx, remote):
        "remote - RemoteReference-like object"
        ctx.write(self.codes[0])
        typeName = "Python" # see comments for the class
        self.typename_streamer.write(ctx, typeName)
        self.url_streamer.write(ctx, remote.url)
types.append(Remote)


def makeTypeMaps(types):
    """ Build maps that allow to find apropriate
    serializer (by object type) or deserializer (by prefix symbol).

    If serialized type does not match serializer class (true for
    embedded types) then Class.ptype is used. If a type does not have
    direct analog in Python (is Hessian - specific) then its serializer
    is used as type.
    """
    codeMap = {} # type code to streamer map
    typeMap = {} # python type to streamer map
    for c in types:
        streamer = c()

        if hasattr(streamer, "autoRegister") and not streamer.autoRegister:
            continue

        for ch in streamer.codes:
            # assert not ch in codeMap
            codeMap[ch] = streamer
        if hasattr(streamer, "ptype"):
            assert not streamer.ptype in typeMap
            typeMap[streamer.ptype] = streamer
        else:
            typeMap[streamer.__class__] = streamer
    return codeMap, typeMap


CODE_MAP, TYPE_MAP = makeTypeMaps(types)


class ParseContext:
    def __init__(self, stream, post = lambda x: x):
        """post - postprocessing function for deserialized object.
        Note: not all streamers use self.post
        """
        self.referencedObjects = [] # objects that may be referenced by Ref
        self.objectIds = {}
        self.stream = stream
        self.read = stream.read
        self.post = post


class WriteContext:
    def __init__(self, stream, pre = lambda x: x):
        """pre - preprocessing function for object being written.
        Note: not all streamers use self.pre
        """
        self.objectIds = {} # is used for back references
        self.count = 0
        self.stream = stream
        self.write = stream.write
        self.pre = pre

    def getRefId(self, obj):
        "Return numeric ref id if object has been already met"
        try:
            return self.objectIds[id(obj)]
        except KeyError, e:
            self.objectIds[id(obj)] = self.count
            self.count += 1
            return -1


if __name__ == "__main__":
    print "Registered types:"
    for t in types:
        print t
        for c in t.codes: print c
        print
