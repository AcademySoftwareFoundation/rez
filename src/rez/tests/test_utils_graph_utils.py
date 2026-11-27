# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'utils.graph_utils' module
"""
import io
import os
import unittest
from unittest.mock import MagicMock, patch

from rez.tests.util import TempdirMixin, TestBase, restore_os_environ
from rez.utils.graph_utils import (
    _request_from_label,
    _write_graph,
    prune_graph,
    read_graph_from_string,
    save_graph,
    save_graph_object,
    view_graph,
    write_compacted,
    write_dot,
)
from rez.vendor.pygraph.classes.digraph import digraph


class TestReadAndWriteGraph(TestBase):
    def test_read_graph_from_string_dot(self) -> None:
        dot_str = (
            'digraph g {\n'
            '    _1 [label="foo-1.0[]", fontsize="10"];\n'
            '    _2 [label="bar-2.0[]"];\n'
            '    _1 -> _2 [label="CONFLICT"];\n'
            '}\n'
        )
        g = read_graph_from_string(dot_str)
        self.assertEqual(set(g.nodes()), {"_1", "_2"})
        self.assertEqual(g.edges(), [("_1", "_2")])
        self.assertEqual(g.edge_label(("_1", "_2")), '"CONFLICT"')

    def test_read_graph_from_string_compacted(self) -> None:
        compacted = str(
            {
                "nodes": [
                    ([("fontsize", 10), ("style", "filled")], ["n1", ("n2", "bar-1.0[]")]),
                ],
                "edges": [
                    ([("weight", 2), ("color", "red")], [("n1", "n2"), ("n2", "n1", "CONFLICT")]),
                ],
            }
        )
        g = read_graph_from_string(compacted)
        self.assertEqual(set(g.nodes()), {"n1", "n2"})
        self.assertEqual(
            dict(g.node_attributes("n1")),
            {"fontsize": 10, "style": '"filled"'},
        )
        self.assertEqual(
            dict(g.node_attributes("n2")),
            {"fontsize": 10, "style": '"filled"', "label": '"bar-1.0[]"'},
        )
        self.assertEqual(g.edge_label(("n1", "n2")), "")
        self.assertEqual(g.edge_label(("n2", "n1")), "CONFLICT")
        self.assertEqual(
            dict(g.edge_attributes(("n2", "n1"))),
            {"weight": 2, "color": '"red"'},
        )

    def test_write_compacted_roundtrip(self) -> None:
        g = digraph()
        g.add_node("n1", attrs=[("label", '"foo-1.0"'), ("fontsize", 10)])
        g.add_node("n2", attrs=[("style", '"filled"')])
        g.add_edge(("n1", "n2"), label="DEP", attrs=[("arrowsize", '"0.5"'), ("weight", 1)])
        g.add_edge(("n2", "n1"))

        compacted = write_compacted(g)
        self.assertTrue(compacted.startswith("{"))

        g2 = read_graph_from_string(compacted)
        self.assertEqual(set(g2.nodes()), {"n1", "n2"})
        self.assertEqual(dict(g2.node_attributes("n1")), {"label": '"foo-1.0"', "fontsize": 10})
        self.assertEqual(dict(g2.node_attributes("n2")), {"style": '"filled"'})
        self.assertEqual(g2.edge_label(("n1", "n2")), "DEP")
        self.assertEqual(dict(g2.edge_attributes(("n1", "n2"))), {"arrowsize": '"0.5"', "weight": 1})
        self.assertEqual(g2.edge_label(("n2", "n1")), "")

    def test_write_dot(self) -> None:
        g = digraph()
        g.add_node("n1", attrs=[("label", '"foo-1.0"'), ("fontsize", 10)])
        g.add_node("n2")
        g.add_edge(("n1", "n2"), label="CONFLICT", attrs=[("color", '"red"')])
        g.add_edge(("n2", "n1"))

        dot_str = write_dot(g)
        lines = dot_str.splitlines()
        self.assertEqual(lines[0], "digraph g {")
        self.assertEqual(lines[-1], "}")
        self.assertIn('n1 [label="foo-1.0", fontsize="10"];', lines)
        self.assertIn("n2 ;", lines)
        self.assertIn('n1 -> n2 [color="red", label="CONFLICT"];', lines)
        self.assertIn("n2 -> n1 ;", lines)


class TestPruneGraph(TestBase):
    def test_prune_graph_keeps_upstream_nodes(self) -> None:
        dot_str = (
            'digraph g {\n'
            '    _1 [label="foo-1"];\n'
            '    _2 [label="bar-1.0[]"];\n'
            '    _3 [label="baz-2.0[]"];\n'
            '    _4 [label="qux-1.0[]"];\n'
            '    _1 -> _2;\n'
            '    _2 -> _3;\n'
            '    _3 -> _4;\n'
            '}\n'
        )
        pruned = prune_graph(dot_str, "bar")
        g = read_graph_from_string(pruned)
        self.assertEqual(set(g.nodes()), {"_1", "_2"})
        self.assertEqual(g.edges(), [("_1", "_2")])

    def test_prune_graph_skips_unlabeled_and_invalid_request_nodes(self) -> None:
        dot_str = (
            'digraph g {\n'
            '    _1;\n'
            '    _2 [label="not a valid request"];\n'
            '    _3 [label="foo-1.0[]"];\n'
            '    _4 [label="bar-1.0[]"];\n'
            '    _1 -> _3;\n'
            '    _3 -> _4;\n'
            '}\n'
        )
        pruned = prune_graph(dot_str, "foo")
        g = read_graph_from_string(pruned)
        self.assertEqual(set(g.nodes()), {"_1", "_3"})

    def test_prune_graph_missing_package_raises(self) -> None:
        dot_str = (
            'digraph g {\n'
            '    _1 [label="foo-1.0[]"];\n'
            '}\n'
        )
        with self.assertRaises(ValueError) as cm:
            prune_graph(dot_str, "missing_pkg")
        self.assertIn("missing_pkg", str(cm.exception))


class TestSaveGraph(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_save_graph_no_graph_raises(self) -> None:
        with patch("rez.utils.graph_utils.pydot.graph_from_dot_data", return_value=[]):
            with self.assertRaises(RuntimeError) as cm:
                save_graph("invalid", os.path.join(self.root, "out.png"))
        self.assertIn("No graph generated", str(cm.exception))

    def test_save_graph_multiple_graphs_raises(self) -> None:
        dot_str = "digraph a { 1 -> 2; } digraph b { 3 -> 4; }"
        out_path = os.path.join(self.root, "multi.png")

        with patch(
            "rez.utils.graph_utils.save_graph_object",
            side_effect=["png", RuntimeError("write failed")],
        ) as mock_save:
            with self.assertRaises(RuntimeError) as cm:
                save_graph(dot_str, out_path, fmt="png", image_ratio=1.2)

        self.assertEqual(mock_save.call_count, 2)
        self.assertIn("More than one graph was generated", str(cm.exception))
        self.assertIn("multi.1.png", str(cm.exception))
        self.assertNotIn("multi.2.png", str(cm.exception))

    def test_save_graph_single_graph(self) -> None:
        dot_str = "digraph g { a -> b; }"
        out_path = os.path.join(self.root, "single.png")
        with patch("rez.utils.graph_utils.save_graph_object", return_value="png") as mock_save:
            fmt = save_graph(dot_str, out_path, fmt="png", image_ratio=2.0)

        self.assertEqual(fmt, "png")
        mock_save.assert_called_once()
        args = mock_save.call_args[0]
        self.assertEqual(args[1:], (out_path, "png", 2.0))

    def test_save_graph_object_infers_format_from_extension(self) -> None:
        g = MagicMock()
        out_path = os.path.join(self.root, "graph.SVG")
        fmt = save_graph_object(g, out_path)

        self.assertEqual(fmt, "svg")
        g.write_svg.assert_called_once_with(out_path)
        g.set_ratio.assert_not_called()

    def test_save_graph_object_defaults_to_png_without_extension(self) -> None:
        g = MagicMock()
        out_path = os.path.join(self.root, "graph_no_ext")
        fmt = save_graph_object(g, out_path)

        self.assertEqual(fmt, "png")
        g.write_png.assert_called_once_with(out_path)

    def test_save_graph_object_sets_image_ratio(self) -> None:
        g = MagicMock()
        out_path = os.path.join(self.root, "ratio.png")
        fmt = save_graph_object(g, out_path, fmt="png", image_ratio=1.5)

        self.assertEqual(fmt, "png")
        g.set_ratio.assert_called_once_with("1.5")
        g.write_png.assert_called_once_with(out_path)

    def test_save_graph_object_unsupported_format_raises(self) -> None:
        g = MagicMock(spec=[])
        with self.assertRaises(RuntimeError) as cm:
            save_graph_object(g, os.path.join(self.root, "out.xyz"), fmt="xyz")
        self.assertIn("Unsupported graph format: 'xyz'", str(cm.exception))


class TestViewAndWriteGraph(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_write_graph_with_explicit_dest_file(self) -> None:
        dest = os.path.join(self.root, "explicit.png")
        with patch("rez.utils.graph_utils.save_graph") as mock_save:
            result = _write_graph("digraph g {}", dest_file=dest)

        self.assertEqual(result, dest)
        mock_save.assert_called_once_with("digraph g {}", dest)

    def test_write_graph_creates_temp_file(self) -> None:
        self.update_settings({"dot_image_format": "svg"})
        with patch("rez.utils.graph_utils.save_graph") as mock_save:
            result = _write_graph("digraph g {}")

        try:
            self.assertTrue(os.path.basename(result).startswith("resolve-dot-"))
            self.assertTrue(result.endswith(".svg"))
            self.assertTrue(os.path.exists(result))
            mock_save.assert_called_once_with("digraph g {}", result)
        finally:
            if os.path.exists(result):
                os.remove(result)

    def test_view_graph_linux_without_display_exits(self) -> None:
        stderr = io.StringIO()
        with restore_os_environ():
            os.environ.pop("DISPLAY", None)
            with patch("rez.system.system.platform", "linux"), patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as cm:
                    view_graph("digraph g {}")

        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Unable to open display.", stderr.getvalue())

    def test_view_graph_with_image_viewer_success(self) -> None:
        self.update_settings({"image_viewer": "fake-viewer"})

        proc = MagicMock()
        proc.returncode = 0
        proc.__enter__.return_value = proc
        proc.__exit__.return_value = False

        with restore_os_environ():
            os.environ["DISPLAY"] = ":0"
            with patch(
                "rez.utils.graph_utils._write_graph", return_value="/tmp/graph.png"
            ), patch(
                "rez.utils.graph_utils.Popen", return_value=proc
            ) as mock_popen, patch("webbrowser.open_new") as mock_browser:
                view_graph("digraph g {}")

        mock_popen.assert_called_once_with(["fake-viewer", "/tmp/graph.png"])
        proc.wait.assert_called_once_with()
        mock_browser.assert_not_called()

    def test_view_graph_with_image_viewer_failure_falls_back_to_browser(self) -> None:
        self.update_settings({"image_viewer": "fake-viewer"})

        proc = MagicMock()
        proc.returncode = 1
        proc.__enter__.return_value = proc
        proc.__exit__.return_value = False

        with restore_os_environ():
            os.environ["DISPLAY"] = ":0"
            with patch(
                "rez.utils.graph_utils._write_graph", return_value="/tmp/graph.png"
            ), patch("rez.utils.graph_utils.Popen", return_value=proc), patch(
                "webbrowser.open_new"
            ) as mock_browser:
                view_graph("digraph g {}")

        mock_browser.assert_called_once_with("file:///tmp/graph.png")

    def test_view_graph_without_image_viewer_opens_browser(self) -> None:
        self.update_settings({"image_viewer": ""})

        with restore_os_environ():
            os.environ["DISPLAY"] = ":0"
            with patch(
                "rez.utils.graph_utils._write_graph", return_value="/tmp/graph.png"
            ), patch("rez.utils.graph_utils.Popen") as mock_popen, patch(
                "webbrowser.open_new"
            ) as mock_browser:
                view_graph("digraph g {}")

        mock_popen.assert_not_called()
        mock_browser.assert_called_once_with("file:///tmp/graph.png")


class TestRequestFromLabel(TestBase):
    def test_request_from_label(self) -> None:
        self.assertEqual(_request_from_label('"PyQt-4.8.0[1]"'), "PyQt-4.8.0")
        self.assertEqual(_request_from_label("'foo-1.0[]'"), "foo-1.0")
        self.assertEqual(_request_from_label("bar>=2"), "bar>=2")


if __name__ == "__main__":
    unittest.main()
