from rez.utils.platform_ import platform_

platform_map = {
    "arch": {
        "^.*$": "IMPOSSIBLE_ARCH",
    },
}

# Test fallback of Conditional
release_hooks = Conditional(
    {
        "Something": False,
    },
    key="3",
    default=["foo"]
)

prune_failed_graph = ArchDependent({
     "IMPOSSIBLE_ARCH": True,
})

# Fallback of OsDependent
warn_all = OsDependent({}, default=False)

plugins = PlatformDependent({
    platform_.name: {
        "release_hook": {
            "emailer": {
                "recipients": ["joe@here.com"]
            }
        }
    }
})
