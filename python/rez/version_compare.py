#! /usr/bin/env python

import re
import itertools

def version_compare(first, second):
    '''
    Returns -1 if the first version is lower than the second,
    0 if they are equal,
    and 1 if the second is lower.

    '''
    tmp = _normalize_and_tokenize(first)
    first = _flatten(tmp)
    
    tmp = _normalize_and_tokenize(second)
    second = _flatten(tmp)

    i = 0
    while 1:
        if i > len(first) - 1 and i > len(second) - 1: # out of tokens
            return 0

        if i > len(first) - 1 :
            f = '0'
        else:
            f = first[i]
        if i > len(second) - 1:
            s = '0'
        else:
            s = second[i]

        f = _get_value(f)
        s = _get_value(s)

        if f < s:
            return -1
        elif s < f:
            return 1
        else:
            i += 1

def rezTokenize(rawVersion):
    trueTokens = _normalize_and_tokenize(rawVersion)
    rezTokens = []
    for each in trueTokens:
        if isinstance(each, str):
            rezTokens.append(each)
        elif isinstance(each, list): # these should only ever go 1 level deep
            rezTokens.append(''.join(each))
        else:
            raise RuntimeError, "Encountered a token which is not a string and is not a list: '%s'" % (each,)
    return rezTokens

def _normalize_and_tokenize(rawVersion):
    val = re.sub(r'[_,.:]+', '.', str(rawVersion))
    rawList = val.split('.')
    ret = []
    for each in rawList:
        subVal = _split_out_non_numbers(each)
        if len(subVal) == 1:
            ret.append(subVal[0])
        else:
            ret.append(subVal)
    return ret

def _flatten(multidimInput):
    '''
    flatten only lists, not splitting strings
    '''
    l2 = [([x] if isinstance(x, str) else x) for x in multidimInput]
    return list(itertools.chain(*l2))

def _split_out_non_numbers(val):
    if re.search(r'^\d+$', val) is not None:
        return [val]
    ret = []
    while 1:
        # leading numbers:
        m = re.search(r'^(\d+)(.*|)$', val)
        if m is not None:
            ret.append(m.group(1))
            val = m.group(2)
            continue

        # leading other:
        m = re.search(r'^(\D+)(.*|)$', val)
        if m is not None:
            ret.append(m.group(1))
            val = m.group(2)
            continue

        break
    return ret

def _get_value(val):
    if re.search(r'^\d+$', val) is not None:
        return int(val)
    elif re.search(re.compile(r'dev|devel|test', re.IGNORECASE), val) is not None:
            return -10
    elif re.search(re.compile(r'alpha', re.IGNORECASE), val) is not None:
            return -9
    elif re.search(re.compile(r'beta', re.IGNORECASE), val) is not None:
            return -8
    elif re.search(re.compile(r'rc', re.IGNORECASE), val) is not None:
            return -7
    elif re.search(re.compile(r'(final|prod)', re.IGNORECASE), val) is not None:
            return -6
    elif re.search(re.compile(r'(int|integration|latest)', re.IGNORECASE), val) is not None:
            return 1
    else: # default, unrecognized - asciibetical
        return val

def _build_ascii_score(val):
    ret = 0
    

########

import unittest

class Test(unittest.TestCase):

    def test_1vs2(self):
        self.assertEqual(version_compare('1', '2'), -1)
    def test_2vs1(self):
        self.assertEqual(version_compare('2', '1'), 1)
    def test_1vs1(self):
        self.assertEqual(version_compare('1', '1'), 0)
    def test_1pt0vs1pt1(self):
        self.assertEqual(version_compare('1.0', '1.1'), -1)
    def test_1pt1vs1pt0(self):
        self.assertEqual(version_compare('1.1', '1.0'), 1)
    def test_1pt0vs1pt0(self):
        self.assertEqual(version_compare('1.0', '1.0'), 0)
    def test_1pt0pt0vs1pt0pt1(self):
        self.assertEqual(version_compare('1.0.0', '1.0.1'), -1)
    def test_1pt0pt1vs1pt0pt0(self):
        self.assertEqual(version_compare('1.0.1', '1.0.0'), 1)
    def test_1pt0pt0vs1pt0pt0(self):
        self.assertEqual(version_compare('1.0.0', '1.0.0'), 0)
    def test_1pt9vs1pt10(self):
        self.assertEqual(version_compare('1.9', '1.10'), -1)
    def test_1pt9vs2pt0(self):
        self.assertEqual(version_compare('1.9', '2.0'), -1)
    def test_1pt9vs2(self):
        self.assertEqual(version_compare('1.9', '2'), -1)
    def test_1pt9vs2pt0pt0(self):
        self.assertEqual(version_compare('1.9', '2.0.0'), -1)
    def test_alphavsbeta(self):
        self.assertEqual(version_compare('alpha', 'beta'), -1)
    def test_betavsint(self):
        self.assertEqual(version_compare('beta', 'int'), -1)
    def test_devvsprod(self):
        self.assertEqual(version_compare('dev', 'prod'), -1)
    def test_1pt2dashfinalvs1pt2pt1(self):
        self.assertEqual(version_compare('1.2-final', '1.2.1'), -1)
    def test_1pt2dashbetavs1pt2(self):
        self.assertEqual(version_compare('1.2-beta', '1.2'), -1)
    def test_1pt1ptrcvs1pt2(self):
        self.assertEqual(version_compare('1.1.rc', '1.2'), -1)
    def test_2011vs2012(self):
        self.assertEqual(version_compare('2011', '2012'), -1)
    def test_2011vs2011AdvPack(self):
        self.assertEqual(version_compare('2011', '2011AdvPack'), -1)
    def test_1pt1rc1vs1pt1rc2(self):
        self.assertEqual(version_compare('1.1rc1', '1.1rc2'), -1)
    def test_1pt1rcdash1vs1pt1rcdash2(self):
        self.assertEqual(version_compare('1.1rc-1', '1.1rc-2'), -1)
    def test_1ptrcdash1vs1ptrcdash2(self):
        self.assertEqual(version_compare('1.rc-1', '1.rc-2'), -1)
    def test_1ptrc1vs1ptrc2(self):
        self.assertEqual(version_compare('1.rc1', '1.rc2'), -1)
    def test_1pt1rcdash2vs1pt1(self):
        self.assertEqual(version_compare('1.1rc-2', '1.1'), -1)  ## Is this what would be wanted?
    def test_1pt1rcdash2vs1pt2(self):
        self.assertEqual(version_compare('1.1rc-2', '1.2'), -1)
    def test_6pt3v1vs6pt3v2(self):
        self.assertEqual(version_compare('6.3v1', '6.3v2'), -1)
    def test_6pt3v1vs7pt0v1(self):
        self.assertEqual(version_compare('6.3v1', '7.0v1'), -1)
    def test_2011AdvPackvs2012(self):
        self.assertEqual(version_compare('2011AdvPack', '2012'), -1) ## Will need to specifically define 'AP vs SP2' in _get_value, however
    def test_1vs1ptfoo(self):
        self.assertEqual(version_compare('1', '1.foo'), -1)
    def test_1pt1RC1vs1pt1RC2(self):
        self.assertEqual(version_compare('1.1RC1', '1.1RC2'), -1)
    def test_1pt2pt3vs2(self):
        self.assertEqual(version_compare('1.2.3', '2'), -1)
    def test_single_letter(self):
        self.assertEqual(version_compare('1.a', '1.a'), 0)
    def test_single_letter2(self):
        self.assertEqual(version_compare('1.a', '1.b'), -1)
    def test_unrecognized_words1(self):
        self.assertEqual(version_compare('1.f', '1.foo'), -1)
    def test_unrecognized_words2(self):
        self.assertEqual(version_compare('1.bar', '1.foo'), -1)
        


if __name__ == '__main__':
    unittest.main()

