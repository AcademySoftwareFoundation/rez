import os.path
import subprocess


def set_authors(data):
    """Add 'authors' attribute based on repo contributions
    """
    if "authors" in data:
        return

    shfile = os.path.join(os.path.dirname(__file__), "get_committers.sh")

    p = subprocess.Popen(["bash", shfile], stdout=subprocess.PIPE)
    out, _ = p.communicate()
    if p.returncode:
        return

    authors = out.strip().split('\n')
    authors = [x.strip() for x in authors]

    data["authors"] = authors
