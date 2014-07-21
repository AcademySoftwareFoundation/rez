# -*- coding: UTF-8 -*-
#
# This file contains UTF8 manipulation code.
# (It would be nice to use standard encoders, but they do not 
# allow to read symbol by symbol.)
#
# Unicode UTF-8
#  0x00000000 — 0x0000007F: 0xxxxxxx
#  0x00000080 — 0x000007FF: 110xxxxx 10xxxxxx
#  0x00000800 — 0x0000FFFF: 1110xxxx 10xxxxxx 10xxxxxx
#  0x00010000 — 0x001FFFFF: 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
#
# Copyright 2006 Petr Gladkikh (batyi at sourceforge net)
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
__revision__ = "$Rev: 3343 $"

# Masks that select code point bits in 1-st byte of UTF8 code point sequence
BYTE_MASKS = [0x7f, 0x1f, 0x0f, 0x07]

# Bounds of code point ranges that need different number of bytes in UTF8 sequence
BYTE_RANGES = [0x0000007F, 0x000007FF, 0x0000FFFF, 0x001FFFFF]

# bit-marks for first byte in UTF8 code point sequence that declare length of sequence
FIRST_MARKS = [0, 0xc0, 0xe0, 0xf0]

# setup module:
def readSymbolPy(sourceFun):
    first = sourceFun(1)
    if len(first) == 0:
        return None
    b = ord(first)
    # count number of 1's: 0, 2, 3, 4
    byteLen = 1
    while b & 0x80:
        byteLen += 1        
        b <<= 1
    if byteLen > 4:
            raise Exception("UTF-8 Error: Incorrect UTF-8 encoding"
                            +" (first octet of symbol = 0x%x)" % ord(first))        
    elif byteLen > 1:
            byteLen -= 1    
    mask = BYTE_MASKS[byteLen - 1]
    codePoint = ord(first) & mask
    for k in xrange(1, byteLen):
        ch = sourceFun(1)
        if len(ch) == 0:
            raise Exception("UTF-8 Error: Incorrect UTF-8 encoding"
                            +" (premature stream end)")
        codePoint <<= 6        
        codePoint |= ord(ch) & 0x3f
        
    return codePoint


def symbolToUTF8Py(codePoint):    
    byteLen = 1
    for k in BYTE_RANGES:
        if codePoint <= k:
            break
        byteLen += 1
    else:
        raise Exception("UTF-8 Error: Can not encode codePoint ["
                        + codePoint + "] in UTF-8. It is bigger than 0x001FFFFF")
                
    result = [0] * byteLen  
    
    c = codePoint    
    k = byteLen - 1
    if byteLen > 3:
        result[k] = chr(c & 0x3f | 0x80)
        c >>= 6
        k -= 1
    if byteLen > 2:
        result[k] = chr(c & 0x3f | 0x80)
        c >>= 6
        k -= 1
    if byteLen > 1:
        result[k] = chr(c & 0x3f | 0x80)
        c >>= 6
        k -= 1
        
    result[0] = chr(FIRST_MARKS[byteLen - 1] | c)
    
    # print "thisByte = %x; mark = %x; firstMark = %x" % ((mark | codePoint & 0x7f), mark, firstMark)
    # print "firstMark = %x" % firstMark
    # print result
    
    return result

import sys

if sys.version_info[0:2] >= (2, 5):
    import codecs
    
    utf8Codec = codecs.lookup("UTF-8")    
    encoder = utf8Codec.incrementalencoder()
    
    readSymbol = readSymbolPy
    symbolToUTF8 = lambda codePoint : encoder.encode(unichr(codePoint))
else:
    readSymbol = readSymbolPy
    symbolToUTF8 = symbolToUTF8Py

 
def test():
    # TODO Test exceptions    
    from StringIO import StringIO
    src = u"""
    В этом нет ничего нового,
    Ибо вообще ничего нового нет.
        Николай Рерих        
    ÀùúûüýþÿĀāĂăĄąĆćĈĉ
    $¢£¤¥₣₤₧₪₫€
    """    
    u0 = src.encode("UTF-8")
    u1 = ""
    for c in src:
        u1 += "".join(symbolToUTF8(ord(c)))
    assert u1.decode("UTF-8") == src
    s = []
    k = 0
    s_read = StringIO(u1)
    while True:
        repr = readSymbol(s_read.read)
        if repr == None:
            break
        s.append(unichr(repr))
        
    s = u"".join(s)
    assert s == src


def testPerformance():
    from StringIO import StringIO
    from time import time as now
    src = u"(Цой|punk|Ленин)Жив!" * 20000
    u0 = src.encode("UTF-8")
    
    tStart = now()
    for c in src:
        symbolToUTF8(ord(c))
    tEncode = now() - tStart
    print "Encoding",  (len(src) / tEncode), "symbols/sec"
    
    tStart = now()
    s_read = StringIO(u0)    
    while True:
        repr = readSymbol(s_read.read)
        if repr == None:
            break 
    tDecode = now() - tStart       
    print "Decoding",  (len(src) / tDecode), "symbols/sec"


if __name__ == "__main__":
        test()
        testPerformance()
        print "Tests passed."
