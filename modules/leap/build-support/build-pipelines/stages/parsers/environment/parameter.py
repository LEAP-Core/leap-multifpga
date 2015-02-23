from physical_via import *

##
##  A simple class for representing platform-specific paramter settings. 
##

class Parameter(object):

    def __init__(self, name, value, typeInit):
        self.name = name
        self.value = value
        self.type = typeInit

    def getAWBRepresentation(self):
        print "Calling param repr\n"
        if(self.type == "INT"):
            return str(self.value)
        else:
            return '"' + str(self.value) + '"'
