import re
import sys
import SCons.Script
from model import  *
from config import *
from fpga_environment_parser import *
from fpgamap_parser import *
from multi_fpga_log_generator import *
from danglingConnection import *

class MultiFPGAConnect():

  def __init__(self, moduleList):
      self.moduleList = moduleList
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
          platformAPMName = makePlatformName(platform.name,APM_NAME) + '.apm'
          platformPath = 'config/pm/private/' + makePlatformName(platform.name,APM_NAME)
          platformBuildDir = moduleList.env['DEFS']['BUILD_DIR'] +'/../../' + makePlatformName(platform.name,APM_NAME) + '/pm/'
          wrapperLog =  platformBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/.bsc/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '_Wrapper.log'
          parameterFile =  platformBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/multifpga_routing.bsh'
          self.platformData[platform.name] = {'LOG': wrapperLog, 'BSH': parameterFile, 'DANGLING': [], 'CONNECTED': [], 'INDEX': {}}


          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'] += [parameterFile] 
 
      subbuild = moduleList.env.Command( 
          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
          moduleList.topModule.moduleDependency['FPGA_PLATFORM_LOGS'],
          self.processDanglingConnections
          )                   
      print "subbuild: " + str(subbuild)


      moduleList.topDependency += [subbuild]

  #First we parse the files, and then attempt to make all the connections.  Lots of dictionaries.
  def processDanglingConnections(self, target, source, env):
      APM_FILE = self.moduleList.env['DEFS']['APM_FILE']
      APM_NAME = self.moduleList.env['DEFS']['APM_NAME']
      
      danglingGlobal = [];
      for platformName in self.environment.getPlatformNames():
          self.parseDangling(platformName)
          # we should now check for matches
          for danglingNew in self.platformData[platformName]['DANGLING']:
              for danglingOld in danglingGlobal:
                  if(danglingNew.matches(danglingOld)): # a potential match
                      # We should check to see that things are directly connected
                      # we don't handle the multi hop case yet, and may need a fixed point to do so. 
                      length = -1
                      if(danglingNew.isSource()):
                          length = self.environment.getPathLength(danglingNew.platform, danglingOld.platform)
                      else:
                          length = self.environment.getPathLength(danglingOld.platform, danglingNew.platform)
                      if(length != 1):
                          print "either there is no connection between the connections named " + danglingNew.name + " or the connection requires multiple hops, which is not yet supported" 
                      matched = 1
                      # need to fill in the connection
                      danglingOld.matched = True
                      danglingNew.matched = True
                      #lookup indexes
                      if(danglingNew.platform in self.platformData[danglingOld.platform]['INDEX']):
                          self.platformData[danglingOld.platform]['INDEX'][danglingNew.platform] += 1
                          self.platformData[danglingNew.platform]['INDEX'][danglingOld.platform] += 1
                          danglingNew.idx = self.platformData[danglingOld.platform]['INDEX'][danglingNew.platform]
                          danglingOld.idx = self.platformData[danglingOld.platform]['INDEX'][danglingNew.platform]
                      else:
                          self.platformData[danglingOld.platform]['INDEX'][danglingNew.platform] = 0
                          self.platformData[danglingNew.platform]['INDEX'][danglingOld.platform] = 0
                          danglingNew.idx = 0 
                          danglingOld.idx = 0

                      # mark the connection in the data structure
                      self.platformData[danglingOld.platform]['CONNECTED'] += [danglingNew]
                      self.platformData[danglingNew.platform]['CONNECTED'] += [danglingOld]
                                            
                      
          danglingGlobal += self.platformData[platformName]['DANGLING']

      #unmatched connections are bad
      for dangling in danglingGlobal:
          if(not dangling.optional and not dangling.matched):
              print 'Unmatched connection ' + dangling.name
              sys.exit(0)
      # now that everything is matched we can ostensibly generate the header file
      # header must include device mapping as well
      for platform in self.environment.getPlatformNames():
          header = open(self.platformData[platform]['BSH'],'w')
          header.write('// Generated by build pipeline\n\n')

          # toss out the mapping functions first
          header.write('module [CONNECTED_MODULE] mkCommunicationModule#(VIRTUAL_PLATFORM vplat) (Empty);\n')
#          for hardConnectionOut in environment.transitTablesOutgoing[platform].keys():
#              header.write('"' + hardConnectionOut + ' ": vdevs.' + environment.transitTablesOutgoing[platform][hardConnectionOut] + ';\n')
#          header.write('endfunction\n')

#          header.write('function Get#(n) getIncomingLink(VIRTUAL_DEVICES vdevs, String str);\n')
#          header.write('  case (str)\n')
#          for hardConnectionIn in environment.transitTablesIncoming[platform].keys():
#              header.write('"' + hardConnectionIn + ' ": vdevs.' + environment.transitTablesIncoming[platform][hardConnectionIn] + ';\n')
#          header.write('endfunction\n')

          # handle the connections themselves
          for dangling in self.platformData[danglingOld.platform]['CONNECTED']:
              if(dangling.sc_type == 'Recv'):
                  header.write('Connection_Receive#(' + dangling.raw_type+ ') g_' + dangling.name + ' <- mkConnectionReceive("' + dangling.name+'");\n')
              if(dangling.sc_type == 'Send'):
                  header.write('Connection_Send#(' + dangling.raw_type+ ') g_' + dangling.name + '<- mkConnectionSend("' + dangling.name+'");\n')


          header.write('endmodule\n')
          header.close();

  def parseDangling(self, platformName):
      logfile = open(self.platformData[platformName]['LOG'],'r')
      print "Processing: " + self.platformData[platformName]['LOG']
      for line in logfile:
          if(re.match("Compilation message: .*: Dangling",line)):
              match = re.search(r".*Dangling (\w+) {(.*)} \[(\d+)\]:(\w+):(\w+):(\w+)", line)
              if(match):
            #python groups begin at index 1  
                  print 'found connection: ' + line
                  self.platformData[platformName]['DANGLING'] += [DanglingConnection(match.group(1), 
                                                                                match.group(2),
                                                                                match.group(3),
                                                                                match.group(4),
                                                                                match.group(5),
                                                                                match.group(6))]
              else:
                  print "Malformed connection message: " + line
                  sys.exit(-1)
