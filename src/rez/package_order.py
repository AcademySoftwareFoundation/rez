


class PackageOrderFunction(object):
    def __init__(self):
        pass

    def reorder(self, packages):
        """Put packages into some order for consumption.

        Note:
            Returning None, and an unchanged `packages` list, are not the same
            thing. Returning None may cause rez to pass the package list to the
            next orderer; whereas a package list that has been reordered (even
            if the unchanged list is returned) is not passed onto another orderer.

        Args:
            `Packages` (list of `Package`): Packages to reorder. Guarantees:
                - There is at least one package;
                - They are in version descending order;
                - They all come from the same family.

        Returns:
            List of `Package`: Packages, in new order. Return None to leave the
                package order unchanged.
        """
        raise NotImplementedError


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

    def reorder(self, packages):
        reordered = []
        first_after = None

        for i, package in enumerate(packages):
            if package.timestamp:
                if package.timestamp >= self.timestamp:
                    first_after = i
                else:
                    break

        if first_after is None:  # all packages are before T
            return None

        before = packages[first_after + 1:]
        after = reversed(packages[:first_after + 1])

        if not self.rank:  # simple case
            return before + list(after)

        # ascend below rank, but descend within
        after_ = []
        postrank = []
        prerank = None

        for package in after:
            prerank_ = package.version.trim(self.rank - 1)
            if prerank_ == prerank:
                postrank.append(package)
            else:
                after_.extend(reversed(postrank))
                postrank = [package]
                prerank = prerank_

        after_.extend(reversed(postrank))
        return before + after
