from physical_via import *

##
##  A simple class for representing platform-specific paramter settings. 
##

class Parameter(object):

    def __init__(self, name, value):
        self.name = name
        self.value = value

