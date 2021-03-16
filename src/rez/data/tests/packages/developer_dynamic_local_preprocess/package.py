
name = "developer_dynamic_local_preprocess"

@early()
def description():
    return "This."

requires = [
    "versioned-*"
]

def preprocess(this, data):
    from early_utils import get_authors
    data["authors"] = get_authors()
    data["added_by_local_preprocess"] = True

# make sure imported modules don't break developer packages
import sys

# make sure attribute can use imported module
built_on = sys.platform
