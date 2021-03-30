
name = "developer_dynamic_global_preprocess"

@early()
def description():
    return "This."

# make sure imported modules don't break developer packages
import sys

# make sure attribute can use imported module
built_on = sys.platform
