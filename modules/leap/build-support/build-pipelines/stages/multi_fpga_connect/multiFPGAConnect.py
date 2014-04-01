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
from analyzeNetwork import *

class MultiFPGAConnect():

  def __init__(self, moduleList):

      def makePlatformConfigPath(name):
          config_dir = 'multi_fpga/apm-local/'
          if not os.path.exists(config_dir): os.makedirs(config_dir)
          return config_dir + name

      self.unique = 0;
      self.moduleList = moduleList
     
      self.MAX_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MAX_NUMBER_OF_VIAS')
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

      analyzeNetwork(self.moduleList, environmentGraph, platformGraph)
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
              
