"""Get information about the current environment.
"""
from rez.resolved_context import ResolvedContext
import yaml
import os
import os.path



_context = None


def get_context():
    """Returns the ResolvedContext associated with the current environment, or
    None if the environment is not Rez-configured.
    """
    global _context
    if _context is None:
        file = os.getenv("REZ_RXT_FILE")
        if file and os.path.exists(file):
            _context = ResolvedContext.load(file)
    return _context or None


def get_tools():
    """Get a list of Rez-configured tools currently available.

    Tools are available in two ways:
    - They are supplied by a package in the current context;
    - They are supplied by a wrapped environment on PATH.

    Returns:
        A list of 3-tuples, where each tuple contains:
        - The tool name;
        - The name of the package containing the tool;
        - The path to the rxt file containing the package, or None.
    """
    entries = []

    # package tools
    r = get_context()
    if r:
        keys = r.get_key("tools")
        for pkg,tools in sorted(keys.items()):
            for tool in sorted(tools):
                entries.append((tool, pkg, None))

    # wrapped tools
    paths = os.environ.get("PATH", "").split(os.pathsep)
    for path in paths:
        wrap_path = os.path.dirname(path.rstrip(os.sep))
        f = os.path.join(wrap_path, "wrapped_environment.yaml")
        if os.path.exists(f):
            rxt_files = []
            for name in os.listdir(wrap_path):
                if os.path.splitext(name)[1] == ".rxt":
                    rxt_files.append(os.path.join(wrap_path, name))

            for rxt_file in rxt_files:
                yaml_file = os.path.splitext(rxt_file)[0] + ".yaml"
                if os.path.isfile(yaml_file):
                    with open(yaml_file) as f:
                        doc = yaml.load(f.read())
                    tools = doc.get("tools", [])
                    for pkg,tool in sorted(tools):
                        entries.append((tool, pkg, rxt_file))
    return entries
