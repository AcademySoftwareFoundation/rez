from rez.rex import RexExecutor, Python, Setenv, Appendenv, Prependenv, Info, \
    Comment, Alias, Command, Source, Error, Shebang, Unsetenv
import unittest
import os



def rex_code():
    # setting env vars
    env.FOO = "foo"
    setenv("BAH", "bah")

    # appending env vars - first reference will overwrite
    appendenv("EEK", "test1")
    env.EEK.append("test2")
    env.EEK.append("test3")

    # prepending env vars - first reference will overwrite
    env.DUDE.prepend("A")
    prependenv("DUDE", "B")
    if getenv("DUDE").split(os.pathsep) == ["B","A"]:
        env.DUDE_VALID=1
    unsetenv("DUDE")

    # flow control using internally-set env vars
    if env.FOO == "foo":
        env.FOO_VALID = 1
        info("FOO validated")

    # flow control using external env-vars
    if defined("EXT") and env.EXT == "alpha":
        env.EXT_FOUND = "1"

        # this will still overwrite on first ref!
        env.EXT.append("beta")



class TestRex(unittest.TestCase):
    def _create_executor(self, **kwargs):
        interp = Python(target_environ={}, passive=True)
        return RexExecutor(interpreter=interp,
                           bind_syspaths=False,
                           bind_rez=False,
                           shebang=False,
                           **kwargs)

    def test_1(self):
        """Test simple use of every available action."""
        def _rex():
            shebang()
            setenv("FOO", "foo")
            setenv("BAH", "bah")
            unsetenv("BAH")
            unsetenv("NOTEXIST")
            prependenv("A", "/tmp")
            prependenv("A", "/data")
            appendenv("B", "/tmp")
            appendenv("B", "/data")
            alias("thing", "thang")
            info("that's interesting")
            error("oh noes")
            command("runme --with --args")
            source("./script.src")

        ex = self._create_executor(parent_environ={})
        ex.execute_function(_rex)

        expected_actions = [Shebang(),
                            Setenv('FOO', 'foo'),
                            Setenv('BAH', 'bah'),
                            Unsetenv('BAH'),
                            Unsetenv('NOTEXIST'),
                            Setenv('A', '/tmp'),
                            Prependenv('A', '/data'),
                            Setenv('B', '/tmp'),
                            Appendenv('B', '/data'),
                            Alias('thing', 'thang'),
                            Info("that's interesting"),
                            Error('oh noes'),
                            Command('runme --with --args'),
                            Source('./script.src')]

        aval = os.pathsep.join(["/data","/tmp"])
        bval = os.pathsep.join(["/tmp","/data"])
        expected_output = {'FOO': 'foo',
                           'A': aval,
                           'B': bval}

        self.assertEqual(ex.actions, expected_actions)
        self.assertEqual(ex.get_output(), expected_output)

    def test_2(self):
        """Test simple setenvs and assignments."""
        def _rex():
            env.FOO = "foo"
            setenv("BAH", "bah")
            env.EEK = env.FOO

        ex = self._create_executor(parent_environ={})
        ex.execute_function(_rex)

        expected_actions = [Setenv('FOO', 'foo'),
                            Setenv('BAH', 'bah'),
                            Setenv('EEK', 'foo')]
        expected_output = {'FOO': 'foo',
                           'EEK': 'foo',
                           'BAH': 'bah'}

        self.assertEqual(ex.actions, expected_actions)
        self.assertEqual(ex.get_output(), expected_output)

    def test_3(self):
        """Test appending/prepending."""
        def _rex():
            appendenv("FOO", "test1")
            env.FOO.append("test2")
            env.FOO.append("test3")

            env.BAH.prepend("A")
            prependenv("BAH", "B")
            env.BAH.append("C")

        # no parent variables enabled
        ex = self._create_executor(parent_environ={})
        ex.execute_function(_rex)

        expected_actions = [Setenv('FOO', 'test1'),
                            Appendenv('FOO', 'test2'),
                            Appendenv('FOO', 'test3'),
                            Setenv('BAH', 'A'),
                            Prependenv('BAH', 'B'),
                            Appendenv('BAH', 'C')]

        fooval = os.pathsep.join(["test1","test2","test3"])
        bahval = os.pathsep.join(["B","A","C"])
        expected_output = {'FOO': fooval,
                           'BAH': bahval}

        self.assertEqual(ex.actions, expected_actions)
        self.assertEqual(ex.get_output(), expected_output)

        # FOO and BAH enabled as parent variables, but not present
        ex = self._create_executor(parent_environ={},
                                   parent_variables=["FOO","BAH"])
        ex.execute_function(_rex)

        expected_actions = [Appendenv('FOO', 'test1'),
                            Appendenv('FOO', 'test2'),
                            Appendenv('FOO', 'test3'),
                            Prependenv('BAH', 'A'),
                            Prependenv('BAH', 'B'),
                            Appendenv('BAH', 'C')]

        fooval = os.pathsep.join(["","test1","test2","test3"])
        bahval = os.pathsep.join(["B","A","","C"])
        expected_output = {'FOO': fooval,
                           'BAH': bahval}

        self.assertEqual(ex.actions, expected_actions)
        self.assertEqual(ex.get_output(), expected_output)

        # FOO and BAH enabled as parent variables, and present
        ex = self._create_executor(parent_environ={"FOO": "tmp",
                                                   "BAH": "Z"},
                                   parent_variables=["FOO","BAH"])
        ex.execute_function(_rex)

        fooval = os.pathsep.join(["tmp","test1","test2","test3"])
        bahval = os.pathsep.join(["B","A","Z","C"])
        expected_output = {'FOO': fooval,
                           'BAH': bahval}

        self.assertEqual(ex.actions, expected_actions)
        self.assertEqual(ex.get_output(), expected_output)

    def test_4(self):
        """Test control flow using internally-set env vars."""
        def _rex():
            env.FOO = "foo"
            setenv("BAH", "bah")
            env.EEK = "foo"

            if env.FOO == "foo":
                env.FOO_VALID = 1
                info("FOO validated")

            if env.FOO == env.EEK:
                comment("comparison ok")

        ex = self._create_executor(parent_environ={})
        ex.execute_function(_rex)

        expected_actions = [Setenv('FOO', 'foo'),
                            Setenv('BAH', 'bah'),
                            Setenv('EEK', 'foo'),
                            Setenv('FOO_VALID', '1'),
                            Info('FOO validated'),
                            Comment('comparison ok')]
        expected_output = {'FOO': 'foo',
                           'BAH': 'bah',
                           'EEK': 'foo',
                           'FOO_VALID': '1'}

        self.assertEqual(ex.actions, expected_actions)
        self.assertEqual(ex.get_output(), expected_output)

    def test_5(self):
        """Test control flow using externally-set env vars."""
        def _rex():
            if defined("EXT") and env.EXT == "alpha":
                env.EXT_FOUND = 1
                env.EXT.append("beta")  # will still overwrite
            else:
                env.EXT_FOUND = 0
                if undefined("EXT"):
                    info("undefined working as expected")

        # EXT undefined
        ex = self._create_executor(parent_environ={})
        ex.execute_function(_rex)

        expected_actions = [Setenv('EXT_FOUND', '0'),
                            Info("undefined working as expected")]
        expected_output = {'EXT_FOUND': '0'}

        self.assertEqual(ex.actions, expected_actions)
        self.assertEqual(ex.get_output(), expected_output)

        # EXT defined
        ex = self._create_executor(parent_environ={"EXT": "alpha"})
        ex.execute_function(_rex)

        expected_actions = [Setenv('EXT_FOUND', '1'),
                            Setenv('EXT', 'beta')]
        expected_output = {'EXT_FOUND': '1',
                           'EXT': 'beta'}

        self.assertEqual(ex.actions, expected_actions)
        self.assertEqual(ex.get_output(), expected_output)



        for a in ex.actions:
            print str(a)

        print
        print ex.get_output()



def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestRex("test_1"))
    suite.addTest(TestRex("test_2"))
    suite.addTest(TestRex("test_3"))
    suite.addTest(TestRex("test_4"))
    suite.addTest(TestRex("test_5"))
    suites.append(suite)
    return suites
