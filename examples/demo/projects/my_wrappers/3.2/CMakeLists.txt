CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(RezInstallWrappers)

# This wrapper creates an environment containing translated_hello_world, and version 2.0.0
# of the translate lib. It exposes the test executable in translated_hello_world as 'hey_old'.
rez_install_wrappers (
	wrapper1
	wrapper1.context
	oldhey
	PACKAGES translated_hello_world translate_lib-2.0.0
	WRAPPERS hey_old:test_translated_hello_world
	DESTINATION .
)

# This wrapper is similar to the previous one, except that it does not lock down to the
# earlier translate lib patch.
rez_install_wrappers (
	wrapper2
	wrapper2.context
	newhey
	PACKAGES translated_hello_world
	WRAPPERS hey_new:test_translated_hello_world
	DESTINATION .
)
