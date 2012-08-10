import sys
import re
from type import *

class PolyTaggedUnion(CompoundType):
  
    def __init__(self, type, members):
        self.members = members
        self.type = type 

    def getTypeRefs(self):
        print "ref PolyTaggedUnion " + str(self)
        return map(lambda m: m.getTypeRefs(), self.members)

    def __repr__(self):
        representation = "TaggedUnion {" + str(self.type) + "} polymorphic {members {"
        representation += " ".join(map(lambda a: str(a), self.members))
        representation += "}} "
        return representation

    def __eq__(self,other):
        # We can strip out the reference, but if it exists we should check it
        equal = False
        if(isinstance(other,PolyType)):
            #poly types subsume everything
            return True
        if(isinstance(other, PolyTaggedUnion) or isinstance(other, TaggedUnion)):
            equal = (self.type == other.type) and (len(self.members) == len(other.members))
            if(equal):
                for idx in range(len(self.members)):
                    equal = equal and (self.members[idx] == other.members[idx])

        return equal       

class TaggedUnion(CompoundType):
  
    def __init__(self, type, members, width):
        self.members = members
        self.width = width
        self.type = type 
        self.payloadwidth = 0
        if(len(self.members) > 0):
            self.payloadwidth = max(map(lambda member: member.width, self.members))
            print "Payload: " + str(self.payloadwidth) + "\n"
        self.tagwidth = self.width - self.payloadwidth

    def getTypeRefs(self):
        print "ref TaggedUnion " + str(self)
        return type.getTypeRefs() + map(lambda m: m.getTypeRefs(), self.members)

    def __repr__(self):
        representation = "TaggedUnion " + str(self.type) + " {members {"
        representation += " ".join(map(lambda a: str(a), self.members))
        representation += "}} {width " + str(self.width) + "}"
        return representation

    def __eq__(self,other):
        # We can strip out the reference, but if it exists we should check it
        equal = False
        if(isinstance(other,PolyType)):
            #poly types subsume everything
            return True
        if(isinstance(other, PolyTaggedUnion) or isinstance(other, TaggedUnion)):
            equal = (self.type == other.type) and (len(self.members) == len(other.members))
            if(equal):
                for idx in range(len(self.members)):
                    equal = equal and (self.members[idx] == other.members[idx])

        return equal       
