name = 'multi'
tools = ["tweak"]

versions = ["1.0",
            "1.1",
            "1.2",
            "2.0"]

with scope("version_overrides"):
    with scope("1.1+"):
        tools = ["twerk"]
