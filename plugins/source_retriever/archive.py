from __future__ import with_statement
from rez.source_retrieval import SourceRetriever, SourceRetrieverError
from rez.plugin_managers import RezPluginFactory
import os.path
import time
import sys
import hashlib
import tarfile

if sys.version_info < (2,6):
    from rez.contrib import zipfile
else:
    import zipfile



class Extractor(object):
    def __init__(self, archive_path, dest_path, dry_run=False):
        self.archive_path = archive_path
        self.dest_path = dest_path
        self.num_total = 0
        self.num_extracted = 0
        self.dry_run = dry_run

    def create_archive(self):
        raise NotImplementedError

    def get_archive_members(self, archive):
        raise NotImplementedError

    def close_archive(self, archive):
        archive.close()

    def extract_member(self, archive, member):
        archive.extract(member, self.dest_path)

    def _extract_member(self, archive, member):
        self.num_extracted += 1
        print "(%d/%d) Extracting %s..." % (self.num_extracted, self.num_total, member)
        if not self.dry_run:
            self.extract_member(archive, member)

    def extract_all(self):
        t1 = time.time()
        archive = self.create_archive()
        members = self.get_archive_members(archive)
        self.num_total = len(members)
        self.num_extracted = 0

        for member in members:
            self._extract_member(archive, member)
        self.close_archive(archive)

        print "Done (%.02fs)" % (time.time() - t1)
        prefix = os.path.commonprefix(members)
        return os.path.join(self.dest_path, prefix)


class ZipExtractor(Extractor):
    def create_archive(self):
        return zipfile.ZipFile(self.archive_path, 'r')

    def get_archive_members(self, archive):
        return archive.namelist()


class TarExtractor(Extractor):
    def create_archive(self):
        return tarfile.open(self.archive_path)

    def get_archive_members(self, archive):
        return [x.name for x in archive]



class ArchiveSourceRetriever(SourceRetriever):
    """
    Downloads source from an archive, such as a tarball or zipfile.
    """
    if sys.version_info < (2,7):
        HASH_TYPES = ('md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512')
    else:
        HASH_TYPES = hashlib.algorithms

    @classmethod
    def name(cls):
        return "archive"

    @classmethod
    def supported_url_types(cls):
        return [
            '.zip',
            '.tar',
            '.tgz',
            '.tar.gz']

    def __init__(self, url, cache_path=None, cache_filename=None, dry_run=False, \
                 do_checksum=False, hash_type=None, hash_str=None, **kwargs):
        super(ArchiveSourceRetriever,self).__init__(url, \
                                                    cache_path=cache_path,
                                                    cache_filename=cache_filename,
                                                    dry_run=dry_run)
        self.do_checksum = do_checksum
        self.hash_type = hash_type
        self.hash_str = hash_str

        if self.do_checksum:
            hash_types = ArchiveSourceRetriever.HASH_TYPES

            if self.hash_type or self.hash_str:
                if self.hash_type and self.hash_type not in hash_types:
                    raise SourceRetrieverError("Unrecognised hash type: '%s'" % self.hash_type)
                if not (self.hash_type and self.hash_str):
                    raise ValueError("hash_type and hash_str must be supplied together")
            else:
                # look for kwarg like sha1=ab58936fda6a8a43221
                for hash_type in hash_types:
                    if hash_type in kwargs:
                        self.hash_type = hash_type
                        self.hash_str = kwargs[hash_type]
                        break
                if not self.hash_type:
                    raise SourceRetrieverError("You must provide one of the following " + \
                        "checksum entries for the url '%s': %s" % (', '.join(hash_types), url))

    def download_to_cache(self, cache_path):
        self.download_file(cache_path)
        return cache_path

    def download_file(self, filepath):
        import urllib2
        u = urllib2.urlopen(self.url)

        with open(filepath, 'wb') as f:
            meta = u.info()
            header = meta.getheaders("Content-Length")
            if header:
                file_size = int(header[0])
                print "Downloading: %s Bytes: %s" % (filepath, file_size)
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
        extractor_type = ZipExtractor if cache_path.endswith('.zip') else TarExtractor
        extractor = extractor_type(cache_path, dest_path, self.dry_run)
        return extractor.extract_all()

    def download_to_source(self, dest_path):
        raise NotImplementedError("%s does not support direct downloading to source" \
                                  % self.__class__.__name__)

    def get_cache_filename(self):
        from urlparse import urlparse
        import posixpath
        return posixpath.basename(urlparse(self.url).path)

    @classmethod
    def _hash_ok(cls, source_path, checksum, hash_type):
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
        return (checksum == real_checksum)

    def _is_invalid_cache(self, path):
        if not os.path.isfile(path):
            if os.path.isdir(path):
                raise InvalidSourceError("%s was a directory, not a file")
            return "%s did not exist" % path

        return (not self.hash_ok(path, self.hash_str, self.hash_type)) \
            if self.do_checksum else False



class ArchiveSourceRetrieverFactory(RezPluginFactory):
    def target_type(self):
        return ArchiveSourceRetriever
