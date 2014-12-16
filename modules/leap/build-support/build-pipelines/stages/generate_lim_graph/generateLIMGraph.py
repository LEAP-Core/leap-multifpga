import os
import sys
import re
import subprocess
from subprocess import Popen, PIPE, STDOUT

import SCons.Script

import model
from model import Module
from fpga_environment_parser import parseFPGAEnvironment

# Dynamic parameters are global, and each platform may have a few
# dynamic parameters.  First we read in the dynamic parameters of
# each platform, which are produced at configuration time (above)
# Then, we build a representation of all dynamic parameters, and
# then overwrite the dynamic parameters of each subordinate build.
def canonicalizeDynamicParameters(environmentGraph, buildDirFunction):        
    dynamicParamsSet = set() # Use set properties to eliminate duplicates
    for platformName in environmentGraph.getPlatformNames():
        platform = environmentGraph.getPlatform(platformName)
        platformBuildDir = buildDirFunction(platform.name)
        paramsFile = os.getcwd() + '/' + platformBuildDir + '/iface/src/dict/dynamic_params.dic'
        paramsHandle = open(paramsFile, 'r')
        for line in paramsHandle.readlines():
            dynamicParamsSet.add(line)
    return dynamicParamsSet    

def writeDynamicParameters(environmentGraph, buildDirFunction, dynamicParamsSet):        
    # now we overwrite the old files. 
    for platformName in environmentGraph.getPlatformNames():
        platform = environmentGraph.getPlatform(platformName)
        platformBuildDir = buildDirFunction(platform.name)
        paramsFile = os.getcwd() + '/' + platformBuildDir + '/iface/src/dict/dynamic_params.dic'
        paramsHandle = open(paramsFile, 'w')
        for line in dynamicParamsSet:
            paramsHandle.write(line)
    
def makePlatformLogName(name, apm):
    return name +'_'+ apm + '_lim_logs'

def makePlatformLogBuildDir(name, apm):
    return 'lim/' + makePlatformLogName(name,apm) + '/pm'

def makePlatformConfigPath(name):
    config_dir = 'lim/apm-local/'
    if not os.path.exists(config_dir): os.makedirs(config_dir)
    return config_dir + name


class GenerateLIMGraph():

    def __init__(self, moduleList):

        self.pipeline_debug = model.getBuildPipelineDebug(moduleList)

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

        def makePlatformDictDir(name):
            return makePlatformLogBuildDir(name, APM_NAME) + '/iface/src/dict'

        def makePlatformRRRDir(name):
            return makePlatformLogBuildDir(name, APM_NAME) + '/iface/src/rrr'

        def makePlatformBuildDir(name):
            return makePlatformLogBuildDir(name,APM_NAME)

        envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENVS')
        if(len(envFile) != 1):
            print "Found more than one environment file: " + str(envFile) + ", exiting\n"

        environment = parseFPGAEnvironment(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0])

        if(self.pipeline_debug):
            print "environment keys: " + str(environment.getPlatformNames)

        # select the connected_app and make it a submodel
        awbBatchFile = 'top.batch'
        awbBatchHandle = open(awbBatchFile,'w')
        awbBatchHandle.write('create submodel ' + APM_FILE + ' connected_application ' + applicationPath + '\n')
        awbBatchHandle.write('rename submodel ' + applicationPath + ' ' + applicationRootName  + '\n')
        awbBatchHandle.write('create submodel ' + APM_FILE + ' fpga_mapping ' + mappingPath  + '\n')
        awbBatchHandle.write('create submodel ' + APM_FILE + ' environment_description ' + environmentPath  + '\n')
        awbBatchHandle.write('rename submodel ' + mappingPath + ' ' + mappingRootName + '\n')

        awbBatchHandle.close()

        subprocess.call(['awb-shell', '--file', awbBatchFile]) 

        def compile_closure(platform, enableCache):
             
             def compile_platform_log(target, source, env):
                
                 platformAPMName = makePlatformLogName(platform.name, APM_NAME) + '.apm'
                 platformPath = makePlatformConfigPath(platformAPMName)
                 platformBuildDir = makePlatformLogBuildDir(platform.name, APM_NAME)
                 # and now we can build them what we want to gather
                 # here is dangling top level connections so we should
                 # depend on the model log

                 # We need to physically reconstruct the apm path set
                 # the fpga parameter for the first pass, we will
                 # ignore mismatched platforms

                 # Compute command line arguments in case they affect topology
                 compile_cmd = 'scons '
                 if(moduleList.getAWBParam('lim_graph_generator', 'ENABLE_SCONS_CACHING_DEBUG_GRAPH')):
                     compile_cmd += ' --cache-show --cache-debug=' + os.path.abspath(makePlatformConfigPath('debug_frontend_'+platform.name)) + ' '
  
                 if(moduleList.getAWBParam('lim_graph_generator', 'ENABLE_SCONS_PROFILING_GRAPH')):
                     compile_cmd += ' --profile=' + os.path.abspath(makePlatformConfigPath('profile_frontend_'+platform.name)) + ' ' 

                 compile_cmd += ' '.join(['%s="%s"' % (key, value) for (key, value) in moduleList.arguments.items()])

                 compile_cmd = 'cd ' + platformBuildDir + '; ' + compile_cmd

                 # set environment for scons caching
                 if(moduleList.getAWBParam('lim_graph_generator', 'ENABLE_SCONS_CACHING_GRAPH')):
                     compile_cmd += ' LEAP_BUILD_CACHE_DIR=' + os.path.abspath(makePlatformConfigPath('codeCache' + platform.name)) + ' '

                 if(self.pipeline_debug or True):
                     print "Compile command is: " + compile_cmd + "\n"

                 sts = model.execute(compile_cmd)

                 if(self.pipeline_debug):
                     print "tool.py: dead in call platform log" + platform.name

                 return sts
             return compile_platform_log

        moduleList.topModule.moduleDependency['FPGA_PLATFORM_LOGS'] = []

        # the stuff below here should likely go in a different file, and there will be many hard-coded paths
        # copy the environment descriptions to private 
        #APM_FILE
        #WORKSPACE_ROOT
        # the first thing to do is construct the global set of dictionaries
        # I can communicate this to the subbuilds 
        # I build the links here, but I can't physcially check the files until later
        moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'] = {}

        for platformName in environment.getPlatformNames():
            platform = environment.getPlatform(platformName)

            if(self.pipeline_debug):
                print "leap-configure --pythonize " +  platform.path

            rawDump = Popen(["leap-configure", "--pythonize", "--silent", platform.path], stdout=PIPE ).communicate()[0]
            moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName] = model.ModuleList(moduleList.env, eval(rawDump), moduleList.arguments, "")
            
        # check that all same named file are the same.  Then we can blindly copy all files to all directories and life will be good. 
        # once that's done, we still need to tell the child about these extra dicts. 
        # need to handle dynamic params specially somehow.... 
        # for now we'll punt on it. 

        # The missing dictionaries and RRRs need to be communicated to the 
        # second compilation pass.
        moduleList.topModule.moduleDependency['MISSING_DICTS'] = {}
        moduleList.topModule.moduleDependency['MISSING_RRRS'] = {}
        
        # the assignment here should really be a path assignment. Platform name is a bit non-sensical.

        for platformName in environment.getPlatformNames():
            platform = environment.getPlatform(platformName)
            for dictionary in moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependencies('GIVEN_DICTS'):
                if(not dictionary in moduleList.topModule.moduleDependency['MISSING_DICTS']):                                                     
                    moduleList.topModule.moduleDependency['MISSING_DICTS'][dictionary] = makePlatformDictDir(platform.name) + '/' + dictionary

            # RRR calls can appear in services which can differ across environments. 
            # This code can probably be deprecated at some point once RRR goes away.
            for rrr in moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'] [platformName].getAllDependenciesWithPaths('GIVEN_RRRS'):
                if(not rrr in moduleList.topModule.moduleDependency['MISSING_RRRS']):                                                     
                    moduleList.topModule.moduleDependency['MISSING_RRRS'][rrr] = makePlatformRRRDir(platform.name) + '/' + rrr

        # Add in user code dictionaries and rrrs.
                    
        for dictionary in moduleList.getAllDependencies('GIVEN_DICTS'):
            if(not dictionary in moduleList.topModule.moduleDependency['MISSING_DICTS']):                                                     
                moduleList.topModule.moduleDependency['MISSING_DICTS'][dictionary] = 'iface/src/dict/' + dictionary

        # RRR calls can appear in services which can differ across environments. 
        # This code can probably be deprecated at some point once RRR goes away.
        for rrr in moduleList.getAllDependenciesWithPaths('GIVEN_RRRS'):
            if(not rrr in moduleList.topModule.moduleDependency['MISSING_RRRS']):                                                     
                moduleList.topModule.moduleDependency['MISSING_RRRS'][rrr] = 'iface/src/rrr/' + rrr
        
        # We can now set up each platform for the first stage of
        # compilation.  this chiefly involves distributing rrr and dict
        # files around to ensure global agreement on their values.
        
        # Every module in the system must be given a unique
        # ID. Ideally this would be a server of some kind, but for
        # now, we use a parameter...
        moduleList.topModule.moduleDependency['MODULE_UID_OFFSET'] = 0

        # This data structure maintains a hash of all the platforms types
        # to which we have bound the user program.  We only bind the user
        # program to one platform of each type. This reduces the
        # compilation complexity of the other platforms, since only the
        # platform code must be compiled.
       
        platformBindings = {}

        # for temporary backwards compatibility, if there is a master
        # platform, this one must be used for both the CPU and FPGA
        # binding.

        for platformName in environment.getPlatformNames():
            platform = environment.getPlatform(platformName)                    
            if(platform.master):
                platformBindings[platform.platformType] = platformName
                if(self.pipeline_debug):
                    print "Master Set as " + platformName
        
        moduleList.topModule.moduleDependency['PLATFORM_LI'] = []
        for platformName in environment.getPlatformNames():

          awbBatchFile = platform.name + '.logs.batch'
          awbBatchHandle = open(awbBatchFile,'w')

          platform = environment.getPlatform(platformName)
          platformAPM = makePlatformLogName(platform.name, APM_NAME)
          platformAPMName = platformAPM + '.apm'
          platformPath = makePlatformConfigPath(platformAPMName)
          platformBuildDir = makePlatformLogBuildDir(platformName, APM_NAME)

          # Make a symlink locally
          platformAPMPath = (Popen(["awb-resolver", platform.path], stdout=PIPE).communicate()[0]).strip()
          relativeAPMPath = os.path.relpath(platformAPMPath, makePlatformConfigPath("")) 
          linkAPMPath = makePlatformConfigPath(platform.getAPMName())

          model.execute('rm -f ' + linkAPMPath + '; ln -s  ' + relativeAPMPath + ' ' + linkAPMPath)
          
          model.execute('asim-shell --batch cp ' + platform.path +" "+ platformPath) 
          # We only need to build the application once for each platform type.
          # The second leg of the or statement deals with legacy platforms which have a master.
          doCache = False
          if((not platform.platformType in platformBindings) or (platformBindings[platform.platformType] == platformName)):
              doCache = True
              platformBindings[platform.platformType] = platformName
              awbBatchHandle.write('replace module ' + platformPath + ' ' + applicationPath + '\n')
              #model.execute('asim-shell --batch replace module ' + platformPath + ' ' + applicationPath)

              if(self.pipeline_debug):
                  print "Platform binding for " + platform.platformType + " is " + platformName

          # For legacy builds, we create software during the first pass. 
          if(platform.master):
              awbBatchHandle.write('set parameter ' + platformPath + ' BUILD_FIRST_PASS_SOFTWARE 1' + '\n')       
              
          awbBatchHandle.write('set parameter ' + platformPath + ' FPGA_PLATFORM_ID ' + str((environment.getSynthesisBoundaryPlatformID(platform.name))) + '\n')
          awbBatchHandle.write('set parameter ' + platformPath + ' CON_CWIDTH ' +  str(moduleList.getAWBParam('lim_graph_generator', 'SOFT_CONN_CWIDTH')) + '\n')
          awbBatchHandle.write('set parameter ' + platformPath + ' CON_CHAIN_CWIDTH ' +  str(moduleList.getAWBParam('lim_graph_generator', 'SOFT_CONN_CWIDTH')) + '\n')
          awbBatchHandle.write('set parameter ' + platformPath + ' FPGA_PLATFORM_NAME \\"' + platform.name + '\\"' + '\n')
          awbBatchHandle.write('set parameter ' + platformPath + ' FPGA_NUM_PLATFORMS ' + str(len(environment.getPlatformNames())) + '\n')
          #awbBatchHandle.write('set parameter ' + platformPath + ' IGNORE_PLATFORM_MISMATCH 1 ' + '\n')
          awbBatchHandle.write('set parameter ' + platformPath + ' EXPOSE_ALL_CONNECTIONS 1 ' + '\n')
          awbBatchHandle.write('set parameter ' + platformPath + ' BUILD_LOGS_ONLY 1 ' + '\n')
          awbBatchHandle.write('set parameter ' + platformPath + ' MODULE_UID_OFFSET ' + str(moduleList.topModule.moduleDependency['MODULE_UID_OFFSET']) + '\n')
          awbBatchHandle.write('set parameter ' + platformPath + ' USE_ROUTING_KNOWN 0 ' + '\n')

          # Platforms may have their own parameter sets. 
          for parameter in platform.parameters:
              awbBatchHandle.write('set parameter ' + platformPath + ' ' + parameter + ' ' + platform.parameters[parameter].getAWBRepresentation() + '\n')
 
          # update uid
          moduleList.topModule.moduleDependency['MODULE_UID_OFFSET'] += len(moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].synthBoundaries())
          # for one platform, we must also include the user code.
          if(doCache):
              moduleList.topModule.moduleDependency['MODULE_UID_OFFSET'] += len(moduleList.synthBoundaries())

          # Dictionaries are global.  Therefore, all builds must see the same context or bad things 
          # will happen.   
          missingDicts = ""
          firstPass = True

          ### TODO: replace with something more pythonic.
          platformDicts = moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependencies('GIVEN_DICTS')     
          for dictionary in moduleList.topModule.moduleDependency['MISSING_DICTS'].keys():
              if(not dictionary in platformDicts):
                seperator = ':'
                if(firstPass):
                    seperator = ''
                missingDicts += seperator+dictionary
                firstPass = False
        
          if(self.pipeline_debug):
              print "missingDicts: " + missingDicts
        
          # RRRs can appear in services sometimes and thereby lack global 
          # visibility.  We need to treat them in the same way we treat dictionaries. 
          missingRRRs = ""
          firstPass = True
          platformRRRs = moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependenciesWithPaths('GIVEN_RRRS')     

          ### TODO: replace with something more pythonic.
          for dict in moduleList.topModule.moduleDependency['MISSING_RRRS'].keys():
              if(not dict in platformRRRs):
                  seperator = ':'
                  if(firstPass):
                      seperator = ''
                  missingRRRs += seperator+dict
                  firstPass = False
            
          if(self.pipeline_debug):
              print "missingRRRs: " + missingRRRs

          # Compiling IFACE requires extra context. 
          incPaths = moduleList.env['DEFS']['ROOT_DIR_SW_INC'].split(" ") + moduleList.env['DEFS']['SW_INC_DIRS'].split(" ")    
          absIncPaths = map(os.path.abspath, incPaths)
          ROOT_DIR_SW_INC = ":".join(absIncPaths)

          awbBatchHandle.write('set parameter ' + platformPath + ' EXTRA_INC_DIRS \\"' + ROOT_DIR_SW_INC  + '\\"' + '\n')
          awbBatchHandle.write('set parameter ' + platformPath + ' EXTRA_DICTS \\"' + missingDicts  + '\\"' + '\n')
          awbBatchHandle.write('set parameter ' + platformPath + ' EXTRA_RRRS \\"' + missingRRRs  + '\\"' + '\n')

          # Configure the build tree
          if not os.path.exists(platformBuildDir): 
              os.makedirs(platformBuildDir) 
          
          awbBatchHandle.write('configure model ' + platformPath + ' --builddir ' + platformBuildDir + '\n')

          awbBatchHandle.close()
          subprocess.call(['awb-shell', '--file', awbBatchFile]) 
          # TODO: Refactor me!
          # set up the symlinks to missing dictionaries- they aree broken
          # at first, but as we fill in the platforms, they'll come up
          for dict in moduleList.topModule.moduleDependency['MISSING_DICTS'].keys():
              if(not dict in platformDicts):
                  # lexists works on broken symlinks...
                  path = os.getcwd()
                  dictPath = os.path.realpath(moduleList.topModule.moduleDependency['MISSING_DICTS'][dict])
                  linkDir  = makePlatformDictDir(platform.name)  
                  linkPath = linkDir  + '/' + dict
                  relDictPath = os.path.relpath(dictPath, linkDir)
                  if(self.pipeline_debug):
                      print "missing link: " + linkPath + ' -> ' + relDictPath

                  if(os.path.lexists(linkPath)):
                      os.remove(linkPath)

                  os.symlink(relDictPath, linkPath)
            
          # do the same for missing RRRs - this code is similar to that above and should be refactored. 
          for rrr in moduleList.topModule.moduleDependency['MISSING_RRRS'].keys():
              if(not rrr in platformRRRs):
                  # lexists works on broken symlinks...
                  path = os.getcwd()
                  linkPath  = makePlatformRRRDir(platform.name)  + '/' + rrr
                  if(os.path.lexists(linkPath)):
                      os.remove(linkPath)
                      
                  rrrpath = os.path.realpath(moduleList.topModule.moduleDependency['MISSING_RRRS'][rrr])
                  #the rrr values have some hierarchical information in them...
                  linkDir = os.path.dirname(linkPath)
                  if(self.pipeline_debug):
                      print ('Link dir is ' + linkDir)
                  # create directory structure first. 
                  if(not os.path.exists(linkDir)):
                      os.makedirs(linkDir)

                  os.symlink(os.path.relpath(rrrpath, linkDir), linkPath)
              

          platformLI = platformBuildDir + '/' + platformAPM +  '.li'

          moduleList.topModule.moduleDependency['PLATFORM_LI'] += [platformLI]
          # Take platform specific build actions  

          if(platform.platformType == 'FPGA' or platform.platformType == 'BLUESIM'):

              routerBSH =  platformBuildDir + '/' + moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/multifpga_routing.bsh'

              if(self.pipeline_debug):
                  print "platformPath: " + platformPath

              subbuild = moduleList.env.Command(
                      [platformLI],
                      [routerBSH],
                      [compile_closure(platform, doCache)]       
                  )                         
              
              # we now need to create a multifpga_routing.bsh so that we can get the sizes of the various links.
              # we'll need this later on. 
              # TODO: This should be refactored as a generate code method.
              header = open(routerBSH,'w')
              header.write('`include "awb/provides/stats_service.bsh"\n')
              header.write('`include "awb/provides/debug_scan_service.bsh"\n')
              header.write('`include "awb/provides/physical_platform.bsh"\n')
              header.write('// we need to pick up the module sizes\n')
              header.write('module [CONNECTED_MODULE] mkCommunicationModule#(PHYSICAL_DRIVERS physicalDrivers) (Empty);\n')
              header.write('let m <- mkCommunicationModuleIfaces(physicalDrivers ') 
              for target in  platform.getEgresses().keys():
                  header.write(', ' + platform.getEgress(target).physicalName + '.write')
              for target in  platform.getIngresses().keys():
                  header.write(', ' + platform.getIngress(target).physicalName + '.first')
           
              header.write(');\n')
              # we also need a stat here to make the stats work right.  
              # we don't care about the ID because it will get replaced later during the second compilation pass
              if (moduleList.getAWBParam('lim_graph_generator', 'GENERATE_ROUTER_STATS')):
                  header.write('let stat <- mkStatCounter(statName("DUMMY", "Dummy stat"));\n')   

              if (moduleList.getAWBParam('lim_graph_generator', 'GENERATE_ROUTER_DEBUG')):
                  header.write('mkDebugScanNode("dummy",List::nil);\n')   

              header.write('endmodule\n')

              header.write('module [CONNECTED_MODULE] mkCommunicationModuleIfaces#(PHYSICAL_DRIVERS physicalDrivers ')

              for target in  platform.getEgresses().keys():
                  # really I should disambiguate by way of a unique path
                  via  = (platform.getEgress(target)).physicalName.replace(".","_").replace("[","_").replace("]","_") + '_write'
                  header.write(', function Action write_' + via + '_egress(Bit#(p' + via + '_egress_SZ) data)') 

              for target in  platform.getIngresses().keys():
                  # really I should disambiguate by way of a unique path
                  via  = (platform.getIngress(target)).physicalName.replace(".","_").replace("[","_").replace("]","_") + '_read'
                  header.write(', function Bit#(p'+ via + '_ingress_SZ) read_' + via + '_ingress()') 

              header.write(') (Empty);\n')

              for target in  platform.getEgresses().keys():
                  via  = (platform.getEgress(target)).physicalName.replace(".","_").replace("[","_").replace("]","_") + '_write'
                  header.write('messageM("SizeOfVia:'+ platform.getEgress(target).physicalName + ':egress:" + integerToString(valueof(p' + via + '_egress_SZ)));\n')
              
              for target in  platform.getIngresses().keys():
                  # really I should disambiguate by way of a unique path
                  via  = (platform.getIngress(target)).physicalName.replace(".","_").replace("[","_").replace("]","_") + '_read' 
                  header.write('messageM("SizeOfVia:' + platform.getIngress(target).physicalName + ':ingress:" + integerToString(valueof(p' + via + '_ingress_SZ)));\n')
              header.write('endmodule\n')

              header.close();

              #force build remove me later....          
              moduleList.topDependency += [subbuild]
              moduleList.env.AlwaysBuild(subbuild)

          elif(platform.platformType == 'CPU'):
              routerH =  platformBuildDir + '/' + moduleList.env['DEFS']['ROOT_DIR_SW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/software_routing.h'

              header = open(routerH,'w')
              
              header.write('// Generated by build pipeline\n\n')
              header.write('#ifndef __SW_ROUTING__\n')
              header.write('#define __SW_ROUTING__\n')
              header.write('#include "awb/provides/physical_channel.h"\n')
              header.write('#include "awb/provides/channelio.h"\n')
              header.write('#include "awb/provides/multifpga_switch.h"\n')
              header.write('#include "awb/provides/umf.h"\n')
              header.write('#include <pthread.h>\n')
              header.write('#include <vector>\n')
              header.write('#include "tbb/concurrent_queue.h"\n')
              
              header.write('using namespace std;\n')

              header.write("typedef class CHANNELIO_CLASS* CHANNELIO;\n")
              header.write("class CHANNELIO_CLASS:  public CHANNELIO_BASE_CLASS\n")
              header.write("{\n")
              header.write("  public:\n")
              header.write("\tCHANNELIO_CLASS(PLATFORMS_MODULE module, PHYSICAL_DEVICES physicalDevicesInit):\n")
              header.write("\t\tCHANNELIO_BASE_CLASS(module, physicalDevicesInit)\n")
              header.write("\n\t{\n");
              header.write("\t};\n")
              header.write("};\n")

              header.write('#endif\n')


              subbuild = moduleList.env.Command( 
                  [platformLI],
                  [routerH],
                  [compile_closure(platform, False)]
                  )

              #force build remove me later....          
              moduleList.topDependency += [subbuild]
              moduleList.env.AlwaysBuild(subbuild)

        paramsSet = canonicalizeDynamicParameters(environment, makePlatformBuildDir) 
        writeDynamicParameters(environment, makePlatformBuildDir, paramsSet) 
        moduleList.topModule.moduleDependency['CANONICAL_PARAMS'] = [paramsSet] 

        # now that we configured things, let's check that the dicts and rrrs are sane
        # we use os.stat to check file equality. It follows symlinks,
        # and it would be an _enormous_ coincidence if non-equal files 
        # matched
        for platformName in environment.getPlatformNames():
            platformDicts = moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependencies('GIVEN_DICTS')
            for dict in platformDicts:
                platStat = os.stat(os.path.abspath(makePlatformDictDir(platformName)  + '/' + dict))
                globalStat = os.stat(os.path.abspath(moduleList.topModule.moduleDependency['MISSING_DICTS'][dict]))

                if(platStat != globalStat):
                    print "Warning, mismatched dicts: " + str(dict) + " on " + platformName

            #and now for RRRs
            platformRRRs = moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependenciesWithPaths('GIVEN_RRRS')
            for rrr in platformRRRs:
                platStat = os.stat(os.path.abspath(makePlatformRRRDir(platformName)  + '/' + rrr))
                globalStat = os.stat(os.path.abspath(moduleList.topModule.moduleDependency['MISSING_RRRS'][rrr]))

                if(platStat != globalStat):
                    print "Warning, mismatched dicts: " + str(rrr) + " on " + platformName
        
        
