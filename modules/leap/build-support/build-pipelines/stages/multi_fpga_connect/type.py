import sys
import re
#import struct 
#import taggedUnion 



class Type():
  
    def __init__(self, name, params):
        self.name = name
        self.params = params

    def getTypeRefs(self):
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
            return True
        else: #It appears to be another type?
            equal = (self.name == other.name) and len(self.params) == len(other.params)
            if(equal):
                for idx in range(len(self.params)):
                    equal = equal and (self.params[idx] == other.params[idx])
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
        if(isinstance(other, PolyType) or isinstance(other, NumericPolyType)):
            return True;
        else:
           return (self.name == other.name) 

class PolyType(Type):
  
    def __init__(self, name):
        self.name = name

    def getTypeRefs(self):
        return []

    def __repr__(self):
        return  "{ type " + self.name + " }"

    def __eq__(self,other):
        #is the other guy a polymorphic numeric type?
        if(isinstance(other, NumericPolyType) or isinstance(other, NumericType)):
            return False;
        else:
            return True;


class PolyNumericType(PolyType):
  
    def __init__(self, name):
        self.name = name

    def getTypeRefs(self):
        return []

    def __repr__(self):
        return  "{numeric type " + self.name + " }"

    def __eq__(self,other):
        #is the other guy a polymorphic numeric type?
        if(isinstance(other, NumericPolyType) or isinstance(other, NumericType)):
            return True;
        else:
            return False;

    

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
        return [self.ref()] + map(lambda m: m.getTypeRefs(),self.params)

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
        return equal and Type.__eq__(other)
