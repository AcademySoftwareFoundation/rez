As mentioned in other pages such as [tests](Package-Definition-Guide#tests),
you can specify Rez tests to run like this:

	]$ rez-test maya_utils lint unittest_name

This example runs two test targets, "lint" and "unittest_name", from the "maya_utils"
Rez package. Rez runs these tests one at a time, in the order you define them.

You may also "enter" any test environment, instead of running a test by
including the *--interactive* flag.

	]$ rez-test maya_utils --interactive unittest_name

Adding *--interactive* makes Rez combine the "maya_utils" Rez package and
"unittest_name" Rez test into a single environment, just like how `rez-env` works.

Note that *--interactive* can only target one Rez test at a time.
