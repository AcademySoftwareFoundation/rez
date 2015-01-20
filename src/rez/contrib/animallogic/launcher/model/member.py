__docformat__ = 'epytext'

from rez.contrib.animallogic.launcher.util import DefaultFormatter


class Member(object):

    def __init__(self, id_, parent_id, name, created_by, created_on):
        super(Member, self).__init__()

        self.id = id_
        self.parent_id = parent_id
        self.name = name
        self.created_by = created_by
        self.created_on = created_on

        self._parent = None
        self._service = None

    def set_service(self, service):
        self._service = service

    def format(self, specification):
        formatter = DefaultFormatter()

        return formatter.format(specification, type=self.getMemberTypeShortIdentifier(),
                                        path=self.path,
                                        **self.__dict__)

    def getMemberTypeShortIdentifier(self):
        raise NotImplementedError

    @property
    def path(self):
        tokens = [self.name]
        parent = self.parent

        while parent is not None:
            tokens.append(parent.name)
            parent = parent.parent

        return "/presets/" + "/".join(reversed(tokens))

    def get_path_relative_to_root(self, root):
        if root.id == self.id:
            return "."

        tokens = [self.name]
        parent = self.parent

        while parent is not None:
            if parent.id == root.id:
                tokens.append(".")
                break

            tokens.append(parent.name)
            parent = parent.parent

        return "/".join(reversed(tokens))

    @property
    def parent(self):
        if self._parent or self.parent_id is None:
            return self._parent

        self._parent = self._service.get_preset_group_from_id(self.parent_id)
        return self._parent

    @parent.setter
    def parent(self, parent):
        self._parent = parent

    def get_children(self, date, recursive=False):
        children = []

        for child in self._service.get_preset_group_children(self, date):
            child.parent = self
            children.append(child)

        if recursive:
            for child in children:
                children.extend(child.get_children(date, recursive=recursive))

        return children

