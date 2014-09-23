__author__ = 'federicon'
__docformat__ = 'epytext'

import datetime
import getpass
import logging


logger = logging.getLogger(__name__)


class Replacer(object):

    def __init__(self, launcher_service):

        self.launcher_service = launcher_service
        self.now = datetime.datetime.now()
        self.username = getpass.getuser()

    def replace(self, newReference, destination, description ):

        references = self.launcher_service.get_references_from_path(destination, self.username)

        for reference in references:
            referencePath = self.launcher_service.get_preset_full_path(reference.get_preset_id_as_dict(), None)
            logger.info('Removing reference %s from %s' % (referencePath, destination))
            self.launcher_service.remove_reference_from_path(destination, referencePath, self.username, description)

        logger.info('Adding %s reference to %s' % (newReference, destination))
        self.launcher_service.add_reference_to_preset_path(destination, newReference, self.username, description)

