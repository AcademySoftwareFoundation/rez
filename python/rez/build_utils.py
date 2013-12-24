"""
Utility functions for performing build-related operations, such as downloading
and patching source code.
"""
import re
import subprocess



def encode_filesystem_name(input_str):
    '''Encodes an arbitrary unicode string to a generic
    filesystem-compatible filename

    The result after encoding will only contain the standard ascii lowercase
    letters (a-z), the digits (0-9), or periods, underscores, or dashes
    (".", "_", or "-").  No uppercase letters will be used, for
    comaptibility with case-insensitive filesystems.

    The rules for the encoding are:

    1) Any lowercase letter, digit, period, or dash (a-z, 0-9, ., or -) is
    encoded as-is.

    2) Any underscore is encoded as a double-underscore ("__")

    3) Any uppercase ascii letter (A-Z) is encoded as an underscore followed
    by the corresponding lowercase letter (ie, "A" => "_a")

    4) All other characters are encoded using their UTF-8 encoded unicode
    representation, in the following format: "_NHH..., where:
        a) N represents the number of bytes needed for the UTF-8 encoding,
        except with N=0 for one-byte representation (the exception for N=1
        is made both because it means that for "standard" ascii characters
        in the range 0-127, their encoding will be _0xx, where xx is their
        ascii hex code; and because it mirrors the ways UTF-8 encoding
        itself works, where the number of bytes needed for the character can
        be determined by counting the number of leading "1"s in the binary
        representation of the character, except that if it is a 1-byte
        sequence, there are 0 leading 1's).
        b) HH represents the bytes of the corresponding UTF-8 encoding, in
        hexadecimal (using lower-case letters)

        As an example, the character "*", whose (hex) UTF-8 representation
        of 2A, would be encoded as "_02a", while the "euro" symbol, which
        has a UTF-8 representation of E2 82 AC, would be encoded as
        "_3e282ac".  (Note that, strictly speaking, the "N" part of the
        encoding is redundant information, since it is essentially encoded
        in the UTF-8 representation itself, but it makes the resulting
        string more human-readable, and easier to decode).

    As an example, the string "Foo_Bar (fun).txt" would get encoded as:
        _foo___bar_020_028fun_029.txt
    '''
    if isinstance(input_str, str):
        input_str = unicode(input_str)
    elif not isinstance(input_str, unicode):
        raise TypeError("input_str must be a basestring")

    as_is = u'abcdefghijklmnopqrstuvwxyz0123456789.-'
    uppercase = u'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    result = []
    for char in input_str:
        if char in as_is:
            result.append(char)
        elif char == u'_':
            result.append('__')
        elif char in uppercase:
            result.append('_%s' % char.lower())
        else:
            utf8 = char.encode('utf8')
            N = len(utf8)
            if N == 1:
                N = 0
            HH = ''.join('%x' % ord(c) for c in utf8)
            result.append('_%d%s' % (N, HH))
    return ''.join(result)


_FILESYSTEM_TOKEN_RE = re.compile(r'(?P<as_is>[a-z0-9.-])|(?P<underscore>__)|_(?P<uppercase>[a-z])|_(?P<N>[0-9])')
_HEX_RE = re.compile('[0-9a-f]+$')

def decode_filesystem_name(filename):
    """Decodes a filename encoded using the rules given in
    encode_filesystem_name to a unicode string
    """
    result = []
    remain = filename
    i = 0
    while remain:
        # use match, to ensure it matches from the start of the string...
        match = _FILESYSTEM_TOKEN_RE.match(remain)
        if not match:
            raise ValueError("incorrectly encoded filesystem name %r"
                             " (bad index: %d - %r)" % (filename, i,
                                                        remain[:2]))
        match_str = match.group(0)
        match_len = len(match_str)
        i += match_len
        remain = remain[match_len:]
        match_dict = match.groupdict()
        if match_dict['as_is']:
            result.append(unicode(match_str))
            # print "got as_is - %r" % result[-1]
        elif match_dict['underscore']:
            result.append(u'_')
            # print "got underscore - %r" % result[-1]
        elif match_dict['uppercase']:
            result.append(unicode(match_dict['uppercase'].upper()))
            # print "got uppercase - %r" % result[-1]
        elif match_dict['N']:
            N = int(match_dict['N'])
            if N == 0:
                N = 1
            # hex-encoded, so need to grab 2*N chars
            bytes_len = 2 * N
            i += bytes_len
            bytes = remain[:bytes_len]
            remain = remain[bytes_len:]

            # need this check to ensure that we don't end up eval'ing
            # something nasty...
            if not _HEX_RE.match(bytes):
                raise ValueError("Bad utf8 encoding in name %r"
                                 " (bad index: %d - %r)" % (filename, i, bytes))

            bytes_repr = ''.join('\\x%s' % bytes[i:i + 2]
                                 for i in xrange(0, bytes_len, 2))
            bytes_repr = "'%s'" % bytes_repr
            result.append(eval(bytes_repr).decode('utf8'))
            # print "got utf8 - %r" % result[-1]
        else:
            raise ValueError("Unrecognized match type in filesystem name %r"
                             " (bad index: %d - %r)" % (filename, i, remain[:2]))
        # print result
    return u''.join(result)


def test_encode_decode():
    def do_test(orig, expected_encoded):
        print '=' * 80
        print orig
        encoded = encode_filesystem_name(orig)
        print encoded
        assert encoded == expected_encoded
        decoded = decode_filesystem_name(encoded)
        print decoded
        assert decoded == orig

    do_test("Foo_Bar (fun).txt", '_foo___bar_020_028fun_029.txt')

    # u'\u20ac' == Euro symbol
    do_test(u"\u20ac3 ~= $4.06", '_3e282ac3_020_07e_03d_020_0244.06')
