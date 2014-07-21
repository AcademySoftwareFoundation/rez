class Preset(object):

    def __init__(self, path):

        self.name = path.rsplit('/', 1)[-1]
        self.path = path
        self.description = ''
        self.id = None
        self.parent_id = None

    def get_parent_path(self):

        return self.path.rsplit('/', 1)[0]
