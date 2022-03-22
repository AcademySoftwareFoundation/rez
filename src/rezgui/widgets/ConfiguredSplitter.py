# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


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
