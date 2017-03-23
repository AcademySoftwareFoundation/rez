
name = 'hello'
version = '1.0'
authors = ["dr.foo"]
uuid = "110c80c135c142479d47e756bdbbddf8"
description = "A very simple C++ project."

tools = ['hai']

build_command = "make -f {root}/Makefile {install}"

def commands():
    env.PATH.append('{root}/bin')
