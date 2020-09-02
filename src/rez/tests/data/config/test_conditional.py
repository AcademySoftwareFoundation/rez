from rez.utils.platform_ import platform_

# Test fallback of Conditional
release_hooks = Conditional(
    {
        "Something": False,
    },
    key="3",
    default=["foo"]
)

prune_failed_graph = ArchDependent({
     platform_._arch(): False,
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
