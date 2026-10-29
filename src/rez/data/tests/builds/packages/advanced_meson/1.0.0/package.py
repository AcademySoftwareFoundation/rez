name = "advanced_meson"

version = "1.0.0"

authors = ["John Doe"]

description = "A project that says something."

uuid = "9a2eeb8b-26bc-4fe8-9c4b-faeddf075c1f"

tools = ["say"]

variants = [
   ["hello_lib_meson-1.0"],
   ["hello_lib_meson-1.1"],
]

def commands() -> None:
    env.PATH.append("{root}/bin")
