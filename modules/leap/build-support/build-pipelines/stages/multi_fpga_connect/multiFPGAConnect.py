# python libraries
import re
import sys
import SCons.Script
import math
import itertools
import cPickle as pickle

# AWB dependencies
from model import  *
from fpga_environment_parser import *
from type_parser import *
from fpgamap_parser import *
from multi_fpga_generate_bitfile import *
from multi_fpga_log_generator import *
from li_module import *

# dependencies from our package 
from via import *
from viaAssignment import *
from linkAssignment import *
from linkType import *
from umfType import *
from umf import *
from taggedUnionCompress import *
from generateCode import *
from activity import *
from routerStats import *

class MultiFPGAConnect():

  def __init__(self, moduleList):

      def makePlatformConfigPath(name):
          config_dir = 'multi_fpga/apm-local/'
          if not os.path.exists(config_dir): os.makedirs(config_dir)
          return config_dir + name

      self.unique = 0;
      self.moduleList = moduleList
      self.ANALYZE_NETWORK = moduleList.getAWBParam('multi_fpga_connect', 'ANALYZE_NETWORK')
      self.MAX_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MAX_NUMBER_OF_VIAS')
      self.ENABLE_AGRESSIVE_UMF_PARAMETERS = moduleList.getAWBParam('multi_fpga_connect', 'ENABLE_AGRESSIVE_UMF_PARAMETERS')
      self.USE_DEFAULT_UMF_PARAMETERS = moduleList.getAWBParam('multi_fpga_connect', 'USE_DEFAULT_UMF_PARAMETERS')
      self.MIN_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MIN_NUMBER_OF_VIAS')

      self.ENABLE_TYPE_COMPRESSION = moduleList.getAWBParam('multi_fpga_connect', 'ENABLE_TYPE_COMPRESSION')
      self.GENERATE_ROUTER_DEBUG = moduleList.getAWBParam('multi_fpga_log_generator', 'GENERATE_ROUTER_DEBUG')
      self.GENERATE_ROUTER_STATS = moduleList.getAWBParam('multi_fpga_log_generator', 'GENERATE_ROUTER_STATS')
      APM_FILE = moduleList.env['DEFS']['APM_FILE']
      APM_NAME = moduleList.env['DEFS']['APM_NAME']
      # Need the FPGA configuration 
      envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENVS')
      if(len(envFile) != 1):
          print "Found more than one environment file: " + str(envFile) + ", exiting\n"
      self.environment = parseFPGAEnvironment(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0])

      mappingFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENV_MAPPINGS')
      if(len(mappingFile) != 1):
          print "Found more than one mapping file: " + str(envFile) + ", exiting\n"
      self.mapping = parseFPGAMap(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + mappingFile[0])

      # we produce some bsh in each platform
      self.platformData = {}
      moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'] = []
      for platformName in self.environment.getPlatformNames():
      # these defs are copied from a previous tool.  refactor
          platform = self.environment.getPlatform(platformName)
          platformLogAPMName = makePlatformLogName(platform.name,APM_NAME) + '.apm'
          platformLogPath = makePlatformConfigPath(makePlatformLogName(platform.name,APM_NAME))
          platformLogBuildDir = 'multi_fpga/' + makePlatformLogName(platform.name,APM_NAME) + '/pm'

          platformBitfileAPMName = makePlatformBitfileName(platform.name,APM_NAME) + '.apm'
          platformBitfilePath = makePlatformConfigPath(makePlatformBitfileName(platform.name,APM_NAME))
          platformBitfileBuildDir = 'multi_fpga/' + makePlatformBitfileName(platform.name,APM_NAME) + '/pm/'

          logs = []

          # We can now have externally generated log files.  find them here.
          if(platform.platformType == 'CPU'):
              print "Base logs for " + platformName + " are : " + str(moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependenciesWithPaths('GIVEN_LOGS'))
              logs += map(lambda path: platformLogBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + path, moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependenciesWithPaths('GIVEN_LOGS'))
              # we also need to look at the program log files. 
              logs += map(lambda path: platformLogBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + path, moduleList.getAllDependenciesWithPaths('GIVEN_LOGS'))
              print "Massaged Logs are : " + str(logs)

          moduleList.topModule.moduleDependency['FPGA_PLATFORM_LOGS'] += logs

          # bsv (FPGA/BLUESIM) builds generate their own log files
          if(platform.platformType == 'FPGA'  or platform.platformType == 'BLUESIM'):
              logs += [platformLogBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/.bsc/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '_Wrapper.log']
          
          print "Final logs are: " + str(logs)

          parameterFile = '?'
          if(platform.platformType == 'FPGA' or platform.platformType == 'BLUESIM'):
               parameterFile =  platformBitfileBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/multifpga_routing.bsh'
          elif(platform.platformType == 'CPU'):
               parameterFile =  platformBitfileBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_SW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/software_routing.h'      

          # We need to build up some context to give bluetcl the right search paths for when
          # we go to inspect the types.  Each platform can have a different hierarchy.
          allModules = [moduleList.topModule] + moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].synthBoundaries() + moduleList.synthBoundaries()
          bluetclPaths = ''

          for boundary in allModules:
              bluetclPaths += platformLogBuildDir + '/hw/' + boundary.buildPath + '/.bsc/:'

          # need ifc as well
          bluetclPaths += platformLogBuildDir + '/iface/build/hw/.bsc/'
          
          platform.putAttribute('HEADER', parameterFile)

          self.platformData[platform.name] = {'LOG': logs, 'HEADER': parameterFile, 'BLUETCL': bluetclPaths, 'DANGLING': [], 'CONNECTED': {}, 'INDEX': {}, 'WIDTHS': {}, 'INGRESS_VIAS': {}, 'EGRESS_VIAS': {}, 'INGRESS_VIAS_PASS_ONE': {}, 'EGRESS_VIAS_PASS_ONE': {}, 'TYPES':{}}


          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'] += [parameterFile] 
 
      subbuild = moduleList.env.Command( 
          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
          moduleList.topModule.moduleDependency['FPGA_PLATFORM_LOGS'] + [moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0]] + [moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + mappingFile[0]] + ['./site_scons/multi_fpga_connect/multiFPGAConnect.py'],
          self.synthesizeRouters
          )                   

      moduleList.topDependency += [subbuild]

  
  # Expands logical paths to physical paths using Djikstras algorithm.
  def connectPath(self, src, sink, platformGraph):

      path = self.environment.getPath(src.platform, sink.platform)

      srcs = [src]
      sinks =[]
      print "Analyzing path: " + str(path)
      for hop in path:
          print "Adding hop: " + src.name + "Hop" + hop        
          #    def __init__(self, sc_type, raw_type, module_idx, name, platform, optional, bitwidth, module_name, type_structure):

          newSink = LIChannel("ChainRoutingRecv", src.raw_type, -1, 
                              src.name + "RoutethroughFrom_" + src.platform + "_To_" + sink.platform + "_Via" + hop, 
                              hop, "False", src.bitwidth, "RouteThrough", "RouteThrough", src.type_structure)
          
          newSink.module_name = hop
          newSink.module = platformGraph.modules[hop]
          sinks.append(newSink)
          platformGraph.modules[hop].addChannel(newSink)

          newSrc = LIChannel("ChainRoutingSend", src.raw_type, -1, 
                             src.name + "RoutethroughFrom_" + src.platform + "_To_" + sink.platform + "_Via" + hop, 
                             hop, "False", src.bitwidth, "RouteThrough", "RouteThrough", src.type_structure)

          newSrc.module_name = hop
          newSrc.module = platformGraph.modules[hop]
          srcs.append(newSrc)
          platformGraph.modules[hop].addChannel(newSrc)

      sinks.append(sink)
    
      # We need to fix the srcs and sinks to point to one another Note
      # that chains and send/recv route-throughs are different.
      for pair in zip(srcs,sinks):
          if(isinstance(pair[0],LIChannel)):
              pair[0].partnerChannel = pair[1]
              pair[0].partnerModule = pair[1].module
              pair[0].matched = True
          else: 
              pair[0].sinkPartnerChain = pair[1]
              pair[0].sinkPartnerModule = pair[1].module
                       
          if(isinstance(pair[1],LIChannel)):
              pair[1].partnerChannel = pair[0]
              pair[1].partnerModule = pair[0].module                    
              pair[1].matched = True
          else:
              pair[1].sourcePartnerChain = pair[0]
              pair[1].sourcePartnerModule = pair[0].module

 
    
  def synthesizeRouters(self, target, source, env):  
      # We should replace this with a call to generate it. 
      environmentGraph = self.environment
      self.parseWidth(environmentGraph)
      moduleGraph = self.parseModuleGraph(environmentGraph)

      # Assign activity factors to all communications channels.
      statsFile = self.moduleList.getAllDependenciesWithPaths('GIVEN_STATS')    
      if(len(statsFile) > 0):
          filename = self.moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + statsFile[0]
          #assignActivity(filename, moduleGraph)

      # Assign modules to platforms.  This yields the platformGraph, a
      # view in which all LIMs have been assigned a platform.
      platformGraph = self.placeModules(environmentGraph, moduleGraph)

      # Route LI channels between platforms.      
      self.routeConnections(platformGraph)

      # Apply compression here. 

      self.analyzeNetwork(environmentGraph, platformGraph)
      generateCode(self.moduleList,environmentGraph, platformGraph)

      # Build backend flow using object code created during the first
      # pass. currenlty not implemented.
 
      # self.constructBitfileBuilds()



  def parseModuleGraph(self, environmentGraph):
      APM_NAME = self.moduleList.env['DEFS']['APM_NAME']
      # Build list of logs.  It might be better if we could directly get the logfile names 
      # from the subbordinate build. 

      subordinateGraphs = []
      for platformName in environmentGraph.getPlatformNames():          
          #open up pickles
          picklePath = makePlatformLogBuildDir(platformName,APM_NAME) + '/' + makePlatformLogName(platformName,APM_NAME) + '.li'
          print "Examining pickle path: " + picklePath + "in " + sys.version +"\n"
          pickleHandle = open(picklePath, 'rb')
          subordinateGraphs.append(pickle.load(pickleHandle))
          pickleHandle.close()
          
      mergedGraph = subordinateGraphs.pop()

      print 'parseModuleGraph base ' + str(mergedGraph) + 'subordinate graphs'
      # merge remaining graphs together 
      for graph in subordinateGraphs:
          print 'parseModuleGraph merging ' + str(graph) + 'subordinate graphs'
          mergedGraph.merge(graph)

      print 'parseModuleGraph found ' + str(mergedGraph) + 'subordinate graphs'

      return mergedGraph
      
  def placeModules(self, environmentGraph, moduleGraph):
      # first we need to map the platform modules to their platform
      for platformName in environmentGraph.getPlatformNames():          
          moduleGraph.modules[platformName].putAttribute('MAPPING', platformName)

      # Pick a mapping algorithm here. We only have one, so we call it directly. 
      self.placeModulesWithMapFile(moduleGraph)

      # now that we have placed the modules, we can build a new view
      # of the system, the platform graph.  In this graph we consider
      # only platforms, and their inter-platform connections.  
      platformConnections = []
      for module in moduleGraph.modules.values():
          platformMapping = module.getAttribute('MAPPING')
          for channel in module.channels:
              print "Mapper Examining Channel: " + channel.name + "\n"
              # it is possible that this channel is unassigned, if so, it is dropped.
              if(channel.partnerChannel == 'unassigned'):
                  continue
              print "Partner channel: " + channel.partnerChannel.name + "\n"
              print "Partner module: " + channel.partnerModule.name + "\n"
              # we only care about inter-FPGA channels
              if(platformMapping == channel.partnerModule.getAttribute('MAPPING')):
                  continue

              print "Placer Examining channel : " + channel.name + " mapped to: " + platformMapping + " partnerModule " + str(channel.partnerModule.name) + "\n"            


              # We don't actually care about specific modules here. We
              # simply re-cast the platforms as the 'modules', with
              # one 'module' per platform.  I wish python had better
              # inheritance support.
              channelCopy = channel.copy()
              channelCopy.module_name = platformMapping
              platformConnections.append(channelCopy)

          for chain in module.chains:
              print "Placer Examining chain : " + chain.name + " mapped to: " + platformMapping + "\n"            
              chainCopy = chain.copy()
              chainCopy.module_name = platformMapping
              platformConnections.append(chainCopy)
              
             
      platformGraph = LIGraph(platformConnections)

      print "Post placement: " + str(platformGraph) + "\n"
      return platformGraph

  def placeModulesWithMapFile(self,moduleGraph):
      for moduleName in moduleGraph.modules:
          # have we already mapped this module?
          if(not moduleName in self.environment.getPlatformNames()):
              moduleObject = moduleGraph.modules[moduleName]   
              moduleObject.putAttribute('MAPPING', self.mapping.getSynthesisBoundaryPlatform(moduleName))
      return moduleGraph

  #First we parse the files, and then attempt to make all the connections.  Lots of dictionaries.
  def routeConnections(self, platformGraph):
      APM_FILE = self.moduleList.env['DEFS']['APM_FILE']
      APM_NAME = self.moduleList.env['DEFS']['APM_NAME']
      
      danglingChainIngresses = {};
      danglingChainEgresses = {};
      for platformName in self.environment.getPlatformNames():
          # we should now check for matches
          for channel in platformGraph.modules[platformName].channels:
              print "Examining Channel " + str(channel.name)
              # For now, we use a simple routing algorithm based on Djikstra.
              if(channel.isSource()):
                  self.connectPath(channel,channel.partnerChannel,platformGraph)         

          for chain in platformGraph.modules[platformName].chains:
              print "Examining Chain " + str(chain.name)
              # build up lists of chains. Ingresses/Egresses occur on each platform.  
              print "Got chain " + chain.name
              if(chain.name in danglingChainIngresses):
                  danglingChainIngresses[chain.name] += [chain]
                  danglingChainEgresses[chain.name] += [chain]
              else:
                  danglingChainIngresses[chain.name] = [chain]
                  danglingChainEgresses[chain.name] = [chain]
                                                           
      # link up the chains.  The algorithm below is suboptimal. 
      # for more complex topologies than the ACP, we will want to 
      # solve a mapping problem 
      # we may want to sort these or something to ensure that we don't form singelton links XXX
      # delete the length 1 chains immediately  -- they live on a single node
      for chainName in danglingChainIngresses.keys():
          if(len(danglingChainIngresses[chainName]) < 2):
              platformGraph.modules[danglingChainIngresses[chainName][0].module_name].deleteChain(chainName)
              del danglingChainIngresses[chainName]
              del danglingChainEgresses[chainName]
              print "Removing single platform chain " + chainName
        
      # Our algorithm here is highly suboptimal.  rotate sinks by one to get an offset list 
      # We assume that the fpga network is strongly connected and that we don't care about transport 
      # lengths.  Bad Bad Bad assumptions, but they work for the ACP
      for chainName in danglingChainIngresses.keys():
          chainIngresses = danglingChainIngresses[chainName]
          chainEgresses = danglingChainEgresses[chainName]
          
          # rotate sinks by one to get an offset list 
          chainEgresses.append(chainEgresses.pop(0))
          for i in range(len(chainEgresses)):
              # we need to make sure the source we pick is not on the same platform.        
              if(chainEgresses[i].module_name == chainIngresses[i].module_name):
                  print "Sink/Src platforms match.  Something is wrong"
                  exit(0)

              print "Trying to pair " + chainIngresses[i].module_name + " and " + chainEgresses[i].module_name + " on chain " + chainName
              self.connectPath(chainIngresses[i],chainEgresses[i], platformGraph)
     
      #unmatched connections at this point are an error. Die.
      if(platformGraph.unmatchedChannels):
          print 'Unmatched channel, terminating ' 
          sys.exit(0)


 
  # In generating router types, we want to minimize the maximum number of chunks
  # In addition to the obvious throughput benefit, it also helps with flowcontrol at the 
  # VC layer, since the VC layer is currently conservative about the buffering and assumes each
  # packet takes the maximum number of chunks
  def generateRouterTypes(self, viaWidth, viaLinks, maxWidth):
    print "Calling generate router types: " + str(viaWidth) + " " + str(viaLinks) + " " + str(maxWidth) +"\n"

    #Should we do whatever umf tells us?
    if(self.USE_DEFAULT_UMF_PARAMETERS):      
        phyReserved = self.moduleList.getAWBParam('umf', 'UMF_PHY_CHANNEL_RESERVED_BITS')
        channelID = self.moduleList.getAWBParam('umf', 'UMF_CHANNEL_ID_BITS')          
        serviceID = self.moduleList.getAWBParam('umf', 'UMF_SERVICE_ID_BITS')          
        methodID  = self.moduleList.getAWBParam('umf', 'UMF_METHOD_ID_BITS')         
        msgLength = self.moduleList.getAWBParam('umf', 'UMF_MSG_LENGTH_BITS')          

        fillerWidth = viaWidth - phyReserved - channelID - serviceID - methodID - msgLength
        print "UMFTYPE using default: " + str(channelID) + "\n"
        return UMFType(channelID, serviceID, methodID, msgLength, phyReserved, fillerWidth, viaWidth)

    # At some point, we can reduce the number of header bits based on 
    # what we actually assign.  This would permit us to allocate smalled link
    links = max([1,int(math.ceil(math.log(viaLinks,2)))])  

    extraChunks = 1
    if(self.ENABLE_AGRESSIVE_UMF_PARAMETERS):
        extraChunks = 0

    # Max chunks depends on filler.  iterate till we get a fixed point.
    # iteration should converge because chunks should monotonically decrease
    # and fillerWidth should monotonically increase
    fillerWidth = -1
    fillerWidthNext = 0
    chunks = -1
    # Method dummy is a hack to support exisiting RRR method functionalities
    methodDummy = 0
    while(fillerWidth != fillerWidthNext):
        fillerWidth = fillerWidthNext
        chunks = extraChunks + int(max([1,math.ceil(math.log(1.0+math.ceil(float(max([0.0, maxWidth - fillerWidth]))/viaWidth),2))]))
        # This is a hack to force RRR UMF type and this UMF type to have similar lengths
        # what this will do is force the generated UMF type to use the same 
        # parameterization as the RRR UMF type.  We get this magic number from the umf, but
        # we should just be using it directly.      
        if(not self.ENABLE_AGRESSIVE_UMF_PARAMETERS):
            methodDummy = max(0,10 - chunks) # negative values make no sense      

        fillerWidthNext = viaWidth - links - chunks - methodDummy

    fillerWidth = fillerWidthNext
    print "Generating " + str(links) + " links " + str(chunks) + " chunks " + str(fillerWidth) + " filler from width " + str(viaWidth) + " calc" + str(1.0+math.ceil(float(max([0.0, maxWidth - fillerWidth]))/viaWidth)) +") max link " + str(maxWidth) + " via links " + str(viaLinks) + " method dummy " + str(methodDummy)
  
    return UMFType(0, links, methodDummy, chunks, 0, fillerWidth, viaWidth)


  # Having a large, conservative header size can cause us to weight 
  # lanes incorrectly during LJF operation.  As a result, we will now 
  # maintain provisional header widths and do a hill climb until we get 
  # feasible header sizes.  This will put much tighter bounds on our header 
  # sizings
  def allocateLJF(self, platformLinks, targetLinks, vias):
      return self.allocateLJFWithHeaders(platformLinks, targetLinks, vias, [1 for via in vias])

  def allocateLJFWithHeaders(self, platformLinks, targetLinks, vias, headers):
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
        umfType = self.generateRouterTypes(vias[via].width, vias[via].links, maxLinkWidth[via])
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
        return self.allocateLJFWithHeaders(platformLinks, targetLinks, viasRollback, headersNext)



  # This code assigns physical indices to the inter-platform connections. 
  def assignLinks(self, provisionalAssignments, provisionalTargetAssignments, platformConnections, targetPlatformConnections):
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



  def analyzeNetwork(self, environmentGraph, platformGraph):
      eval('self.' + self.ANALYZE_NETWORK + '(environmentGraph, platformGraph)')

  def generateViaLJF(self, platform, targetPlatform, environmentGraph, platformGraph):
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
      
      # Gets the partner of the given connection.
      def getPartner(connection):
          if(isinstance(connection, LIChannel)):
              return connection.partnerChannel
          else:
              return connection.sourcePartnerChain

      partnerSortedLinks = map(getPartner, sortedLinks)

      for numberOfVias in range(self.MIN_NUMBER_OF_VIAS,self.MAX_NUMBER_OF_VIAS+1):
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
          [viasProvisional, platformConnectionsProvisional, targetPlatformConnectionsProvisional] = self.allocateLJF(platformConnections, targetPlatformConnections , vias)


          platformConnections = sorted(sortedLinks, key = lambda connection: connection.name)
          targetPlatformConnections = sorted(partnerSortedLinks, key = lambda connection: connection.name)          
     
          if(max([via.load for via in viasProvisional]) < maxLoad or firstAllocationPass):
              print "Better allocation with  " + str(len(viasProvisional)) + " vias found."
              maxLoad = max([via.load for via in viasProvisional])
              viasFinal = viasProvisional
              self.assignLinks(platformConnectionsProvisional, targetPlatformConnectionsProvisional, platformConnections, targetPlatformConnections)

          firstAllocationPass = False

      return viasFinal



  # The general strategy here is 
  # 1) hueristically pick lane widths
  # 2) Assign links to lanes using Longest Job First hueristic
  # Repeat until maximum link occupancy increases (although we might just try repeatedly and keep all the results) 

  def generateViaCombinational(self, platform, targetPlatform):
      firstAllocationPass = True; # We can't terminate in the first pass 
      viaWidthsFinal = [] # at some point, we'll want to derive this. 
      viasFinal = []   
      maxLoad = 0;
      headerSize = 7 # simplifying assumption: headers have uniform size.  This isn't actually the case.

      hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
      egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
      hopToTarget = self.environment.transitTablesOutgoing[targetPlatform][platform]
      ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'

      sortedLinks = sorted(self.platformData[platform]['CONNECTED'][targetPlatform], key = lambda dangling: dangling.activity * -2048 + dangling.bitwidth) # sorted is ascending
        

      for numberOfVias in range(self.MIN_NUMBER_OF_VIAS,self.MAX_NUMBER_OF_VIAS + 1):
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
              platformConnections = sorted(self.platformData[platform]['CONNECTED'][targetPlatform],key = lambda connection: connection.name)
              targetPlatformConnections = sorted(self.platformData[targetPlatform]['CONNECTED'][platform],key = lambda connection: connection.name)

              vias = [ViaAssignment(width, 0, 0) for width in viaWidths]
              [viasProvisional, platformConnectionsProvisional, targetPlatformConnectionsProvisional] = self.allocateLJF(platformConnections, targetPlatformConnections , vias)


              platformConnections = sorted(self.platformData[platform]['CONNECTED'][targetPlatform],key = lambda connection: connection.name)
              targetPlatformConnections = sorted(self.platformData[targetPlatform]['CONNECTED'][platform],key = lambda connection: connection.name)          
            
              if(max([via.load for via in viasProvisional]) < maxLoad or firstAllocationPass):
                  print "Better allocation with  " + str(len(viasProvisional)) + " vias found."
                  maxLoad = max([via.load for via in viasProvisional])
                  viasFinal = viasProvisional
                  self.assignLinks(platformConnectionsProvisional, targetPlatformConnectionsProvisional, platformConnections, targetPlatformConnections)

              firstAllocationPass = False

      print "Combinational returns " + str(viasFinal) + "\n"
      return viasFinal


  def analyzeNetworkNonuniform(self, allocateFunction, environmentGraph, platformGraph):

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

            viasFinal = allocateFunction(platform, targetPlatform, environmentGraph, platformGraph)

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

                umfType = self.generateRouterTypes(viasFinal[via].width, viasFinal[via].links, maxWidth)

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
                umfType = self.generateRouterTypes(egress_first_pass.via_width, egressLinks[platform][targetPlatform][via], maxWidth) 

                egress = Via(platform,targetPlatform,"egress", umfType, egress_first_pass.via_width, egressLinks[platform][targetPlatform][via], egress_first_pass.via_links, egressLinks[platform][targetPlatform][via] - egress_first_pass.via_links, egress_first_pass.via_method, egress_first_pass.via_switch, ingressFlowcontrolAssignment[targetPlatform][platform][via][1], ingressFlowcontrolAssignment[targetPlatform][platform][via][0], viaLoads[platform][targetPlatform][via], umfType.fillerBits)
       
                ingress = Via(targetPlatform,platform,"ingress", umfType, ingress_first_pass.via_width, egressLinks[platform][targetPlatform][via], ingress_first_pass.via_links,  egressLinks[platform][targetPlatform][via] - ingress_first_pass.via_links, ingress_first_pass.via_method, ingress_first_pass.via_switch, ingressFlowcontrolAssignment[targetPlatform][platform][via][1],  ingressFlowcontrolAssignment[targetPlatform][platform][via][0], viaLoads[platform][targetPlatform][via], umfType.fillerBits)

                logicalEgress.append(egress)
                logicalIngress.append(ingress) 

                print "Via pair " + egress_first_pass.via_switch + ": " + str(via) + ' width: '  + str(ingress_first_pass.via_width) + ' links" ' + str(egressLinks[platform][targetPlatform][via])


                print "LogicalEgress: " + str(logicalEgress)
                print "LogicalIngress: " + str(logicalIngress)
        

  def analyzeNetworkComb(self, environmentGraph, platformGraph):
      self.analyzeNetworkNonuniform(self.generateViaCombinational, environmentGraph, platformGraph)

  def analyzeNetworkLJF(self, environmentGraph, platformGraph):
      self.analyzeNetworkNonuniform(self.generateViaLJF, environmentGraph, platformGraph)

  def analyzeNetworkCompletelyRandom(self, environmentGraph, platformGraph):
      self.analyzeNetworkUniform(False, environmentGraph, platformGraph)

  def analyzeNetworkRandom(self, environmentGraph, platformLIGraph):
      self.analyzeNetworkUniform(True, environmentGraph, platformGraph)

  def analyzeNetworkUniform(self, useActivity, environmentGraph, platformGraph):

    # let's do a simple scheme with an equal number of vias.
    numberOfVias = self.MAX_NUMBER_OF_VIAS
 
    for platform in self.environment.getPlatformNames():
        for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
            # instantiate multiplexors - we need one per link chains
            # must necessarily have two links, one in and one out.  We
            # now have two virtual channels for flow control purposes
            # the following code is fairly wrong.  We need to
            # aggregate all virtual channels across a link.  If we
            # don't have a strongly connected FPGA graph, this code
            # will fail miserably XXX
            
            # for this target, we assume that we have a monolithic fifo via.  
            # first, we must decide how to break up the via.  We will store that information
            # and use it later

            # handle the connections themselves
            
            self.platformData[platform]['EGRESS_VIAS'][targetPlatform] = []
            self.platformData[targetPlatform]['INGRESS_VIAS'][platform] = []
                
                                             
            hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
            egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
            hopToTarget = self.environment.transitTablesOutgoing[targetPlatform][platform]
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
            [viasProvisional, platformConnectionsProvisional, targetPlatformConnectionsProvisional] = self.allocateLJF(platformConnections, targetPlatformConnections , vias)
            self.assignLinks(platformConnectionsProvisional, targetPlatformConnectionsProvisional, platformConnections, targetPlatformConnections)
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

                umfType = self.generateRouterTypes(viaWidth, viaLinks, maxWidth)
                
                print "Creating Via " + 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  +str(via) + " : links " + str(viaLinks)
                self.platformData[platform]['EGRESS_VIAS'][targetPlatform].append(Via(platform,targetPlatform,"egress", umfType, viaWidth, viaLinks, viaLinks - 1, 1, hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via) + '_write', 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via), 0, via, 0, umfType.fillerBits))
                self.platformData[targetPlatform]['INGRESS_VIAS'][platform].append(Via(targetPlatform,platform,"ingress", umfType, viaWidth, viaLinks, viaLinks - 1, 1, hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via) + '_read', 'switch_ingress_' + platform + '_from_' + targetPlatform + '_' + hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via), 0, via, 0, umfType.fillerBits)) 
          

  def parseWidth(self, environmentGraph):
      for platformName in environmentGraph.getPlatformNames():
          # we may have several logfiles. Let's combine them together. 
          lines = []

          # XXXX -- This code needs to be refactored to be online. Reading the logs in is a bad idea.
          for infile in self.platformData[platformName]['LOG']:
              logfile = open(infile,'r')
              print "Examining file " + infile
              for line in logfile:
                  lines.append(line)
              logfile.close()
          
          for line in lines:
              # also pull out link widths
              if(re.match('.*SizeOfVia:.*',line)):
                  match = re.search(r'.*SizeOfVia:([^:]+):([^:]+):(\d+)',line)
                  if(match):
                      # match group 1 is a the bluespec name of the
                      # communication device.  We must look up which
                      # platform this device targets.         
                      if(match.group(2) == 'ingress'):
                          environmentGraph.getPlatform(platformName).getIngressByPhysicalName(match.group(1)).width = int(match.group(3))
                      else:
                          environmentGraph.getPlatform(platformName).getEgressByPhysicalName(match.group(1)).width = int(match.group(3))
              
