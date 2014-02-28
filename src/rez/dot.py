"""
Functions for manipulating dot-based resolve graphs.
"""
import os.path
from rez.contrib.pydot import pydot



def save_graph(graph, path, fmt=None, image_ratio=None,
               prune_to_conflict=False, prune_to_package=None):
    # create the graph
    if isinstance(graph, basestring):
        g = pydot.graph_from_dot_data(graph)
    else:
        raise NotImplementedError

    if prune_to_conflict or prune_to_package:
        # group graph edges by dest pkg, and find 'seed' pkg(s)
        edges = {}
        seed_pkgs = set()
        opt_pkg_exists_as_source = False

        oldedges = g.get_edge_list()
        for e in oldedges:
            pkgsrc = e.get_source().replace('"', '')
            pkgdest = e.get_destination()

            if pkgdest in edges:
                edges[pkgdest].add(e)
            else:
                s = set()
                s.add(e)
                edges[pkgdest] = s

            if prune_to_conflict and \
                "label" in e.get_attributes() and \
                    e.get_attributes()["label"] == "CONFLICT":
                seed_pkgs.add(pkgdest)
            elif prune_to_package:
                pkgdest_ = pkgdest.replace('"', '')
                if pkgdest_.startswith(prune_to_package):
                    seed_pkgs.add(pkgdest)
                if pkgsrc.startswith(prune_to_package):
                    opt_pkg_exists_as_source = True

        # extract all edges dependent (directly or not) on seed pkgs
        newg = pydot.Dot()
        consumed_edges = set()

        if seed_pkgs:
            while True:
                new_seed_pkgs = set()
                for seed_pkg in seed_pkgs:
                    seed_edges = edges.get(seed_pkg)
                    if seed_edges:
                        for seededge in seed_edges:
                            attribs = seededge.get_attributes()
                            if "lp" in attribs:
                                del attribs["lp"]
                            if "pos" in attribs:
                                del attribs["pos"]

                            if seededge not in consumed_edges:
                                newg.add_edge(seededge)
                                consumed_edges.add(seededge)
                            new_seed_pkgs.add(seededge.get_source())

                if not new_seed_pkgs:
                    break
                seed_pkgs = new_seed_pkgs

        if newg.get_edge_list():
            g = newg
        elif opt_pkg_exists_as_source:
            # pkg was directly in the request list
            e = pydot.Edge("DIRECT REQUEST", prune_to_package)
            newg.add_edge(e)
            g = newg

    # determine the dest format
    if fmt is None:
        fmt = os.path.splitext(path)[1].lower().strip('.') or "png"
    if hasattr(g, "write_"+fmt):
        write_fn = getattr(g, "write_"+fmt)
    else:
        raise Exception("Unsupported graph format: '%s'" % fmt)

    if image_ratio:
        g.set_ratio(str(image_ratio))
    write_fn(path)
    return fmt
