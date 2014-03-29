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
        if(self.direction == PhysicalVia.source):
            return 'CONNECTION\n' + self.endpointName + ' input from '  + self.physicalName
        else:
            return 'CONNECTION\n' + self.endpointName + ' output to '  + self.physicalName

