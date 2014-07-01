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
from lim_executable_generator import *
from lim_graph_generator import *
from li_module import *
from lim_generate_code import *
from lim_common import *
from lim_compression import *
from lim_analyze_network import *
from lim_place_modules import *
from lim_backend_builds import *

# dependencies from our package 
from activity import *


class MultiFPGAConnect():

    def __init__(self, moduleList):

        def makePlatformConfigPath(name):
            config_dir = 'multi_fpga/apm-local/'
            if not os.path.exists(config_dir): os.makedirs(config_dir)
            return config_dir + name

        self.pipeline_debug = getBuildPipelineDebug(moduleList)

        self.unique = 0;
        self.moduleList = moduleList
           
        APM_FILE = moduleList.env['DEFS']['APM_FILE']
        APM_NAME = moduleList.env['DEFS']['APM_NAME']
        # Need the FPGA configuration 
        envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENVS')
        if(len(envFile) != 1):
            print "Found more than one environment file: " + str(envFile) + ", exiting\n"
    
        self.environment = parseFPGAEnvironment(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0])

        # we produce some bsh in each platform
        moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'] = []
        moduleList.topModule.moduleDependency['FPGA_PLATFORM_LOGS'] = []

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
            #if(platform.platformType == 'CPU'):
            #    if(self.pipeline_debug):
            #        print "Base logs for " + platformName + " are : " + str(moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependenciesWithPaths('GIVEN_LOGS'))
            #    logs += map(lambda path: platformLogBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + path, moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependenciesWithPaths('GIVEN_LOGS'))
            #    # we also need to look at the program log files. 
            #    logs += map(lambda path: platformLogBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + path, moduleList.getAllDependenciesWithPaths('GIVEN_LOGS'))
      

            #moduleList.topModule.moduleDependency['FPGA_PLATFORM_LOGS'] += logs

            # bsv (FPGA/BLUESIM) builds generate their own log files
            #if(platform.platformType == 'FPGA'  or platform.platformType == 'BLUESIM'):
            #    # READ Logs from LI graph..
            #    logs += [platformLogBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/.bsc/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '_Wrapper.log']
            
            parameterFile = '?'
            
            liFile = platformBitfileBuildDir + '/lim.li'

            if(platform.platformType == 'FPGA' or platform.platformType == 'BLUESIM'):
                 parameterFile =  platformBitfileBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/multifpga_routing.bsh'
            elif(platform.platformType == 'CPU'):
                 parameterFile =  platformBitfileBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_SW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/software_routing.h'      

            # We need to build up some context to give bluetcl the right search paths for when
            # we go to inspect the types.  Each platform can have a different hierarchy.
            # Really, each platform should be providing this. It's a little ugly for this code
            # be so dependent on bluespec.
            allModules = [moduleList.topModule] + moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].synthBoundaries() + moduleList.synthBoundaries()
            bluetclPaths = ''

            for boundary in allModules:
                bluetclPaths += platformLogBuildDir + '/hw/' + boundary.buildPath + '/.bsc/:'

            # need ifc as well
            bluetclPaths += platformLogBuildDir + '/iface/build/hw/.bsc/'
            
            platform.putAttribute('HEADER', parameterFile)

            moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'] += [parameterFile, liFile] 
    
        mappingFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENV_MAPPINGS')

        subbuildDeps = moduleList.topModule.moduleDependency['PLATFORM_LI'] + [moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0]] + [moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + mappingFile[0]] 

        subbuild = moduleList.env.Command( 
            moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],        
            subbuildDeps,
            self.synthesizeRouters
            )                   

        moduleList.topDependency += [subbuild]

    
    # Expands logical paths to physical paths using Djikstras
    # algorithm to introduce hops across platforms.
    def connectPath(self, src, sink, platformGraph):
       
        path = self.environment.getPath(src.platform(), sink.platform())

        srcs = [src]
        sinks =[]

        if(self.pipeline_debug):
            print "Analyzing path: " + str(path)

        for hop in path:

            if(self.pipeline_debug):
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

   
    # Main compiler routine.  

    # 1) Reads in LI graph dumps from
    # subordinate builds.  Merges these graphs to form a
    # representation of the LI program

    # 2) Decorates graph with feedback about program properties.  This
    # includes channel traffic information and module area usages.

    # 3) Assigns modules to platforms based on physical
    # properties. Alternatively, programmer can provide a direct
    # mapping.
    
    # 4) Routes connections.  Communicating modules may be placed on
    # platforms that are physically distant.  In this phase, we
    # introduce new logical channels that bridge platforms.

    # 5) Construct optimized routers (called analyzeNetwork).  Uses
    # physical information about the platform to build
    # program-specific routers.  Generally tries to do static load
    # balancing.
               
    # 6) Generate Code.  Produces platform-specific routing code
    # source. 

    # 7) Construct bitfiles (unimplemented).  Uses object code
    # produced during the first compilation pass to orchestrate the
    # construction of bitfiles for each FPGA target.

    def synthesizeRouters(self, target, source, env):  
        # We should replace this with a call to generate it. 
        environmentGraph = self.environment

        # Pull all the first pass module representations.
        moduleGraph = self.parseModuleGraph(environmentGraph)

        # Find information about physical graph.
        self.parseWidth(environmentGraph, moduleGraph)

        # Assign activity factors to all communications channels.
        if(self.pipeline_debug):
            print "Module Graph: " + str(moduleGraph) + "\n"
  
        assignActivity(self.moduleList, moduleGraph)

        # Assign modules to platforms.  This yields the platformGraph, a
        # view in which all LIMs have been assigned a platform.
        platformGraph = placeModules(self.moduleList, environmentGraph, moduleGraph)

        # Route LI channels between platforms.      
        self.routeConnections(platformGraph)

        # Apply compression here. 

        analyzeNetwork(self.moduleList, environmentGraph, platformGraph)
 
        if(self.pipeline_debug):
            print "Platform Graph: " + str(platformGraph) + "\n"

        generateCode(self.moduleList,environmentGraph, platformGraph)

        # Build backend flow using object code created during the
        # first pass. The module graph is needed here because it
        # contains the object code from the first pass. 
        constructBackendBuilds(self.moduleList, environmentGraph, platformGraph, moduleGraph)


    # Constructs a graph representation of the complete LI program.
    # Reads in LI Graphs from each language build/object code, merging
    # these together to produce a single LI graph.
    def parseModuleGraph(self, environmentGraph):
        APM_NAME = self.moduleList.env['DEFS']['APM_NAME']
        # Build list of logs.  It might be better if we could directly get the logfile names 
        # from the subbordinate build. 

        subordinateGraphs = []
        # I could also just use the PLATFORM_LIs
        for platformName in environmentGraph.getPlatformNames():          
            #open up pickles
            picklePath = makePlatformLogBuildDir(platformName,APM_NAME) + '/' + makePlatformLogName(platformName,APM_NAME) + '.li'
            pickleHandle = open(picklePath, 'rb')
            subordinateGraphs.append(pickle.load(pickleHandle))
            pickleHandle.close()
            

        mergedGraph = subordinateGraphs.pop()
        
        if(self.pipeline_debug):
            print 'parseModuleGraph base ' + str(mergedGraph) + 'subordinate graphs'

        # merge remaining graphs together 
        if(self.pipeline_debug):
            for graph in subordinateGraphs:
                print 'parseModuleGraph merging ' + str(graph) + 'subordinate graphs'
           
        mergedGraph.merge(subordinateGraphs)

        if(self.pipeline_debug):
            print 'parseModuleGraph found ' + str(mergedGraph) + 'subordinate graphs'

        # now that we've completely merged the graph, we can check for
        # errors and trim optional links.
        mergedGraph.trimOptionalChannels()
        if(mergedGraph.checkUnmatchedChannels()):
            print "Unmatched Channels in : " + str(mergedGraph)

            mergedGraph.dumpUnmatchedChannels()

            exit(1)

        return mergedGraph
        

    # Routes channels between physical platforms.  Uses different
    # strategies depending on the communication class.  LIChannels are
    # routed using a channel-load oblivious Djiskstra's algorithm.
    # LIChains are routed using a by creating a logical chain.
    # Really, we should try to solve a Travelling Salesman Problem for
    # the chains.
    def routeConnections(self, platformGraph):
        APM_FILE = self.moduleList.env['DEFS']['APM_FILE']
        APM_NAME = self.moduleList.env['DEFS']['APM_NAME']
        
        danglingChainIngresses = {};
        danglingChainEgresses = {};
        for platformName in self.environment.getPlatformNames():
            # we should now check for matches
            for channel in platformGraph.modules[platformName].channels:
                if(self.pipeline_debug):
                    print "Examining Channel " + str(channel.name)
                # For now, we use a simple routing algorithm based on Djikstra.
                if(channel.isSource()):
                    self.connectPath(channel,channel.partnerChannel,platformGraph)         

            # build up lists of chains. Ingresses/Egresses occur on each platform.  
            for chain in platformGraph.modules[platformName].chains:
                if(self.pipeline_debug):
                    print "Examining Chain " + str(chain.name)
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
        # we may want to sort these or something to ensure that we don't form singelton links
        # delete the length 1 chains immediately  -- they live on a single node
        for chainName in danglingChainIngresses.keys():
            if(len(danglingChainIngresses[chainName]) < 2):
                platformGraph.modules[danglingChainIngresses[chainName][0].module_name].deleteChain(chainName)
                del danglingChainIngresses[chainName]
                del danglingChainEgresses[chainName]
                if(self.pipeline_debug):
                    print "Removing single platform chain " + chainName
           
        # Our algorithm here is highly suboptimal.  rotate sinks by one to get an offset list 
        # We assume that the fpga network is strongly connected and that we don't care about transport 
        # lengths.  
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

                if(self.pipeline_debug):
                    print "Trying to pair " + chainIngresses[i].module_name + " and " + chainEgresses[i].module_name + " on chain " + chainName
                self.connectPath(chainIngresses[i],chainEgresses[i], platformGraph)
       
        #unmatched connections at this point are an error. Die.
        if(platformGraph.unmatchedChannels):
            print 'Unmatched channel, terminating ' 
            sys.exit(0)
   

    # A routine for gathering information about the physical platform
    # widths.  These widths are dumped during compilation by the
    # various platforms.  This function doesn't really belong here.
    def parseWidth(self, environmentGraph, moduleGraph):
        for platformName in environmentGraph.getPlatformNames():            
            # Get logs for this plaform 
            logs = []
            modules = []
            for module in moduleGraph.modules.values():
                # Only pinned physical platform modules will have width logs.
                if(not module.getAttribute('MAPPING') is None):
                    if(module.getAttribute('MAPPING') == platformName):
                        modules += [module.name]
                        logs += module.getObjectCode('GIVEN_LOGS')
                        logs += module.getObjectCode('GEN_LOGS')
                        
            print "Logs for " + platformName + " are " + str(logs)
            print "Modules for " + platformName + " are " + str(modules)
            for infile in logs:          
                try:
                    logfile = open(infile,'r')
                except FileNotFoundError:
                    # Oops. Didn't find the file. 
                    continue

                for line in logfile:
                    # also pull out link widths
                    matchSize = re.match('.*SizeOfVia:(.*)$',line)
                    if(matchSize):
                        match = re.search(r'([^:]+):([^:]+):(\d+)', matchSize.group(1))
                        if(match):
                            # match group 1 is a the bluespec name of the
                            # communication device.  We must look up which
                            # platform this device targets.         
                            if(match.group(2) == 'ingress'):
                                # sometimes, we encounter a
                                # specification for a physical link
                                # that was not specified in the
                                # environment.  We'll warn on that.
                                if(environmentGraph.getPlatform(platformName).getIngressByPhysicalName(match.group(1)) is None):
                                    print "Warning Unused Physical Link: " + match.group(1)
                                else:
                                    environmentGraph.getPlatform(platformName).getIngressByPhysicalName(match.group(1)).width = int(match.group(3))
                            else:
                                if(environmentGraph.getPlatform(platformName).getEgressByPhysicalName(match.group(1)) is None):
                                    print "Warning Unused Physical Link: " + match.group(1)
                                else:
                                    environmentGraph.getPlatform(platformName).getEgressByPhysicalName(match.group(1)).width = int(match.group(3))
                logfile.close()
   
    
