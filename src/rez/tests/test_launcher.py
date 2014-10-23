from rez.contrib.animallogic.launcher.tests.test_setting import TestSetting
from rez.contrib.animallogic.launcher.tests.test_settingtype import TestSettingType
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService_GetSettings
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService_CreatePreset
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService_AddSettingToPreset
from rez.contrib.animallogic.launcher.tests.test_operatingsystem import TestOperatingSystem
from rez.contrib.animallogic.launcher.tests.test_baker import TestBaker, TestBakerCLI
from rez.contrib.animallogic.launcher.tests.test_syncer import TestSyncer

import rez.vendor.unittest2 as unittest


def get_test_suites():

    suites = []
    tests = [TestSetting,
             TestSettingType,
             TestOperatingSystem,
             TestLauncherHessianService_GetSettings,
             TestLauncherHessianService_CreatePreset,
             TestLauncherHessianService_AddSettingToPreset,
             TestBaker,
             TestBakerCLI,
             TestSyncer]

    for test in tests:

        suites.append(unittest.TestLoader().loadTestsFromTestCase(test))

    return suites

if __name__ == '__main__':
    unittest.main()
