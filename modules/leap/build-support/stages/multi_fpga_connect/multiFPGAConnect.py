import SCons.Script
from model import  *
from config import *
from fpga_environment_parser import *
from fpgamap_parser import *
from subprocess import call


class MultiFPGAConnect():

  def __init__(self, moduleList):
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
      for platformName in environment.getPlatformNames():
      # these defs are copied from a previous tool.  refactor
          platform = environment.getPlatform(platformName)
          platformAPMName = makePlatformName(platform.name,APM_NAME) + '.apm'
          platformPath = 'config/pm/private/' + makePlatformName(platform.name,APM_NAME)
          platformBuildDir = moduleList.env['DEFS']['BUILD_DIR'] +'/' + makePlatformName(platform.name,APM_NAME)
          wrapperLog =  platformBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/.bsc/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '_Wrapper.log'
          parameterFile =  platformBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/multifpga_routing.bsh'
          self.platformData[platform.name] = {'LOG': wrapperLog, 'BSH': parameterFile, 'SENDS':{}, RECVS: {}}


          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'].append(parameterFile) 
      subbuild = moduleList.env.Command( 
          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
          moduleList.topModule.moduleDependency['FPGA_PLATFORM_LOGS'],
          self.processDanglingConnections
          )                   
      
  #First we parse the files, and then attempt to make all the connections.  Lots of dictionaries.
  def processDanglingConnections(self):
      APM_FILE = moduleList.env['DEFS']['APM_FILE']
      APM_NAME = moduleList.env['DEFS']['APM_NAME']

      danglingSends = {};
      danglingRecvs = {};
  
