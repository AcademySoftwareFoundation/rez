from rez.utils._version import _rez_version
import logging.config
import os


__version__ = _rez_version
__author__ = "Allan Johns"
__license__ = "LGPL"

module_root_path = __path__[0]

logging_conf_file = os.environ.get(
    'REZ_LOGGING_CONF',
    os.path.join(module_root_path, 'utils', 'logging.conf'))
logging.config.fileConfig(logging_conf_file, disable_existing_loggers=False)


# Copyright 2016 Allan Johns.
# 
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
