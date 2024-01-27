# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'utils.resolve_graph' module
"""
from rez.tests.util import TestBase
from rez.utils import resolve_graph
import rez.utils.graph_utils
import unittest


class TestResolveGraph(TestBase):
    def test_conflict_graph_with_cycle(self):
        """ Tests creating a test digraph which contains a cycle foo-1.0.0 => bar-0.0.1 => !foo-1.0.0
            Note that the solver doesn't detect this as a cycle. See #1568
        """

        g = '''
        digraph g {
            _1 [label="foo-1", fontsize="10", fillcolor="#FFFFAA", style="filled,dashed"];
            _2 [label="bar", fontsize="10", fillcolor="#FFFFAA", style="filled,dashed"];
            _6 [label="foo-1.0.0[]", fontsize="10", fillcolor="#AAFFAA", style="filled"];
            _7 [label="bar-0.0.1[]", fontsize="10", fillcolor="#AAFFAA", style="filled"];
            _8 [label="!foo-1.0.0", fontsize="10", fillcolor="#F6F6F6", style="filled,dashed"];
            _1 -> _6 [arrowsize="0.5"];
            _2 -> _7 [arrowsize="0.5"];
            _6 -> _2 [arrowsize="0.5"];
            _7 -> _8 [arrowsize="0.5"];
            _8 -> _6 [arrowsize="1", style="bold", color="red", fontcolor="red", label=CONFLICT];
        }
        '''
        graph = rez.utils.graph_utils.read_graph_from_string(g)
        # strip extra quoting from fill color
        for k, v in graph.node_attr.items():
            for index, a in enumerate(v):
                if a[0] == "fillcolor":
                    stripped_color = a[1].strip("'").strip('"')
                    v[index] = ("fillcolor", stripped_color)

        # attempt to graph result
        result = resolve_graph.failure_detail_from_graph(graph)
        self.assertTrue("foo-1 --> foo-1.0.0 --> bar-0.0.1 --> !foo-1.0.0" in result)
        self.assertTrue("bar --> bar-0.0.1 --> !foo-1.0.0" in result)


if __name__ == '__main__':
    unittest.main()
