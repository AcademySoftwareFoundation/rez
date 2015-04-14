from rez.resolved_context import ResolvedContext

class LauncherContext(object):
    """
    This class is a facade from a ResolvedContext instance to be used by
    Launcher.  The intention is for this class to mask any backwards
    incompatible changes in Rez so that the Launcher script code is less brittle
    and subject to change.
    """

    def __init__(self, requestedPackages, **kwargs):
        resolved_context_kwargs = {}

        if "timestamp" in kwargs:
            resolved_context_kwargs["timestamp"] = float(kwargs["timestamp"])

        if "package_paths" in kwargs:
            resolved_context_kwargs["package_paths"] = kwargs["package_paths"]

        if "max_fails" in kwargs:
            resolved_context_kwargs["max_fails"] = int(kwargs["max_fails"])

        if "caching" in kwargs:
            resolved_context_kwargs["max_fails"] = bool(kwargs["caching"])

        self._resolved_context = ResolvedContext(requestedPackages, **resolved_context_kwargs)

    def print_info(self, **kwargs):
        print_info_kwargs = {}

        # From rez 2.0.b.30.0 'sort' (to denote alphabetically sorting) was
        # replaced with 'source_order' (the inverse).  Therefore if Launcher
        # asked for the info to be sorted we don't want source_order=False.
        if "sort" in kwargs:
            print_info_kwargs["source_order"] = not kwargs["sort"]
        
        if "verbosity" in kwargs:
            print_info_kwargs["verbosity"] = int(kwargs["verbosity"])

        self._resolved_context.print_info(**print_info_kwargs)

    def save(self, path):
        self._resolved_context.save(path)

    def apply(self):
        self._resolved_context.apply()

    def get_shell_code(self):
        self._resolved_context.get_shell_code()

    @property
    def success(self):
        return self._resolved_context.success
