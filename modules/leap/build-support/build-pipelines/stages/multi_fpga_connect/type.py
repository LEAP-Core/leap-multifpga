import sys
import re

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

class NumericType(Type):
  
    def __init__(self, name):
        self.name = name

    def getTypeRefs(self):
        return []

    def __repr__(self):
        return  str(self.name)


class PolyType(Type):
  
    def __init__(self, name):
        self.name = name

    def getTypeRefs(self):
        return []

    def __repr__(self):
        return  "{ type " + self.name + " }"

class PolyNumericType(PolyType):
  
    def __init__(self, name):
        self.name = name

    def getTypeRefs(self):
        return []

    def __repr__(self):
        return  "{numeric type " + self.name + " }"


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

