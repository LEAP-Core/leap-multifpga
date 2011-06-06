import re
import sys
import SCons.Script
from fpga_environment_parser import *
from multi_fpga_log_generator import *
from model import  *
from config import *

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
  
    envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENVS')
    if(len(envFile) != 1):
      print "Found more than one environment file: " + str(envFile) + ", exiting\n"
    environment = parseFPGAEnvironment(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0])
    print "environment keys: " + str(environment.getPlatformNames)

    def compile_closure(platform):

         def compile_platform_log(target, source, env):

           platformAPMName = makePlatformName(platform.name,APM_NAME) + '.apm'
           platformPath = 'config/pm/private/' + platformAPMName
           platformBuildDir = moduleList.env['DEFS']['BUILD_DIR'] +'/' + platformAPMName
           # and now we can build them -- should we use SCons here?
           # what we want to gather here is dangling top level connections
           # so we should depend on the model log
           # Ugly - we need to physically reconstruct the apm path
           # set the fpga parameter
           # for the first pass, we will ignore mismatched platforms
           execute('asim-shell set parameter ' + platformPath + ' MULTI_FPGA_PLATFORM \\"' + platform.name + '\\"')
           execute('asim-shell set parameter ' + platformPath + ' IGNORE_PLATFORM_MISMATCH 0 ')
           execute('asim-shell set parameter ' + platformPath + ' BUILD_LOGS_ONLY 0 ')
           execute('asim-shell set parameter ' + platformPath + ' USE_ROUTING_KNOWN 1 ')
           execute('asim-shell configure model ' + platformPath)

           print "alive in call platform log " + platformPath
           execute('awb-shell build model ' + platformPath)   
           print "dead in call platform log"
         return compile_platform_log

    moduleList.topModule.moduleDependency['FPGA_PLATFORM_BITFILES'] = []

    # the stuff below here should likely go in a different file, and there will be many hard-coded paths
    # copy the environment descriptions to private 
    #APM_FILE
    #WORKSPACE_ROOT
    for platformName in environment.getPlatformNames():
      platform = environment.getPlatform(platformName)
      platformAPMName = makePlatformName(platform.name,APM_NAME) + '.apm'
      platformPath = 'config/pm/private/' + platformAPMName
      platformBuildDir = moduleList.env['DEFS']['BUILD_DIR'] +'/../../' + makePlatformName(platform.name,APM_NAME) + '/pm/'
      bitfile = platformBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/.xilinx/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '_'

      print "wrapper: " + bitfile
      print "platformPath: " + moduleList.env['DEFS']['WORKSPACE_ROOT'] + '/src/private/' + platformPath

      # this dependency on platform logs is coarse.  we could do better, but it may not be necessary
      subbuild = moduleList.env.Command( 
          [bitfile],
          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
          compile_closure(platform)
          )                   
      moduleList.topModule.moduleDependency['FPGA_PLATFORM_BITFILES'] += [bitfile] 

      #force build remove me later....          
      moduleList.topDependency += [subbuild]
