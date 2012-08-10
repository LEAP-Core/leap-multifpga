import sys
import re
#import struct 
#import taggedUnion 



class Type():
  
    def __init__(self, name, params):
        self.name = name
        self.params = params

    def getTypeRefs(self):
        print "ref Type " + str(self)
        return  map(lambda m: m.getTypeRefs(),self.params)

    def __repr__(self):
        representation = self.name
        if(len(self.params) > 0):
            representation += "#(" + ",".join(map(lambda a: str(a) , self.params)) + ")"
        return representation

    def __eq__(self,other):
        #is the other guy polymorphic
        equal = False
        # we aren't equal to several other kinds of types
        if(isinstance(other, CompoundType) or isinstance(other,NumericType) or isinstance(other,PolyNumericType)):
            equal = False
        elif(isinstance(other, PolyType) and len(self.params) == 0 and len(other.params)):
            equal = True
        else: #It appears to be another type?
            equal = (self.name == other.name) and len(self.params) == len(other.params)
            if(equal):
                for idx in range(len(self.params)):
                    equal = equal and (self.params[idx] == other.params[idx])
        

        print "Compare: " + str(self) + " and " +  str(other) + " -> " + str(equal)
        return equal

class CompoundType(Type):

    def __init__():
        print "Virtual Class!"


class Function(Type):
  
    def __init__(self, name, returnType, params):
        self.name = name
        self.returnType = returnType
        self.params = params

    def getTypeRefs(self):
        return  [returnType.getTypeRefs()] + map(lambda m: m.getTypeRefs(),self.params)

    def __repr__(self):
        representation = 'function ' + str(self.returnType) + ' ' + self.name
        if(len(self.params) > 0):
            representation += "(" + ",".join(map(lambda a: str(a) , self.params)) + ")"
        else:
            representation += "()"
        return representation

class NumericType(Type):
  
    def __init__(self, name):
        self.name = name

    def getTypeRefs(self):
        return []

    def __repr__(self):
        return  str(self.name)

    def __eq__(self,other):
        #is the other guy a polymorphic numeric type?
        returnVal = False
        if(isinstance(other, PolyType) or isinstance(other, PolyNumericType)):
            returnVal = True
        else:
           returnVal = (self.name == other.name) 

        print "Compare: " + str(self) + " and " +  str(other) + " -> " + str(returnVal)
        return returnVal

class PolyType(Type):
  
    def __init__(self, name):
        self.name = name

    def getTypeRefs(self):
        return []

    def __repr__(self):
        return  "{ type " + self.name + " }"

    def __eq__(self,other):
        #is the other guy a polymorphic numeric type?
        returnVal = True
        if(isinstance(other, PolyNumericType) or isinstance(other, NumericType)):
            returnVal = False

        print "Compare: " + str(self) + " and " +  str(other) + " -> " + str(returnVal)
        return returnVal

class PolyNumericType(PolyType):
  
    def __init__(self, name):
        self.name = name

    def getTypeRefs(self):
        return []

    def __repr__(self):
        return  "{numeric type " + self.name + " }"

    def __eq__(self,other):
        returnVal = False
        #is the other guy a polymorphic numeric type?
        if(isinstance(other, PolyNumericType) or isinstance(other, NumericType)):
            returnVal =  True

        print "Compare: " + str(self) + " and " +  str(other) + " -> " + str(returnVal)
        return returnVal
    

# Type ref is also a type, but it isn't composed of the base types.  it's 

class TypeRef(Type):
  
    def __init__(self, namespace, name, params):
        self.namespace = namespace
        self.name = name
        self.params = params
        self.basetype = Type("uknown",[]) # We will fill this in later...

    def ref(self):
        return self.namespace + "::" + self.name

    def getTypeRefs(self):
        print "ref TypeRef " + str(self)
        return [self] + map(lambda m: m.getTypeRefs(),self.params)

    def __repr__(self):
        representation = self.namespace + "::" + self.name
        if(len(self.params) > 0):
            representation += "#(" + ",".join(map(lambda a: str(a) , self.params)) + ")"
        return representation

    def __eq__(self,other):
        # We can strip out the reference, but if it exists we should check it
        equal = True
        if(isinstance(other, TypeRef)):
            equal = (self.namespace == other.namespace)
        returnVal = equal and (Type.__eq__(self,other)) 
        print "Compare: " + str(self) + " and " +  str(other) + " -> " + str(returnVal)
        return returnVal


class Proviso(Type):
  
    def __init__(self, name, terms):
        self.name = name
        self.terms = terms

    def getTypeRefs(self):
        return []

    def __repr__(self):
        representation = self.name
        if(len(self.terms) > 0):
            representation += "#(" + ",".join(map(lambda a: str(a) , self.terms)) + ")"
        return representation

    # Provisos don't actually have type
    def __eq__(self,other):
        return False

class TypeAlias():
  
    def __init__(self, base, alias):
        self.base= base
        self.alias = alias

    def getTypeRefs(self):
        print "ref TypeAlias " + str(self)
        return self.alias.getTypeRefs()

    def __repr__(self):
        return "Alias {" + str(self.base) +"} -> {" + str(self.alias) + "}" 

    def __eq__(self,other):
        #is the other guy polymorphic
        returnVal = (self.base == other) or (self.alias == other)
        print "Compare: " + str(self) + " and " +  str(other) + " -> " + str(returnVal)
        return returnVal

class TypeFunction(Type):
  
    def __init__(self, name, terms):
        self.name = name
        self.terms = terms

    def getTypeRefs(self):
        return []

    def __repr__(self):
        representation = self.name
        if(len(self.terms) > 0):
            representation += "#(" + ",".join(map(lambda a: str(a) , self.terms)) + ")"
        return representation

    # Let's claim for now that the type function always evaluates correctly... 
    def __eq__(self,other):
        returnVal = False
        #is the other guy a polymorphic numeric type?
        if(isinstance(other, PolyNumericType) or isinstance(other, NumericType)):
            returnVal = True;
        # we can also match other functions.  We should really attempt an eval here.
        if(isinstance(other,TypeFunction)):
            returnVal = (self.name == other.name)
            if(returnVal):
                for idx in range(len(self.terms)):
                    returnVal = returnVal and (self.terms[idx] == other.terms[idx])
        print "Compare: " + str(self) + " and " +  str(other) + " -> " + str(returnVal)
        return returnVal
