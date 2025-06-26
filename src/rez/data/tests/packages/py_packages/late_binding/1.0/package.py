name = 'late_binding'

version = "1.0"

@late()
def tools():
    return ["util"]

def commands() -> None:
    env.PATH.append("{root}/bin")
