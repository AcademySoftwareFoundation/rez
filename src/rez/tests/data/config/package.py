name = "foo"

version = "1.0.0"

description = "This package exists only to test config overrides."

uuid = "28d94bcd1a934bb4999bcf70a21106cc"

authors = [
    "joe.bloggs"
]

with scope("config") as c:
    c.build_directory = "weeble"

    c.parent_variables = [
        "FOO",
        "BAH_${FUNK}",
        "EEK"
    ]

    c.release_hooks = ModifyList(append=["bah"])

    c.plugins = {
        "release_vcs": {
            "tag_name": "tag"
        },
        "release_hook": {
            "emailer": {
                "sender": "{system.user}@somewhere.com",

                "recipients": ModifyList(append=["jay@there.com"]),

                # nonexistant keys should not cause a problem
                "nonexistant": "hello"
            }
        }
    }
