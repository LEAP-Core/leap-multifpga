import sys
import re
from type import *


class Struct(CompoundType):
  
    def __init__(self, type, members, width):
        self.members = members
        self.width = width
        self.type = type 

    def getTypeRefs(self):
        print "ref struct " + str(self)
        return type.getTypeRefs() + map(lambda m: m.getTypeRefs(), self.members)
        
    def __repr__(self):
        representation = "Struct " + str(self.type) + " {members {"
        representation += " ".join(map(lambda a: str(a), self.members))
        representation += "}} {width " + str(self.width) + "}"
        return representation

    def __eq__(self,other):
        # We can strip out the reference, but if it exists we should check it
        equal = False
        if(isinstance(other,PolyType)):
            #poly types subsume everything
            return True
        elif(isinstance(other, PolyStruct) or isinstance(other, Struct)):
            equal = (self.type == other.type) and (len(self.members) == len(other.members))
            if(equal):
                for idx in range(len(self.members)):
                    equal = equal and (self.members[idx] == other.members[idx])

        return equal       

class PolyStruct(CompoundType):
  
    def __init__(self, type, members):
        self.members = members
        self.type = type 

    def getTypeRefs(self):
        print "ref PolyStruct " + str(self)
        return map(lambda m: m.getTypeRefs(),self.members)
        
    def __repr__(self):
        representation = "Struct {" + str(self.type) + "} polymorphic {members {"
        representation += " ".join(map(lambda a: str(a), self.members))
        representation += "}} "
        return representation

    def __eq__(self,other):
        # We can strip out the reference, but if it exists we should check it
        equal = False
        if(isinstance(other,PolyType)):
            #poly types subsume everything
            return True
        elif(isinstance(other, PolyStruct) or isinstance(other, Struct)):
            equal = (self.type == other.type) and (len(self.members) == len(other.members))
            if(equal):
                for idx in range(len(self.members)):
                    equal = equal and (self.members[idx] == other.members[idx])

        return equal       



      
