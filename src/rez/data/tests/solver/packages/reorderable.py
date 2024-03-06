name = 'reorderable'

versions = [
        "3.1.1",
        "3.0.0",
        "2.2.1",
        "2.2.0",
        "2.1.5",
        "2.1.1",
        "2.1.0",
        "2.0.6",
        "2.0.5",
        "2.0.0",
        "1.9.1",
        "1.9.0",
]

# Note - we've intentionally left out timestamps for 2.2.0 and 1.9.1 to
# make sure the system still works
version_overrides = {
    "3.1.1": {"timestamp": 1470728488},
    "3.0.0": {"timestamp": 1470728486},
    "2.1.5": {"timestamp": 1470728484},
    "2.2.1": {"timestamp": 1470728482},
    "2.1.1": {"timestamp": 1470728480},
    "2.1.0": {"timestamp": 1470728478},
    "2.0.6": {"timestamp": 1470728476},
    "2.0.5": {"timestamp": 1470728474},
    "2.0.0": {"timestamp": 1470728472},
    "1.9.0": {"timestamp": 1470728470},
}
