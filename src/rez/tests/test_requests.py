"""
Test requests
"""
import unittest
from rez.tests.util import TestBase
from rez.package_repository import package_repository_manager
from rez.package_py_utils import expand_requirement
from rez.utils.request_directives import \
    parse_directive, anonymous_directive_string


class TestRequest(TestBase):

    def test_old_style_expansion(self):
        pkg_data = {
            "bar": {
                "1.2.1": {"name": "bar", "version": "1.2.1"},
                "1.2.2": {"name": "bar", "version": "1.2.2"},
                "2.2.3": {"name": "bar", "version": "2.2.3"},
            },
        }
        mem_path = "memory@%s" % hex(id(pkg_data))
        resolved_repo = package_repository_manager.get_repository(mem_path)
        resolved_repo.data = pkg_data

        def expand_on_mem(request):
            return expand_requirement(request, paths=[mem_path])

        self.assertEqual("bar-1.2+<2", expand_on_mem("bar-1.*+<*"))
        self.assertEqual("bar<2", expand_on_mem("bar<*"))
        self.assertEqual("bar<2.2.3", expand_on_mem("bar<**"))
        self.assertEqual("bar-2.2.3", expand_on_mem("bar-**"))
        self.assertEqual("bar-1.2+", expand_on_mem("bar-1.*+"))

    def test_wildcard_to_directive(self):
        requests = [
            ("foo-**", "foo//harden", None),
            ("foo==**", "foo//harden", None),
            ("foo-*", "foo//harden(1)", None),
            ("foo-1.**", "foo-1//harden", None),
            ("foo-1.0.*", "foo-1.0//harden(3)", None),
            ("foo==*", "foo//harden(1)", None),
            ("foo==1.*", "foo==1//harden(2)", None),
            ("foo-1.*+", "foo-1+//harden(2)", None),
            ("foo>1.*", "foo>1//harden(2)", None),
            ("foo>=1.*", "foo-1+//harden(2)", None),
            ("foo<**", "foo//harden", None),  # but meaningless
            # unsupported
            ("foo-2.*|1", None, "multi-rank hardening"),
            ("foo<=4,>2.*", None, "multi-rank hardening"),
            ("foo-1..2.*", None, "multi-rank hardening"),
            ("foo-1|2.*", None, "multi-rank hardening"),
            ("foo-1.*+<2.*.*", None, "multi-rank hardening"),
            ("foo-1.*+<3|==5.*.*", None, "multi-rank hardening"),
        ]

        for case, expected, message in requests:
            request = parse_directive(case)

            if expected is None:
                self.assertEqual(case, request, message)
            else:
                directive = anonymous_directive_string(request) or ""
                self.assertEqual(expected, "//".join([request, directive]), case)


if __name__ == '__main__':
    unittest.main()
