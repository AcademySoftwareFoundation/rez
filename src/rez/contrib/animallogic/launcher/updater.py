__author__ = 'federicon'
__docformat__ = 'epytext'

import datetime
import getpass
import logging


logger = logging.getLogger(__name__)


class Updater(object):

    def __init__(self, launcher_service):

        self.launcher_service = launcher_service
        self.now = datetime.datetime.now()
        self.username = getpass.getuser()

    def update(self, target, description, remove_all_references=False, references_to_add=None, settings_to_add=None):
        if references_to_add is None:
            references_to_add = []

        if settings_to_add is None:
            settings_to_add = []

        if remove_all_references:
            references = self.launcher_service.get_references_from_path(target)

            for reference in references:
                referencePath = self.launcher_service.get_preset_full_path(reference.preset_id, None)
                logger.info('Removing reference %s from %s' % (referencePath, target))
                self.launcher_service.remove_reference_from_path(target, referencePath, self.username, description)

        for reference in references_to_add:
            logger.info('Adding %s reference to %s' % (reference, target))
            self.launcher_service.add_reference_to_preset_path(target, reference, self.username, description)

        for setting in settings_to_add:
            logger.info("Adding %s" % setting)
            self.launcher_service.add_setting_to_preset(setting, target, username=self.username)
