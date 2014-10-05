from physical_via import *
from parameter    import *

##
##  This class represents a platform, a computational entity capable
##  of executing latency-insensitive modules.
##

class Platform(object):

    def getEgresses(self):
        return self.egresses

    def getEgress(self, targetName):
        return self.egresses[targetName]

    def getIngresses(self):
        return self.ingresses

    def getIngress(self, targetName):
        return self.ingresses[targetName]

    def insertEgress(self,target,via):
        self.egresses[target] = via

    def insertIngress(self,target,via):
        self.ingresses[target] = via

    def getEgressByPhysicalName(self, physicalName):
        if(physicalName in  self.egressesByPhysicalName):
            return self.egressesByPhysicalName[physicalName]
        else:
            return None

    def getIngressByPhysicalName(self, physicalName):
        if(physicalName in  self.ingressesByPhysicalName):
            return self.ingressesByPhysicalName[physicalName]
        else:
            return None    

    def __init__(self, platformType, name, isMaster, path, platformDescriptorList):
        self.name = name
        self.platformType = platformType
        self.path = path
        self.master = isMaster
        self.parameters = {}
        self.attributes = {}

        self.ingresses = {}
        self.egresses = {}
        # a view of the platform useful in parsing via widths.
        self.ingressesByPhysicalName = {} 
        self.egressesByPhysicalName = {} 

        # the physical via list can have both vias AND paramters. 
        for platformDescriptor in platformDescriptorList:
            if(isinstance(platformDescriptor, PhysicalVia)):
                physicalVia = platformDescriptor
                if(physicalVia.direction == PhysicalVia.ingress):
                    self.insertIngress(physicalVia.endpointName, physicalVia)
                    self.ingressesByPhysicalName[physicalVia.physicalName] = physicalVia
                else:
                    self.insertEgress(physicalVia.endpointName, physicalVia)
                    self.egressesByPhysicalName[physicalVia.physicalName] = physicalVia
            else:
                # this is a parameter. 
                self.parameters[platformDescriptor.name] = platformDescriptor

    def __repr__(self):
       ingressRepr = ''
       for ingress in self.ingresses:
           ingressRepr = ingressRepr + self.ingresses[ingress].__repr__() + '\n'
           
       egressRepr = ''
       for egress in self.egresses:
           egressRepr = egressRepr + self.egresses[egress].__repr__() + '\n'
           
       return 'Platform ' + self.name + '\n Ingresses: \n' + ingressRepr + '\n Egresses: \n' + egressRepr
  
    def getAPMName(self):
       tokens = (self.path).split("/")
       return tokens[-1]


    def putAttribute(self, key, value):       
        self.attributes[key] = value
        

    def getAttribute(self, key):
        return self.attributes[key]
