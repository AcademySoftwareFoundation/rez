from inspect import isclass
from hashlib import sha1


class PackageOrderFunction(object):
    """Package reorderer base class."""
    name = None

    def __init__(self):
        pass

    def reorder(self, iterable, key=None):
        """Put packages into some order for consumption.

        Note:
            Returning None, and an unchanged `iterable` list, are not the same
            thing. Returning None may cause rez to pass the package list to the
            next orderer; whereas a package list that has been reordered (even
            if the unchanged list is returned) is not passed onto another orderer.

        Args:
            iterable: Iterable list of packages, or objects that contain packages.
            key (callable): Callable, where key(iterable) gives a `Package`. If
                None, iterable is assumed to be a list of `Package` objects.

        Returns:
            List of `iterable` type, reordered.
        """
        raise NotImplementedError

    @property
    def sha1(self):
        return sha1(repr(self)).hexdigest()

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class TimestampPackageOrderFunction(PackageOrderFunction):
    """A timestamp order function.

    Given a time T, this orderer returns packages released before T, in descending
    order, followed by those released after. If `rank` is non-zero, version
    changes at that rank and above are allowed over the timestamp.

    For example, consider the common case where we want to prioritize packages
    released before T, except for newer patches. Consider the following package
    versions, and time T:

        2.2.1
        2.2.0
        2.1.1
        2.1.0
        2.0.6
        2.0.5
              <-- T
        2.0.0
        1.9.0

    A timestamp orderer set to rank=3 (patch versions) will attempt to consume
    the packages in the following order:

        2.0.6
        2.0.5
        2.0.0
        1.9.0
        2.1.1
        2.1.0
        2.2.1
        2.2.0

    Notice that packages before T are preferred, followed by newer versions.
    Newer versions are consumed in ascending order, except within rank (this is
    why 2.1.1 is consumed before 2.1.0).
    """
    name = "soft_timestamp"

    def __init__(self, timestamp, rank=0):
        """Create a reorderer.

        Args:
            timestamp (int): Epoch time of timestamp. Packages before this time
                are preferred.
            rank (int): If non-zero, allow version changes at this rank or above
                past the timestamp.
        """
        self.timestamp = timestamp
        self.rank = rank

    def reorder(self, iterable, key=None):
        reordered = []
        first_after = None
        key = key or (lambda x: x)

        # sort by version descending
        descending = sorted(iterable, key=lambda x: key(x).version, reverse=True)

        for i, o in enumerate(descending):
            package = key(o)
            if package.timestamp:
                if package.timestamp > self.timestamp:
                    first_after = i
                else:
                    break

        if first_after is None:  # all packages are before T
            return None

        before = descending[first_after + 1:]
        after = list(reversed(descending[:first_after + 1]))

        if not self.rank:  # simple case
            return before + after

        # include packages after timestamp but within rank
        if before and after:
            package = key(before[0])
            first_prerank = package.version.trim(self.rank - 1)

            for i, o in enumerate(after):
                package = key(o)
                prerank = package.version.trim(self.rank - 1)
                if prerank != first_prerank:
                    break

            if i:
                before = list(reversed(after[:i])) + before
                after = after[i:]

        # ascend below rank, but descend within
        after_ = []
        postrank = []
        prerank = None

        for o in after:
            package = key(o)
            prerank_ = package.version.trim(self.rank - 1)

            if prerank_ == prerank:
                postrank.append(o)
            else:
                after_.extend(reversed(postrank))
                postrank = [o]
                prerank = prerank_

        after_.extend(reversed(postrank))
        return before + after_

    def to_pod(self):
        return dict(timestamp=self.timestamp,
                    rank=self.rank)

    @classmethod
    def from_pod(cls, data):
        return cls(timestamp=data["timestamp"],
                   rank=data["rank"])

    def __str__(self):
        return "%d.%d" % (self.timestamp, self.rank)


def to_pod(orderer):
    data_ = orderer.to_pod()
    data = (orderer.name, data_)
    return data


def from_pod(data):
    cls_name, data_ = data
    cls = _orderers[cls_name]
    return cls.from_pod(data_)


def register_orderer(cls):
    if isclass(cls) and issubclass(cls, PackageOrderFunction) and \
            hasattr(cls, "name") and cls.name:
        _orderers[cls.name] = cls
        return True
    else:
        return False


# registration of builtin orderers
_orderers = {}
for o in globals().values():
    register_orderer(o)
