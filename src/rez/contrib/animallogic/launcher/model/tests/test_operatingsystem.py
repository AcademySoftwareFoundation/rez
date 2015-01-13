from rez.contrib.animallogic.launcher.model.operatingsystem import OperatingSystem
import rez.vendor.unittest2 as unittest
import platform

class TestOperatingSystem(unittest.TestCase):

    def test_get_current_operating_system(self):

        if platform.system().lower() != "linux":
            self.skipTest("This test does not run on Windows or OSX.")

        os = OperatingSystem.get_current_operating_system()
        expected = OperatingSystem.linux

        self.assertEqual(expected, os)
