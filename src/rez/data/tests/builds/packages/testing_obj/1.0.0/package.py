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

def pre_test_commands():
    env.REZ_TEST_ROOT = root
    env.REZ_TEST_BASE = base

build_command = 'python {root}/build.py {install}'

tests = {
    "command_as_string_success": {
        "command": "exit 0"
    },
    "command_as_string_fail": {
        "command": "exit 1"
    },
    "check_car_ideas": {
        "command": ["python", "-c", "import os; assert os.environ.get('CAR_IDEA') == 'STURDY STEERING WHEEL'"],
        "requires": ["python"]
    },
    "move_meeting_to_noon": {
        # We want this test to fail. SKIP_LUNCH should not be set.
        # TODO: We should not test for failures here. Testing failures, str vs lsit commands, etc
        # should we tested separately.
        "command": ["python", "-c", "import os; assert os.environ.get('SKIP_LUNCH') is not None"],
        "requires": ["python"]
    },
    "pre_test_commands_bindings": {
        "command": ["python", "-c", "import os; assert os.environ.get('REZ_TEST_ROOT') is not None; assert os.environ.get('REZ_TEST_BASE') is not None"],
        "requires": ["python"],
        "run_on": "pre_test"
    }
}
