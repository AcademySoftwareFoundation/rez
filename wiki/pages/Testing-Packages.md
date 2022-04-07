As mentioned in other pages such as [tests](Package-Definition-Guide#tests),
you can specify tests to run like this:

	]$ rez-test maya_utils lint unittest

This test would run two tests, "lint" and "unittest", from a Rez package called
"maya_utils". When that happens, the pre-defined commands for "lint" and
"unittest" will run. However if you to "rez-env" into those test environments,
you can do that using the *--interactive* flag.

	]$ rez-test maya_utils --interactive lint
	]$ rez-test maya_utils --interactive unittest

In the example commands above, a "rez-env" is auto-generated to combine
"maya_utils" and "lint" / "maya_utils" and "unittest" into two, separate
environments.

Note that you cannot call *--interactive* on more than one Rez test at a time.

The resulting environment is exactly what Rez sees, just before a test
"command" gets run.
