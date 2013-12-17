import sys
import os
import re
import inspect
import traceback
import os.path
import subprocess
import abc
from rez.cli import error, output

SOURCE_ROOT = 'src'

_type_name_to_class = None

class SourceRetrieverError(Exception):
    pass

class InvalidSourceError(SourceRetrieverError):
    pass

def _get_url(metadict):
    """
    Return the (url, retriever_class, metadict) for the given metadict or
    None, if no url entry is present
    """
    url = metadict.get('url')
    if not url:
        return None

    # TODO: more gud smart make logic for figuring out type from url!
    type_name = metadict.get('type')
    if not type_name:
        basename = url.rsplit('/', 1)[-1]
        ext = os.path.splitext(basename)[-1]
        ext_to_type = {
            '.gz': 'archive',  # also covers .tar.gz
            '.tar': 'archive',
            '.tgz': 'archive',
            # '.zip': 'archive', # haven't implemented yet
            '.git': 'git',
            '.hg': 'hg',
        }
        type_name = ext_to_type.get(ext, 'archive')
    return url, type_name_to_class(type_name), metadict

def type_name_to_class(type_name):
    global _type_name_to_class
    if _type_name_to_class is None:
        # populate _type_name_to_class if we haven't yet
        _type_name_to_class = {}

        def is_retriever(obj):
            return (inspect.isclass(obj)
                    and issubclass(obj, SourceRetriever)
                    # used to do:
                    # and not inspect.isabstract(obj)
                    # ...but technically, RepoCloner isn't abstract, because
                    # all of it's "overridden" methods are classmethods,
                    # which as of python 2.7 can't be made abstract...
                    and obj.TYPE_NAME is not None)

        for obj in globals().itervalues():
            if is_retriever(obj):
                curr_name = obj.TYPE_NAME
                if curr_name != curr_name.lower():
                    raise ValueError("Invalid TYPE_NAME %r for %s - must be"
                                     " all lower case" % (curr_name,
                                                          obj.__name__))
                existing_cls = _type_name_to_class.get(curr_name)
                if existing_cls:
                    raise ValueError("Duplicate TYPE_NAME %r (%s and %s)"
                                     % (curr_name, obj.__name__,
                                        existing_cls.__name__))
                _type_name_to_class[curr_name] = obj
    try:
        return _type_name_to_class[type_name]
    except KeyError:
        raise SourceRetrieverError("unrecognized SourceRetriever type name"
                                   " %r - valid values are %s"
                                   % (type_name,
                                      ', '.join(_type_name_to_class.iterkeys())))

def get_source_retrievers(metadata):
    '''Given a metadata object, returns SourceRetriever objects for all the
    url entries in the external_build section
    '''
    retrievers = []
    package = metadata['name']
    build_data = metadata.get('external_build')
    if build_data:
        url = _get_url(build_data)
        if url:
            urls = [url]
        else:
            urls = [_get_url(x) for x in build_data.get('urls', [])]
        if urls:
            for url, retriever_class, metadict in urls:
                retrievers.append(retriever_class(package, metadict))
    return retrievers

class SourceRetriever(object):
    '''Classes which are used to retrieve source necessary for building.

    The use of these classes is triggered by the inclusion of url entries
    in the external_build dict of the package.yaml file
    '''
    __metaclass__ = abc.ABCMeta

    # override with a list of names that must be in the url's metadata dict
    REQUIRED_METADATA = ['url']

    # override with a name for this type of SourceRetriever, for use in
    # package.yaml files
    TYPE_NAME = None

    def __init__(self, package, metadict):
        '''Construct a SourceRetriever object from the given (raw) metadata dict
        (ie, as parsed straight from the yaml file).  Will raise a
        SourceRetrieverMissingMetadataError if the metadict is not compatible
        with this SourceRetriever
        '''
        self.package = package
        self.metadict = self.parse_metadict(metadict)

    @property
    def url(self):
        return self.metadict['url']

    @classmethod
    def parse_metadict(cls, raw_metadict):
        parsed = dict(raw_metadict)
        for required_attr in cls.REQUIRED_METADATA:
            if required_attr not in parsed:
                raise SourceRetrieverError('%s classes must define %s in their'
                                           ' metadict' % (cls.__name__,
                                                          required_attr))
        return parsed

    def get_source(self, src_path=SOURCE_ROOT):
        '''Retreives/downlods the source code into the src directory

        Uses a cached version of the source if possible, otherwise downloads a
        fresh copy.

        Returns the directory the source was extracted to, or None if
        unsuccessful
        '''
        # need this for rez-release, but break rez-build
        # src_path = os.path.abspath(src_path)
        cache_path = self._source_cache_path(self.url)
        if cache_path is not None:
            if not os.path.isdir(cache_path):
                os.makedirs(cache_path)
            # first see if the metadict gives an explicit cache filename...
            filename = self.metadict.get('external_build', {}).get('cache_filename')
            if filename is None:
                filename = self.source_cache_filename(self.url)
            cache_path = os.path.join(cache_path, filename)

            if not self._is_invalid_cache(cache_path):
                print "Using cached archive %s" % cache_path
            else:
                try:
                    cache_path = self.download_to_cache(cache_path)
                except Exception as e:
                    err_msg = ''.join(traceback.format_exception_only(type(e), e))
                    print "error downloading %s: %s" % (self.url, err_msg.rstrip())
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                    raise
                else:
                    invalid_reason = self._is_invalid_cache(cache_path)
                    if invalid_reason:
                        raise InvalidSourceError("source downloaded to %s was"
                                                 " invalid: %s"
                                                 % (cache_path,
                                                    invalid_reason))
            src_path = self.get_source_from_cache(cache_path, src_path)
        else:
            src_path = self.download_to_source(src_path)
        invalid_reason = self._is_invalid_source(src_path)
        if invalid_reason:
            raise InvalidSourceError("source extracted to %s was invalid: %s"
                                     % (src_path, invalid_reason))
        return src_path

    def _is_invalid_source(self, source_path):
        '''Check that the given source_path is valid; should raise a
        SourceRetrieverError if we wish to abort the build, return False if
        the cache was invalid, but we wish to simply delete and re-download, or
        True if the cache is valid, and we should use it.
        '''
        if not os.path.exists(source_path):
            return "%s did not exist" % source_path

    def _is_invalid_cache(self, cache_path):
        '''Make sure the cache is valid.

        Default implementation runs _is_invalid_source
        '''
        return self._is_invalid_source(cache_path)

    @abc.abstractmethod
    def download_to_source(self, source_path):
        '''Download the source code directly to the given source_path.

        Note that specific implementations are not guaranteed to actually
        extract/download/etc to the given cache path - for this reason, this
        function returns the path that the source was TRULY downloaded to.

        Parameters
        ----------
        source_path : str
            path that we should attempt to download this to
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def download_to_cache(self, cache_path):
        '''Download the source code to the given cache_path.

        Note that specific implementations are not guaranteed to actually
        extract/download/etc to the given cache path - for this reason, this
        function returns the path that the source was TRULY downloaded to.

        This function is paired with get_source_from_cache()

        Parameters
        ----------
        cache_path : str
            path that we should attempt to download this to
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_source_from_cache(self, cache_path, source_path):
        '''
        extract to the final build source directory from the given cache path

        Parameters
        ----------
        cache_path : str
            path where source has previously been cached
        source_path : str
            path to which the source code directory should be extracted
        '''

        raise NotImplementedError

    def _source_cache_path(self, url):
        """
        Return the path for the local source archive, or None if does not support
        caching.
        """
        archive_dir = os.environ.get('REZ_BUILD_DOWNLOAD_CACHE')
        if archive_dir:
            # organize by retriever-type and package -
            #   $REZ_BUILD_DOWNLOAD_CACHE/<retriever_type>/<package>/
            return os.path.join(archive_dir, self.TYPE_NAME, self.package)

    @abc.abstractmethod
    def source_cache_filename(self, url):
        """
        get the default filename (without directory) for the local source
        archive of the given url (will be overridden if the url has an explicit
        cache_filename entry in it's metadata)
        """
        raise NotImplementedError


def _extract_tar_process(tarpath, srcdir, members):
    """
    used by multiprocessed tar extraction
    """
    # would liked to have made this a staticmethod on the class, but it would
    # have required some heavy python magic to make it picklable.
    import tarfile
    print "extracting %s files" % len(members)
    tar = tarfile.open(tarpath)
    for member in members:
        tar.extract(member, srcdir)
    tar.close()


class SourceDownloader(SourceRetriever):
    TYPE_NAME = 'archive'
    # in python 2.7, this list is stored in hashlib.algorithms
    HASH_TYPES = ('md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512')

    # this may eventually be exposed as an option, or taken from -j flag somehow
    EXTRACTION_THREADS = 8

    @property
    def hash_str(self):
        return self.metadict['hash_str']

    @property
    def hash_type(self):
        return self.metadict['hash_type']

    @classmethod
    def parse_metadict(cls, raw_metadict):
        # get the hash string and hash type
        metadict = super(SourceDownloader, cls).parse_metadict(raw_metadict)
        url = metadict['url']
        for hash_type in cls.HASH_TYPES:
            hash_str = metadict.get(hash_type)
            if hash_str:
                metadict['hash_str'] = hash_str
                metadict['hash_type'] = hash_type
                return metadict
        raise SourceRetrieverError("when providing a download url for"
                                   " external build you must also provide a checksum entry (%s):"
                                   " %s" % (', '.join(cls.HASH_TYPES), url))

    def _source_cache_path(self, url):
        # Override to provide local download directory, which means that caching
        # is always supported, and thus we do not need to provide download_to_source()
        archive_dir = super(SourceDownloader, self)._source_cache_path(url)
        if archive_dir is not None:
            return archive_dir
        # if no $REZ_BUILD_DOWNLOAD_CACHE, we just put downloads in
        # subdirectory of the CWD:
        #   ./.rez-downloads/
        return '.rez-downloads'

    def download_to_cache(self, cache_path):
        self.download_file(self.url, cache_path)
        return cache_path

    @classmethod
    def download_file(cls, url, file_name):
        import urllib2

        u = urllib2.urlopen(url)

        with open(file_name, 'wb') as f:
            meta = u.info()
            header = meta.getheaders("Content-Length")
            if header:
                file_size = int(header[0])
                print "Downloading: %s Bytes: %s" % (file_name, file_size)
            else:
                file_size = None

            file_size_dl = 0
            block_sz = 8192
            while True:
                buffer = u.read(block_sz)
                if not buffer:
                    break

                file_size_dl += len(buffer)
                f.write(buffer)
                if file_size is not None:
                    status = r"%10d  [%3.2f%%]" % (file_size_dl, file_size_dl * 100. / file_size)
                    status = status + chr(8) * (len(status) + 1)
                    print status,

    def get_source_from_cache(self, cache_path, dest_path):
        return self._extract_tar(cache_path, dest_path)

    def download_to_source(self, dest_path):
        raise NotImplementedError("%s does not support direct downloading to source" % self.__class__.__name__)

    def source_cache_filename(self, url):
        from urlparse import urlparse
        import posixpath
        return posixpath.basename(urlparse(url).path)

    @classmethod
    def _extract_tar(cls, tarpath, outdir, dry_run=False):
        """
        extract the tar file at the given path, returning the common prefix of all
        paths in the archive
        """
        import tarfile
        import time
        from multiprocessing.pool import Pool

        print "Extracting %s" % tarpath
        s = time.time()
        tar = tarfile.open(tarpath)
        try:
            if dry_run:
                prefix = os.path.commonprefix(tar.getnames())
                return os.path.join(outdir, prefix)
            directories = []
            files = []
            total_size = 0
            for tarinfo in tar:
                if tarinfo.isdir():
                    # Extract directories with a safe mode.
                    directories.append(tarinfo)
                else:
                    files.append(tarinfo)
                    total_size += tarinfo.size

            if len(files + directories) > (1000 * cls.EXTRACTION_THREADS):
                bin_size = total_size / float(cls.EXTRACTION_THREADS)
                jobs = [[]]
                curr_size = 0
                for tarinfo in files:
                    if curr_size > bin_size:
                        jobs.append([])
                        curr_size = 0
                    curr_size += tarinfo.size
                    jobs[-1].append(tarinfo)
                if not len(jobs[-1]):
                    jobs.pop(-1)

                print "Using %d threads" % (len(jobs))
                # do directories first
                tar.extractall(outdir, directories)

                pool = Pool(processes=cls.EXTRACTION_THREADS)
                for job in jobs:
                    pool.apply_async(_extract_tar_process,
                                     (tarpath, outdir, job))
                pool.close()
                pool.join()
            else:
                tar.extractall(outdir)
            prefix = os.path.commonprefix([x.name for x in files])
            return os.path.join(outdir, prefix)
        finally:
            tar.close()
            print "done (%.02fs)" % (time.time() - s)

    @classmethod
    def _check_hash(cls, source_path, checksum, hash_type):
        import hashlib
        hasher = hashlib.new(hash_type)
        with open(source_path, 'rb') as f:
            while True:
                # read in 16mb blocks
                buf = f.read(16 * 1024 * 1024)
                if not buf:
                    break
                hasher.update(buf)
        real_checksum = hasher.hexdigest()
        if checksum != real_checksum:
            error("checksum mismatch: expected %s, got %s" % (real_checksum,
                                                              checksum))
            sys.exit(1)

    def _is_invalid_cache(self, cache_path):
        if not os.path.isfile(cache_path):
            if os.path.isdir(cache_path):
                raise InvalidSourceError("%s was a directory, not a file")
            return "%s did not exist" % cache_path
        return self._check_hash(cache_path, self.hash_str, self.hash_type)


class RepoCloner(SourceRetriever):
    REQUIRED_METADATA = SourceRetriever.REQUIRED_METADATA + ['revision']

    @classmethod
    def _subprocess(cls, args, wait=True, check_return=True,
                    **subprocess_kwargs):
        '''Run a git command for the given repo_dir, with the given args

        Parameters
        ----------
        args : strings
            args to pass to subprocess.call (or subprocess.Popen, if wait is
            False)
        wait : if True, then the result of subprocess.call is returned (ie,
            we wait for the process to finish, and return the returncode); if
            False, then the result of subprocess.Popen is returned (ie, we do
            not wait for the process to finish, and return the Popen object)
        check_return:
            if wait is True, and check_return is True, then an error will be
            raised if the return code is non-zero
        subprocess_kwargs : strings
            keyword args to pass to subprocess.call (or subprocess.Popen, if
            wait is False)
        '''
        if wait:
            exitcode = subprocess.call(args, **subprocess_kwargs)
            if check_return and exitcode:
                raise RuntimeError("Error running %r - exitcode: %d"
                                   % (' '.join(args), exitcode))
            return exitcode
        else:
            return subprocess.Popen(args, **subprocess_kwargs)

    @property
    def revision(self):
        return self.metadict['revision']

    @classmethod
    def revision_to_hash(cls, repo_dir, revision):
        '''Convert a revision (which may be a symbolic name, hash, etc) to a
        hash
        '''
        raise NotImplementedError

    @classmethod
    def repo_current_symbol(cls, repo_dir):
        '''Returns the symbol that represents the "current" revision
        '''
        raise NotImplementedError

    @classmethod
    def repo_current_hash(cls, repo_dir):
        return cls.revision_to_hash(repo_dir, cls.repo_current_symbol(repo_dir))

    @classmethod
    def repo_at_revision(cls, repo_dir, revision):
        '''Whether the repo is currently at the given revision
        '''
        return cls.repo_current_hash(repo_dir) == cls.revision_to_hash(repo_dir,
                                                                       revision)

    @classmethod
    def is_branch_name(cls, repo_dir, revision):
        raise NotImplementedError

    @classmethod
    def repo_has_revision(cls, repo_dir, revision):
        raise NotImplementedError

    @classmethod
    def repo_clone(cls, repo_dir, repo_url, to_cache=False):
        raise NotImplementedError

    @classmethod
    def repo_pull(cls, repo_dir, repo_url):
        raise NotImplementedError

    @classmethod
    def repo_update(cls, repo_dir, revision):
        raise NotImplementedError

    @classmethod
    def repo_clone_or_pull(cls, repo_dir, other_repo, revision, to_cache=False):
        '''If repo_dir does not exist, clone from other_repo to repo_dir;
        otherwise, pull from other_repo to repo_dir if it does not have the
        given revision
        '''
        if not os.path.isdir(repo_dir):
            print "Cloning repo %s (to %s)" % (other_repo, repo_dir)
            cls.repo_clone(repo_dir, other_repo, to_cache)
            if not to_cache:
                print "Updating repo %s to %s" % (repo_dir, revision)
                cls.repo_update(repo_dir, revision)
        # if the revision is a branch name, we always pull
        elif cls.is_branch_name(repo_dir, revision) or not cls.repo_has_revision(repo_dir, revision):
            print "Pulling from repo %s (to %s)" % (other_repo, repo_dir)
            cls.repo_pull(repo_dir, other_repo)
            if not cls.repo_at_revision(repo_dir, revision):
                print "Updating repo %s to %s" % (repo_dir, revision)
                cls.repo_update(repo_dir, revision)
        return repo_dir

    def _is_invalid_source(self, source_path):
        if not os.path.isdir(source_path):
            if os.path.isfile(source_path):
                raise InvalidSourceError("%s was a file, not a directory")
            return "%s did not exist" % source_path
        if not self.repo_at_revision(source_path, self.revision):
            return "%s was not at revision %s" % (source_path, self.revision)

    def _is_invalid_cache(self, cache_path):
        if not os.path.isdir(cache_path):
            if os.path.isfile(cache_path):
                raise InvalidSourceError("%s was a file, not a directory")
            return "%s did not exist" % cache_path
        if not self.repo_has_revision(cache_path, self.revision):
            return "%s did not contain revision %s" % (cache_path, self.revision)

    def download_to_cache(self, dest_path):
        # from url to cache
        return self.repo_clone_or_pull(dest_path, self.url, self.revision,
                                       to_cache=True)

    def download_to_source(self, dest_path):
        # from url to source
        return self.repo_clone_or_pull(dest_path, self.url, self.revision,
                                       to_cache=False)

    def get_source_from_cache(self, cache_path, dest_path):
        # from cache to source
        return self.repo_clone_or_pull(dest_path, cache_path, self.revision,
                                       to_cache=False)

    def source_cache_filename(self, url):
        return self.encode_filesystem_name(url)

    @classmethod
    def encode_filesystem_name(cls, input_str):
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

    FILESYSTEM_TOKEN_RE = re.compile(r'(?P<as_is>[a-z0-9.-])|(?P<underscore>__)|_(?P<uppercase>[a-z])|_(?P<N>[0-9])')
    HEX_RE = re.compile('[0-9a-f]+$')

    @classmethod
    def decode_filesystem_name(cls, filename):
        """Decodes a filename encoded using the rules given in
        encode_filesystem_name to a unicode string
        """
        result = []
        remain = filename
        i = 0
        while remain:
            # use match, to ensure it matches from the start of the string...
            match = cls.FILESYSTEM_TOKEN_RE.match(remain)
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
                if not cls.HEX_RE.match(bytes):
                    raise ValueError("Bad utf8 encoding in name %r"
                                     " (bad index: %d - %r)" % (filename, i,
                                                                bytes))

                bytes_repr = ''.join('\\x%s' % bytes[i:i + 2]
                                     for i in xrange(0, bytes_len, 2))
                bytes_repr = "'%s'" % bytes_repr
                result.append(eval(bytes_repr).decode('utf8'))
                # print "got utf8 - %r" % result[-1]
            else:
                raise ValueError("Unrecognized match type in filesystem name %r"
                                 " (bad index: %d - %r)" % (filename, i,
                                                            remain[:2]))
            # print result
        return u''.join(result)

    @classmethod
    def test_encode_decode(cls):
        def do_test(orig, expected_encoded):
            print '=' * 80
            print orig
            encoded = cls.encode_filesystem_name(orig)
            print encoded
            assert encoded == expected_encoded
            decoded = cls.decode_filesystem_name(encoded)
            print decoded
            assert decoded == orig

        do_test("Foo_Bar (fun).txt", '_foo___bar_020_028fun_029.txt')

        # u'\u20ac' == Euro symbol
        do_test(u"\u20ac3 ~= $4.06", '_3e282ac3_020_07e_03d_020_0244.06')


class GitCloner(RepoCloner):
    TYPE_NAME = 'git'

    @classmethod
    def git(cls, repo_dir, git_args, bare=None, wait=True, check_return=True,
            **subprocess_kwargs):
        '''Run a git command for the given repo_dir, with the given args

        Parameters
        ----------
        repo_dir : basestring or None
            if non-None, a git working dir to set as the repo to use; note that
            since this is a required argument, if you wish to run a git command
            that does not need a current repository (ie,
            'git --version', 'hg clone', etc), you must explicitly pass None
        git_args : strings
            args to pass to git (as on the command line)
        bare : bool or None
            whether or not the repo_dir is a "bare" git repo (ie, if this is
            false, <repo_dir>/.git should exist); if None, then will attempt
            to auto-determine whether the repo is bare (by checking for a
            <repo_dir>/.git dir)
        wait : if True, then the result of subprocess.call is returned (ie,
            we wait for the process to finish, and return the returncode); if
            False, then the result of subprocess.Popen is returned (ie, we do
            not wait for the process to finish, and return the Popen object)
        check_return:
            if wait is True, and check_return is True, then an error will be
            raised if the return code is non-zero
        subprocess_kwargs : strings
            keyword args to pass to subprocess.call (or subprocess.Popen, if
            wait is False)
        '''
        args = ['git']
        if repo_dir is not None:
            if bare is None:
                bare = not os.path.exists(os.path.join(repo_dir, '.git'))
            if bare:
                args.extend(['--git-dir', repo_dir])
            else:
                args.extend(['--work-tree', repo_dir, '--git-dir',
                             os.path.join(repo_dir, '.git')])
        args.extend(git_args)
        return cls._subprocess(args, wait=wait, check_return=check_return,
                               **subprocess_kwargs)

    @classmethod
    def _current_branch(cls, repo_dir):
        # proc = cls.git(repo_dir, ['branch'], wait=False, stdout=subprocess.PIPE)
        proc = cls.git(repo_dir, ['rev-parse', '--abbrev-ref', 'HEAD'],
                       wait=False, stdout=subprocess.PIPE)
        stdout = proc.communicate()[0]
        if proc.returncode:
            raise RuntimeError("Error running git rev-parse - exitcode: %d"
                               % proc.returncode)
        return stdout.strip()

    @classmethod
    def _repo_remote_for_url(cls, repo_dir, repo_url):
        '''Given a remote repo url, returns the remote name that has that url
        as it's fetch url (creating / setting the rez_remote remote, if none
        exists)
        '''
        default_remote = 'rez_remote'

        proc = cls.git(repo_dir, ['remote', '-v'], wait=False,
                       stdout=subprocess.PIPE)
        stdout = proc.communicate()[0]
        if proc.returncode:
            raise RuntimeError("Error running git branch - exitcode: %d"
                               % proc.returncode)

        # for comparison, we need to "standardize" the repo url, by removing
        # any multiple whitespace (though there probably shouldn't be
        # whitespace)
        repo_url = ' '.join(repo_url.strip().split())

        found_default = False
        for line in stdout.split('\n'):
            # line we want looks like:
            # origin  git@github.com:SomeGuy/myrepo.git (fetch)
            fetch_str = ' (fetch)'
            line = line.strip()
            if not line.endswith(fetch_str):
                continue
            split_line = line[:-len(fetch_str)].split()
            if len(split_line) < 2:
                continue
            remote_name = split_line[0]
            if remote_name == default_remote:
                found_default = True
            remote_url = ' '.join(split_line[1:])
            print "remote_url: %r" % remote_url
            if remote_url == repo_url:
                return remote_name

        # if we've gotten here, we didn't find an existing remote that had
        # the desired url...

        if not found_default:
            # make one...
            cls.git(repo_dir, ['remote', 'add', default_remote, repo_url])
        else:
            # ...or update existing...
            cls.git(repo_dir, ['remote', 'set-url', default_remote, repo_url])
        return default_remote

    @classmethod
    def revision_to_hash(cls, repo_dir, revision):
        '''Convert a revision (which may be a symbolic name, hash, etc) to a
        hash
        '''
        branch = cls._find_branch(repo_dir, revision)
        if branch:
            revision = branch
        proc = cls.git(repo_dir, ['rev-parse', revision],
                       wait=False, stdout=subprocess.PIPE)
        stdout = proc.communicate()[0]
        if proc.returncode:
            raise RuntimeError("Error running git rev-parse - exitcode: %d"
                               % proc.returncode)
        return stdout.rstrip()

    @classmethod
    def repo_current_symbol(cls, repo_dir):
        '''Returns the symbol that represents the "current" revision
        '''
        return "HEAD"

    @classmethod
    def _iter_branches(cls, repo_dir, remote=True, local=True):
        proc = cls.git(repo_dir, ['branch', '-a'],
                       wait=False, stdout=subprocess.PIPE)
        stdout = proc.communicate()[0]
        if proc.returncode:
            raise RuntimeError("Error running git branch - exitcode: %d"
                               % proc.returncode)
        for line in stdout.split('\n'):
            if line and '->' not in line:
                branch = line.strip('* ')
                if remote and branch.startswith('remotes/'):
                    yield branch
                elif local and not branch.startswith('remotes/'):
                    yield branch

    @classmethod
    def _find_branch(cls, repo_dir, name, remote=True, local=True):
        for branch in cls._iter_branches(repo_dir, remote, local):
            if branch.split('/')[-1] == name:
                return branch

    @classmethod
    def is_branch_name(cls, repo_dir, revision):
        return bool(cls._find_branch(repo_dir, revision))

    @classmethod
    def repo_has_revision(cls, repo_dir, revision):
        exitcode = cls.git(repo_dir, ['cat-file', '-e', revision],
                           check_return=False)
        return exitcode == 0

    @classmethod
    def repo_clone(self, repo_dir, repo_url, to_cache):
        # -n makes it not do a checkout
        args = ['clone', '-n']
        if to_cache:
            # use mirror so we get all the branches as well, with a direct
            # mirror default fetch for branches.
            # mirror implies bare.
            args.append('--mirror')
        args.extend([repo_url, repo_dir])
        self.git(None, args)

    @classmethod
    def repo_pull(cls, repo_dir, repo_url):
        remote_name = cls._repo_remote_for_url(repo_dir, repo_url)
        cls.git(repo_dir, ['fetch', remote_name])

    @classmethod
    def repo_update(cls, repo_dir, revision):
        curr_branch = cls._current_branch(repo_dir)
        branch = cls._find_branch(repo_dir, revision)
        if branch and branch.startswith('remotes/'):
            print "creating tracking branch for", revision
            cls.git(repo_dir, ['checkout', '--track', 'origin/' + revision])
        else:
            # need to use different methods to update, depending on whether or
            # not we're switching branches...
            if curr_branch == 'rez':
                # if branch is already rez, need to use "reset"
                cls.git(repo_dir, ['reset', '--hard', revision])
            else:
                # create / checkout a branch called "rez"
                cls.git(repo_dir, ['checkout', '-B', 'rez', revision])

class HgCloner(RepoCloner):
    TYPE_NAME = 'hg'

    @classmethod
    def hg(cls, repo_dir, hg_args, wait=True, check_return=True,
           **subprocess_kwargs):
        '''Run an hg command for the given repo_dir, with the given args

        Parameters
        ----------
        repo_dir : basestring or None
            if non-None, a mercurial working dir to set as the repo to use; note
            that since this is a required argument, if you wish to run an hg
            command that does not need a current repository (ie, 'hg --version',
            'hg clone', etc), you must explicitly pass None
        hg_args : strings
            args to pass to hg (as on the command line)
        wait : if True, then the result of subprocess.call is returned (ie,
            we wait for the process to finish, and return the returncode); if
            False, then the result of subprocess.Popen is returned (ie, we do
            not wait for the process to finish, and return the Popen object)
        check_return:
            if wait is True, and check_return is True, then an error will be
            raised if the return code is non-zero
        subprocess_kwargs : strings
            keyword args to pass to subprocess.call
        '''
        args = ['hg']
        if repo_dir is not None:
            args.extend(['-R', repo_dir])
        args.extend(hg_args)
        return cls._subprocess(args, wait=wait, check_return=check_return,
                               **subprocess_kwargs)

    @classmethod
    def revision_to_hash(cls, repo_dir, revision):
        '''Convert a revision (which may be a symbolic name, hash, etc) to a
        hash
        '''
        proc = cls.hg(repo_dir, ['log', '-r', revision, '--template', "{node}"],
                      wait=False, stdout=subprocess.PIPE)
        stdout = proc.communicate()[0]
        if proc.returncode:
            raise RuntimeError("Error running hg log - exitcode: %d"
                               % proc.returncode)
        return stdout

    @classmethod
    def repo_current_symbol(cls, repo_dir):
        '''Returns the symbol that represents the "current" revision
        '''
        return "."

    @classmethod
    def repo_has_revision(cls, repo_dir, revision):
        # don't want to print error output if revision doesn't exist, so
        # use subprocess.PIPE to swallow output
        exitcode = cls.hg(repo_dir, ['id', '-r', revision], check_return=False,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return exitcode == 0

    @classmethod
    def is_branch_name(cls, repo_dir, revision):
        proc = cls.hg(repo_dir, ['branches', '--active'],
                      wait=False, stdout=subprocess.PIPE)
        stdout = proc.communicate()[0]
        if proc.returncode:
            raise RuntimeError("Error running hg log - exitcode: %d"
                               % proc.returncode)
        for line in stdout.split('\n'):
            if line and revision == line.split()[0]:
                return True
        return False

    @classmethod
    def repo_clone(cls, repo_dir, repo_url, to_cache):
        cls.hg(None, ['clone', '--noupdate', repo_url, repo_dir])

    @classmethod
    def repo_pull(cls, repo_dir, repo_url):
        cls.hg(repo_dir, ['pull', repo_url])

    @classmethod
    def repo_update(cls, repo_dir, revision):
        cls.hg(repo_dir, ['update', revision])

def _apply_patch(package, patch_info, source_path):
    action = patch_info['type']
    if action == 'patch':
        patch = patch_info['file']
        print "applying patch %s" % patch
        patch = os.path.abspath(patch)
        # TODO: handle urls. for now, assume relative
        result = subprocess.call(['patch', '-p1', '-i', patch],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 cwd=source_path)
        if result:
            error("Failed to apply patch: %s" % patch)
            sys.exit(1)
    elif action == 'append':
        path = patch_info['file']
        text = patch_info['text']
        path = os.path.join(source_path, path)
        print "appending %r to %s" % (text, path)
        with open(path, 'a') as f:
            f.write(text)
    elif action == 'prepend':
        path = patch_info['file']
        text = patch_info['text']
        path = os.path.join(source_path, path)
        print "prepending %r to %s" % (text, path)
        with open(path, 'r') as f:
            curr_text = f.read()
        with open(path, 'w') as f:
            f.write(text + curr_text)
    elif action == 'replace':
        path = patch_info['file']
        find = patch_info['find']
        replace = patch_info['replace']
        path = os.path.join(source_path, path)
        print "replacing %r with %r in %s" % (find, replace, path)
        with open(path, 'r') as f:
            curr_text = f.read()
        curr_text = curr_text.replace(find, replace)
        with open(path, 'w') as f:
            f.write(curr_text)
    elif action == 'mq':
        url = patch_info['url']
        rev = patch_info['revision']
        metadict = dict(url=url, type='hg', revision=rev)
        print "using mercurial patch queue..."
        cloner = HgCloner(package, metadict)
        cloner.get_source(os.path.join(SOURCE_ROOT, '.hg', 'patches'))
#             tags = cloner.hg(SOURCE_ROOT,
#                              ['log', '-r',  '.', '--template', '{tags}']).split()
#             if 'qtip' not in tags:
        print "applying patches"
        cloner.hg(SOURCE_ROOT, ['qpop', '--all'],
                  check_return=False)
        guards = patch_info.get('guards')
        if guards:
            if not isinstance(guards, list):
                guards = [guards]
            print "applying patch guards: " + ' '.join(guards)
            cloner.hg(SOURCE_ROOT, ['qselect'] + guards)
        cloner.hg(SOURCE_ROOT, ['qpush', '--exact', '--all'],
                  check_return=False)
    else:
        error("Unknown patch action: %s" % action)
        sys.exit(1)

def _write_cmakelist(install_commands, srcdir, working_dir_mode):
    assert not os.path.isabs(srcdir), "source dir must not be an absolute path: %s" % srcdir
    # there are different modes available for the current working directory
    working_dir_mode = working_dir_mode.lower()
    if working_dir_mode == 'source':
        working_dir = "${REZ_SOURCE_DIR}"
    elif working_dir_mode == 'source_root':
        working_dir = "${REZ_SOURCE_ROOT}"
    elif working_dir_mode == 'build':
        working_dir = "${REZ_BUILD_DIR}"
    else:
        error("Invalid option for 'working_dir': provide one of 'source', 'source_root', or 'build'")
        sys.exit(1)

    lines = ['custom_build ALL ' + install_commands[0]]
    for line in install_commands[1:]:
        if line.strip():
            lines.append('  COMMAND ' + line)

    variables = set([])
    for line in install_commands:
        variables.update(re.findall('\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}', line))

    extra_cmake_commands = []
    if variables:
        width = max(len(x) for x in variables)
        extra_cmake_commands.append('message("")')
        extra_cmake_commands.append('message("External build cmake variables:")')
        for cmake_var in sorted(variables):
            extra_cmake_commands.append('message("    {0:<{fill}} ${{{0}}}")'.format(cmake_var, fill=width))

    env_variables = set([])
    for line in install_commands:
        env_variables.update(re.findall('\$ENV\{([a-zA-Z_][a-zA-Z0-9_]*)\}', line))

    if env_variables:
        width = max(len(x) for x in env_variables)
        extra_cmake_commands.append('message("")')
        extra_cmake_commands.append('message("External build environment variables:")')
        for cmake_var in sorted(env_variables):
            extra_cmake_commands.append('message("    {0:<{fill}} $ENV{{{0}}}")'.format(cmake_var, fill=width))

    if variables or env_variables:
        extra_cmake_commands.append('message("")')

    text = """\
CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)

rez_find_packages(PREFIX pkgs AUTO)

set(REZ_BUILD_DIR ${CMAKE_BINARY_DIR}/rez-external)
file(MAKE_DIRECTORY ${REZ_BUILD_DIR})

# copy CMAKE_INSTALL_PREFIX to a rez variable for future proofing
set(REZ_INSTALL_PREFIX ${CMAKE_INSTALL_PREFIX})

set(REZ_SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/%s)
set(REZ_SOURCE_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/%s)

%s

add_custom_target(
  %s
  WORKING_DIRECTORY %s
)

# Create Cmake file
rez_install_cmake(AUTO)
""" % (srcdir,
        SOURCE_ROOT,
        '\n'.join(extra_cmake_commands),
        '\n'.join(lines),
        working_dir)

    print "writing CMakeLists.txt"
    with open('CMakeLists.txt', 'w') as f:
        f.write(text)

def get_source(metadata):
    build_data = metadata.get('external_build')
    # we don't retrieve source on a release build.  this assumes that a build has
    # been run prior to the release. eventually, rez-release will be called by
    # rez-build, instead of the other way around, which will give us more control.
    if build_data:
        try:
            retrievers = get_source_retrievers(metadata)
            if retrievers:
                for retriever in retrievers:
                    try:
                        srcdir = retriever.get_source()
                        return srcdir
                    except Exception as e:
                        # err_msg = ''.join(traceback.format_exception_only(type(e), e))
                        err_msg = traceback.format_exc()
                        error("Error retrieving source from %s: %s"
                              % (retriever.url, err_msg.rstrip()))
                error("All retrievers failed to retrieve source")
                sys.exit(1)

        except SourceRetrieverError as e:
            error(str(e))
            sys.exit(1)

def patch_source(metadata, srcdir):
    build_data = metadata.get('external_build')
    for patch in build_data.get('patches', []):
        _apply_patch(metadata['name'], patch, srcdir)

def write_build_script(metadata, srcdir):
    build_data = metadata.get('external_build')
    if 'commands' in build_data:
        # cleanup prevous runs
        if os.path.exists('CMakeLists.txt'):
            os.remove('CMakeLists.txt')
        install_commands = build_data['commands']
        assert isinstance(install_commands, list)
        working_dir = build_data.get('working_dir', 'source')
        _write_cmakelist(install_commands, srcdir, working_dir)

def get_patched_source(metadata):
    '''
    Main entry point for retrieving source code and patching it
    '''
    srcdir = get_source(metadata)
    if srcdir:
        patch_source(metadata, srcdir)
        write_build_script(metadata, srcdir)
        return srcdir
