import sys
import os.path

here = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(here, "installer")
sys.path.insert(0, path)
path = os.path.join(here, "src")
sys.path.insert(0, path)

from packager import generate_script

ignores = set([
        os.path.join("rez", "cli"),
        os.path.join("rez", "bind"),
        os.path.join("rez", "tests"),
        os.path.join("rez", "packages"),
        os.path.join("rez", "vendor", "pydot"),
        os.path.join("rez", "vendor", "pygraph"),
        os.path.join("rez", "vendor", "schema"),
        os.path.join("rez", "vendor", "unittest2"),
        os.path.join("rez", "vendor", "yaml")])

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
