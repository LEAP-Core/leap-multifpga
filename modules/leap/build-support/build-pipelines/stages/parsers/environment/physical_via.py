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
        strRepr = 'CONNECTION\n    ' + self.endpointName
        if (self.direction == PhysicalVia.ingress):
            strRepr += ' input from '
        else:
            strRepr += ' output to '
        strRepr += self.physicalName + '\n'
        
        strRepr += '    width ' + str(self.width) + '\n'

        if (isinstance(self.logicalVias, str)):
            strRepr += '    Logical Vias Unassigned\n'
        else:
            for via in self.logicalVias:
                strRepr += '    ' + str(via) + '\n'

        return strRepr
