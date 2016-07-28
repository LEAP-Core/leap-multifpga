
class ScratchpadRing():
    def __init__(self, baseName, level):
        self.baseName = baseName
        self.level = level
        self.minId = 0
        self.maxId = 0
    def __eq__(self, other):
        return self.__dict__ == other.__dict__
    def __str__(self):
        return "ScratchpadRing: baseName=" + self.baseName + " level=" + str(self.level) + " [" + str(self.minId) + ":" + str(self.maxId) + "]"
    def __repr__(self):
        return "ScratchpadRing: baseName=" + self.baseName + " level=" + str(self.level) + " [" + str(self.minId) + ":" + str(self.maxId) + "]"

class ScratchpadTreeNode():
    def __init__(self, name):
        self.name = name
        self.children = []
        self.idRange = (0, 0)
        self.bandwidth = 0
        self.isLeaf = False
        self.depth = 0
    def add_child(self, child):
        if len(self.children) == 0: 
            self.idRange = child.idRange
        else:
            self.idRange = (min(self.idRange[0], child.idRange[0]), max(self.idRange[1], child.idRange[1]))
        self.bandwidth += child.bandwidth
        self.children.append(child)
    def add_children(self, children):
        for child in children:
            self.add_child(child) 
    def traverse_post_order(self):
        for child in self.children:
            for node in child.traverse_post_order():
                yield node
        yield self
    def assign_depth(self, depth):
        self.depth = depth
        for child in self.children:
            child.assign_depth(depth+1)
    def weight(self,depth=0):
        weight = 0
        for child in self.children:
            weight += child.weight(depth+1)
        return weight
    def __str__(self, depth=0):
        print_str = "\t"*depth + self.name + "\n"
        for child in self.children:
            print_str += child.__str__(depth+1)
        return print_str
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

class ScratchpadTreeLeaf():
    def __init__(self, scratchpad, newId, bandwidth):
        self.scratchpad = scratchpad
        self.id = newId
        self.name = "leaf" + newId
        self.idRange = (int(newId), int(newId))
        self.bandwidth = max(bandwidth, 1)
        self.isLeaf = True
        self.depth = 0
    def traverse_post_order(self):
        yield self
    def assign_depth(self, depth):
        self.depth = depth
    def weight(self,depth):
        return self.scratchpad.treeWeight(depth)
    def __str__(self, depth=0):
        return "\t"*depth + self.id + "[" + self.scratchpad.id + "]\n"
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

class Scratchpad():
    def __init__(self, id, connection, traffic=0):
        self.id = id
        self.remappedIds = {}
        self.connection = connection
        self.platformName = connection.platform()
        self.traffic = traffic
        self.partition = []
        self.controllerIdx = []
        self.matchingPorts = {}
        self.level = 0
        self.latency = 0
        self.bandwidth = 1
        self.weightVals = []
        self.finalBandwidthFraction = {}
    #
    # This function returns the bandwidth fraction given the controller index
    #
    def getBandwidthFraction(self, controllerIdx):
        if len(self.partition) == 0: 
            return self.bandwidth
        else:
            idx = self.controllerIdx.index(controllerIdx)
            return int(round(self.partition[idx]*self.bandwidth/float(sum(self.partition))))
   
    def treeWeight(self,depth):
        if len(self.weightVals) == 0: 
            return 0
        elif depth > len(self.weightVals): # use linear model
            return self.latency * (depth -1) + 1.0
        else: 
            return self.weightVals[depth-1]
    
    def __repr__(self):
        print_str =  "Scratchpad: name: " + self.connection.name + " id: " + self.id
        print_str += " controllerIdx: " + str(self.controllerIdx) + " traffic: " + str(self.traffic)
        print_str += " remappedIds: " + str(self.remappedIds)
        print_str += " level: " + str(self.level) + " latency: " + str(self.latency) + " bandwidth: " + str(self.bandwidth)
        return print_str
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

class ScratchpadPlatform():
    def __init__(self, name, id, filePath):
        self.name = name
        self.id = id
        self.clients = []
        self.partitionedClients = []
        self.restClients = []
        self.controllers = []
        self.network = []
        self.networkType = ""
        self.remapFile = filePath
    def __repr__(self):
        print_str =  "Platform: name: " + self.name + " id: " + str(self.id)
        print_str += " clients: " + str(self.clients) + " controllers: " + str(self.controllers)
        print_str += " remapFile: " + self.remapFile
        return print_str
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

