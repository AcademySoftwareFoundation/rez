name = 'late_binding'

version = "1.0"

@late()
def tools():
    return ["util"]

def commands():
    env.PATH.append("{root}/bin")
