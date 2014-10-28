name = 'shelltest2'
version = '1'

def commands():
    # prepend to existing var
    setenv("VARIABLE_WITH_QUOTES", 'loadPlugin("mayaPlugin")')
    setenv("VARIABLE_ESCAPED_WITH_QUOTES", 'loadPlugin(\"mayaPlugin\")')

