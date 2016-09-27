# python libraries
import re
import math
import os.path
import shutil
import random
import operator
import sys

# AWB dependencies
import scratchpadTree
from scratchpadModules import Scratchpad, ScratchpadPlatform, ScratchpadRing, ScratchpadTreeNode, ScratchpadTreeLeaf
from li_module import LIModule, LIChain, LIService


######################################################################
#
#  Latency-insensitive Module Scratchpad Connection Remapping
#
######################################################################

#
# This function separates scratchpad connections based on the platform 
# they are mapped to
# 
def separateScratchpadConnections(clients, controllers, platforms):
    
    names = [x.name for x in platforms]
    
    for controller in controllers: 
        idx = names.index(controller.platform())
        platforms[idx].controllers.append(controller.copy())
    
    for client in clients: 
        idx = names.index(client.platform())
        platforms[idx].clients.append(Scratchpad(client.client_idx, client.copy()))

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
                l = re.match("LEAP_SCRATCHPAD_(\d+)_PLATFORM_(\d+)_LATENCY,([0-9.]+) \((.+)\)", line)
                b = re.match("LEAP_SCRATCHPAD_(\d+)_PLATFORM_(\d+)_BANDWIDTH,(\d+)", line)
                p = re.match("LEAP_SCRATCHPAD_(\d+)_PLATFORM_(\d+)_PRIORITY,(\d+)", line)
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
                        client.latency = float(l.group(3))
                        client.weightVals = map(float,l.group(4).split(' '))
                elif b:
                    client = next((x for x in clients if x.id == b.group(1)), None)
                    if client != None: 
                        client.bandwidth = int(b.group(3))
                elif p:
                    client = next((x for x in clients if x.id == p.group(1)), None)
                    if client != None: 
                        client.priority = int(p.group(3))

        statsFile.close()     

#
# This function interleaves each client scratchpad to the all available controllers
#
def interleaveAllClients(controllers, clients, statsFiles):
    # parse stats file and assign scratchpad info
    if len(statsFiles) > 0:  
        parseStatsFile(clients, statsFiles)
    
    # initialization
    network = {}
    partitioned_clients = clients
    rest_clients = []
    
    # assign client partitions
    for client in partitioned_clients: 
        client.partition = [1]*len(controllers)
        client.controllerIdx = list(range(0,len(controllers)))

    for i, c in enumerate(controllers):
        network[c.name] = partitioned_clients
    printNetwork(network)
    
    return partitioned_clients, rest_clients, controllers

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
        network[c.name] = ringstops[i]
    printNetwork(network)
    
    print "bandwidthPartition: total bandwidth = " + str(total_bandwidth)
    
    return partitioned_clients, rest_clients, controllers

#
# This function assigns client scratchpads to the available controllers
#
def assignScratchpadClients(controllers, clients, scratchpadStats, remapMode, interleaveAll):
    if len(clients) and interleaveAll: 
        return interleaveAllClients(controllers, clients, scratchpadStats)
    elif len(scratchpadStats) and len(clients) and (remapMode != 1) > 0:
        return bandwidthPartition(controllers, clients, scratchpadStats)
    else: # random partition
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
            network[c.name] = ringstops[i]
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
    ids = [(int(x[0]), x[1]) for x in remapIds.items()]
    sorted_ids = sorted(ids, key=operator.itemgetter(0))
    print "Remapped ID: scratchpad ID"
    for i in sorted_ids: 
        print str(i[0]) + ": " + i[1]

#
# This function remaps client ids for different kinds of networks
#
def remapClientIds(platforms, remapMode, treeKary, treeMode):
    # tree structure 
    if remapMode == 2 or remapMode == 3: 
        return scratchpadTree.buildScratchpadTrees(platforms, treeKary, treeMode)
    elif remapMode == 4: 
        for platform in platforms:
            platform.networkType = "crossbar"
        remapIds = {}
        return remapIds
    else:
        hierarchy = 0
        for platform in platforms:
            hierarchy += sum([x.level for x in platform.clients])
        if hierarchy == 0 or remapMode == 1: 
            for platform in platforms:
                platform.networkType = "ring"
            remapIds = {}
            return remapIds
        else:
            return buildHierarchicalRing(platforms)

    
# This function builds hierarchical ring structure 
def buildHierarchicalRing(platforms):
    remapIds = {}
    for platform in platforms:
        new_id = 1
        for platform in platforms:
            controllers = platform.controllers
            network = [x[:] for x in [[]]*len(controllers)]
            for i, controller in enumerate(controllers):
                clients = [x for x in platform.clients if i in x.controllerIdx]
                clients.sort(key=lambda x: x.level, reverse=True)
                rings  = network[i]
                min_id = new_id
                max_id = new_id
                for client in clients:
                    ring = ScratchpadRing(controller.name, client.level)
                    if ring not in rings: 
                        if len(rings) > 0: 
                            rings[-1].minId = min_id
                            rings[-1].maxId = max_id - 1
                        rings.append(ring)
                        min_id = new_id
                        max_id = new_id
                    client.remappedIds[i] = str(new_id)
                    if len(client.controllerIdx) > 1:
                        remapIds[str(new_id)] = client.id + "*"
                    else: 
                        remapIds[str(new_id)] = client.id
                    new_id += 1
                    max_id += 1
                if len(rings) > 0: 
                    rings[-1].minId = min_id
                    rings[-1].maxId = max_id - 1
            platform.network = network
            platform.networkType = "hring"
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
def genRemapWrapper(platform, remapIds, fastNetwork, dynBandwidthEn, interleaveAll):
    
    fileHandle = open(platform.remapFile, 'w')
    fileHandle.write("// Generated by build pipeline (lim_memory)\n\n")
        
    # include headers
    fileHandle.write("`include \"awb/provides/scratchpad_memory_common.bsh\"\n")
    fileHandle.write("`include \"awb/provides/scratchpad_memory_service.bsh\"\n")
    fileHandle.write("`include \"awb/provides/soft_connections.bsh\"\n")
    fileHandle.write("`include \"awb/provides/soft_connections_alg.bsh\"\n")
    fileHandle.write("`include \"awb/provides/clocks_device.bsh\"\n")
    if len(remapIds) > 0 or fastNetwork == True:
        fileHandle.write("`include \"awb/provides/fpga_components.bsh\"\n")
    if platform.networkType == "tree" or platform.networkType == "crossbar": 
        fileHandle.write("`include \"awb/provides/common_services.bsh\"\n")

    fileHandle.write("\n")
    
    fileHandle.write("import Vector::*;\n\n")
    
    controllers = platform.controllers
    pClients = platform.partitionedClients
    rClients = platform.restClients
    hr_module_body = "" 
    clock_info = ""
    interleave_addr_bit = 4

    if len(pClients) > 0: 
        fileHandle.write("module [CONNECTED_MODULE] connectScratchpadNetwork#(CLOCKS_DRIVER clocksDriver)\n")
        fileHandle.write("    // Interface:\n")
        fileHandle.write("    ()\n")
        if (interleaveAll):  
            addr_bits = [interleave_addr_bit for x in pClients]
        else: 
            addr_bits = [int(math.ceil(math.log(sum(x.partition), 2))) for x in pClients]
        fileHandle.write("    provisos(NumAlias#(TLog#(" + str(len(controllers)) + "), t_CTRLR_IDX_SZ),\n")
        fileHandle.write("             Alias#(UInt#(t_CTRLR_IDX_SZ), t_CTRLR_IDX),\n")
        fileHandle.write("             Bits#(SCRATCHPAD_MEM_ADDRESS, t_ADDR_SZ),\n")
        fileHandle.write("             Add#(b_, " + str(max(addr_bits)) + ", t_ADDR_SZ));\n\n")
    else: 
        fileHandle.write("module [CONNECTED_MODULE] connectScratchpadNetwork#(CLOCKS_DRIVER clocksDriver)\n")
        fileHandle.write("    // Interface:\n")
        fileHandle.write("    ();\n\n")
        
    if fastNetwork: 
        fileHandle.write("    let networkClockPackage <- mkUserClockFromFrequency(`CRYSTAL_CLOCK_FREQ,\n")
        fileHandle.write("                                                        `MODEL_CLOCK_FREQ*16,\n")
        fileHandle.write("                                                        clocked_by clocksDriver.rawClock,\n")
        fileHandle.write("                                                        reset_by   clocksDriver.rawReset);\n\n")
        fileHandle.write("    Clock networkClock = networkClockPackage.clk;\n")
        fileHandle.write("    Reset networkReset = networkClockPackage.rst;\n\n")
        fileHandle.write("    MakeResetIfc soft_reset_wrapper <- mkReset(64, True, networkClock,\n")
        fileHandle.write("                                               clocked_by networkClock,\n")
        fileHandle.write("                                               reset_by   networkReset);\n")
        fileHandle.write("    Reset softReset = soft_reset_wrapper.new_rst;\n")
        fileHandle.write("    let finalReset <- mkResetFanout(softReset, clocked_by networkClock);\n\n")
        
        clock_info = "clocked_by networkClock, reset_by finalReset"

    fileHandle.write("    let clients <- getUnmatchedServiceClients();\n")
    fileHandle.write("    let servers <- getUnmatchedServiceServers();\n\n")

    if platform.networkType != "tree": 
        fileHandle.write("    NumTypeParam#(" + str(controllers[0].req_bitwidth) + ") reqSz = ?;\n")
        fileHandle.write("    NumTypeParam#(" + str(controllers[0].resp_bitwidth) + ") rspSz = ?;\n")
        fileHandle.write("    NumTypeParam#(" + str(controllers[0].idx_bitwidth) + ") idxSz = ?;\n\n")
        
    if platform.networkType == "crossbar" and (dynBandwidthEn or interleaveAll): 
        fileHandle.write("    PARAMETER_NODE paramNode <- mkDynamicParameterNode();\n\n")
    elif platform.networkType == "tree": 
        fileHandle.write("    PARAMETER_NODE paramNode <- mkDynamicParameterNode();\n")
        fileHandle.write("    Param#(1) prioritySelEnParam <- mkDynamicParameterFromStringInitialized(\"LEAP_SCRATCHPAD_PLATFORM_" + str(platform.id) + "_NETWORK_PRIORITY_SEL_EN\", 1'd1, paramNode);\n")
        fileHandle.write("    Param#(1) bandwidthSelEnParam <- mkDynamicParameterFromStringInitialized(\"LEAP_SCRATCHPAD_PLATFORM_" + str(platform.id) + "_NETWORK_BANDWIDTH_SEL_EN\", 1'd1, paramNode);\n")
        fileHandle.write("    let prioritySelEn = (prioritySelEnParam == 1);\n")
        fileHandle.write("    let bandwidthSelEn = (bandwidthSelEnParam == 1);\n\n")

    # instantiate service network modules and connect them with service controllers
    for i, controller in enumerate(controllers):
        fileHandle.write("    let server" + str(i) + " <- findMatchingServiceServer(servers, \"" + controller.name + "\");\n")
        clients = [x for x in platform.clients if i in x.controllerIdx]
        # deal with single client service
        if len(clients) == 1: # no network needed
            # directly connect the service server with the service client
            req_matching_port = "server" + str(i) + ".incoming"
            # need to remap client's id
            if i != clients[0].controllerIdx[0] and clients[0].remappedIds.has_key(i): 
                fileHandle.write("    function SCRATCHPAD_PORT_NUM getRemappedIdx" + str(i) + "(SCRATCHPAD_PORT_NUM idx);\n")
                fileHandle.write("        if (pack(idx) == " + clients[0].remappedIds[clients[0].controllerIdx[0]] + ")\n")
                fileHandle.write("            return unpack(" + clients[0].remappedIds[i] + ");\n")
                fileHandle.write("        else\n")
                fileHandle.write("            return idx;\n")
                fileHandle.write("    endfunction\n\n")
                server_rsp_port = "remapScratchpadServiceConnectionOut(server" + str(i) + ".outgoing, getRemappedIdx" + str(i) + ")" 
            else: 
                server_rsp_port = "server" + str(i) + ".outgoing"
            rsp_matching_port = "resizeServiceConnectionOut(" + server_rsp_port + ")"
            clients[0].matchingPorts[i] = (req_matching_port, rsp_matching_port)
        
        elif platform.networkType == "ring": 
            fileHandle.write("    Vector#(" +  str(len(clients)) + ", Integer) clientIdVec" + str(i) + " = newVector();\n")
            for j, client in enumerate(clients): 
                 fileHandle.write("    clientIdVec" + str(i) + "[" + str(j) + "] = " +  str(client.id) + ";\n")
                 req_matching_port = "network" + str(i) + ".clientReqPorts[" + str(j) + "]"
                 rsp_matching_port = "network" + str(i) + ".clientRspPorts[" + str(j) + "]"
                 client.matchingPorts[i] = (req_matching_port, rsp_matching_port)
            fileHandle.write("    let network" +  str(i) + " <- mkServiceRingNetworkModule(clientIdVec" + str(i) + ", reqSz, rspSz, idxSz);\n")
            fileHandle.write("    connectOutToIn(server" + str(i) + ".outgoing, network" + str(i) + ".serverRspPort, 0);\n")
            fileHandle.write("    connectOutToIn(network" + str(i) + ".serverReqPort, server" + str(i) + ".incoming, 0);\n\n")
        
        elif platform.networkType == "tree": 
            bandwidth_bits = 6
            root = platform.network[i]
            for node in root.traverse_post_order():
                if node.isLeaf:
                    fileHandle.write("    let "+ node.name + " <- mkServiceTreeLeaf(" + clock_info + ");\n")
                    req_matching_port = node.name + ".clientReqIncoming"
                    rsp_matching_port = node.name + ".clientRspOutgoing"
                    node.scratchpad.matchingPorts[i] = (req_matching_port, rsp_matching_port)
                else:
                    r = len(node.children)
                    fileHandle.write("\n    Vector#(" + str(r) + ", CONNECTION_ADDR_TREE#(SCRATCHPAD_PORT_NUM, SCRATCHPAD_MEM_REQ, SCRATCHPAD_READ_RSP)) children_" + node.name + " = newVector();\n")
                    fileHandle.write("    Vector#(" + str(r+1) + ", SCRATCHPAD_PORT_NUM) addressBounds_" + node.name + " = newVector();\n")
                    fileHandle.write("    Vector#(" + str(r) + ", UInt#(" + str(bandwidth_bits) + ")) bandwidthFractions_" + node.name + " = newVector();\n")
                    fileHandle.write("    Vector#(" + str(r) + ", Bool) priorityVec_" + node.name + " = newVector();\n")
                    for j, child in enumerate(node.children): 
                        if child.isLeaf: 
                            name = child.name + ".tree"
                        else:
                            name = child.name
                        fileHandle.write("    children_" + node.name + "[" + str(j) + "] = " + name + ";\n")
                        
                    for j, child in enumerate(node.children): 
                        fileHandle.write("    addressBounds_" + node.name + "[" + str(j) + "] = " + str(child.idRange[0]) + ";\n")
                    fileHandle.write("    addressBounds_" + node.name + "[" + str(r) + "] = " + str(node.idRange[1]+1) + ";\n")
                   
                    bandwidth_max = max(1, max([x.bandwidth for x in node.children]))
                    for j, child in enumerate(node.children): 
                        # fraction = max(1,min(child.bandwidth, int(round(float(child.bandwidth)*(math.pow(2, bandwidth_bits)-1)/bandwidth_max))))
                        static_fraction = max(1,min(child.bandwidth, int(math.pow(2, bandwidth_bits)-1)))
                        if child.isLeaf and dynBandwidthEn:
                            fileHandle.write("    Param#(" + str(bandwidth_bits) + ") bandwidthParam_" + node.name + "_" + str(j))
                            fileHandle.write(" <- mkDynamicParameterFromStringInitialized(\"LEAP_SCRATCHPAD_" + child.scratchpad.id + "_CTRL" + str(i))
                            fileHandle.write("_PLATFORM_" + str(platform.id) + "_NETWORK_BANDWIDTH\", " + str(bandwidth_bits) + "'d" + str(static_fraction) + ", paramNode);\n")
                            fraction = "unpack(bandwidthParam_" + node.name + "_" + str(j) + ")"
                            fileHandle.write("    Param#(1) priorityParam_" + node.name + "_" + str(j))
                            fileHandle.write(" <- mkDynamicParameterFromStringInitialized(\"LEAP_SCRATCHPAD_" + child.scratchpad.id + "_CTRL" + str(i))
                            fileHandle.write("_PLATFORM_" + str(platform.id) + "_NETWORK_PRIORITIZED\", 1'd" + str(child.scratchpad.priority) + ", paramNode);\n")
                            priority = "(priorityParam_" + node.name + "_" + str(j) + " == 1)"
                        else: 
                            fraction = str(static_fraction)
                            if child.isLeaf and child.scratchpad.priority == 0:
                                priority = "False"
                            else: 
                                priority = "True"
                        fileHandle.write("    bandwidthFractions_" + node.name + "[" + str(j) + "] = " + fraction + ";\n")
                        fileHandle.write("    priorityVec_" + node.name + "[" + str(j) + "] = " + priority + ";\n")

                    if node == root:
                        remapped_clients = [x for x in platform.clients if i in x.controllerIdx and i != x.controllerIdx[0]]
                        if len(remapped_clients) > 0: 
                            fileHandle.write("    function SCRATCHPAD_PORT_NUM getRemappedIdx" + str(i) + "(SCRATCHPAD_PORT_NUM idx);\n")
                            for r, client in enumerate(remapped_clients): 
                                if r == 0:
                                    fileHandle.write("        if (pack(idx) == " + client.remappedIds[client.controllerIdx[0]] + ")\n")
                                else: 
                                    fileHandle.write("        else if (pack(idx) == " + client.remappedIds[client.controllerIdx[0]] + ")\n")
                                fileHandle.write("            return unpack(" + client.remappedIds[i] + ");\n")
                            fileHandle.write("        else\n")
                            fileHandle.write("            return idx;\n")
                            fileHandle.write("    endfunction\n\n")
                            server_rsp_port = "remapScratchpadServiceConnectionOut(server" + str(i) + ".outgoing, getRemappedIdx" + str(i) + ")" 
                        else: 
                            server_rsp_port = "server" + str(i) + ".outgoing"
                        
                        indent = ""
                        if fastNetwork: 
                            fileHandle.write("    mkServiceTreeRootDualClock(server" + str(i) + ".incoming,\n")
                            indent = "         "
                        else:    
                            fileHandle.write("    mkServiceTreeRoot(server" + str(i) + ".incoming,\n")
                        fileHandle.write( indent + "                      " + server_rsp_port + ",\n")
                        fileHandle.write( indent + "                      children_" + node.name + ",\n")
                        fileHandle.write( indent + "                      addressBounds_" + node.name + ",\n")
                        fileHandle.write( indent + "                      bandwidthFractions_" + node.name + ",\n");
                        fileHandle.write( indent + "                      priorityVec_" + node.name + ",\n");
                        fileHandle.write( indent + "                      bandwidthSelEn,\n");
                        if fastNetwork: 
                            fileHandle.write( indent + "                      prioritySelEn,\n");
                            fileHandle.write( indent + "                      " + clock_info + ");\n\n");
                        else: 
                            fileHandle.write( indent + "                      prioritySelEn);\n\n");
                    else:
                        fileHandle.write("    let " + node.name + " <- mkTreeRouter(children_" + node.name + ", addressBounds_" + node.name + ", ")
                        if fastNetwork: 
                            fileHandle.write("mkLocalArbiterBandwidthWithPriority(bandwidthFractions_" + node.name + ", priorityVec_" + node.name + ", bandwidthSelEn, prioritySelEn)," + clock_info + ");\n");
                        else: 
                            fileHandle.write("mkLocalArbiterBandwidthWithPriority(bandwidthFractions_" + node.name + ", priorityVec_" + node.name + ", bandwidthSelEn, prioritySelEn));\n");
   
        elif platform.networkType == "hring": 
            fileHandle.write("    Vector#(" +  str(len(clients)) + ", Integer) clientIdVec" + str(i) + " = newVector();\n")
            clients.sort(key=lambda x: int(x.remappedIds[i]), reverse=False)
            for j, client in enumerate(clients): 
                 fileHandle.write("    clientIdVec" + str(i) + "[" + str(j) + "] = " +  client.remappedIds[i] + ";\n")
                 req_matching_port = "network" + str(i) + ".clientReqPorts[" + str(j) + "]"
                 rsp_matching_port = "network" + str(i) + ".clientRspPorts[" + str(j) + "]"
                 client.matchingPorts[i] = (req_matching_port, rsp_matching_port)
            fileHandle.write("    let network" +  str(i) + " <- mkServiceHierarchicalRingNetworkModule" + str(i) + "(clientIdVec" + str(i) + ", reqSz, rspSz, idxSz);\n")
            fileHandle.write("    connectOutToIn(server" + str(i) + ".outgoing, network" + str(i) + ".serverRspPort, 0);\n")
            fileHandle.write("    connectOutToIn(network" + str(i) + ".serverReqPort, server" + str(i) + ".incoming, 0);\n\n")
            
            hrings = platform.network[i]
            hr_module_body += "module mkServiceHierarchicalRingNetworkModule" + str(i) + "#(Vector#(" + str(len(clients)) + ", Integer) clientIdVec,\n"
            hr_module_body += "                                                NumTypeParam#(t_REQ_SZ) reqSz,\n"
            hr_module_body += "                                                NumTypeParam#(t_RSP_SZ) rspSz,\n" 
            hr_module_body += "                                                NumTypeParam#(t_IDX_SZ) idxSz)\n"
            hr_module_body += "    // Interface:\n"
            hr_module_body += "    (CONNECTION_SERVICE_NETWORK_IFC#(" + str(len(clients)) + "))\n"
            hr_module_body += "    provisos(Alias#(Bit#(t_REQ_SZ), t_REQ),\n"
            hr_module_body += "             Alias#(Bit#(t_RSP_SZ), t_RSP),\n"
            hr_module_body += "             Alias#(Bit#(t_IDX_SZ), t_IDX));\n\n"
            hr_module_body += "    Clock localClock <- exposeCurrentClock();\n"
            hr_module_body += "    Reset localReset <- exposeCurrentReset();\n\n"
            hr_module_body += "    function Bool isLocalFunc(Integer clientId, t_IDX idx);\n"
            hr_module_body += "        return idx == fromInteger(clientId);\n"
            hr_module_body += "    endfunction\n\n"
            hr_module_body += "    Vector#(" + str(len(clients)) + ", CONNECTION_SERVICE_RING_NODE_IFC#(t_REQ_SZ, t_RSP_SZ, t_IDX_SZ)) ringNodes <- \n"
            hr_module_body += "        mapM(mkServiceRingNode, map(isLocalFunc, clientIdVec));\n\n"
           
            # connect ring nodes on the same level
            for j in range(len(clients)-1): 
                 if clients[j].level == clients[j+1].level: 
                     hr_module_body += "    connectOutToIn(ringNodes[" + str(j) + "].reqChainOutgoing, ringNodes[" + str(j+1) + "].reqChainIncoming, 0);\n"
                     hr_module_body += "    connectOutToIn(ringNodes[" + str(j) + "].rspChainOutgoing, ringNodes[" + str(j+1) + "].rspChainIncoming, 0);\n"
                 else: # instantiate connectors 
                     connector_idx = [x for x, y in enumerate(hrings) if y.level == clients[j].level][0]
                     ring = hrings[connector_idx]
                     hr_module_body += "    function Bool isChildFunc" + str(connector_idx) + "(t_IDX idx) = (idx <= " + str(ring.maxId) + ") && (idx >= " + str(hrings[0].minId) + ");\n"
                     hr_module_body += "    let connector" + str(connector_idx) + " <- mkServiceRingNode(isChildFunc" + str(connector_idx) + ");\n"
                     hr_module_body += "    connectOutToIn(ringNodes[" + str(j) + "].reqChainOutgoing, connector" + str(connector_idx) + ".clientReqIncoming, 0);\n"
                     if connector_idx == 0: # connector at the maximum level
                         hr_module_body += "    connectOutToIn(connector" + str(connector_idx) + ".clientRspOutgoing, ringNodes[" + str(ring.minId-hrings[0].minId) + "].rspChainIncoming, 0);\n"
                     else:
                         hr_module_body += "    connectOutToIn(connector" + str(connector_idx-1) + ".reqChainOutgoing, connector" + str(connector_idx) + ".reqChainIncoming, 0);\n"
                         hr_module_body += "    connectOutToIn(connector" + str(connector_idx-1) + ".rspChainOutgoing, ringNodes[" + str(ring.minId-hrings[0].minId) + "].rspChainIncoming, 0);\n"
                         hr_module_body += "    connectOutToIn(connector" + str(connector_idx) + ".clientRspOutgoing, connector" + str(connector_idx-1) + ".rspChainIncoming, 0);\n"
            
            # connect the last connector
            hr_module_body += "    connectOutToIn(connector" + str(len(hrings)-2) + ".reqChainOutgoing, ringNodes[" + str(hrings[-1].minId-hrings[0].minId) + "].reqChainIncoming, 0);\n"
            hr_module_body += "    connectOutToIn(connector" + str(len(hrings)-2) + ".rspChainOutgoing, ringNodes[" + str(hrings[-1].minId-hrings[0].minId) + "].rspChainIncoming, 0);\n"
                 
            hr_module_body += "\n    Vector#(" + str(len(clients)) + ", CONNECTION_IN#(SERVICE_CON_DATA_SIZE))  clientReqPortsVec = newVector();\n"
            hr_module_body += "    Vector#(" + str(len(clients)) + ", CONNECTION_OUT#(SERVICE_CON_DATA_SIZE)) clientRspPortsVec = newVector();\n\n"
            hr_module_body += "    for (Integer x = 0; x < " + str(len(clients)) + "; x = x + 1)\n"
            hr_module_body += "    begin\n"
            hr_module_body += "        clientReqPortsVec[x] = (interface CONNECTION_IN#(SERVICE_CON_DATA_SIZE);\n"
            hr_module_body += "                                    method Action try(Bit#(SERVICE_CON_DATA_SIZE) d);\n"
            hr_module_body += "                                        ringNodes[x].clientReqIncoming.try(truncateNP(d));\n"
            hr_module_body += "                                    endmethod\n"
            hr_module_body += "                                    method Bool success = ringNodes[x].clientReqIncoming.success;\n"
            hr_module_body += "                                    method Bool dequeued = ringNodes[x].clientReqIncoming.dequeued;\n"
            hr_module_body += "                                    interface Clock clock = localClock;\n"
            hr_module_body += "                                    interface Reset reset = localReset;\n"
            hr_module_body += "                                endinterface); \n\n"
            hr_module_body += "        clientRspPortsVec[x] = (interface CONNECTION_OUT#(SERVICE_CON_DATA_SIZE);\n"
            hr_module_body += "                                    method Bit#(SERVICE_CON_DATA_SIZE) first();\n"
            hr_module_body += "                                        Tuple2#(t_IDX, t_RSP) tmp = unpack(ringNodes[x].clientRspOutgoing.first());\n"
            hr_module_body += "                                        return zeroExtendNP(tpl_2(tmp));\n"
            hr_module_body += "                                    endmethod\n"
            hr_module_body += "                                    method Action deq = ringNodes[x].clientRspOutgoing.deq;\n"
            hr_module_body += "                                    method Bool notEmpty = ringNodes[x].clientRspOutgoing.notEmpty;\n"
            hr_module_body += "                                    interface clock = localClock;\n"
            hr_module_body += "                                    interface Reset reset = localReset;\n"
            hr_module_body += "                                endinterface);\n"
            hr_module_body += "    end\n\n"
            hr_module_body += "    interface clientReqPorts = clientReqPortsVec;\n"
            hr_module_body += "    interface clientRspPorts = clientRspPortsVec;\n\n"
            hr_module_body += "    interface serverRspPort = interface CONNECTION_IN#(SERVICE_CON_RESP_SIZE);\n"
            hr_module_body += "                                  method Action try(Bit#(SERVICE_CON_RESP_SIZE) d);\n"
            hr_module_body += "                                      Tuple2#(Bit#(SERVICE_CON_IDX_SIZE),Bit#(SERVICE_CON_DATA_SIZE)) tmp = unpack(d);\n"
            hr_module_body += "                                      t_IDX idx = truncateNP(tpl_1(tmp));\n"
            hr_module_body += "                                      t_RSP rsp = truncateNP(tpl_2(tmp));\n"
            hr_module_body += "                                      connector" + str(len(hrings)-2) + ".rspChainIncoming.try(pack(tuple2(idx,rsp)));\n"
            hr_module_body += "                                  endmethod\n"
            hr_module_body += "                                  method Bool success  = connector" + str(len(hrings)-2) + ".rspChainIncoming.success;\n"
            hr_module_body += "                                  method Bool dequeued = connector" + str(len(hrings)-2) + ".rspChainIncoming.dequeued;\n"
            hr_module_body += "                                  interface Clock clock = localClock;\n"
            hr_module_body += "                                  interface Reset reset = localReset;\n"
            hr_module_body += "                              endinterface; \n\n"
            hr_module_body += "    interface serverReqPort = interface CONNECTION_OUT#(SERVICE_CON_DATA_SIZE);\n"
            hr_module_body += "                                  method Bit#(SERVICE_CON_DATA_SIZE) first();\n"
            hr_module_body += "                                      t_REQ req = ringNodes[" + str(len(clients)-1) + "].reqChainOutgoing.first();\n"
            hr_module_body += "                                      return zeroExtendNP(req);\n"
            hr_module_body += "                                  endmethod\n"
            hr_module_body += "                                  method Action deq = ringNodes[" + str(len(clients)-1) + "].reqChainOutgoing.deq;\n"
            hr_module_body += "                                  method Bool notEmpty = ringNodes[" + str(len(clients)-1) + "].reqChainOutgoing.notEmpty;\n"
            hr_module_body += "                                  interface clock = localClock;\n"
            hr_module_body += "                                  interface reset = localReset;\n"
            hr_module_body += "                              endinterface;\n\n"
            hr_module_body += "endmodule\n\n"

        elif platform.networkType == "crossbar":
            bandwidth_bits = 5
            bandwidth_max = max(1, max([x.getBandwidthFraction(i) for x in clients]))
            fileHandle.write("    Vector#(" +  str(len(clients)) + ", Integer) clientIdVec" + str(i) + " = newVector();\n")
            fileHandle.write("    Vector#(" +  str(len(clients)) + ", UInt#(" + str(bandwidth_bits) + ")) bandwidthFractionVec" + str(i) + " = newVector();\n")
            fileHandle.write("    Vector#(" +  str(len(clients)) + ", Bool) priorityVec" + str(i) + " = newVector();\n")
            fileHandle.write("    Vector#(" +  str(len(clients)) + ", CONNECTION_OUT#(SERVICE_CON_DATA_SIZE)) clientReqPortsVec" + str(i) + " = newVector();\n")
            fileHandle.write("    Vector#(" +  str(len(clients)) + ", CONNECTION_IN_WITH_IDX#(SERVICE_CON_DATA_SIZE,SERVICE_CON_IDX_SIZE)) clientRspPortsVec" + str(i) + " = newVector();\n")
            for j, client in enumerate(clients): 
                 fileHandle.write("    clientIdVec" + str(i) + "[" + str(j) + "] = " +  str(client.id) + ";\n")
                 static_fraction = max(1,min(client.getBandwidthFraction(i), int(round(float(client.getBandwidthFraction(i))*(math.pow(2, bandwidth_bits)-1)/bandwidth_max))))
                 if dynBandwidthEn:  
                     fileHandle.write("    Param#(" + str(bandwidth_bits) + ") bandwidthParam" + str(i) + "_" + str(j))
                     fileHandle.write(" <- mkDynamicParameterFromStringInitialized(\"LEAP_SCRATCHPAD_" + client.id + "_CTRL" + str(i) + "_PLATFORM_" + str(platform.id) + "_NETWORK_BANDWIDTH\", " + str(bandwidth_bits) + "'d" + str(static_fraction) + ", paramNode);\n")
                     fraction = "unpack(bandwidthParam" + str(i) + "_" + str(j) + ")"
                     fileHandle.write("    Param#(1) priorityParam" + str(i) + "_" + str(j))
                     fileHandle.write(" <- mkDynamicParameterFromStringInitialized(\"LEAP_SCRATCHPAD_" + client.id + "_CTRL" + str(i) + "_PLATFORM_" + str(platform.id) + "_NETWORK_PRIORITIZED\", 1'd1, paramNode);\n")
                     priority = "(priorityParam" + str(i) + "_" + str(j) + " == 1)"
                 else: 
                     fraction = str(static_fraction)
                     priority = "True"
                 fileHandle.write("    bandwidthFractionVec" + str(i) + "[" + str(j) + "] = " + fraction + ";\n")
                 fileHandle.write("    priorityVec" + str(i) + "[" + str(j) + "] = " + priority + ";\n")
                 if len(client.partition) == 0: # non-interleaved clients
                      client_idx = rClients.index(client)
                      fileHandle.write("    let client" +  str(client_idx) + " <- findMatchingServiceClient(clients, \"" + client.connection.name + "\", \"" + client.id + "\");\n")
                      fileHandle.write("    clientReqPortsVec" + str(i) + "[" + str(j) + "] = client" + str(client_idx) + ".outgoing;\n")
                      fileHandle.write("    clientRspPortsVec" + str(i) + "[" + str(j) + "] = client" + str(client_idx) + ".incoming;\n")
                 else: # interleaved clients 
                      client_idx = pClients.index(client)
                      fileHandle.write("    let connector" + str(client_idx) + "Ctrl" + str(i) + "Req <- mkServiceConnector();\n")
                      fileHandle.write("    let connector" + str(client_idx) + "Ctrl" + str(i) + "Rsp <- mkServiceConnector();\n")
                      fileHandle.write("    clientReqPortsVec" + str(i) + "[" + str(j) + "] = connector" + str(client_idx) + "Ctrl" + str(i) + "Req.outgoing;\n")
                      fileHandle.write("    clientRspPortsVec" + str(i) + "[" + str(j) + "] = convertConnectionInToConnectionInWithIdx(connector" + str(client_idx) + "Ctrl" + str(i) + "Rsp.incoming);\n")
                      req_matching_port = "connector" + str(client_idx) + "Ctrl" + str(i) + "Req.incoming"
                      rsp_matching_port = "connector" + str(client_idx) + "Ctrl" + str(i) + "Rsp.outgoing"
                      client.matchingPorts[i] = (req_matching_port, rsp_matching_port)
            fileHandle.write("    connectManyOutToIn(clientReqPortsVec" + str(i) + ", server" + str(i) + ".incoming, 0, mkLocalArbiterBandwidthWithPriority(bandwidthFractionVec" + str(i) + ", priorityVec" + str(i) + ", True, True));\n")
            fileHandle.write("    connectOutToManyInWithIdx(server" + str(i) + ".outgoing, clientRspPortsVec" + str(i) + ", clientIdVec" + str(i) + ", 0);\n\n")
            
    # connect network modules with services clients
    if len(rClients) > 0 and platform.networkType != "crossbar": 
        fileHandle.write("\n    // Connect non-interleaved service clients\n")
        for k, client in enumerate(rClients): 
            if len(client.remappedIds) == 0:
                remapped_id = client.id
            else: 
                remapped_id = client.remappedIds[client.controllerIdx[0]]
            fileHandle.write("    let client" +  str(k) + " <- findMatchingServiceClient(clients, \"" + client.connection.name + "\", \"" + client.id + "\");\n")
            if fastNetwork: 
                fileHandle.write("    connectOutToInDualClock(client" +  str(k) + ".outgoing, " + client.matchingPorts[client.controllerIdx[0]][0] + ", " + clock_info +  ");\n")
                fileHandle.write("    connectOutToInWithIdxDualClock(" + client.matchingPorts[client.controllerIdx[0]][1] + ", client" + str(k) + ".incoming, " + remapped_id + ", " + clock_info + ");\n\n")
            else: 
                fileHandle.write("    connectOutToIn(client" +  str(k) + ".outgoing, " + client.matchingPorts[client.controllerIdx[0]][0] + ", 0);\n")
                fileHandle.write("    connectOutToInWithIdx(" + client.matchingPorts[client.controllerIdx[0]][1] + ", client" + str(k) + ".incoming, " + remapped_id + ", 0);\n\n")
    
    if len(pClients) > 0:
        fileHandle.write("\n    // Connect interleaved service clients\n")
        for i, client in enumerate(pClients):
            interleave_portions = []
            if interleaveAll:
                equal_portion = (2**interleave_addr_bit)/len(client.partition)
                for c in client.controllerIdx[:len(client.controllerIdx)-1]:
                    fileHandle.write("    Param#(" + str(interleave_addr_bit + 1) + ") interleavePortionParam" + str(i) + "_c" + str(c))
                    fileHandle.write(" <- mkDynamicParameterFromStringInitialized(\"LEAP_SCRATCHPAD_" + client.id + "_CTRL" + str(c))
                    fileHandle.write("_PLATFORM_" + str(platform.id) + "_INTERLEAVE_PORTION\", " + str(interleave_addr_bit + 1) + "'d" + str(equal_portion) + ", paramNode);\n")
                    if len(interleave_portions) > 0: 
                        interleave_portions.append(interleave_portions[-1] + " + pack(interleavePortionParam" + str(i) + "_c" + str(c) + ")")
                    else: 
                        interleave_portions.append("pack(interleavePortionParam" + str(i) + "_c" + str(c) + ")")
                interleave_portions = ["(" + x + ")" for x in interleave_portions]
            else: 
                for j in range(len(client.partition)): 
                    interleave_portions.append(str(int(math.ceil(float(2**addr_bits[i])*sum(client.partition[:j+1])/sum(client.partition)))))
            
            fileHandle.write("    function t_CTRLR_IDX getControllerIdxFromAddr" + str(i) + "(SCRATCHPAD_MEM_ADDRESS addr);\n")
            fileHandle.write("        Bit#(" + str(addr_bits[i])+ ") short_addr = truncate(addr);\n")
            fileHandle.write("        Bit#(" + str(addr_bits[i] + 1) + ") test_addr = zeroExtend(short_addr);\n")
            for j in range(len(client.partition)): 
                if j == 0:
                    fileHandle.write("        if (test_addr < " + interleave_portions[j] + ")\n")
                elif j == (len(client.partition) -1) :
                    fileHandle.write("        else\n")
                else:
                    fileHandle.write("        else if (test_addr < " + interleave_portions[j] + ")\n")
                fileHandle.write("            return unpack(" + str(j) + ");\n")
            fileHandle.write("    endfunction\n\n")
            fileHandle.write("    Vector#(" + str(len(client.partition))+ ", CONNECTION_IN#(SERVICE_CON_DATA_SIZE)) controllerReqPortVec" + str(i) + " = newVector();\n")
            fileHandle.write("    Vector#(" + str(len(client.partition))+ ", CONNECTION_OUT#(SERVICE_CON_DATA_SIZE)) controllerRspPortVec" + str(i) + " = newVector();\n")
            for k, c in enumerate(client.controllerIdx):
                fileHandle.write("    controllerReqPortVec" + str(i) + "[" + str(k) + "] = " + client.matchingPorts[c][0] + ";\n")
                fileHandle.write("    controllerRspPortVec" + str(i) + "[" + str(k) + "] = " + client.matchingPorts[c][1] + ";\n")
            
            if len(client.remappedIds) == 0:
                remapped_id = client.id
            else: 
                remapped_id = client.remappedIds[client.controllerIdx[0]]
            
            fileHandle.write("    let interleaver" + str(i) + " <- mkScratchpadClientInterleaver(controllerReqPortVec" + str(i) + ",")
            if fastNetwork: 
                fileHandle.write(" controllerRspPortVec" + str(i) + ", " + remapped_id + ", getControllerIdxFromAddr" + str(i) + ", True, " + clock_info + ");\n")
            else: 
                fileHandle.write(" controllerRspPortVec" + str(i) + ", " + remapped_id + ", getControllerIdxFromAddr" + str(i) + ", False);\n")
            fileHandle.write("    let client" +  str(i+len(rClients)) + " <- findMatchingServiceClient(clients, \"" + client.connection.name + "\", \"" + client.id + "\");\n")
            if fastNetwork: 
                fileHandle.write("    connectOutToInDualClock(client" +  str(i+len(rClients)) + ".outgoing, interleaver" + str(i) + ".clientReqIncoming, " + clock_info + ");\n")
                fileHandle.write("    connectOutToInWithIdxDualClock(interleaver" + str(i) + ".clientRspOutgoing, client" + str(i+len(rClients)) + ".incoming, " + remapped_id + ", " + clock_info + ");\n\n")
            else: 
                fileHandle.write("    connectOutToIn(client" +  str(i+len(rClients)) + ".outgoing, interleaver" + str(i) + ".clientReqIncoming, 0);\n")
                fileHandle.write("    connectOutToInWithIdx(interleaver" + str(i) + ".clientRspOutgoing, client" + str(i+len(rClients)) + ".incoming, " + remapped_id + ", 0);\n\n")
        
    fileHandle.write("endmodule\n\n")
    fileHandle.write(hr_module_body) 
    fileHandle.close()
    
#
# This function outputs the default remapping function in the bsh wrapper 
#
def createDefaultRemapFile(remapFilePath):
    remapHandle = open(remapFilePath, 'w')
    remapHandle.write("// Generated by build pipeline (lim_memory)\n\n")
    remapHandle.write("`include \"awb/provides/clocks_device.bsh\"\n\n")
    remapHandle.write("module connectScratchpadNetwork#(CLOCKS_DRIVER clocksDriver)();\nendmodule\n\n")
    remapHandle.close()

#
# This function is the top function that handles scratchpad connection remapping
#
def remapScratchpadConnections(liModules, platforms, scratchpadStats, remapMode, treeKary, treeMode, dynBandwidthEn, interleaveAll, statsEn):
    print "remapScratchpadConnections: "
    scratchpadClients = []
    scratchpadServers = []
    nonMemoryConnections = []

    if statsEn == 0: 
        scratchpadStats = []

    for liModule in liModules:
        for service in liModule.services:
            if re.search("^Scratchpad_", service.name):
                if service.isClient():
                    print "Find scratchpad service client: " + service.name + " clientId: " + service.client_idx + " in module: " + service.module_name + " idx: " + service.module_idx + " in platform: " + service.platform()
                    scratchpadClients.append(service)
                else: 
                    print "Find scratchpad service server: " + service.name + " in module: " + service.module_name + " idx: " + service.module_idx + " in platform: " + service.platform()
                    scratchpadServers.append(service)
            else: 
                print "Find non-memory service: " + service.name + " in module: " + service.module_name + " idx: " + service.module_idx + " in platform: " + service.platform()
                nonMemoryConnections.append(service)

    separateScratchpadConnections(scratchpadClients, scratchpadServers, platforms)

    # scratchpad remap is enabled
    if sum([len(x.clients) for x in platforms]) > 0:
        for platform in platforms: 
            print "client ids: " + str([x.id for x in platform.clients]).replace("\'", "")
            partitioned_clients, rest_clients, controllers = assignScratchpadClients(platform.controllers, platform.clients, scratchpadStats, remapMode, (interleaveAll == 1))
            platform.partitionedClients = partitioned_clients 
            platform.restClients = rest_clients
        remapIds = remapClientIds(platforms, remapMode, treeKary, treeMode)
        # print remapIds
        printRemapTable(remapIds)
        print ""
        
    # generate scratchpad service network file
    
    for platform in platforms: 
        if len(platform.clients) > 0: 
            genRemapWrapper(platform, remapIds, (remapMode == 3), (dynBandwidthEn==1), (interleaveAll == 1))
        else:
            createDefaultRemapFile(platform.remapFile)

