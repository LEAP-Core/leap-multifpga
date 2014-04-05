class PhysicalVia(object):

    ingress = 1
    egress = 0

    def __init__(self, direction, endpointName, physicalName):
        self.endpointName = endpointName
        self.direction = direction
        self.physicalName = physicalName
        # The following are assigned at compile time
        self.connectionPair = 'unassigned' 
        self.logicalVias = 'unassigned' 
        self.width = "unassigned" 

    def __repr__(self):
        strRepr = ''
        if(self.direction == PhysicalVia.source):
            strRepr += 'CONNECTION\n' + self.endpointName + ' input from '  + self.physicalName + "\n"
        else:
            strRepr += 'CONNECTION\n' + self.endpointName + ' output to '  + self.physicalName +"\n"
        
        if(isinstance(self.logicalVias, str)):
            strRepr += "Logical Vias Unassigned" + "\n"
        else:
            for via in self.logicalVias:
                strRepr += str(via) + "\n"

        return strRepr
