import re
import sys
import SCons.Script
from model import  *
from config import *
from fpga_environment_parser import *
from fpgamap_parser import *
# we write to bitfile 
# we read from logfile
from multi_fpga_generate_bitfile import *
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
          platformLogAPMName = makePlatformLogName(platform.name,APM_NAME) + '.apm'
          platformLogPath = 'config/pm/private/' + makePlatformLogName(platform.name,APM_NAME)
          platformLogBuildDir = moduleList.env['DEFS']['BUILD_DIR'] +'/../../' + makePlatformLogName(platform.name,APM_NAME) + '/pm/'

          platformBitfileAPMName = makePlatformBitfileName(platform.name,APM_NAME) + '.apm'
          platformBitfilrPath = 'config/pm/private/' + makePlatformBitfileName(platform.name,APM_NAME)
          platformBitfileBuildDir = moduleList.env['DEFS']['BUILD_DIR'] +'/../../' + makePlatformBitfileName(platform.name,APM_NAME) + '/pm/'

          wrapperLog =  platformLogBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/.bsc/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '_Wrapper.log'
          parameterFile =  platformBitfileBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/multifpga_routing.bsh'
          self.platformData[platform.name] = {'LOG': wrapperLog, 'BSH': parameterFile, 'DANGLING': [], 'CONNECTED': {}, 'INDEX': {}}


          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'] += [parameterFile] 
 
      subbuild = moduleList.env.Command( 
          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
          moduleList.topModule.moduleDependency['FPGA_PLATFORM_LOGS'] + [moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0]] + [moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + mappingFile[0]],
          self.processDanglingConnections
          )                   
      print "subbuild: " + str(subbuild)


      moduleList.topDependency += [subbuild]

  def assignIndices(self,sourceConn,sinkConn):
    print "Now processing a connection between " + sourceConn.platform + " <->" + sinkConn.platform
    if(sinkConn.platform in self.platformData[sourceConn.platform]['INDEX']):
      # only increment the sourceConn.  
      self.platformData[sourceConn.platform]['INDEX'][sinkConn.platform] += 1
      index = self.platformData[sourceConn.platform]['INDEX'][sinkConn.platform]
      sourceConn.idx = index 
      sinkConn.idx = index 
    else:
      self.platformData[sourceConn.platform]['INDEX'][sinkConn.platform] = 0
      sourceConn.idx = 0
      sinkConn.idx = 0 
    
    # Tell the sink about the source.  The sink may have been processed already
    if(sinkConn.platform in self.platformData[sourceConn.platform]['CONNECTED']):
      self.platformData[sourceConn.platform]['CONNECTED'][sinkConn.platform] += [sinkConn]
    else:   
      self.platformData[sourceConn.platform]['CONNECTED'][sinkConn.platform] = [sinkConn]

    if(sourceConn.platform in self.platformData[sinkConn.platform]['CONNECTED']):
      self.platformData[sinkConn.platform]['CONNECTED'][sourceConn.platform] += [sourceConn]
    else:   
      self.platformData[sinkConn.platform]['CONNECTED'][sourceConn.platform] = [sourceConn]



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
                          self.assignIndices(danglingNew,danglingOld)
                      else:
                          length = self.environment.getPathLength(danglingOld.platform, danglingNew.platform)
                          self.assignIndices(danglingOld,danglingNew)

                      if(length != 1):
                          print "either there is no connection between the connections named " + danglingNew.name + " or the connection requires multiple hops, which is not yet supported" 
                      matched = 1
                      # need to fill in the connection
                      danglingOld.matched = True
                      danglingNew.matched = True
                      #lookup indexes.  Note that the subhashes are indexed 
               
                      # mark the connection in the data structure

                                            
                      
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
          header.write('messageM("Instantiating Custom Router"); \n')

          # handle the connections themselves
          for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
            header.write('// Connection to ' + targetPlatform + ' \n')
            sends = 0
            recvs = 0

            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              if(dangling.sc_type == 'Recv'):
                  header.write('Connection_Receive#(' + dangling.raw_type+ ') recv_' + dangling.name + ' <- mkConnectionRecv("' + dangling.name+'");\n')
                  recvs += 1 
              if(dangling.sc_type == 'Send'):
                  header.write('Connection_Send#(' + dangling.raw_type+ ') send_' + dangling.name + '<- mkConnectionSend("' + dangling.name+'");\n')
                  sends += 1

            # instantiate multiplexors - we need one per link 
            if(recvs > 0):
              print "Querying " + platform + ' <- ' + targetPlatform
              hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
              header.write('CHANNEL_VIRTUALIZER#(0,1) virtual_out_' + targetPlatform  + '<- mkChannelVirtualizer(?,' + hopFromTarget + '.write);\n')
              header.write('ARBITED_CLIENT#(' + str(recvs) + ') switch_out_' + targetPlatform  + '<- mkArbitedClient(?, virtual_out_' + targetPlatform + '.writePorts[0].write);\n')

            if(sends > 0):
              print "Querying " + platform + ' -> ' + targetPlatform
              hopToTarget = self.environment.transitTablesOutgoing[platform][targetPlatform]
              header.write('CHANNEL_VIRTUALIZER#(1,0) virtual_in_' + targetPlatform  + '<- mkChannelVirtualizer(' + hopFromTarget + '.read,?);\n')
              header.write('ARBITED_SERVER#(' + str(sends) + ') switch_in_' + targetPlatform  + '<- mkArbitedServer(virtual_in_' + targetPlatform + '.readPorts[0].read,?);\n')

            # hook 'em up
            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              if(dangling.sc_type == 'Recv'):
                  header.write('Empty pack_recv_' + dangling.name + ' <- mkPacketizeConnectionReceive(recv_' + dangling.name+',switch_out_' + targetPlatform  + '.requestPorts[' + str(dangling.idx) + '],' + str(dangling.idx) + ');\n')
              if(dangling.sc_type == 'Send'):
                  header.write('Empty pack_send_' + dangling.name + ' <- mkPacketizeConnectionSend(send_' + dangling.name+',switch_in_' + targetPlatform  +'.requestPorts['+str(dangling.idx) + ']);\n')




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
