name = "developer_dynamic"

@early()
def description():
    return "This."

requires = [
    "versioned-*"
]

def preprocess(this, data):
    from early_utils import get_authors
    data["authors"] = get_authors()
