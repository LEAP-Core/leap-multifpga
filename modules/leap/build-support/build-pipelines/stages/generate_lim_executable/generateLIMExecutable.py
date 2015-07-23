import os
import subprocess
import re
import sys
import SCons.Script

import model
import lim_graph_generator
from fpga_environment_parser import parseFPGAEnvironment
from fpgamap_parser import parseFPGAMap

def makePlatformBitfileName(name, apm):
    return name +'_'+ apm + '_lim_bitfile'

class GenerateLIMExecutable():

    def __init__(self, moduleList):

        self.pipeline_debug = model.getBuildPipelineDebug(moduleList)

        def makePlatformConfigPath(name):
            config_dir = 'lim/apm-local/'
            if not os.path.exists(config_dir): os.makedirs(config_dir)
            return config_dir + name

        # we should always be building these things
        # looks a lot like the log file generation, but with different params.  We should refactor
        APM_FILE = moduleList.env['DEFS']['APM_FILE']
        APM_NAME = moduleList.env['DEFS']['APM_NAME']
        applicationRootName = APM_NAME  + '_lim_connected_application'
        applicationName = applicationRootName + '.apm'
        applicationPath =  makePlatformConfigPath(applicationName)
        mappingRootName = APM_NAME  + '_lim_mapping'
        mappingName = mappingRootName + '.apm'
        mappingPath =  makePlatformConfigPath(mappingName)
        environmentRootName = APM_NAME  + '_lim_environment'
        environmentName = environmentRootName + '.apm'
        environmentPath =  makePlatformConfigPath(environmentName)

        def makePlatformBuildDir(name):
            return 'lim/' + makePlatformBitfileName(name,APM_NAME) + '/pm'

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

        def compile_closure_executable(platform):

             def compile_platform_executable(target, source, env):

                 platformAPMName = makePlatformBitfileName(platform.name,APM_NAME) + '.apm'
                 platformPath = makePlatformConfigPath(platformAPMName)
                 platformBuildDir = makePlatformBuildDir(platform.name)

                 ##
                 ## Did the user specify a command to compile the bitfiles as an
                 ## argument?  If not, construct a scons command.
                 ##
                 compile_cmd = moduleList.arguments.get('MULTIFPGA_BITFILE_COMPILE_CMD', None)
                 if (compile_cmd == None):
                     # Compute the build options
                     compile_cmd = 'scons'

                     if (moduleList.getAWBParam('lim_executable_generator', 'ENABLE_SCONS_CACHING_DEBUG_EXECUTABLE')):
                         compile_cmd += ' --cache-show --cache-debug=' + os.path.abspath(makePlatformConfigPath('debug_'+platform.name))

                     compile_cmd += " " + moduleList.getAWBParam('lim_graph_generator', 'BUILD_PARAMETERS') + " "
                     
                     if(moduleList.getAWBParam('lim_executable_generator', 'ENABLE_SCONS_PROFILING_EXECUTABLE')):
                         compile_cmd += ' --profile=' + os.path.abspath(makePlatformConfigPath('profile_backend_'+platform.name))

                     compile_cmd += ' ' + ' '.join(['%s="%s"' % (key, value) for (key, value) in moduleList.arguments.items()])

                 compile_cmd = 'cd ' + platformBuildDir + '; ' + compile_cmd
                 compile_cmd += ' LIM_BUILD_DIR=' + platformBuildDir

                 # set environment for scons caching
                 if (moduleList.getAWBParam('lim_executable_generator', 'ENABLE_SCONS_CACHING_EXECUTABLE')):
                     compile_cmd += ' LEAP_BUILD_CACHE_DIR=' + os.path.abspath(makePlatformConfigPath('codeCache' + platform.name))

                 sts = model.execute(compile_cmd)
                 
                 # Check for non-fatal failures, communicated using an error file.
                 if (sts == 0):
                     try:
                         errinfo_file = platformBuildDir + '/' + \
                                        makePlatformBitfileName(platform.name, APM_NAME) + \
                                        '_hw.errinfo'
                         if os.stat(errinfo_file).st_size > 0:
                             print "Non-fatal error: " + errinfo_file
                             # Note error at end of build
                             model.nonFatalFailures.append(errinfo_file)
                     except OSError:
                         # Assume no error if errinfo file not found
                         pass

                 return sts
             return compile_platform_executable

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

            awbBatchFile = 'config/' + platformName + '.exec.batch'
            need_config = not os.path.isdir(platformBuildDir)
            if (need_config):
                awbBatchHandle = open(awbBatchFile, 'w')
            else:
                awbBatchHandle = open(os.devnull, 'w')

            #sprinkle breadcrumbs in config file
            master = 0
            if (platform.master):
                master = 1

            # in legacy multifpga compiles, master refers to the platform with the CPU attached. 
            # to maintain compatibility, we inject a pointer to the CPU in this case.
            if (master):
                # For legacy builds, software is generated during the first pass of compilation. 
                platformLogBuildDir = lim_graph_generator.makePlatformLogBuildDir(platform.name, APM_NAME)
                platformMetadata.append('{"name" =>"' + lim_graph_generator.makePlatformLogName(platform.name,APM_NAME) + '", "type" => "CPU"' + \
                                        ', "directory" => "' + platformLogBuildDir + '", "master" => "0" , "logicalName" => "CPU0"}')
          
            platformMetadata.append('{"name" =>"' + makePlatformBitfileName(platform.name,APM_NAME) + '", "type" => "' + platformType + \
                                    '", "directory" => "' + platformBuildDir + '", "master" => "' + str(platform.master) + \
                                    '", "logicalName" => "' + platform.name + '"}')

            awbBatchHandle.write('cp ' + platform.path +" "+ platformPath + '\n')        
            
            # For software builds, we don't bother with the object
            # code flow -- software compiles quickly, so the flow is
            # not necessary at this time.
            if (platform.platformType == 'CPU'):
                awbBatchHandle.write('replace module ' + platformPath + ' ' + applicationPath + '\n')

            # and now we can build them
            # what we want to gather here is dangling top level connections
            # so we should depend on the model log
            # Ugly - we need to physically reconstruct the apm path
            # set the fpga parameter
            # for the first pass, we will ignore mismatched platforms
            awbBatchHandle.write(' set parameter ' + platformPath + ' FPGA_PLATFORM_ID ' + str((self.environment.getSynthesisBoundaryPlatformID(platform.name)))  + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' FPGA_PLATFORM_NAME \\"' + platform.name + '\\"' + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' FPGA_NUM_PLATFORMS ' + str(len(self.environment.getPlatformNames()))  + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' CON_CWIDTH ' +  str(moduleList.getAWBParam('lim_graph_generator', 'SOFT_CONN_CWIDTH'))  + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' CON_CHAIN_CWIDTH ' +  str(moduleList.getAWBParam('lim_graph_generator', 'SOFT_CONN_CWIDTH'))  + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' EXPOSE_ALL_CONNECTIONS 0 ' + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' BUILD_PLATFORM_MODULES 0 ' + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' BUILD_LOGS_ONLY 0 ' + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' USE_BVI 1 ' + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' USE_ROUTING_KNOWN 1 ' + '\n')    
            awbBatchHandle.write(' set parameter ' + platformPath + ' MODULE_UID_OFFSET ' + str(moduleList.topModule.moduleDependency['MODULE_UID_OFFSET']) + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' SOFT_CONNECTION_REMAP 1 ' + '\n')    

            # Platforms may have their own parameter sets. 
            for parameter in platform.parameters:
                awbBatchHandle.write('set parameter ' + platformPath + ' ' + parameter + ' ' + platform.parameters[parameter].getAWBRepresentation() + '\n')

            moduleList.topModule.moduleDependency['MODULE_UID_OFFSET'] += len(moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].synthBoundaries())
            

            # Dictionaries are global.  Therefore, all builds must see the same context or bad things 
            # will happen.   
            platformDicts = moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependencies('GIVEN_DICTS')
            missingDicts = ":".join([dictionary for dictionary in moduleList.topModule.moduleDependency['MISSING_DICTS'].keys() if not dictionary in platformDicts])

            # RRRs can appear in services sometimes and thereby lack global 
            # visibility.  We need to treat them in the same way we treat dictionaries. 
            platformRRRs = moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependenciesWithPaths('GIVEN_RRRS') 
            missingRRRs = ":".join([rrr for rrr in moduleList.topModule.moduleDependency['MISSING_RRRS'].keys() if not rrr in platformRRRs])


            # Compiling IFACE requires extra context. 
            incPaths = moduleList.env['DEFS']['ROOT_DIR_SW_INC'].split(" ") + moduleList.env['DEFS']['SW_INC_DIRS'].split(" ")    
            absIncPaths = map(os.path.abspath, incPaths)
            ROOT_DIR_SW_INC = ":".join(absIncPaths)

            awbBatchHandle.write(' set parameter ' + platformPath + ' EXTRA_INC_DIRS \\"' + ROOT_DIR_SW_INC  + '\\"' + '\n')

            awbBatchHandle.write(' set parameter ' + platformPath + ' EXTRA_INC_DIRS \\"' + ROOT_DIR_SW_INC  + '\\"' + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' EXTRA_DICTS \\"' + missingDicts  + '\\"' + '\n')
            awbBatchHandle.write(' set parameter ' + platformPath + ' EXTRA_RRRS \\"' + missingRRRs  + '\\"' + '\n')                      
            awbBatchHandle.write(' set parameter ' + platformPath + ' CLOSE_CHAINS 1 ' + '\n')

            awbBatchHandle.write(' configure model ' + platformPath + ' --builddir ' + platformBuildDir + '\n')
            awbBatchHandle.close()

            # Configure the build tree
            if need_config:
                os.makedirs(platformBuildDir)
                model.execute(['awb-shell', '--file', awbBatchFile], shell=False)

            # set up the symlinks to missing dictionaries- they are broken
            # at first, but as we fill in the platforms, they'll come up
            for dict in moduleList.topModule.moduleDependency['MISSING_DICTS'].keys():
                if (not dict in platformDicts):
                    # lexists works on broken symlinks...
                    dictPath = os.path.realpath(moduleList.topModule.moduleDependency['MISSING_DICTS'][dict])
                    linkDir  = makePlatformDictDir(platform.name)  
                    linkPath = linkDir  + '/' + dict
                    relPath = os.path.relpath(dictPath, linkDir)

                    if (not os.path.lexists(linkPath)):
                        print "Link: " + linkPath + ' -> ' + relPath
                        os.symlink(relPath, linkPath)
            
            # do the same for missing RRRs - this code is similar to that above and should be refactored. 
            for rrr in moduleList.topModule.moduleDependency['MISSING_RRRS'].keys():
                if (not rrr in platformRRRs):
                    # lexists works on broken symlinks...
                    rrrPath = os.path.realpath(moduleList.topModule.moduleDependency['MISSING_RRRS'][rrr])
                    linkPath  = makePlatformRRRDir(platform.name)  + '/' + rrr
                    linkDir = os.path.dirname(linkPath)
                    relPath = os.path.relpath(rrrPath, linkDir)

                    if (not os.path.lexists(linkPath)):
                        print "Link: " + linkPath + ' -> ' + relPath
                        d = os.path.dirname(linkPath)
                        if (not os.path.isdir(d)):
                            os.makedirs(d)
                        os.symlink(relPath, linkPath)
                  
            strfile = os.getcwd() + '/' + platformBuildDir + '/.bsc/' + platformAPMBaseName + '.str'

            # this dependency on platform logs is coarse.  we could do better, but it may not be necessary
            # TODO: This dependency is too coarse. We should only depend on the files for a particular platform.
            subbuild = moduleList.env.Command( 
                [bitfile, strfile],
                moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
                compile_closure_executable(platform)
                )                   

            # Force build (dependence isn't tracked through sub-builds)
            moduleList.env.AlwaysBuild(subbuild)
            # Don't delete the top-level target.  It might not need to be
            # rebuilt.
            moduleList.env.Precious(subbuild)

            moduleList.topModule.moduleDependency['FPGA_PLATFORM_BITFILES'] += [subbuild] 

        paramsSet = moduleList.topModule.moduleDependency['CANONICAL_PARAMS'][0]
        lim_graph_generator.writeDynamicParameters(self.environment, makePlatformBuildDir, paramsSet) 
               
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
