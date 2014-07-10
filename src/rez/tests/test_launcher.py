from rez.contrib.animallogic.launcher.tests.test_setting import TestSetting
from rez.contrib.animallogic.launcher.tests.test_settingtype import TestSettingType
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService
from rez.contrib.animallogic.launcher.tests.test_operatingsystem import TestOperatingSystem
from rez.contrib.animallogic.launcher.tests.test_baker import TestBaker

import rez.vendor.unittest2 as unittest

def get_test_suites():

    suites = []
    tests = [TestSetting, TestSettingType, TestLauncherHessianService, TestOperatingSystem, TestBaker]

    for test in tests:
        suites.append(unittest.TestLoader().loadTestsFromTestCase(test))

    return suites

if __name__ == '__main__':
    unittest.main()
