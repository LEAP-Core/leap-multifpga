#import type 

#TaggedUnion union::UnionTest1 {members {{void YesEmpty {width 0}} {Bool NotEmpty {width 1}} {Bit#(32) Value {width 32}}}} {width 34} {position {union.bsv 7 3}}
class Member():
    def __init__(self, type, name, width, index):
        self.type = type
        self.name = name
        self.width = width 
        self.index = index

    def getTypeRefs(self):
        print "ref Member " + str(self)
        return [self.type.getTypeRefs()] 

    def __repr__(self):
        return "{" + str(self.type) + " " + self.name +" {width "+str(self.width)+"} "+str(self.index)+" }"

    def __eq__(self,other):
        # We can strip out the reference, but if it exists we should check it
        equal = False
        if(isinstance(other, Member) or isinstance(other, PolyMember)):
            equal = (self.name == other.name) and (self.type == other.type)
        return equal 

class PolyMember():
    def __init__(self, type, name, index):
        self.type = type
        self.name = name
        self.index = index

    def getTypeRefs(self):
        print "ref PolyMember " + str(self)
        return []

    def __repr__(self):
        return "{" + str(self.type) + " " + self.name +" "+str(self.index)+" }"

    def __eq__(self,other):
        # We can strip out the reference, but if it exists we should check it
        equal = False
        if(isinstance(other, Member) or isinstance(other, PolyMember)):
            equal = (self.name == other.name) and (self.type == other.type)
        return equal 
