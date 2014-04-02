import sys
import re
from type import *

# It may be a poor decision to base the typeclass types on 
# the Type class, but our current usage of the typeclass 
# will be sparse enough that it should not matter.  
class Typeclass(Type):

    def __init__(self, type, instances):
        self.type = type
        self.instances = instances

    def __repr__(self):
        representation = "Typeclass {" + str(self.type) + "} {instances {"
        representation += " ".join(map(lambda a: str(a), self.instances))
        representation += "}} "
        return representation


      
