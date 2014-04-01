import re
import sys
import SCons.Script
from fpga_environment_parser import *
from fpgamap_parser import *
from model import  *


def makePlatformBitfileName(name, apm):
    return name +'_'+ apm + '_multifpga_bitfile'

class MultiFPGAGenerateBitfile():

    def __init__(self, moduleList):

        self.pipeline_debug = getBuildPipelineDebug(moduleList)

        def makePlatformConfigPath(name):
            config_dir = 'multi_fpga/apm-local/'
            if not os.path.exists(config_dir): os.makedirs(config_dir)
            return config_dir + name

        # we should always be building these things
        # looks a lot like the log file generation, but with different params.  We should refactor
        APM_FILE = moduleList.env['DEFS']['APM_FILE']
        APM_NAME = moduleList.env['DEFS']['APM_NAME']
        applicationRootName = APM_NAME  + '_mutlifpga_connected_application'
        applicationName = applicationRootName + '.apm'
        applicationPath =  makePlatformConfigPath(applicationName)
        mappingRootName = APM_NAME  + '_mutlifpga_mapping'
        mappingName = mappingRootName + '.apm'
        mappingPath =  makePlatformConfigPath(mappingName)
        environmentRootName = APM_NAME  + '_multifpga_environment'
        environmentName = environmentRootName + '.apm'
        environmentPath =  makePlatformConfigPath(environmentName)

        def makePlatformBuildDir(name):
            return 'multi_fpga/' + makePlatformBitfileName(name,APM_NAME) + '/pm'

        def makePlatformDictDir(name):
            return makePlatformBuildDir(name) + '/iface/src/dict'

        def makePlatformRRRDir(name):
            return makePlatformBuildDir(name) + '/iface/src/rrr'

        envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENV_MAPPINGS')
        if(len(envFile) != 1):
            print "Found more than one mapping file: " + str(envFile) + ", exiting\n"

        self.mapping = parseFPGAMap(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0])

      
        envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENVS')
        if(len(envFile) != 1):
            print "Found more than one environment file: " + str(envFile) + ", exiting\n"

        self.environment = parseFPGAEnvironment(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0])

        def compile_closure(platform):

             def compile_platform_log(target, source, env):

                 platformAPMName = makePlatformBitfileName(platform.name,APM_NAME) + '.apm'
                 platformPath = makePlatformConfigPath(platformAPMName)
                 platformBuildDir = makePlatformBuildDir(platform.name)

                 ##
                 ## Did the user specify a command to compile the bitfiles as an
                 ## argument?  If not, construct a scons command.
                 ##
                 compile_cmd = moduleList.arguments.get('MULTIFPGA_BITFILE_COMPILE_CMD', None)
                 if compile_cmd == None:
                     # Compute the build options
                     compile_cmd = 'scons'
                     compile_cmd += ' DEBUG=1' if getDebug(moduleList) else ' OPT=1'
                     compile_cmd += ' TRACE=' + str(getTrace(moduleList))
                     compile_cmd += ' EVENTS=' + str(getEvents(moduleList))

                 compile_cmd = 'cd ' + platformBuildDir + '; ' + compile_cmd
       
                 sts = execute(compile_cmd)
                 
                 return sts
             return compile_platform_log

        moduleList.topModule.moduleDependency['FPGA_PLATFORM_BITFILES'] = []

        # now that we know what the structure of the design, we can write to the config file
        configFile = open("config/platform_env.sh","w");


        # the stuff below here should likely go in a different file, and there will be many hard-coded paths
        # copy the environment descriptions to private 
        #APM_FILE
        #WORKSPACE_ROOT
        platformMetadata = []
        
        for platformName in self.environment.getPlatformNames():
            platform = self.environment.getPlatform(platformName)
            platformType = platform.platformType
            platformAPMBaseName = makePlatformBitfileName(platform.name,APM_NAME)
            platformAPMName = platformAPMBaseName + '.apm'
            platformPath = makePlatformConfigPath(platformAPMName)
            platformBuildDir = makePlatformBuildDir(platform.name)
            bitfile = platformBuildDir + '/' + moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/.xilinx/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '_'


            #sprinkle breadcrumbs in config file
            master = 0

            if(platform.master):
                master = 1

            # in legacy multifpga compiles, master refers to the platform with the CPU attached. 
            # to maintain compatibility, we inject a pointer to the CPU in this case.
            if(master):
                platformMetadata.append('{"name" =>"' + makePlatformBitfileName(platform.name,APM_NAME) + '", "type" => "CPU"' + \
                                        ', "directory" => "' + platformBuildDir + '", "master" => "0" , "logicalName" => "CPU0"}')
          
            platformMetadata.append('{"name" =>"' + makePlatformBitfileName(platform.name,APM_NAME) + '", "type" => "' + platformType + \
                                    '", "directory" => "' + platformBuildDir + '", "master" => "' + str(platform.master) + \
                                    '", "logicalName" => "' + platform.name + '"}')

            execute('asim-shell --batch cp ' + platform.path +" "+ platformPath)        
            execute('asim-shell --batch replace module ' + platformPath + ' ' + applicationPath)
            execute('asim-shell --batch replace module ' + platformPath + ' ' + mappingPath)
            execute('asim-shell --batch replace module ' + platformPath + ' ' + environmentPath)


            # and now we can build them
            # what we want to gather here is dangling top level connections
            # so we should depend on the model log
            # Ugly - we need to physically reconstruct the apm path
            # set the fpga parameter
            # for the first pass, we will ignore mismatched platforms
            execute('asim-shell --batch set parameter ' + platformPath + ' FPGA_PLATFORM_ID ' + str((self.environment.getSynthesisBoundaryPlatformID(platform.name))))
            execute('asim-shell --batch set parameter ' + platformPath + ' FPGA_PLATFORM_NAME \\"' + platform.name + '\\"')
            execute('asim-shell --batch set parameter ' + platformPath + ' FPGA_NUM_PLATFORMS ' + str(len(self.environment.getPlatformNames())))
            execute('asim-shell --batch set parameter ' + platformPath + ' CON_CWIDTH ' +  str(moduleList.getAWBParam('multi_fpga_log_generator', 'SOFT_CONN_CWIDTH')))
            execute('asim-shell --batch set parameter ' + platformPath + ' CON_CHAIN_CWIDTH ' +  str(moduleList.getAWBParam('multi_fpga_log_generator', 'SOFT_CONN_CWIDTH')))
            execute('asim-shell --batch set parameter ' + platformPath + ' EXPOSE_ALL_CONNECTIONS 0 ')
            execute('asim-shell --batch set parameter ' + platformPath + ' IGNORE_PLATFORM_MISMATCH 0 ')
            execute('asim-shell --batch set parameter ' + platformPath + ' BUILD_LOGS_ONLY 0 ')
            execute('asim-shell --batch set parameter ' + platformPath + ' USE_ROUTING_KNOWN 1 ')    





            # Dictionaries are global.  Therefore, all builds must see the same context or bad things 
            # will happen.   
            platformDicts = moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependencies('GIVEN_DICTS')   
            missingDicts = ":".join([dict for dict in moduleList.topModule.moduleDependency['MISSING_DICTS'].keys() if not dict in platformDicts])

            # RRRs can appear in services sometimes and thereby lack global 
            # visibility.  We need to treat them in the same way we treat dictionaries. 
            platformRRRs = moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependenciesWithPaths('GIVEN_RRRS')     
            missingRRRs = ":".join([rrr for rrr in moduleList.topModule.moduleDependency['MISSING_RRRS'].keys() if not rrr in platformRRRs])

            execute('asim-shell --batch set parameter ' + platformPath + ' EXTRA_DICTS \\"' + missingDicts  + '\\"')
            execute('asim-shell --batch set parameter ' + platformPath + ' EXTRA_RRRS \\"' + missingRRRs  + '\\"')                      
            execute('asim-shell --batch set parameter ' + platformPath + ' CLOSE_CHAINS 1 ')

            if not os.path.exists(platformBuildDir): os.makedirs(platformBuildDir) 

            execute('asim-shell --batch -- configure model ' + platformPath + ' --builddir ' + platformBuildDir)

            # set up the symlinks to missing dictionaries- they are broken
            # at first, but as we fill in the platforms, they'll come up
            for dict in moduleList.topModule.moduleDependency['MISSING_DICTS'].keys():
                if(not dict in platformDicts):
                    # lexists works on broken symlinks...
                    path = os.getcwd()
                    dictPath = os.path.realpath(makePlatformDictDir(moduleList.topModule.moduleDependency['MISSING_DICTS'][dict]) + '/' + dict)
                    linkDir  = makePlatformDictDir(platform.name)  
                    linkPath = linkDir  + '/' + dict
                    relDictPath = relpath(dictPath, linkDir)
                    if(os.path.lexists(linkPath)):
                        print("This symlink already exists: " + makePlatformDictDir(platform.name)  + '/' + dict)
                    else:
                        os.symlink(relDictPath, linkPath)
            
            # do the same for missing RRRs - this code is similar to that above and should be refactored. 
            for rrr in moduleList.topModule.moduleDependency['MISSING_RRRS'].keys():
                if(not rrr in platformRRRs):
                    # lexists works on broken symlinks...
                    path = os.getcwd()
                    if(os.path.lexists(makePlatformRRRDir(platform.name)  + '/' + rrr)):
                        print("This symlink already exists: " + makePlatformRRRDir(platform.name)  + '/' + rrr)
                    else:
                        rrrPath = os.path.realpath( makePlatformRRRDir(moduleList.topModule.moduleDependency['MISSING_RRRS'][rrr]) + '/' + rrr)
                        #the rrr values have some hierarchical information in them...
                        linkPath  = makePlatformRRRDir(platform.name)  + '/' + rrr
                        linkDir = os.path.dirname(linkPath)
                        os.symlink(relpath(rrrPath, linkDir), linkPath)
                  
            strfile = os.getcwd() + '/' + platformBuildDir + '/.bsc/' + platformAPMBaseName + '.str'
            # this dependency on platform logs is coarse.  we could do better, but it may not be necessary
            subbuild = moduleList.env.Command( 
                [bitfile, strfile],
                moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
                compile_closure(platform)
                )                   
            moduleList.topModule.moduleDependency['FPGA_PLATFORM_BITFILES'] += [bitfile] 

          # Dynamic parameters are global, and each platform may have a few
          # dynamic parameters.  First we read in the dynamic parameters of
          # each platform, which are produced at configuration time (above)
          # Then, we build a representation of all dynamic parameters, and
          # then overwrite the dynamic parameters of each subordinate build.
        
        dynamicParamsSet = set() # Use set properties to eliminate duplicates
        for platformName in self.environment.getPlatformNames():
            platform = self.environment.getPlatform(platformName)
            platformBuildDir = makePlatformBuildDir(platform.name)
            paramsFile = os.getcwd() + '/' + platformBuildDir + '/iface/src/dict/dynamic_params.dic'
            paramsHandle = open(paramsFile, 'r')
            for line in paramsHandle.readlines():
                dynamicParamsSet.add(line)
        
        # now we overwrite the old files. 
        for platformName in self.environment.getPlatformNames():
            platform = self.environment.getPlatform(platformName)
            platformBuildDir = makePlatformBuildDir(platform.name)
            paramsFile = os.getcwd() + '/' + platformBuildDir + '/iface/src/dict/dynamic_params.dic'
            paramsHandle = open(paramsFile, 'w')
            for line in dynamicParamsSet:
                paramsHandle.write(line)
        
               
        # END for platform
        configFile.write('platforms=['+ ",".join(platformMetadata) +']\n')
        configFile.close()
        # each platform can have a different strings file.  Let's cat all the strings files together...
        # because the hash signatures are unique we can be quite sloppy in this.
        strlist = []
        for platformName in self.environment.getPlatformNames():
            platform = self.environment.getPlatform(platformName)
            platformAPMBaseName = makePlatformBitfileName(platform.name,APM_NAME)
            platformBuildDir = makePlatformBuildDir(platform.name)
            strfile = os.getcwd() + '/' + platformBuildDir + '/.bsc/' + platformAPMBaseName + '.str'

            # CPUs don't have strings (maybe they should?)
            if(platform.platformType == 'FPGA' or platform.platformType == 'BLUESIM'):
                strlist.append(strfile)
        
        # not all top-level targets produce bitfiles.
        moduleList.topDependency += moduleList.topModule.moduleDependency['FPGA_PLATFORM_BITFILES']
        
