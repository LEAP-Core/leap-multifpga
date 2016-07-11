# python libraries
import os

# AWB dependencies
from li_module import LIGraph, LIModule
from fpga_environment_parser import parseFPGAEnvironment
import lim_executable_generator
import lim_graph_generator
import lim_remap_scratchpad

######################################################################
#
#  Latency-insensitive Module Memory Optimizer 
#
######################################################################

class LIMMemory():

    def __init__(self, moduleList, moduleGraph):
        
        def makePlatformConfigPath(name):
            config_dir = 'lim/apm-local/'
            if not os.path.exists(config_dir): os.makedirs(config_dir)
            return config_dir + name
        
        self.moduleList = moduleList
        # Need the FPGA configuration 
        envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENVS')
        if(len(envFile) != 1):
            print "Found more than one environment file: " + str(envFile) + ", exiting\n"
    
        self.environment = parseFPGAEnvironment(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0])
        self.moduleGraph = moduleGraph
        
        APM_FILE = moduleList.env['DEFS']['APM_FILE']
        APM_NAME = moduleList.env['DEFS']['APM_NAME']

        # generate scratchpad connection remapping function
        # remapFilePath = moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + moduleList.topModule.buildPath + '/soft_connection_remap.bsh' 
        # remapHandle = open(remapFilePath, 'w')
        # remapScratchpadConnections(moduleGraph.modules.values(), remapHandle, scratchpadStats) 
        # remapHandle.close();
        print "LIMMemory: dir: " + os.getcwd()
        
        # Collect scratchpad stat file supplied by the user.
        self.scratchpadStats = []
        for statFile in moduleList.getAllDependenciesWithPaths('GIVEN_SCRATCHPAD_STATS'):
            print "scratchpad stat file: " + statFile
            self.scratchpadStats.append(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + statFile)
        
        moduleList.topModule.moduleDependency['FPGA_MEMORY_PARAMETERS'] = []

        self.hwPlatforms= []
        
        for platformName in self.environment.getPlatformNames():
        # these defs are copied from a previous tool.  refactor
            platform = self.environment.getPlatform(platformName)
            platformLogAPMName = lim_graph_generator.makePlatformLogName(platform.name,APM_NAME) + '.apm'
            platformLogPath = makePlatformConfigPath(lim_graph_generator.makePlatformLogName(platform.name,APM_NAME))
            platformLogBuildDir = 'lim/' + lim_graph_generator.makePlatformLogName(platform.name,APM_NAME) + '/pm'

            platformBitfileAPMName = lim_executable_generator.makePlatformBitfileName(platform.name,APM_NAME) + '.apm'
            platformBitfilePath = makePlatformConfigPath(lim_executable_generator.makePlatformBitfileName(platform.name,APM_NAME))
            platformBitfileBuildDir = 'lim/' + lim_executable_generator.makePlatformBitfileName(platform.name,APM_NAME) + '/pm/'

            parameterFile = '?'
            
            if(platform.platformType == 'FPGA' or platform.platformType == 'BLUESIM'):
                 # Generate a default remapping file in log dir to pass the tool check 
                 remapFile = moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/soft_connection_remap.bsh' 
                 lim_remap_scratchpad.createDefaultRemapFile(platformLogBuildDir + '/' + remapFile)
                 # Set dependencies for real output files (in bitfile dir) 
                 parameterFile =  platformBitfileBuildDir +'/'+ remapFile
                 moduleList.topModule.moduleDependency['FPGA_MEMORY_PARAMETERS'] += [parameterFile]
                 self.hwPlatforms.append(lim_remap_scratchpad.ScratchpadPlatform(platform.name, self.environment.getSynthesisBoundaryPlatformID(platform.name), parameterFile))

        subbuild = moduleList.env.Command( 
            moduleList.topModule.moduleDependency['FPGA_MEMORY_PARAMETERS'],        
            moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
            self.optimizeMemory
            )                   
        
        moduleList.topDependency += [subbuild]
        
    def optimizeMemory(self, target, source, env):
        print "LIMMemory: optimizeMemory"
        # generate scratchpad connection remapping function
        REMAP_MODE = self.moduleList.getAWBParam('lim_memory', 'SCRATCHPAD_REMAP_MODE')
        K_ARY = self.moduleList.getAWBParam('lim_memory', 'SCRATCHPAD_REMAP_TREE_K_ARY')
        DYN_BANDWIDTH = self.moduleList.getAWBParam('lim_memory', 'SCRATCHPAD_DYN_BANDWIDTH_ALLOC_EN')
        lim_remap_scratchpad.remapScratchpadConnections(self.moduleGraph.modules.values(), self.hwPlatforms, self.scratchpadStats, REMAP_MODE, K_ARY, DYN_BANDWIDTH) 

