from rez.contrib.animallogic.launcher.model.group import Group

class Tool(Group):
    def __init__(self, id_, parent_id, name, created_by, created_on, icon_path):
        super(Tool, self).__init__(id_, parent_id, name, created_by, created_on)

        self.icon_path = icon_path

    def getMemberTypeShortIdentifier(self):
        return "t"

    def __repr__(self):
        return "<Tool name=%s, id=%s>" % (self.name, self.id)
