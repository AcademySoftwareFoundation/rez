from rez.contrib.animallogic.launcher.tests.test_replace import TestReplace
from rez.contrib.animallogic.launcher.tests.test_setting import TestSetting
from rez.contrib.animallogic.launcher.tests.test_settingtype import TestSettingType
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService_GetSettings
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService_AddReferenceToPreset
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService_RemoveReferenceToPreset
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService_GetReferenceFromPreset
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService_GetPresetFullPath
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService_CreatePreset
from rez.contrib.animallogic.launcher.tests.test_service import TestLauncherHessianService_AddSettingToPreset
from rez.contrib.animallogic.launcher.tests.test_operatingsystem import TestOperatingSystem
from rez.contrib.animallogic.launcher.tests.test_baker import TestBaker, TestBakerCLI

import rez.vendor.unittest2 as unittest


def get_test_suites():
    suites = []

    tests = [TestSetting, TestSettingType, TestOperatingSystem, TestLauncherHessianService_GetSettings,
             TestLauncherHessianService_CreatePreset,
             TestLauncherHessianService_AddSettingToPreset, TestBaker, TestBakerCLI, TestReplace,
             TestLauncherHessianService_AddReferenceToPreset,
             TestLauncherHessianService_RemoveReferenceToPreset,
             TestLauncherHessianService_GetReferenceFromPreset,
             TestLauncherHessianService_GetPresetFullPath]

    for test in tests:
        suites.append(unittest.TestLoader().loadTestsFromTestCase(test))

    return suites

if __name__ == '__main__':
    unittest.main()
