import re
import sys
import SCons.Script
from fpga_environment_parser import *
from fpgamap_parser import *
from model import  *
from config import *

def makePlatformBitfileName(name, apm):
  return name +'_'+ apm + '_multifpga_bitfile'

class MultiFPGAGenerateBitfile():

  def __init__(self, moduleList):
    # we should always be building these things
    # looks a lot like the log file generation, but with different params.  We should refactor
    APM_FILE = moduleList.env['DEFS']['APM_FILE']
    APM_NAME = moduleList.env['DEFS']['APM_NAME']
    applicationRootName = APM_NAME  + '_mutlifpga_connected_application'
    applicationName = applicationRootName + '.apm'
    applicationPath =  'config/pm/private/' + applicationName
    mappingRootName = APM_NAME  + '_mutlifpga_mapping'
    mappingName = mappingRootName + '.apm'
    mappingPath =  'config/pm/private/' + mappingName
    environmentRootName = APM_NAME  + '_multifpga_environment'
    environmentName = environmentRootName + '.apm'
    environmentPath =  'config/pm/private/' + environmentName

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
    print "mapping keys: " + str(self.mapping.getPlatformNames)
  
    envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENVS')
    if(len(envFile) != 1):
      print "Found more than one environment file: " + str(envFile) + ", exiting\n"
    self.environment = parseFPGAEnvironment(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0])
    print "environment keys: " + str(self.environment.getPlatformNames)

    def compile_closure(platform):

         def compile_platform_log(target, source, env):

           platformAPMName = makePlatformBitfileName(platform.name,APM_NAME) + '.apm'
           platformPath = 'config/pm/private/' + platformAPMName
           platformBuildDir = makePlatformBuildDir(platform.name)

           print "alive in call platform log " + platformPath

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
           print compile_cmd

           sts = execute(compile_cmd)
           print "dead in call platform log"
           return sts
         return compile_platform_log

    moduleList.topModule.moduleDependency['FPGA_PLATFORM_BITFILES'] = []

    # the stuff below here should likely go in a different file, and there will be many hard-coded paths
    # copy the environment descriptions to private 
    #APM_FILE
    #WORKSPACE_ROOT
    for platformName in self.environment.getPlatformNames():
      platform = self.environment.getPlatform(platformName)
      platformAPMName = makePlatformBitfileName(platform.name,APM_NAME) + '.apm'
      platformPath = 'config/pm/private/' + platformAPMName
      platformBuildDir = makePlatformBuildDir(platform.name)
      bitfile = platformBuildDir + '/' + moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/.xilinx/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '_'

      print "wrapper: " + bitfile
      print "platformPath: " + moduleList.env['DEFS']['WORKSPACE_ROOT'] + '/src/private/' + platformPath

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

      execute('asim-shell --batch set parameter ' + platformPath + ' IGNORE_PLATFORM_MISMATCH 0 ')
      execute('asim-shell --batch set parameter ' + platformPath + ' BUILD_LOGS_ONLY 0 ')
      execute('asim-shell --batch set parameter ' + platformPath + ' USE_ROUTING_KNOWN 1 ')    


      # Dictionaries are global.  Therefore, all builds must see the same context or bad things 
      # will happen.   
      missingDicts = "multifpga_routing.dic"
      firstPass = True
      platformDicts = moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependencies('GIVEN_DICTS')     
      for dict in moduleList.topModule.moduleDependency['MISSING_DICTS'].keys():
        if(not dict in platformDicts):
          seperator = ':'
          missingDicts += seperator+dict
          firstPass = False

      print "missingDictsBitfile: " + missingDicts
    
      # RRRs can appear in services sometimes and thereby lack global 
      # visibility.  We need to treat them in the same way we treat dictionaries. 
      missingRRRs = ""
      firstPass = True
      platformRRRs = moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].getAllDependenciesWithPaths('GIVEN_RRRS')     
      for rrr in moduleList.topModule.moduleDependency['MISSING_RRRS'].keys():
        if(not rrr in platformRRRs):
          seperator = ':'
          if(firstPass):
            seperator = ''
          missingRRRs += seperator+rrr
          firstPass = False

      print "missingRRRsBitfiles: " + missingRRRs
  
      execute('asim-shell --batch set parameter ' + platformPath + ' EXTRA_DICTS \\"' + missingDicts  + '\\"')
      execute('asim-shell --batch set parameter ' + platformPath + ' EXTRA_RRRS \\"' + missingRRRs  + '\\"')                      
      execute('asim-shell --batch set parameter ' + platformPath + ' CLOSE_CHAINS 1 ')

      if not os.path.exists(platformBuildDir): os.makedirs(platformBuildDir) 

      execute('asim-shell --batch -- configure model ' + platformPath + ' --builddir ' + platformBuildDir)


      # set up the symlink - it'll be broken at first, but as we fill in the platforms, they'll come up      
      for dict in moduleList.topModule.moduleDependency['MISSING_DICTS'].keys():
        if(not dict in platformDicts):
          # lexists works on broken symlinks...
          path = os.getcwd()
          dictPath = os.path.realpath( makePlatformDictDir(moduleList.topModule.moduleDependency['MISSING_DICTS'][dict]) + '/' + dict)
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
            print ('Link dir is ' + linkDir)
            os.symlink(relpath(rrrPath, linkDir), linkPath)


      # this dependency on platform logs is coarse.  we could do better, but it may not be necessary
      subbuild = moduleList.env.Command( 
          [bitfile],
          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
          compile_closure(platform)
          )                   
      moduleList.topModule.moduleDependency['FPGA_PLATFORM_BITFILES'] += [bitfile] 

      #force build remove me later....          
      moduleList.topDependency += [subbuild]
