config_version = 0
name = 'multi'
tools = ["tweak"]

versions = ["1.0",
            "1.1",
            "1.2"]

with scope("version_overrides"):
    with scope("1.1+"):
        tools = ["twerk"]
