name = 'testing obj'
version = '1.0.0'
authors = ["Dan Flashes"]

description = "testing the 'testing' attribute available during rez test"

@late()
def requires():
    if in_context() and testing:
        return ["floob"]
    return ["hello"]

private_build_requires = ["build_util", "python"]

def commands():
    env.PYTHONPATH.append('{root}/python')
    if testing:
        env.CAR_IDEA = "STURDY STEERING WHEEL"
    else:
        env.SKIP_LUNCH = "False"

build_command = 'python {root}/build.py {install}'

tests = {
    "check_car_ideas": {
        "command": "[[ -z ${CAR_IDEA} ]] && exit 1 || exit 0"
    },
    "move_meeting_to_noon": {
        "command": "[[ -z ${SKIP_LUNCH} ]] && exit 1 || exit 0"
    }
}