"""
Pluggable API for downloading source code from various archive and scm repositories.
"""
import os
import os.path
import traceback
import subprocess as sp
from rez.util import encode_filesystem_name



def get_source(url, dest_path, type=None, cache_path=None, cache_filename=None, \
               dry_run=False, **retriever_kwargs):
    ''' Download the source at the given url to dest_path.

        Returns the directory the source was extracted to, or None if
        unsuccessful
    '''
    from rez.plugin_managers import source_retriever_plugin_manager

    retriever = source_retriever_plugin_manager().create_instance(url, \
        type=type,
        cache_path=cache_path,
        cache_filename=cache_filename,
        dry_run=dry_run,
        **retriever_kwargs)

    return retriever.get_source(dest_path)


class SourceRetrieverError(Exception):
    pass


class InvalidSourceError(SourceRetrieverError):
    pass


class SourceRetriever(object):
    '''An object that is able to retrieve/download source from a given url, possibly caching
    the data in an interim location, or loading from that cache.
    '''
    @classmethod
    def name(cls):
        """ Return name of source retriever, eg 'git'"""
        raise NotImplementedError

    @classmethod
    def supported_url_types(cls):
        """ Return a list of supported url extensions, eg ['.gz']"""
        raise NotImplementedError

    def __init__(self, url, cache_path=None, cache_filename=None, dry_run=False, verbosity=2):
        '''Construct a SourceRetriever object to download source from the given url.
        Parameters
        ----------
        cache_path : str
            path to cache source downloads into
        cache_filename: str
            filename to store source cache into. If None, derives a filename based on the url.
        '''
        if cache_filename and not cache_path:
            raise ValueError("Cannot provide cache filename without a cache path")

        self.url = url
        self.cache_path = cache_path
        self.cache_filename = cache_filename
        self.dry_run = dry_run
        self.verbosity = verbosity

    def get_source(self, dest_path):
        '''Retreives/downloads the source code into the given directory

        Uses a cached version of the source if possible, otherwise downloads a
        fresh copy.

        Returns the directory the source was extracted to, or None if
        unsuccessful
        '''
        if self.cache_path:
            if not os.path.isdir(self.cache_path):
                os.makedirs(self.cache_path)

            cache_filename = self.cache_filename or self.get_cache_filename()
            cache_path = os.path.join(self.cache_path, cache_filename)

            if not self._is_invalid_cache(cache_path):
                print "Using cached archive %s" % cache_path
            else:
                try:
                    cache_path = self.download_to_cache(cache_path)
                except Exception, e:
                    err_msg = ''.join(traceback.format_exception_only(type(e), e))
                    print "error downloading %s: %s" % (self.url, err_msg.rstrip())
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                    raise
                else:
                    invalid_reason = self._is_invalid_cache(cache_path)
                    if invalid_reason:
                        raise InvalidSourceError("source downloaded to %s was invalid: %s"
                                                 % (cache_path, invalid_reason))
            dest_path = self.get_source_from_cache(cache_path, dest_path)
        else:
            dest_path = self.download_to_source(dest_path)

        invalid_reason = self._is_invalid_source(dest_path)
        if invalid_reason:
            raise InvalidSourceError("source extracted to %s was invalid: %s"
                                     % (dest_path, invalid_reason))
        return dest_path

    def _is_invalid_source(self, path):
        '''Check that the given source_path is valid; should raise a
        SourceRetrieverError if we wish to abort the build, return False if
        the cache was invalid, but we wish to simply delete and re-download, or
        True if the cache is valid, and we should use it.
        '''
        if not os.path.exists(path):
            return "%s did not exist" % path

    def _is_invalid_cache(self, path):
        '''Make sure the cache is valid.
        '''
        return self._is_invalid_source(path)

    #@abc.abstractmethod
    def download_to_source(self, dest_path):
        '''Download the source code directly to the given source_path.

        Note that specific implementations are not guaranteed to actually
        extract/download/etc to the given cache path - for this reason, this
        function returns the path that the source was TRULY downloaded to.

        Parameters
        ----------
        dest_path : str
            path that we should attempt to download this to
        '''
        raise NotImplementedError

    #@abc.abstractmethod
    def download_to_cache(self, cache_path):
        '''Download the source code to the given cache path.

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

    #@abc.abstractmethod
    def get_source_from_cache(self, cache_path, dest_path):
        '''
        extract to the final build source directory from the given cache path

        Parameters
        ----------
        cache_path : str
            path where source has previously been cached
        dest_path : str
            path to which the source code directory should be extracted
        '''
        raise NotImplementedError

    #@abc.abstractmethod
    def get_cache_filename(self):
        """
        get the default filename (without directory) for the local source
        archive of the given url (will be overridden if the url has an explicit
        cache_filename entry in it's metadata)
        """
        raise NotImplementedError

    def _subprocess(self, args, get_stdout=False, get_stderr=False, check_return=True,
                    quiet=False, **subprocess_kwargs):
        """
        Returns (exitcode,stdout,stderr), where stdout/err will be None if get_stdout/err
        is False. If check_return is True, an exception is raised if the subprocess fails.
        """
        cmd = ' '.join(args)
        if (self.verbosity > 1) and (not quiet):
            print "running: " + cmd

        _stdout = sp.PIPE if get_stdout else None
        _stderr = sp.PIPE if get_stderr else None
        p = sp.Popen(args, stdout=_stdout, stderr=_stderr, **subprocess_kwargs)
        _out,_err = p.communicate()

        if check_return and p.returncode:
            raise RuntimeError("Error running %r - exitcode: %d"
                               % (cmd, p.returncode))

        if _out: _out = _out.strip()
        if _err: _err = _err.strip()
        return p.returncode,_out,_err


class RepoCloner(SourceRetriever):
    def __init__(self, url, cache_path=None, cache_filename=None, revision=None,
                 dry_run=False, verbosity=2):
        super(RepoCloner,self).__init__(url, \
                                        cache_path=cache_path,
                                        cache_filename=cache_filename,
                                        dry_run=dry_run,
                                        verbosity=verbosity)
        self.revision = revision

    @classmethod
    def repo_current_symbol(cls, repo_dir):
        '''Returns the symbol that represents the "current" revision
        '''
        raise NotImplementedError

    def revision_to_hash(self, repo_dir, revision):
        '''Convert a revision (which may be a symbolic name, hash, etc) to a hash
        '''
        raise NotImplementedError

    def repo_current_hash(self, repo_dir):
        return self.revision_to_hash(repo_dir, self.repo_current_symbol(repo_dir))

    def repo_at_revision(self, repo_dir, revision):
        '''Whether the repo is currently at the given revision
        '''
        return self.repo_current_hash(repo_dir) == self.revision_to_hash(repo_dir, revision)

    def is_branch_name(self, repo_dir, revision):
        raise NotImplementedError

    def repo_has_revision(self, repo_dir, revision):
        raise NotImplementedError

    def repo_clone(self, repo_dir, repo_url, to_cache=False):
        raise NotImplementedError

    def repo_pull(self, repo_dir, repo_url):
        raise NotImplementedError

    def repo_update(self, repo_dir, revision):
        raise NotImplementedError

    def repo_clone_or_pull(self, repo_dir, other_repo, revision, to_cache=False):
        '''If repo_dir does not exist, clone from other_repo to repo_dir;
        otherwise, pull from other_repo to repo_dir if it does not have the
        given revision
        '''
        if not os.path.isdir(repo_dir):
            print "Cloning repo %s (to %s)" % (other_repo, repo_dir)
            self.repo_clone(repo_dir, other_repo, to_cache)
            if not to_cache:
                print "Updating repo %s to %s" % (repo_dir, revision)
                self.repo_update(repo_dir, revision)
        # if the revision is a branch name, we always pull
        elif self.is_branch_name(repo_dir, revision) or \
                not self.repo_has_revision(repo_dir, revision):
            print "Pulling from repo %s (to %s)" % (other_repo, repo_dir)
            self.repo_pull(repo_dir, other_repo)
            if not self.repo_at_revision(repo_dir, revision):
                print "Updating repo %s to %s" % (repo_dir, revision)
                self.repo_update(repo_dir, revision)
        return repo_dir

    def _is_invalid_source(self, path):
        if not os.path.isdir(path):
            if os.path.isfile(path):
                raise InvalidSourceError("%s was a file, not a directory")
            return "%s did not exist" % path
        if (self.revision is not None) and \
                (not self.repo_at_revision(path, self.revision)):
            return "%s was not at revision %s" % (path, self.revision)

    def _is_invalid_cache(self, path):
        if not os.path.isdir(path):
            if os.path.isfile(path):
                raise InvalidSourceError("%s was a file, not a directory")
            return "%s did not exist" % path
        if (self.revision is not None) and \
                (not self.repo_has_revision(path, self.revision)):
            return "%s did not contain revision %s" % (path, self.revision)

    def _revision(self, repo_dir):
        if self.revision is None:
            return self.repo_current_symbol(repo_dir)
        else:
            return self.revision

    def download_to_cache(self, dest_path):
        # from url to cache
        return self.repo_clone_or_pull(dest_path, self.url, self._revision(dest_path),
                                       to_cache=True)

    def download_to_source(self, dest_path):
        # from url to source
        return self.repo_clone_or_pull(dest_path, self.url, self._revision(dest_path),
                                       to_cache=False)

    def get_source_from_cache(self, cache_path, dest_path):
        # from cache to source
        return self.repo_clone_or_pull(dest_path, cache_path, self._revision(dest_path),
                                       to_cache=False)

    def get_cache_filename(self):
        return encode_filesystem_name(self.url)
