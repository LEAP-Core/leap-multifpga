import sys
import re
from type import *

class PolyTaggedUnion(Type):
  
    def __init__(self, type, members):
        self.members = members
        self.type = type 

    def getTypeRefs(self):
        return map(lambda m: m.getTypeRefs(),members)

    def __repr__(self):
        representation = "TaggedUnion {" + str(self.type) + "} polymorphic {members {"
        representation += " ".join(map(lambda a: str(a), self.members))
        representation += "}} "
        return representation


class TaggedUnion(Type):
  
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
        return type.getTypeRefs() + map(lambda m: m.getTypeRefs(),members)

    def __repr__(self):
        representation = "TaggedUnion " + str(self.type) + " {members {"
        representation += " ".join(map(lambda a: str(a), self.members))
        representation += "}} {width " + str(self.width) + "}"
        return representation

      
