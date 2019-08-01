from Qt import QtWidgets


class ConfiguredSplitter(QtWidgets.QSplitter):
    """A QSplitter that remembers its widget sizes.
    """
    def __init__(self, config, config_key, *nargs, **kwargs):
        super(ConfiguredSplitter, self).__init__(*nargs, **kwargs)
        self.config = config
        self.config_key = config_key

        self.splitterMoved.connect(self._splitterMoved)

    def apply_saved_layout(self):
        """Call this after adding your child widgets."""
        num_widgets = self.config.get(self.config_key + "/num_widgets", int)
        if num_widgets:
            sizes = []
            for i in range(num_widgets):
                key = "%s/size_%d" % (self.config_key, i)
                size = self.config.get(key, int)
                sizes.append(size)
            self.setSizes(sizes)
            return True
        return False

    def _splitterMoved(self, pos, index):
        sizes = self.sizes()
        self.config.setValue(self.config_key + "/num_widgets", len(sizes))
        for i, size in enumerate(sizes):
            key = "%s/size_%d" % (self.config_key, i)
            self.config.setValue(key, size)


# Copyright 2013-2016 Allan Johns.
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
