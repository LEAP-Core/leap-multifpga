from connection import *

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
        return self.egressesByPhysicalName[physicalName]

    def getIngressByPhysicalName(self, physicalName):
        return self.ingressesByPhysicalName[physicalName]
    
    def __init__(self, platformType, name, isMaster, path, physicalViaList):
        self.name = name
        self.platformType = platformType
        self.path = path
        self.master = isMaster
        self.ingresses = {}
        self.egresses = {}
        # a view of the platform useful in parsing via widths.
        self.ingressesByPhysicalName = {} 
        self.egressesByPhysicalName = {} 

        for physicalVia in physicalViaList:
            if(physicalVia.direction == PhysicalVia.ingress):
                self.insertIngress(physicalVia.endpointName, physicalVia)
                self.ingressesByPhysicalName[physicalVia.physicalName] = physicalVia
            else:
                self.insertEgress(physicalVia.endpointName, physicalVia)
                self.egressesByPhysicalName[physicalVia.physicalName] = physicalVia

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
