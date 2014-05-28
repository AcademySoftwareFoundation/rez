import sys
import os.path

here = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(here, "installer")
sys.path.insert(0, path)
path = os.path.join(here, "src")
sys.path.insert(0, path)

from packager import generate_script

ignores = dict(
    rez=set([
        "cli",
        "bind",
        "tests",
        "packages",
        os.path.join("vendor", "pydot"),
        os.path.join("vendor", "pygraph"),
        os.path.join("vendor", "unittest2")
    ]))

patterns = ("*.py",
            "*.pem",
            "rezconfig")


def main():
    get_rez_file = os.path.join(here, 'get-rez.py')
    get_rez_tpl_file = os.path.join(here, "installer", "get-rez.py")
    with open(get_rez_tpl_file) as f:
        entry = f.read()

    print "creating get-rez.py installer..."
    script = generate_script(entry, ['pip', 'rez'],
                             ignores=ignores,
                             patterns=patterns)

    with open(get_rez_file, 'w') as f:
        f.write(script)
    print "\nget-rez.py was written."

if __name__ == '__main__':
    main()
