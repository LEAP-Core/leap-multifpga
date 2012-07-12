import sys
import re
from type import *

class Struct(Type):
  
    def __init__(self, type, members, width):
        self.members = members
        self.width = width
        self.type = type 

    def getTypeRefs(self):
        return type.getTypeRefs() + map(lambda m: m.getTypeRefs(),members)
        
    def __repr__(self):
        representation = "Struct " + str(self.type) + " {members {"
        representation += " ".join(map(lambda a: str(a), self.members))
        representation += "}} {width " + str(self.width) + "}"
        return representation


class PolyStruct(Type):
  
    def __init__(self, type, members):
        self.members = members
        self.type = type 

    def getTypeRefs(self):
        return map(lambda m: m.getTypeRefs(),members)
        
    def __repr__(self):
        representation = "Struct {" + str(self.type) + "} polymorphic {members {"
        representation += " ".join(map(lambda a: str(a), self.members))
        representation += "}} "
        return representation





      
