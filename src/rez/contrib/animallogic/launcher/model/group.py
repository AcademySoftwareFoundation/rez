from rez.contrib.animallogic.launcher.model.member import Member

class Group(Member):
    def __init__(self, id_, parent_id, name, created_by, created_on):
        super(Group, self).__init__(id_, parent_id, name, created_by,
                                    created_on)

    def getMemberTypeIdentifier(self):
        return "g"

    def __repr__(self):
        return "<Group name=%s, id=%s>" % (self.name, self.id)
