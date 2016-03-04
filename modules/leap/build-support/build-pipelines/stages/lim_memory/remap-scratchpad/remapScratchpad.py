# python libraries
import re
import math
import os.path
import shutil
import random
import operator

# AWB dependencies
from li_module import LIModule, LIChain

######################################################################
#
#  Latency-insensitive Module Scratchpad Connection Remapping
#
######################################################################

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
    def __str__(self, depth=0):
        print_str = "\t"*depth + self.name + "\n"
        for child in self.children:
            print_str += child.__str__(depth+1)
        return print_str
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

class ScratchpadTreeLeaf():
    def __init__(self, scratchpad):
        self.scratchpad = scratchpad
        self.id = scratchpad.remappedId
        self.name = "leaf" + scratchpad.remappedId
        self.idRange = (int(scratchpad.remappedId), int(scratchpad.remappedId))
        self.bandwidth = scratchpad.bandwidth
        self.isLeaf = True
    def traverse_post_order(self):
        yield self
    def __str__(self, depth=0):
        return "\t"*depth + self.id + "[" + self.scratchpad.id + "]\n"
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

class Scratchpad():
    def __init__(self, id, ringBaseName, platformName="", traffic=0):
        self.id = id
        self.remappedId = id
        self.ringBaseName = ringBaseName
        self.platformName = platformName
        self.traffic = traffic
        self.partition = []
        self.controllerIdx = []
        self.level = 0
        self.latency = 1
        self.bandwidth = 1
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

#
# This function separates scratchpad chains into a list of available 
# scratchpad controllers and a list of client scratchpad IDs 
# 
def separateScratchpadChains(chains):
    platforms = []
    for chain in chains: 
        names = [x['name'] for x in platforms]
        idx = 0
        # new platform name found
        if chain.platform() not in names:
            idx = len(platforms)
            platforms.append({})
            platforms[idx]['name'] = chain.platform()
            platforms[idx]['clients'] = []
            platforms[idx]['controllers'] = []
        else:
            idx = names.index(chain.platform())
        m = re.match("(.*)_(?:Req|Resp)_(\d+)", chain.name)
        if m:
            client = Scratchpad(m.group(2), m.group(1), chain.platform())
            if client not in platforms[idx]['clients']:
                platforms[idx]['clients'].append(client)
        else:
            n = re.match("(.*)_(?:Req|Resp)", chain.name)
            if n: 
                if n.group(1) not in platforms[idx]['controllers']:
                    platforms[idx]['controllers'].append(n.group(1))
    return platforms

#
# This function parses scratchpad statsFile
#
def parseStatsFile(clients, statsFiles):
    for fname in statsFiles:
        statsFile = open(fname, 'r')
        for line in statsFile:
            if re.match("//", line):
                next
            else: 
                m = re.match("LEAP_SCRATCHPAD_(\d+)_PLATFORM_(\d+)_(?:READ|WRITE)_REQUESTS,.*,(\d+)", line)
                n = re.match("Scratchpad bandwidth partition:\s*ID:\s*(\d+).*Ratio:(.*)", line)
                h = re.match("Scratchpad hierarchical ring assignment:(.*)", line)
                l = re.match("LEAP_SCRATCHPAD_(\d+)_PLATFORM_(\d+)_LATENCY,(\d+)", line)
                b = re.match("LEAP_SCRATCHPAD_(\d+)_PLATFORM_(\d+)_BANDWIDTH,(\d+)", line)
                if m:
                    client = next((x for x in clients if x.id == m.group(1)), None)
                    if client != None: 
                        client.traffic += int(m.group(3))
                elif n: 
                    client = next((x for x in clients if x.id == n.group(1)), None)
                    if client != None: 
                        ratio = ''.join(n.group(2).split())
                        client.partition = map(int, ratio.split(":"))
                        if len(client.partition) > 1:
                            client.partition.sort(reverse=True)
                        else:
                            client.partition = []
                elif h:
                    ring_list = [re.sub('[()]', '', x) for x in re.findall("\([0-9,]*\)", h.group(1))]
                    for i, level in enumerate(ring_list):
                        if i == 0:
                            continue
                        nodes = level.split(',')
                        for n in nodes:
                            client = next((x for x in clients if x.id == n), None)
                            if client != None: 
                                client.level = i
                                # print "client id: " + n + " level=" + str(i) 
                elif l:
                    client = next((x for x in clients if x.id == l.group(1)), None)
                    if client != None: 
                        client.latency = int(l.group(3))
                elif b:
                    client = next((x for x in clients if x.id == b.group(1)), None)
                    if client != None: 
                        client.bandwidth = int(b.group(3))

        statsFile.close()     

#
# This function assigns client scratchpads to the available controllers
# by balancing the total number of requests
#
def bandwidthPartition(controllers, clients, statsFiles):
   
    # parse stats file and assign scratchpad info
    parseStatsFile(clients, statsFiles)
    
    # initialization
    network = {}
    num_groups = len(controllers)
    total_bandwidth = [0]*num_groups
    ringstops = [x[:] for x in [[]]*num_groups]
    idx = 0
    
    # sort clients according to their traffic
    clients.sort(key=lambda x: x.traffic, reverse=True)
    
    partitioned_clients = []
    # deal with clients that need to be partitioned first (only for multi-controller case)
    if len(controllers) > 1: 
        partitioned_clients = [x for x in clients if len(x.partition) > 0]
        for client in partitioned_clients:
            client_bandwidth = [ x*client.traffic/sum(client.partition) for x in client.partition ] 
            tmp = list(total_bandwidth)
            mins = sorted(total_bandwidth)[:len(client_bandwidth)]
            for i, b in enumerate(client_bandwidth): 
                idx = tmp.index(mins[i])
                client.controllerIdx += [idx]
                ringstops[idx].append(client)
                total_bandwidth[idx] += b
                tmp[idx] = -1
            print "client: id: ", client.id, ", bandwidth: ", str(client.traffic), \
                   ", partitioned_bandwidth: ", str(client_bandwidth), ", controllerIdx: ", \
                   str(client.controllerIdx), ", total_bandwidth: ", str(total_bandwidth)

    # deal with the rest of the clients
    rest_clients = [x for x in clients if x not in partitioned_clients]
    for client in rest_clients:
        if client.traffic > 0: 
            idx = total_bandwidth.index(min(total_bandwidth))
        else:
            idx = map(len, ringstops).index(min(map(len, ringstops)))
        total_bandwidth[idx] += client.traffic
        ringstops[idx].append(client)
        client.controllerIdx += [idx]
    
    for i, c in enumerate(controllers):
        network[c] = ringstops[i]
    printNetwork(network)
    
    print "bandwidthPartition: total bandwidth = " + str(total_bandwidth)
    
    return partitioned_clients, rest_clients, controllers

#
# This function assigns client scratchpads to the available controllers
#
def connectScratchpadChains(controllers, clients, scratchpadStats, remapMode):
    if len(scratchpadStats) and len(clients) and (remapMode != 1) > 0:
        return bandwidthPartition(controllers, clients, scratchpadStats)
    else:
        network = {}
        num_groups = len(controllers)
        ringstops = [x[:] for x in [[]]*num_groups]
        clients_per_group = int(math.ceil(float(len(clients))/num_groups))
        if remapMode == 1:
            random.seed(1)
            random.shuffle(clients)
        for i, c in enumerate(clients):
            idx = i/clients_per_group
            ringstops[idx].append(c)
            c.controllerIdx += [idx]
        for i, c in enumerate(controllers):
            network[c] = ringstops[i]
        printNetwork(network)
        return [], clients, controllers

#
# This function prints out the scratchpad network
#
def printNetwork(network):
    for controller in network: 
        msg = controller + ": [ "
        for i, client in enumerate(network[controller]):
            if i > 0:
                msg += ", "
            msg += client.id
        print msg, "]"
   
#
# This function prints out the remap table
#
def printRemapTable(remapIds):
    ids = [(x[0], int(x[1])) for x in remapIds.items()]
    sorted_ids = sorted(ids, key=operator.itemgetter(1))
    print "Remapped ID: scratchpad ID"
    for i in sorted_ids: 
        print str(i[1]) + ": " + i[0]

#
# This function remaps client ids for different kinds of networks
#
def remapClientIds(platforms, remapMode):
    # tree structure 
    if remapMode == 2: 
        return buildScratchpadTree(platforms)
    else:
        hierarchy = 0
        for platform in platforms:
            hierarchy += sum([x.level for x in platform['clients']])
        if hierarchy == 0 or remapMode == 1: 
            for platform in platforms:
                platform['networkType'] = "ring"
            remapIds = {}
            return remapIds
        else:
            return buildHierarchicalRing(platforms)

#
# This function builds scratchpad trees
#
def buildScratchpadTree(platforms): 
    radix  = 6
    remapIds = {}
    new_id = 1
    internal_node_id = 1
    for platform in platforms:
        controllers = platform['controllers']
        network = [ScratchpadTreeNode("root"+str(x)) for x in range(len(controllers))]
        for i, controller in enumerate(controllers):
            clients = [x for x in platform['clients'] if i == x.controllerIdx[0]]
            clients.sort(key=lambda x: x.latency, reverse=False)
            total_leaves = len(clients)
            depth = int(math.ceil(math.log(total_leaves,radix)))
            # determine the number of leaf nodes for each level 
            num_leaves = []
            level = max(1, depth-1)
            if total_leaves < int(math.pow(radix,level)): # depth == 1 case
                num_leaves.append(total_leaves)
            else:
                num_leaves.append(int(math.pow(radix, level)))
                level = level + 1
                ret = total_leaves - num_leaves[0]
                internals = int(math.ceil(float(ret)/radix))
                while num_leaves[0] + internals > int(math.pow(radix, level-1)):
                    num_leaves[0] = int(math.pow(radix, level-1)) - internals
                    ret = total_leaves - num_leaves[0]
                    internals = int(math.ceil(float(ret)/radix))
                num_leaves.append(ret)
            
            # remap client IDs
            for client in clients:
                client.remappedId = str(new_id)
                remapIds[client.id] = str(new_id)
                new_id += 1
                       
            # build scratchpad tree
            root = network[i]
            if depth >= 2:
               # create leaf nodes
                parent_nodes = [ScratchpadTreeLeaf(x) for x in clients[:num_leaves[0]]]
                child_nodes = [ScratchpadTreeLeaf(x) for x in clients[len(clients)-num_leaves[1]:]]
                level = depth
                if num_leaves[1]%radix > 0:  
                    n = ScratchpadTreeNode("n"+str(internal_node_id))
                    n.add_children(child_nodes[:num_leaves[1]%radix])
                    parent_nodes.append(n)
                    child_nodes = child_nodes[num_leaves[1]%radix:]
                    internal_node_id += 1
                while level >= 2:
                    while len(child_nodes) > 0:
                        n = ScratchpadTreeNode("n"+str(internal_node_id))
                        n.add_children(child_nodes[:radix])
                        parent_nodes.append(n)
                        child_nodes = child_nodes[radix:]
                        internal_node_id += 1
                    child_nodes = parent_nodes
                    parent_nodes = []
                    level -= 1
                root.add_children(child_nodes) 
            else: # depth == 1 
                # create leaf nodes
                child_nodes = [ScratchpadTreeLeaf(x) for x in clients]
                root.add_children(child_nodes)
            print root
        platform['network'] = network
        platform['networkType'] = "tree"
    return remapIds
    
# This function builds hierarchical ring structure 
def buildHierarchicalRing(platforms):
    remapIds = {}
    for platform in platforms:
        new_id = 1
        for platform in platforms:
            controllers = platform['controllers']
            network = [x[:] for x in [[]]*len(controllers)]
            for i, controller in enumerate(controllers):
                clients = [x for x in platform['clients'] if i == x.controllerIdx[0]]
                clients.sort(key=lambda x: x.level, reverse=True)
                rings  = network[i]
                min_id = new_id
                max_id = new_id
                for client in clients:
                    ring = ScratchpadRing(controller, client.level)
                    if ring not in rings: 
                        if len(rings) > 0: 
                            rings[-1].minId = min_id
                            rings[-1].maxId = max_id - 1
                        rings.append(ring)
                        min_id = new_id
                        max_id = new_id
                    client.remappedId = str(new_id)
                    remapIds[client.id] = str(new_id)
                    new_id += 1
                    max_id += 1
                if len(rings) > 0: 
                    rings[-1].minId = min_id
                    rings[-1].maxId = max_id - 1
            platform['network'] = network
            platform['networkType'] = "hring"
            print network
    return remapIds        

def getHierarchyRingName(baseName, level):
    if level == 0:
        return baseName
    else:
        return baseName + "_l" + str(level)

#
# This function outputs the remapping function in the bsh wrapper 
#
def genRemapWrapper(platforms, remapIds, fileLists):
    refFile = fileLists.pop()
    fileHandle = open(refFile, 'w')
    fileHandle.write("// Generated by build pipeline\n\n")
        
    # include headers
    fileHandle.write("`include \"awb/provides/scratchpad_memory_common.bsh\"\n")
    fileHandle.write("`include \"awb/provides/scratchpad_memory_service.bsh\"\n")
    if len(remapIds) > 0:
        fileHandle.write("`include \"awb/provides/fpga_components.bsh\"\n")
    if sum([x['networkType'] == "tree" for x in platforms]) > 0:
        fileHandle.write("`include \"awb/provides/soft_connections.bsh\"\n")
    
    fileHandle.write("\n")
    
    if sum([len(x['partitioned_clients']) for x in platforms]) + sum([x['networkType'] == "tree" for x in platforms]) > 0:
        fileHandle.write("import Vector::*;\n\n")

    # For clients that are partitioned across multiple controllers, generate connectors 
    # which connect each client to associated controllers
    if sum([len(x['partitioned_clients']) for x in platforms]) > 0:
        if len(platforms) > 1:
            fileHandle.write("module [CONNECTED_MODULE] connectPartitionedScratchpads();\n")
            for platform in platforms:
                if len(platform['partitioned_clients']) > 0:
                    fileHandle.write("    connectPartitionedScratchpads" + platform['name'].title() + "();\n")
            fileHandle.write("endmodule\n\n")
        
        for platform in platforms: 
            pClients = platform['partitioned_clients']
            controllers = platform['controllers']
            if len(pClients) > 0:
                if len(platforms) == 1: 
                    fileHandle.write("module [CONNECTED_MODULE] connectPartitionedScratchpads()\n")
                else:
                    fileHandle.write("module [CONNECTED_MODULE] connectPartitionedScratchpads" + platform['name'].title() + "()\n")
            addr_bits = [int(math.ceil(math.log(sum(x.partition), 2))) for x in pClients]
            fileHandle.write("    provisos (NumAlias#(TLog#(" + str(len(controllers)) + "), t_CTRLR_IDX_SZ),\n")
            fileHandle.write("              Alias#(UInt#(t_CTRLR_IDX_SZ), t_CTRLR_IDX),\n")
            fileHandle.write("              Bits#(SCRATCHPAD_MEM_ADDRESS, t_ADDR_SZ),\n")
            fileHandle.write("              Add#(b_, " + str(max(addr_bits)) + ", t_ADDR_SZ));\n\n")
    
            # The current implementation only supports partitioned scratchpads with level 0
            for i, client in enumerate(pClients):
            
                fileHandle.write("    function t_CTRLR_IDX getControllerIdxFromAddr" + str(i) + "(SCRATCHPAD_MEM_ADDRESS addr);\n")
                fileHandle.write("        Bit#(" + str(addr_bits[i])+ ") test_addr = truncate(addr);\n")
                
                for j, par in enumerate(client.partition): 
                    if j == 0:
                        fileHandle.write("        if (test_addr < " + str((2**addr_bits[i])*par/sum(client.partition)) + ")\n")
                        fileHandle.write("            return unpack(0);\n")
                    elif j == (len(client.partition) -1) :
                        fileHandle.write("        else\n")
                        fileHandle.write("            return unpack(" + str(j) + ");\n")
                    else:
                        fileHandle.write("        else if (test_addr < " + str((2**addr_bits[i])*par/sum(client.partition)) + ")\n")
                        fileHandle.write("            return unpack(" + str(j) + ");\n")
                
                fileHandle.write("    endfunction\n\n")

                fileHandle.write("    Vector#(" + str(len(client.partition))+ ", String) controllerReqRingNameVec" + str(i) + " = newVector();\n")
                fileHandle.write("    Vector#(" + str(len(client.partition))+ ", String) controllerRespRingNameVec" + str(i) + " = newVector();\n")
                for k, c in enumerate(client.controllerIdx):
                    fileHandle.write("    controllerReqRingNameVec" + str(i) + "[" + str(k) + "] = \"" + controllers[c] + "_Req\";\n")
                    fileHandle.write("    controllerRespRingNameVec" + str(i) + "[" + str(k) + "] = \"" + controllers[c] + "_Resp\";\n")

                fileHandle.write("\n    mkScratchpadClientRingConnector(\"" + client.ringBaseName + "_Req_" + client.id + "\",\n")
                fileHandle.write("                                    \"" + client.ringBaseName + "_Resp_" + client.id + "\",\n")
                if remapIds.has_key(client.id): 
                    fileHandle.write("                                    " + remapIds[client.id] + ",\n")
                else:
                    fileHandle.write("                                    " + client.id + ",\n")
                fileHandle.write("                                    controllerReqRingNameVec" + str(i) + ",\n")
                fileHandle.write("                                    controllerRespRingNameVec" + str(i) + ",\n")
                fileHandle.write("                                    getControllerIdxFromAddr" + str(i) + ");\n\n")

            fileHandle.write("endmodule\n\n")
    else: 
        fileHandle.write("module connectPartitionedScratchpads();\nendmodule\n\n")

    # For clients that are not partitioned across multiple controllers or not tree leaves, do name remapping
    fileHandle.write("function String connectionNameRemap(String inputName);\n")
    fileHandle.write("    String outputName = inputName;\n")
    is_first = True
    for platform in platforms:
        rClients = platform['rest_clients']
        controllers = platform['controllers']
        if platform['networkType'] != "tree":
            for client in rClients:
                if is_first:
                    fileHandle.write("    if (inputName == \"" + client.ringBaseName + "_Req_" + client.id + "\")\n    begin\n")
                    is_first = False
                else:
                    fileHandle.write("    else if (inputName == \"" + client.ringBaseName + "_Req_" + client.id + "\")\n    begin\n")
                fileHandle.write("        outputName = \"" + getHierarchyRingName(controllers[client.controllerIdx[0]] + "_Req", client.level) + "\";\n    end\n")
                fileHandle.write("    else if (inputName == \"" + client.ringBaseName + "_Resp_" + client.id + "\")\n    begin\n")
                fileHandle.write("        outputName = \"" + getHierarchyRingName(controllers[client.controllerIdx[0]] + "_Resp", client.level) + "\";\n    end\n")
    fileHandle.write("    return outputName;\n")
    fileHandle.write("endfunction\n\n")
   
    # Generate connectors for hierarchical ring and tree networks
    if len(remapIds) > 0:
        if len(platforms) > 1:
            fileHandle.write("module [CONNECTED_MODULE] connectScratchpadNetwork();\n")
            for platform in platforms:
                if platform['networkType'] == "hring": 
                    if sum(map(len,platform['network'])) > 0:
                        fileHandle.write("    connectScratchpadRings" + platform['name'].title() + "();\n")
                elif platform['networkType'] == "tree":
                    if sum(map(len, [x.children for x in platform['network']])) > 0:
                        fileHandle.write("    connectScratchpadTree" + platform['name'].title() + "();\n")
            fileHandle.write("endmodule\n\n")
        
        for platform in platforms: 
            network = platform['network']
            controllers = platform['controllers']

            # construct hierarchical ring networks
            if platform['networkType'] == "hring":
                if sum(map(len,platform['network'])) > 0:
                    if len(platforms) == 1: 
                        fileHandle.write("module [CONNECTED_MODULE] connectScratchpadNetwork();\n\n")
                    else:
                        fileHandle.write("module [CONNECTED_MODULE] connectScratchpadRings" + platform['name'].title() + "();\n\n")
                
                for i, controller in enumerate(controllers):
                    rings = network[i]
                    for j, ring in enumerate(rings):
                        if ring.level > 0:
                            if ring.maxId == ring.minId: 
                                fileHandle.write("    function Bool isChildNodeC" + str(i) + "L" + str(j) + "(SCRATCHPAD_PORT_NUM id) = (id == " + str(ring.maxId) + ");\n")
                            else:
                                fileHandle.write("    function Bool isChildNodeC" + str(i) + "L" + str(j) + "(SCRATCHPAD_PORT_NUM id) = (id <= " + str(ring.maxId) + ") && (id >= " + str(ring.minId) + ");\n")
                            fileHandle.write("\n    mkScratchpadHierarchicalRingConnector(\"" + getHierarchyRingName(ring.baseName + "_Req", ring.level) + "\",\n")
                            fileHandle.write("                                          \"" + getHierarchyRingName(ring.baseName + "_Resp", ring.level) + "\",\n")
                            fileHandle.write("                                          \"" + getHierarchyRingName(ring.baseName + "_Req", ring.level - 1) + "\",\n")
                            fileHandle.write("                                          \"" + getHierarchyRingName(ring.baseName + "_Resp", ring.level - 1) + "\",\n")
                            fileHandle.write("                                          isChildNodeC" + str(i) + "L" + str(j) + ");\n\n")
                fileHandle.write("endmodule\n\n")
            
            # construct tree networks
            elif platform['networkType'] == "tree": 
                bandwidth_bits = 3
                if sum(map(len, [x.children for x in platform['network']])) > 0:
                    if len(platforms) == 1: 
                        fileHandle.write("module [CONNECTED_MODULE] connectScratchpadNetwork();\n\n")
                    else:
                        fileHandle.write("module [CONNECTED_MODULE] connectScratchpadTree" + platform['name'].title() + "();\n\n")
                for i, controller in enumerate(controllers):
                    root = network[i]
                    for node in root.traverse_post_order():
                        if node.isLeaf:
                            fileHandle.write("    let "+ node.name + " <- mkScratchpadTreeLeafNodeConnector(\"" + node.scratchpad.ringBaseName + "_Req_" + node.scratchpad.id +"\", ")
                            fileHandle.write("\"" + node.scratchpad.ringBaseName + "_Resp_" + node.scratchpad.id +"\", ")
                            fileHandle.write(node.id +");\n")
                        else:
                            r = len(node.children)
                            fileHandle.write("\n    Vector#(" + str(r) + ", CONNECTION_ADDR_TREE#(SCRATCHPAD_PORT_NUM, SCRATCHPAD_MEM_REQ, SCRATCHPAD_READ_RSP)) children_" + node.name + " = newVector();\n")
                            fileHandle.write("    Vector#(" + str(r+1) + ", SCRATCHPAD_PORT_NUM) addressBounds_" + node.name + " = newVector();\n")
                            fileHandle.write("    Vector#(" + str(r) + ", UInt#(" + str(bandwidth_bits) + ")) bandwidthFractions_" + node.name + " = newVector();\n")
                            for j, child in enumerate(node.children): 
                                fileHandle.write("    children_" + node.name + "[" + str(j) + "] = " + child.name + ";\n")
                                
                            for j, child in enumerate(node.children): 
                                fileHandle.write("    addressBounds_" + node.name + "[" + str(j) + "] = " + str(child.idRange[0]) + ";\n")
                            fileHandle.write("    addressBounds_" + node.name + "[" + str(r) + "] = " + str(node.idRange[1]+1) + ";\n")
                           
                            bandwidth_max = max([x.bandwidth for x in node.children])
                            for j, child in enumerate(node.children): 
                                fraction = max(1,min(child.bandwidth, int(round(float(child.bandwidth)*(math.pow(2, bandwidth_bits)-1)/bandwidth_max))))
                                fileHandle.write("    bandwidthFractions_" + node.name + "[" + str(j) + "] = " + str(fraction) + ";\n")
                            
                            if node == root:
                                fileHandle.write("    mkScratchpadTreeRoot(\"" + controller + "_Req\",\n")
                                fileHandle.write("                         \"" + controller + "_Resp\",\n")
                                fileHandle.write("                         " + str(node.idRange[1]) + ",\n")
                                fileHandle.write("                         children_" + node.name + ",\n")
                                fileHandle.write("                         addressBounds_" + node.name + ",\n")
                                fileHandle.write("                         bandwidthFractions_" + node.name + ");\n\n");
                            else:
                                fileHandle.write("    let " + node.name + " <- mkTreeRouter(children_" + node.name + ", addressBounds_" + node.name + ", mkLocalArbiterBandwidth(bandwidthFractions_" + node.name + "));\n");
                             
                fileHandle.write("endmodule\n\n")

    else: 
        fileHandle.write("module connectScratchpadNetwork();\nendmodule\n\n")


    # Generate scratchpad ID remapping initializer
    if len(remapIds) > 0:
        fileHandle.write("interface SCRATCHPAD_ID_REMAP_IFC;\n")
        fileHandle.write("    method SCRATCHPAD_PORT_NUM getRemappedId(SCRATCHPAD_PORT_NUM id);\n")
        fileHandle.write("endinterface\n\n")
        fileHandle.write("module mkScratchpadIdRemapInitializer(SCRATCHPAD_ID_REMAP_IFC);\n\n")
        fileHandle.write("    Reg#(Bool) initialized <- mkReg(False);\n")
        fileHandle.write("    Reg#(Bit#(" + str(int(math.ceil(math.log(len(remapIds), 2)))) + ")) remapCnt <- mkReg(0);\n")
        fileHandle.write("    LUTRAM#(SCRATCHPAD_PORT_NUM, SCRATCHPAD_PORT_NUM) remapTable <- mkLUTRAM(0);\n\n")
        fileHandle.write("    rule initTable(!initialized);\n")
        for i, key in enumerate(remapIds.keys()):
            if i == 0:
                fileHandle.write("        if (remapCnt == 0)\n")
            else:
                fileHandle.write("        else if (remapCnt == " + str(i) +")\n")
            fileHandle.write("        begin\n")
            fileHandle.write("            remapTable.upd(" + key + "," + remapIds[key] +");\n")
            if i == (len(remapIds) - 1):
                fileHandle.write("            initialized <= True;\n")
            fileHandle.write("        end\n")
        fileHandle.write("        remapCnt <= remapCnt + 1;\n")
        fileHandle.write("    endrule\n\n")
        
        fileHandle.write("    method SCRATCHPAD_PORT_NUM getRemappedId(SCRATCHPAD_PORT_NUM id) if (initialized);\n")
        fileHandle.write("        return remapTable.sub(id);\n")
        fileHandle.write("    endmethod\n\n")
        fileHandle.write("endmodule\n\n")

    # Generate scratchpad ID remapping controller
    fileHandle.write("module [CONNECTED_MODULE] mkScratchpadIdRemap();\n\n")
    if len(remapIds) == 0:
        fileHandle.write("    function SCRATCHPAD_PORT_NUM remappedId(SCRATCHPAD_PORT_NUM id) = id;\n\n")
    else:
        fileHandle.write("    SCRATCHPAD_ID_REMAP_IFC m <- mkScratchpadIdRemapInitializer();\n")
        fileHandle.write("    let remappedId = m.getRemappedId();\n")
    fileHandle.write("    mkScratchpadIdRemapController(remappedId);\n\n")
    fileHandle.write("endmodule\n\n")
    
    fileHandle.close()
    
    for file in fileLists:
        shutil.copy2(refFile, os.path.dirname(file))
    
#
# This function outputs the default remapping function in the bsh wrapper 
#
def createDefaultRemapFile(remapFilePath):
    remapHandle = open(remapFilePath, 'w')
    remapHandle.write("// Generated by build pipeline\n\n")
    remapHandle.write("function String connectionNameRemap(String inputName) = inputName;\n\n")
    remapHandle.write("module connectPartitionedScratchpads();\nendmodule\n\n")
    remapHandle.write("module connectScratchpadNetwork();\nendmodule\n\n")
    remapHandle.write("module mkScratchpadIdRemap();\nendmodule\n\n")
    remapHandle.close()

#
# This function is the top function that handles scratchpad connection remapping
#
def remapScratchpadConnections(liModules, fileLists, scratchpadStats, remapMode):
    print "remapScratchpadConnections: "
    scratchChains = []
    for liModule in liModules:
        for chain in liModule.chains:
            if re.search("^Scratchpad_", chain.name):
                if re.match("Scratchpad_ID_Remap_(?:Req|Resp)", chain.name):
                    continue
                print "Find Scratchpad Chain: " + chain.name + " in module: " + chain.module_name + " in platform: " + chain.platform()
                scratchChains.append(chain)
        
    platforms = separateScratchpadChains(scratchChains)
    
    # scratchpad remap is enabled
    if sum([len(x['clients']) for x in platforms]) > 0:
        for platform in platforms: 
            partitioned_clients, rest_clients, controllers = connectScratchpadChains(platform['controllers'], platform['clients'], scratchpadStats, remapMode)
            platform['partitioned_clients'] = partitioned_clients 
            platform['rest_clients'] = rest_clients
        
        remapIds = remapClientIds(platforms, remapMode)
        # print remapIds
        printRemapTable(remapIds)
        print ""
        genRemapWrapper(platforms, remapIds, fileLists)
    else:
        for remapFile in fileLists:
            createDefaultRemapFile(remapFile)

