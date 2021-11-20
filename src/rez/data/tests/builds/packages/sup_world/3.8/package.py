name = 'sup_world'
version = '3.8'
authors = ["someone"]
uuid = "040c80c135c142479d47e756bdbbddf5"
description = "A C++ executable that links to a library that is part of this " \
              "package, and a library from a different package"

requires = ['translate_lib-2.2']

tools = ['greeter']

def commands():
    env.PATH.append('{root}/bin')
