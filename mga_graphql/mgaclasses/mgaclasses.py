from graphene import ObjectType, ID, String, List


class MgaObject(ObjectType):
    # class Meta:
    #     abstract = True

    id = ID()
    name = String()


class MgaFco(MgaObject):
    pass


class MgaModel(MgaFco):
    children = List(MgaFco)

    def resolve_children(self, info):
        if self.children:
            return [info.context['data'][str(i)] for i in self.children]
        else:
            return None


class MgaAtom(MgaFco):
    pass


class MgaReference(MgaFco):
    pass


class MgaSet(MgaFco):
    pass


class MgaConnection(MgaFco):
    pass


class MgaFolder(MgaObject):
    children = List(MgaObject)

    def resolve_children(self, info):
        if self.children:
            return [info.context['data'][i] for i in self.children]
        else:
            return None
