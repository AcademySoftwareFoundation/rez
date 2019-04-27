import os
import subprocess

pypirc = """\
[distutils]
index-servers=pypi
[pypi]
username={PYPI_LOGIN}
password={PYPI_PASSWORD}
""".format(**os.environ)


def main():
    print("Deploying to PyPI..")

    with open(os.path.expanduser("~/.pypirc"), "w") as f:
        f.write(pypirc)

    subprocess.check_call(["pip", "install", "wheel", "twine"])
    subprocess.check_call(["python", "setup.py", "sdist", "bdist_wheel"])
    subprocess.check_call(["python", "-m", "twine", "upload", "dist/*"])


if os.getenv("APPVEYOR_REPO_TAG") == "true":
    main()
else:
    print("Deployment skipped, not a tag")
