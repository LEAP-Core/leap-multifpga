#TaggedUnion union::UnionTest1 {members {{void YesEmpty {width 0}} {Bool NotEmpty {width 1}} {Bit#(32) Value {width 32}}}} {width 34} {position {union.bsv 7 3}}
class Member():
    def __init__(self, type, name, width, index):
        self.type = type
        self.name = name
        self.width = width 
        self.index = index

    def getTypeRefs(self):
        return [self.getTypeRefs()] 

    def __repr__(self):
        return "{" + str(self.type) + " " + self.name +" {width "+str(self.width)+"} "+str(self.index)+" }"


class PolyMember():
    def __init__(self, type, name, index):
        self.type = type
        self.name = name
        self.index = index

    def getTypeRefs(self):
        return []

    def __repr__(self):
        return "{" + str(self.type) + " " + self.name +" "+str(self.index)+" }"
