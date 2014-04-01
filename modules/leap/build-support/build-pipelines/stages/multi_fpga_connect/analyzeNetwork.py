# python libraries
import re
import sys
import copy
import math

# AWB dependencies
from model import  *
from li_module import *

# dependencies from our package 
from via import *
from viaAssignment import *
from linkAssignment import *
from linkType import *
from umfType import *
from umf import *

# Gets the partner of the given connection.
def getPartner(connection):
    if(isinstance(connection, LIChannel)):
        return connection.partnerChannel
    else:
        return connection.sourcePartnerChain

# This code assigns physical indices to the inter-platform connections. 
def assignLinks(provisionalAssignments, provisionalTargetAssignments, platformConnections, targetPlatformConnections):
    # by definition these are sources
    for provisional in provisionalAssignments:
        assigned = False
        for idx in range(len(platformConnections)): # we can probably do better than this n^2 loop. 
            # Watch out for chain Sinks and sources
            print "Examining: " + platformConnections[idx].name + " " + provisional.name
            if(platformConnections[idx].name == provisional.name): 
                assigned = True
                platformConnections[idx].via_idx_egress  = provisional.via_idx
                platformConnections[idx].via_link_egress = provisional.via_link
                print "Assigning egress " + platformConnections[idx].name + ' of type ' + platformConnections[idx].sc_type  +' ' + str(provisional.via_idx) + ' ' + str(provisional.via_link)

        if(not assigned):
            print "failed to assign: " + platformConnections[idx].name +"\n"
            exit(0)

    # by definition these are sinks.
    for provisional in provisionalTargetAssignments:
        assigned = False
        for idx in range(len(targetPlatformConnections)): # we can probably do better than this n^2 loop. 
            # Watch out for chain Sinks and sources
            print "Examining: " + targetPlatformConnections[idx].name + " " + provisional.name
            if(targetPlatformConnections[idx].name == provisional.name):    
                assigned = True
                targetPlatformConnections[idx].via_idx_ingress  = provisional.via_idx
                targetPlatformConnections[idx].via_link_ingress = provisional.via_link

                print "Assigning ingress " + targetPlatformConnections[idx].name + ' of type ' + targetPlatformConnections[idx].sc_type  +' ' + str(provisional.via_idx) + ' ' + str(provisional.via_link)
        if(not assigned):
            print "failed to assign: " + targetPlatformConnections[idx].name +"\n"
            exit(0)





def generateViaLJF(platform, targetPlatform, moduleList, environmentGraph, platformGraph):

    MAX_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MAX_NUMBER_OF_VIAS')
    MIN_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MIN_NUMBER_OF_VIAS')

    print "Allocating vias for " + platform + " -> " + targetPlatform + "\n"
    firstAllocationPass = True; # We can't terminate in the first pass 
    viaWidthsFinal = [] # at some point, we'll want to derive this. 
    viasFinal = []   
    maxLoad = 0;
    headerSize = 12 # simplifying assumption: headers have uniform size.  This isn't actually the case.

    hopFromTarget = environmentGraph.transitTablesIncoming[platform][targetPlatform]
    egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
    hopToTarget = environmentGraph.transitTablesOutgoing[targetPlatform][platform]
    ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'

    moduleLinks = egressChannelsByPartner(platformGraph.modules[platform], targetPlatform) + egressChainsByPartner(platformGraph.modules[platform], targetPlatform)

    sortedLinks = sorted(moduleLinks, key = lambda dangling: dangling.activity * -2048 + dangling.bitwidth) # sorted is ascending
    
    partnerSortedLinks = map(getPartner, sortedLinks)

    for numberOfVias in range(MIN_NUMBER_OF_VIAS, MAX_NUMBER_OF_VIAS+1):
        viaSizingIdx = 0          
        noViasRemaining = 0
        # pick our via links deterministically
        viaWidths = []
        for via in range(numberOfVias):
            # A singleton via doesn't require a valid bit.  This is a software optimization.
            # however, we must repair this assumption if we end up choosing 
            # multiple vias.
              
            if(via == 0):
                viaWidths.append(environmentGraph.getPlatform(platform).getEgress(targetPlatform).width)
            else: # carve off a lane for the longest running jobs
                # If we're selecting the second via, we need to subtract a bit for the first via's 
                # valid bit. We left this bit out of single via routers to optmize software decoding. 
                if(len(viaWidths) == 1):
                    viaWidths[0] = viaWidths[0] - 1

                while(viaWidths[0] < (sortedLinks[viaSizingIdx].bitwidth + 2*(headerSize + 1))): # Give extra for header sizing - the base via should also have space
                    if(viaSizingIdx + 1 == len(sortedLinks)):
                        noViasRemaining = 1
                        print "No suitable vias remain"
                        # we aren't actually going to pick a second via, 
                        # so give back the valid bit to the first via.
                        if(len(viaWidths) == 1):
                            viaWidths[0] = viaWidths[0] + 1
                        break
                    else:
                        viaSizingIdx += 1
      
                # found minimum, ajust the top guy
                if(not noViasRemaining):
                    viaWidths[0] = viaWidths[0] - (sortedLinks[viaSizingIdx].bitwidth + headerSize + 1)
                    viaWidths.append(sortedLinks[viaSizingIdx].bitwidth + headerSize) # need one bit for the header
                    viaSizingIdx += 1
      
        # We've exhausted the supply of feasible vias.
        if(noViasRemaining):
            print "There are no suitable mapping candidates"
            break

        # send/recv pairs had better be matched.
        # so let's match them up
        # need to maintain the sorted order
        print "sortedLinks: " + str(sortedLinks) + "\n"
        print "partnerSortedLinks: " + str(partnerSortedLinks) + "\n"
        platformConnections = sorted(sortedLinks, key = lambda connection: connection.name)
        targetPlatformConnections = sorted(partnerSortedLinks, key = lambda connection: connection.name)

        vias = [ViaAssignment(width, 0, 0) for width in viaWidths]
        [viasProvisional, platformConnectionsProvisional, targetPlatformConnectionsProvisional] = allocateLJF(platformConnections, targetPlatformConnections , vias, moduleList)


        platformConnections = sorted(sortedLinks, key = lambda connection: connection.name)
        targetPlatformConnections = sorted(partnerSortedLinks, key = lambda connection: connection.name)          
   
        if(max([via.load for via in viasProvisional]) < maxLoad or firstAllocationPass):
            print "Better allocation with  " + str(len(viasProvisional)) + " vias found."
            maxLoad = max([via.load for via in viasProvisional])
            viasFinal = viasProvisional
            assignLinks(platformConnectionsProvisional, targetPlatformConnectionsProvisional, platformConnections, targetPlatformConnections)

        firstAllocationPass = False

    return viasFinal

# Having a large, conservative header size can cause us to weight 
# lanes incorrectly during LJF operation.  As a result, we will now 
# maintain provisional header widths and do a hill climb until we get 
# feasible header sizes.  This will put much tighter bounds on our header 
# sizings
def allocateLJF(platformLinks, targetLinks, vias, moduleList):
    return allocateLJFWithHeaders(platformLinks, targetLinks, vias, [1 for via in vias], moduleList)

def allocateLJFWithHeaders(platformLinks, targetLinks, vias, headers, moduleList):
    #first sort the links on both sides
    links = sorted(platformLinks, key = lambda dangling: dangling.activity * -2048 + dangling.bitwidth) # sorted is ascending   
  
    platformConnectionsProvisional = []
    targetPlatformConnectionsProvisional = []
    #since we can recurse, we should copy our inputs
    viasRollback = copy.deepcopy(vias)
    # do I need to rename all the links to be sorted?  Probably...
    maxLinkWidth = [-1 for via in vias]
    for danglingIdx in range(len(links)):           
        #if((links[danglingIdx].sc_type == 'Recv') or (links[danglingIdx].sc_type == 'ChainSink') or (links[danglingIdx].sc_type == 'ChainRoutingRecv')):
        # depending on the width of the vias, and the width of our type we get different loads on different processors
        # need to choose the minimum

        print "\n\n Analyzing   " + links[danglingIdx].name + " of width " + str(links[danglingIdx].bitwidth)  + " raw load: " + str(links[danglingIdx].activity) + "\n"
        
        minIdx = -1 
        minLoad = 0        
        
        for via in range(len(vias)):
            extraChunk = 0
            viaWidth = vias[via].width
            viaLoad = vias[via].load
            headerSize = headers[via] # reserve some space for the header.  we may actually find that this sizing is wrong.
            if(((links[danglingIdx].bitwidth + headerSize )%viaWidth) > 0):
                extraChunk = 1
            chunks = (links[danglingIdx].bitwidth + headerSize )/viaWidth + extraChunk       
            load = links[danglingIdx].activity * chunks + viaLoad
            
            # We don't do a great job here of evaluating opportunity cost.  Picking the longest running on the fastest processor 
            # might be a bad choice.
            if((load < minLoad) or (minIdx == -1)):
                minIdx = via
                minLoad = load
               
        vias[minIdx].load = minLoad

        if(links[danglingIdx].bitwidth > maxLinkWidth[minIdx]):
            maxLinkWidth[minIdx] = links[danglingIdx].bitwidth

        # Build up a provisional mapping of channels to vias. 
        platformConnectionsProvisional.append(LinkAssignment(links[danglingIdx].name, links[danglingIdx].sc_type, minIdx, vias[minIdx].links))

        if(isinstance(links[danglingIdx], LIChannel)):
            targetPlatformConnectionsProvisional.append(LinkAssignment(links[danglingIdx].partnerChannel.name, links[danglingIdx].partnerChannel.sc_type, minIdx, vias[minIdx].links))  
        else: # Dealing with a chain...
            targetPlatformConnectionsProvisional.append(LinkAssignment(links[danglingIdx].sourcePartnerChain.name, links[danglingIdx].sourcePartnerChain.sc_type, minIdx, vias[minIdx].links))  

        print "Assigning Recv " + links[danglingIdx].name   + " Via " + str(minIdx) + " Link " + str(vias[minIdx].links) + " Load " + str(vias[minIdx].load) + "\n"
        print "Vias are " +  str(vias) + "\n"
        vias[minIdx].links += 1

    # check for a legal assignment by verifying that the header types chosen are feasible.
    needRecurse = False
    headersNext = []
    for via in range(len(vias)):
        umfType = generateRouterTypes(vias[via].width, vias[via].links, maxLinkWidth[via], moduleList)
        headerActual = vias[via].width - umfType.fillerBits
        #To ensure termination, we require monotonically increasing
        #header sizes 
        headersNext.append(max([headerActual,headers[via]]))
        if(headers[via] < headerActual):
            needRecurse = True
              
    if(not needRecurse):
        print "NoRecurse Assigned " + str(vias) + "\n"
        return [vias, platformConnectionsProvisional, targetPlatformConnectionsProvisional]
    else:
        print "Recursing with header: " + str(headersNext) + "\n"
        return allocateLJFWithHeaders(platformLinks, targetLinks, viasRollback, headersNext, moduleList)

# The general strategy here is 
# 1) hueristically pick lane widths
# 2) Assign links to lanes using Longest Job First hueristic
# Repeat until maximum link occupancy increases (although we might just try repeatedly and keep all the results) 

def generateViaCombinational(platform, targetPlatform, moduelList, environmentGraph, platformGraph):
    firstAllocationPass = True; # We can't terminate in the first pass 
    viaWidthsFinal = [] # at some point, we'll want to derive this. 
    viasFinal = []   
    maxLoad = 0;
    headerSize = 7 # simplifying assumption: headers have uniform size.  This isn't actually the case.

    hopFromTarget = environmentGraph.transitTablesIncoming[platform][targetPlatform]
    egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
    hopToTarget = environmentGraph.transitTablesOutgoing[targetPlatform][platform]
    ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'

    moduleLinks = egressChannelsByPartner(platformGraph.modules[platform], targetPlatform) + egressChainsByPartner(platformGraph.modules[platform], targetPlatform)

    sortedLinks = sorted(moduleLinks, key = lambda dangling: dangling.activity * -2048 + dangling.bitwidth) # sorted is ascending

    partnerSortedLinks = map(getPartner, sortedLinks)

    MAX_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MAX_NUMBER_OF_VIAS')
    MIN_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MIN_NUMBER_OF_VIAS')      

    for numberOfVias in range(MIN_NUMBER_OF_VIAS, MAX_NUMBER_OF_VIAS + 1):
        viaSizingIdx = 0          
        noViasRemaining = 0
        # pick our via widths deterministically
        # if numberOfVias is 1, we need a special case.  
        viaWidths = [self.platformData[platform]['WIDTHS'][egressVia]]
        viaOptions = [[]] 
        if(numberOfVias > 1):
            viaOptions = itertools.combinations(sortedLinks,numberOfVias - 1) # we always have the base via..

        for allocation in viaOptions:
            if(numberOfVias > 1):
                #is it legal?
                baseViaWidth = self.platformData[platform]['WIDTHS'][egressVia] - (sum(map(lambda x: x.bitwidth, allocation)) + (1+numberOfVias)*(headerSize + 1)) 
                if(baseViaWidth > 0):
                    viaWidths = map(lambda x: x.bitwidth + headerSize, allocation) + [baseViaWidth+headerSize]
                else:
                    continue


            # send/recv pairs had better be matched.
            # so let's match them up
            # need to maintain the sorted order
            platformConnections = sorted(sortedLinks, key = lambda connection: connection.name)
            targetPlatformConnections = sorted(partnerSortedLinks, key = lambda connection: connection.name)

            vias = [ViaAssignment(width, 0, 0) for width in viaWidths]
            [viasProvisional, platformConnectionsProvisional, targetPlatformConnectionsProvisional] = allocateLJF(platformConnections, targetPlatformConnections, vias, moduleList)

            platformConnections = sorted(sortedLinks, key = lambda connection: connection.name)
            targetPlatformConnections = sorted(partnerSortedLinks, key = lambda connection: connection.name)

          
            if(max([via.load for via in viasProvisional]) < maxLoad or firstAllocationPass):
                print "Better allocation with  " + str(len(viasProvisional)) + " vias found."
                maxLoad = max([via.load for via in viasProvisional])
                viasFinal = viasProvisional
                assignLinks(platformConnectionsProvisional, targetPlatformConnectionsProvisional, platformConnections, targetPlatformConnections)

            firstAllocationPass = False

    print "Combinational returns " + str(viasFinal) + "\n"
    return viasFinal


def analyzeNetworkNonuniform(allocateFunction, moduleList, environmentGraph, platformGraph):

    # set up intermediate data structures.  We need a couple of passes to resolve link allocation. 

    # This analysis operates on sources. The sinks on the target
    # platform must be the exact inverse of the sources on this paltform.

    egressViasInitial = {}
    ingressViasInitial = {}

    platforms = environmentGraph.getPlatformNames()
    egressPlatforms = {} # addressable by source platform name

    for sourcePlatform in platforms:
        egressPlatforms[sourcePlatform] = []
        egressViasInitial[sourcePlatform] = {}
        ingressViasInitial[sourcePlatform] = {}

    for sourcePlatform in platforms:
        platformEgresses = environmentGraph.getPlatform(sourcePlatform).getEgresses()
        for egressVia in platformEgresses.keys():  
            egressPlatforms[sourcePlatform].append(platformEgresses[egressVia].endpointName)
            egressViasInitial[sourcePlatform][platformEgresses[egressVia].endpointName] = []
            ingressViasInitial[platformEgresses[egressVia].endpointName][sourcePlatform] = []

    print "Egress Platforms: " + str(egressPlatforms) + "\n"

        
    for platform in environmentGraph.getPlatformNames():
        for targetPlatform in egressPlatforms[platform]:

            # for this target, we assume that we have a monolithic fifo via.  
            # first, we must decide how to break up the via.  We will store that information
            # and use it later

            viasFinal = allocateFunction(platform, targetPlatform, moduleList, environmentGraph, platformGraph)

            headerSize = 7 # simplifying assumption: headers have uniform size.  This isn't actually the case.
            hopFromTarget = environmentGraph.transitTablesIncoming[platform][targetPlatform]
            egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
            hopToTarget = environmentGraph.transitTablesOutgoing[targetPlatform][platform]
            ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'
       
            environmentGraph.getPlatform(platform).egresses[targetPlatform].logicalVias = []
            environmentGraph.getPlatform(targetPlatform).ingresses[platform].logicalVias = []

            logicalEgressInitial = egressViasInitial[platform][targetPlatform]
            logicalIngressInitial = ingressViasInitial[platform][targetPlatform] 


            # We don't yet have information about how to handle flowcontrol
            # But we will fill in the data structure temporarily.  
            # Once all data via assignments have been handeled, we will do flowcontrol.
            for via in range(len(viasFinal)):

                # let's find the maximum width connection so that we calculate the types correctly.
                assignedConnections = egressChannelsByPartner(platformGraph.modules[platform], targetPlatform) + egressChainsByPartner(platformGraph.modules[platform], targetPlatform)
                print "Assigned Connections: " + str(assignedConnections) + "\n"
                viaConnections = filter(lambda connection: connection.via_idx_egress == via, assignedConnections)
                maxWidth = max(map(lambda connection: connection.bitwidth,viaConnections))

                umfType = generateRouterTypes(viasFinal[via].width, viasFinal[via].links, maxWidth, moduleList)

                egress = Via(platform,targetPlatform,"egress", umfType, viasFinal[via].width, viasFinal[via].links, viasFinal[via].links, 0, hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via) + '_write', 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via), -1, -1, viasFinal[via].load, umfType.fillerBits)

                ingress = Via(targetPlatform,platform,"ingress", umfType, viasFinal[via].width, viasFinal[via].links, viasFinal[via].links, 0, hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via) + '_read', 'switch_ingress_' + targetPlatform + '_from_' + platform + '_' + hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via), -1, -1, viasFinal[via].load, umfType.fillerBits)

                logicalEgressInitial.append(egress)
                logicalIngressInitial.append(ingress) 
                print "LogicalEgress: " + str(logicalEgressInitial)
                print "LogicalIngress: " + str(logicalIngressInitial)
                print "Via pair " + egress.via_switch + ": " + str(via) + ' width: '  + str(viasFinal[via].width) + ' links" ' + str(viasFinal[via].links)



    # We finished lane allocation. 
    # Now we need to assign flow control and build the final metadata structures. 
    # We can't do this in the previous loop because the algorithm will select
    # potentially assymetric links for each target.
    ingressFlowcontrolAssignment = {}
    egressLinks = {}
    viaLoads = {}
    for platform in environmentGraph.getPlatformNames():
          ingressFlowcontrolAssignment[platform] = {}
          egressLinks[platform] = {}
          viaLoads[platform] = {}
          for targetPlatform in egressPlatforms[platform]:

              logicalEgress = environmentGraph.getPlatform(platform).egresses[targetPlatform].logicalVias
              logicalIngress = environmentGraph.getPlatform(targetPlatform).ingresses[platform].logicalVias

              # We need to first consider the other platform's ingress.
              # It gets mapped to our egress. XXX This seems buggy? Should local ingress be reversed?
              localIngress = ingressViasInitial[platform][targetPlatform]
              localEgress = egressViasInitial[platform][targetPlatform]


              egressLinks[platform][targetPlatform] = []
              ingressFlowcontrolAssignment[platform][targetPlatform] = []
              viaLoads[platform][targetPlatform] = []
              viaLoadsOld = []
              for via in range(len(localEgress)):
                  egressLinks[platform][targetPlatform].append(localEgress[via].via_links)
                  viaLoads[platform][targetPlatform].append(localEgress[via].via_load)
                  viaLoadsOld.append(localEgress[via].via_load)

              for ingress in localIngress:
                  minIdx = -1 
                  minLoad = 0
                  for via in range(len(localEgress)):
                      extraChunk = 0
                      bitwidth = 8
                      if((bitwidth + headerSize)%localEgress[via].via_width != 0):
                          extraChunk = 1

                      # where did this 128 come from....
                      load = viaLoadsOld[via]/128 * ((bitwidth + headerSize )/localEgress[via].via_width + extraChunk) + viaLoads[platform][targetPlatform][via]
                        
                      # We don't do a great job here of evaluating opportunity
                      # cost.  Picking the longest running on the fastest
                      # processor might be a bad choice.
                      if(load < minLoad or minIdx == -1):
                          minIdx = via
                          minLoad = load
                         
                  viaLoads[platform][targetPlatform][minIdx] = minLoad

                  # after this assignment we can finalize the ingress 
                  ingressFlowcontrolAssignment[platform][targetPlatform].append([minIdx, egressLinks[platform][targetPlatform][minIdx]])
                  print "Assigning Flowcontrol ingress " + ingress.via_method + " to " + egressViasInitial[platform][targetPlatform][minIdx].via_method  + " Idx " + str(minIdx) + " Link " + str(egressLinks[platform][targetPlatform][minIdx]) + "\n"
                  egressLinks[platform][targetPlatform][minIdx] += 1
                    
    #And now we can finally finish the synthesized routers
    for platform in environmentGraph.getPlatformNames():
        for targetPlatform in egressPlatforms[platform]: 
            for via in range(len(egressLinks[platform][targetPlatform])):
                egress_first_pass = egressViasInitial[platform][targetPlatform][via]
                ingress_first_pass = ingressViasInitial[targetPlatform][platform][via]

                logicalEgress = environmentGraph.getPlatform(platform).egresses[targetPlatform].logicalVias
                logicalIngress = environmentGraph.getPlatform(targetPlatform).ingresses[platform].logicalVias

                # let's find the maximum width guy so that we calculate the types correctly. 
                assignedConnections = egressChannelsByPartner(platformGraph.modules[platform], targetPlatform) + egressChainsByPartner(platformGraph.modules[platform], targetPlatform)
                print "Assigned Connections: " + str(assignedConnections) + "\n"
                viaConnections = filter(lambda connection: connection.via_idx_egress == via, assignedConnections)

                # notice that we are not taking in to account the flow
                # control bits here. We might well want to do that at some
                # point.
                maxWidth = max(map(lambda connection: connection.bitwidth, viaConnections)) 


                print "Idx  " + str(via) + " links " + str(len(egressLinks[platform][targetPlatform])) + " loads " + str(len(viaLoads[platform][targetPlatform]))
                umfType = generateRouterTypes(egress_first_pass.via_width, egressLinks[platform][targetPlatform][via], maxWidth, moduleList) 

                egress = Via(platform,targetPlatform,"egress", umfType, egress_first_pass.via_width, egressLinks[platform][targetPlatform][via], egress_first_pass.via_links, egressLinks[platform][targetPlatform][via] - egress_first_pass.via_links, egress_first_pass.via_method, egress_first_pass.via_switch, ingressFlowcontrolAssignment[targetPlatform][platform][via][1], ingressFlowcontrolAssignment[targetPlatform][platform][via][0], viaLoads[platform][targetPlatform][via], umfType.fillerBits)
       
                ingress = Via(targetPlatform,platform,"ingress", umfType, ingress_first_pass.via_width, egressLinks[platform][targetPlatform][via], ingress_first_pass.via_links,  egressLinks[platform][targetPlatform][via] - ingress_first_pass.via_links, ingress_first_pass.via_method, ingress_first_pass.via_switch, ingressFlowcontrolAssignment[targetPlatform][platform][via][1],  ingressFlowcontrolAssignment[targetPlatform][platform][via][0], viaLoads[platform][targetPlatform][via], umfType.fillerBits)

                logicalEgress.append(egress)
                logicalIngress.append(ingress) 

                print "Via pair " + egress_first_pass.via_switch + ": " + str(via) + ' width: '  + str(ingress_first_pass.via_width) + ' links" ' + str(egressLinks[platform][targetPlatform][via])


                print "LogicalEgress: " + str(logicalEgress)
                print "LogicalIngress: " + str(logicalIngress)


def analyzeNetworkComb(moduleList, environmentGraph, platformGraph):
    analyzeNetworkNonuniform(generateViaCombinational, moduleList, environmentGraph, platformGraph)

def analyzeNetworkLJF(moduleList, environmentGraph, platformGraph):
    analyzeNetworkNonuniform(generateViaLJF, moduleList, environmentGraph, platformGraph)

def analyzeNetworkCompletelyRandom(moduleList, environmentGraph, platformGraph):
    analyzeNetworkUniform(False, moduleList, environmentGraph, platformGraph)

def analyzeNetworkRandom(moduleList, environmentGraph, platformLIGraph):
    analyzeNetworkUniform(True, moduleList, environmentGraph, platformGraph)

def analyzeNetworkUniform(useActivity, moduleList, environmentGraph, platformGraph):

    MAX_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MAX_NUMBER_OF_VIAS')
    MIN_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MIN_NUMBER_OF_VIAS')      

    numberOfVias = MAX_NUMBER_OF_VIAS
 
    for platform in environmentGraph.getPlatformNames():
        for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
            # instantiate multiplexors - we need one per link chains
            # must necessarily have two links, one in and one out.  We
            # now have two virtual channels for flow control purposes
            # the following code is fairly wrong.  We need to
            # aggregate all virtual channels across a link.  If we
            # don't have a strongly connected FPGA graph, this code
            # will fail miserably.
            
            # for this target, we assume that we have a monolithic fifo via.  
            # first, we must decide how to break up the via.  We will store that information
            # and use it later

            # handle the connections themselves
            
            self.platformData[platform]['EGRESS_VIAS'][targetPlatform] = []
            self.platformData[targetPlatform]['INGRESS_VIAS'][platform] = []
                
                                             
            hopFromTarget = environmentGraph.transitTablesIncoming[platform][targetPlatform]
            egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
            hopToTarget = environmentGraph.transitTablesOutgoing[targetPlatform][platform]
            ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'

            # send/recv pairs had better be matched.
            # We want the slower chains to be evenly dispersed across the randomly assigned links
            platformConnections = self.platformData[platform]['CONNECTED'][targetPlatform]
            targetPlatformConnections = self.platformData[targetPlatform]['CONNECTED'][platform]
            #special case handling of single via instance
            viaWidth = self.platformData[platform]['WIDTHS'][egressVia]
            if(numberOfVias > 1):
                viaWidth = (self.platformData[platform]['WIDTHS'][egressVia] - numberOfVias) / numberOfVias
            
            #We already assign the flow control link to zero, so we must initialize the 
            #via assignment to have one link already gone
            vias = [ViaAssignment(viaWidth, 0, 1) for via in range(numberOfVias)]
            [viasProvisional, platformConnectionsProvisional, targetPlatformConnectionsProvisional] = allocateLJF(platformConnections, targetPlatformConnections , vias, moduleList)
            assignLinks(platformConnectionsProvisional, targetPlatformConnectionsProvisional, platformConnections, targetPlatformConnections)
            # Now that we have an assignment of links, we can calculate the via types. 
            # We're dropping some bits here
            # this loop should be refactored to split ingress and egress
            # we need to reserve space for valid bits
            for via in range(numberOfVias):
                # need to set the via widths here...
                viaLinks = viasProvisional[via].links
                print "Uniform Via " + str(via) + " links " + str(viasProvisional[via].links)
                # let's find the maximum width guy so that we calculate the types correctly. 
                viaConnections = filter(lambda connection: connection.via_idx == via,self.platformData[platform]['CONNECTED'][targetPlatform])
                maxWidth = viaWidth
                if(len(viaConnections) > 0):
                    # notice that we are not taking in to account the flow control bits here. We might well want to do that at some point. 
                    maxWidth = max(map(lambda connection: connection.bitwidth,viaConnections))

                umfType = generateRouterTypes(viaWidth, viaLinks, maxWidth, moduleList)
                
                print "Creating Via " + 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  +str(via) + " : links " + str(viaLinks)
                self.platformData[platform]['EGRESS_VIAS'][targetPlatform].append(Via(platform,targetPlatform,"egress", umfType, viaWidth, viaLinks, viaLinks - 1, 1, hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via) + '_write', 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via), 0, via, 0, umfType.fillerBits))
                self.platformData[targetPlatform]['INGRESS_VIAS'][platform].append(Via(targetPlatform,platform,"ingress", umfType, viaWidth, viaLinks, viaLinks - 1, 1, hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via) + '_read', 'switch_ingress_' + platform + '_from_' + targetPlatform + '_' + hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via), 0, via, 0, umfType.fillerBits)) 
          

def analyzeNetwork(moduleList, environmentGraph, platformGraph):
    ANALYZE_NETWORK = moduleList.getAWBParam('multi_fpga_connect', 'ANALYZE_NETWORK')
    eval(ANALYZE_NETWORK + '(moduleList, environmentGraph, platformGraph)')
