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
          platformLogBuildDir = 'multi_fpga/' + makePlatformLogName(platform.name,APM_NAME) + '/pm'

          platformBitfileAPMName = makePlatformBitfileName(platform.name,APM_NAME) + '.apm'
          platformBitfilePath = 'config/pm/private/' + makePlatformBitfileName(platform.name,APM_NAME)
          platformBitfileBuildDir = 'multi_fpga/' + makePlatformBitfileName(platform.name,APM_NAME) + '/pm/'

          wrapperLog =  platformLogBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/.bsc/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '_Wrapper.log'
          dictionaryFileDir =  platformBitfileBuildDir +'iface/src/dict/'  
          parameterFile =  platformBitfileBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/multifpga_routing.bsh'
          dictionaryFile =  platformBitfileBuildDir +'iface/src/dict/multifpga_routing.dic'
          try:
            os.makedirs(dictionaryFileDir) # why does the parameter file work?
          except OSError:
            oserr = 0
               
          self.platformData[platform.name] = {'LOG': wrapperLog, 'BSH': parameterFile, 'DIC': dictionaryFile, 'DANGLING': [], 'CONNECTED': {}, 'INDEX': {}, 'WIDTHS': {}}


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
      danglingChainSources = {};
      danglingChainSinks = {};
      for platformName in self.environment.getPlatformNames():
          self.parseDangling(platformName)
          # we should now check for matches
          for danglingNew in self.platformData[platformName]['DANGLING']:
              # build up lists of chains. 
              if(danglingNew.isChain()):
                print "Got chain " + danglingNew.name
                if(danglingNew.isSource()):
                  if(danglingNew.name in danglingChainSources):
                    danglingChainSources[danglingNew.name] += [danglingNew]
                  else:
                    danglingChainSources[danglingNew.name] = [danglingNew]
                else:
                  if(danglingNew.name in danglingChainSinks):
                    danglingChainSinks[danglingNew.name] += [danglingNew]
                  else:
                    danglingChainSinks[danglingNew.name] = [danglingNew]
                continue # don't fall down the usual code path here
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

      # link up the chains.  The algorithm below is suboptimal. 
      # for more complex topologies than the ACP, we will want to 
      # solve a mapping problem 
      # we may want to sort these or something to ensure that we don't form singelton links XXX
      # delete the length 1 chains immediately  -- they live on a single node
      for chainName in danglingChainSources.keys():
        if(len(danglingChainSources[chainName]) < 2):
          del danglingChainSources[chainName]
          del danglingChainSinks[chainName]
          print "Removing single platform chain " + chainName

      # Our algorithm here is highly suboptimal.  rotate sinks by one to get an offset list 
      # We assume that the fpga network is strongly connected and that we don't care about transport 
      # lengths.  Bad Bad Bad assumptions, but they work for the ACP
      for chainName in danglingChainSources.keys():
        chainSrcs = danglingChainSources[chainName]
        chainSinks = danglingChainSinks[chainName]
        
        # rotate sinks by one to get an offset list 
        chainSinks.append(chainSinks.pop(0))
        for i in range(len(chainSinks)):
          # we need to make sure the source we pick is not on the same platform.        
          if(chainSinks[i].platform == chainSrcs[i].platform):
            print "Sink/Src platforms match.  Something is wrong"

          chainSinks[i].chainPartner = chainSrcs[i]
          chainSrcs[i].chainPartner = chainSinks[i]
          # get them indexes
          print "Trying to pair " + chainSrcs[i].platform + " and " + chainSinks[i].platform + " on chain " + chainName
          self.assignIndices(chainSrcs[i],chainSinks[i])




      #unmatched connections are bad
      for dangling in danglingGlobal:
          if(not dangling.optional and not dangling.matched):
              print 'Unmatched connection ' + dangling.name
              sys.exit(0)

      # now that everything is matched we can ostensibly generate the header file
      # header must include device mapping as well

      # we generate a set of router stats 
      dictionary = "" 

      for platform in self.environment.getPlatformNames():
          header = open(self.platformData[platform]['BSH'],'w')
          header.write('// Generated by build pipeline\n\n')
          if(GENERATE_ROUTER_STATS):
             header.write('`include "awb/dict/STATS_ROUTER.bsh"\n\n')
     
          # toss out the mapping functions first
          header.write('module [CONNECTED_MODULE] mkCommunicationModule#(VIRTUAL_PLATFORM vplat) (Empty);\n')

          header.write('String platformName <- getSynthesisBoundaryPlatform();\n')
          header.write('messageM("Instantiating Custom Router on " + platformName); \n')

          # chains can and will have two different communications outlets, therefore, the chains connections
          # cannot be filled in until after all the links are instantiated
          # the chain insertion code must lexically come after the arbiter instantiation
          chainsStr = ''


          # handle the connections themselves
          for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
            header.write('// Connection to ' + targetPlatform + ' \n')
            sends = 0
            recvs = 0
            chains = 0           

            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              if(dangling.sc_type == 'Recv'):
                  header.write('CONNECTION_RECV#(Bit#(PHYSICAL_CONNECTION_SIZE)) recv_' + dangling.name + ' <- mkPhysicalConnectionRecv("' + dangling.name + '", tagged Invalid, False, "' + dangling.raw_type + '");\n')
                  dictionary += ('def STATS.ROUTER.' + dangling.name + '_BLOCKED "' + dangling.name +' cycles blocked";\n')
                  dictionary += ('def STATS.ROUTER.' + dangling.name + '_SENT "' + dangling.name +' cycles sent";\n')

                  if(GENERATE_ROUTER_STATS):
                    header.write('STAT blocked_' + dangling.name + ' <- mkStatCounter(`STATS_ROUTER_' + dangling.name + '_BLOCKED);\n')
                    header.write('STAT sent_' + dangling.name + ' <- mkStatCounter(`STATS_ROUTER_' + dangling.name + '_SENT);\n')

                  recvs += 1 
              if(dangling.sc_type == 'Send'):
                  header.write('CONNECTION_SEND#(Bit#(PHYSICAL_CONNECTION_SIZE)) send_' + dangling.name + ' <- mkPhysicalConnectionSend("' + dangling.name + '", tagged Invalid, False, "' + dangling.raw_type + '");\n')

                  sends += 1
              # only create a chain when we see the source
              if(dangling.sc_type == 'ChainSrc'):
                chains += 1 
                # we must create a logical chain information
                chainsStr += 'let chain_' + dangling.name + ' = LOGICAL_CHAIN_INFO{logicalName: "' + dangling.name + '", logicalType: "' + \
                             dangling.raw_type + '", computePlatform: "' + platform + '", incoming: pack_chain_' + dangling.name + \
                             ', outgoing: unpack_chain_' + dangling.name + '};\n'
                      
                chainsStr += 'registerChain(chain_' + dangling.name + ');\n'



            # instantiate multiplexors - we need one per link chains
            # must necessarily have two links, one in and one out.  We
            # now have two virtual channels for flow control purposes
            # the following code is fairly wrong.  We need to
            # aggregate all virtual channels across a link.  If we
            # don't have a strongly connected FPGA graph, this code
            # will fail miserably XXX
            egressType = ""
            ingressType = ""
            if(recvs + chains > 0):
              print "Querying " + platform + ' <- ' + targetPlatform
              hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
              # dump out the packet type for this link...
              via = hopFromTarget.replace(".","_") + '_write'
              egressType = "GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(\n" + \
                           "             1, TLog#(TAdd#(1," + str(recvs+chains) + ")) ,\n" + \
                           "             0,  TLog#(TAdd#(1,TMax#(1,TDiv#(PHYSICAL_CONNECTION_SIZE," + str(self.platformData[platform]['WIDTHS'][via]) + ")))),\n" + \
                           "             `UMF_PHY_CHANNEL_RESERVED_BITS, TSub#(" + str(self.platformData[platform]['WIDTHS'][via])  + ", TAdd#(TAdd#(1,TLog#(TAdd#(1," + str(recvs+chains) + "))),TAdd#(`UMF_PHY_CHANNEL_RESERVED_BITS, TLog#(TAdd#(1,TMax#(1,TDiv#(PHYSICAL_CONNECTION_SIZE," +  str(self.platformData[platform]['WIDTHS'][via]) + ")))))))), Bit#(" +  str(self.platformData[platform]['WIDTHS'][via]) + "))"
              header.write('CHANNEL_VIRTUALIZER#(0,2,' + egressType +') virtual_out_' + targetPlatform  + '<- mkChannelVirtualizer(?,' + hopFromTarget + '.write);\n')

            if(sends + chains > 0):
              print "Querying " + platform + ' -> ' + targetPlatform
              hopToTarget = self.environment.transitTablesOutgoing[platform][targetPlatform]
              via = hopToTarget.replace(".","_") + '_write'
              ingressType = "GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(\n" + \
                           "             1, TLog#(TAdd#(1," + str(sends+chains) + ")) ,\n" + \
                           "             0,  TLog#(TAdd#(1,TMax#(1,TDiv#(PHYSICAL_CONNECTION_SIZE," + str(self.platformData[platform]['WIDTHS'][via])  + ")))),\n" + \
                           "             `UMF_PHY_CHANNEL_RESERVED_BITS, TSub#(" + str(self.platformData[platform]['WIDTHS'][via]) + ", TAdd#(TAdd#(1,TLog#(TAdd#(1," + str(sends+chains) + "))),TAdd#(`UMF_PHY_CHANNEL_RESERVED_BITS, TLog#(TAdd#(1,TMax#(1,TDiv#(PHYSICAL_CONNECTION_SIZE," + str(self.platformData[platform]['WIDTHS'][via])  + ")))))))), Bit#(" + str(self.platformData[platform]['WIDTHS'][via])  + "))"

              header.write('CHANNEL_VIRTUALIZER#(2,0,' + ingressType + ') virtual_in_' + targetPlatform  + '<- mkChannelVirtualizer(' + hopFromTarget + '.read,?);\n')

            if(recvs + chains > 0):
              hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
              header.write('EGRESS_SWITCH#(' + str(recvs + chains) + ',' + egressType + ') switch_out_' + targetPlatform  + '<- mkEgressSwitch(virtual_in_' + targetPlatform + '.readPorts[1].read, virtual_out_' + targetPlatform + '.writePorts[0].write);\n')

            if(sends + chains > 0):
              hopToTarget = self.environment.transitTablesOutgoing[platform][targetPlatform]
              header.write('INGRESS_SWITCH#(' + str(sends + chains) + ',' + ingressType + ') switch_in_' + targetPlatform  + '<- mkIngressSwitch(virtual_in_' + targetPlatform + '.readPorts[0].read, virtual_out_' + targetPlatform + '.writePorts[1].write);\n')

            # hook 'em up
            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              if(dangling.sc_type == 'Recv'):
	        header.write('NumTypeParam#('+ str(dangling.bitwidth) +') width_recv_' + dangling.name +' = ?;\n')
                if(GENERATE_ROUTER_STATS):
                  header.write('Empty pack_recv_' + dangling.name + ' <- mkPacketizeConnectionReceive(recv_' + dangling.name+',switch_out_' + targetPlatform  + '.egressPorts[' + str(dangling.idx) + '],' + str(dangling.idx) + ', width_recv_' + dangling.name + ',blocked_'+ dangling.name +', sent_'+ dangling.name +');\n')
                else:
                  header.write('Empty pack_recv_' + dangling.name + ' <- mkPacketizeConnectionReceive(recv_' + dangling.name+',switch_out_' + targetPlatform  + '.egressPorts[' + str(dangling.idx) + '],' + str(dangling.idx) + ', width_recv_' + dangling.name + ', ?, ?);\n') #Woohoo a ?
              if(dangling.sc_type == 'Send'):
	        header.write('NumTypeParam#('+ str(dangling.bitwidth) +') width_send_' + dangling.name +' = ?\n;')
                header.write('Empty unpack_send_' + dangling.name + ' <- mkPacketizeConnectionSend(send_' + dangling.name+',switch_in_' + targetPlatform  +'.ingressPorts['+str(dangling.idx) + '], ' + str(dangling.idx) + ', width_send_' + dangling.name+');\n')
              if(dangling.sc_type == 'ChainSrc' ):
                header.write('PHYSICAL_CHAIN_OUT unpack_chain_' + dangling.name + ' <- mkPacketizeOutgoingChain(switch_in_' + targetPlatform  +'.ingressPorts['+str(dangling.idx) + ']);\n')
              if(dangling.sc_type == 'ChainSink' ):
                header.write('PHYSICAL_CHAIN_IN pack_chain_' + dangling.name + ' <- mkPacketizeIncomingChain(switch_out_' + targetPlatform  + '.egressPorts[' + str(dangling.idx) + '],' + str(dangling.idx) + ');\n')
          
     
          # Add in chain insertion code 
          header.write(chainsStr + '\n')

          header.write('endmodule\n')
          header.close();

      #write out all the union dictionaries
      for platform in self.environment.getPlatformNames():
          header = open(self.platformData[platform]['DIC'],'w')
          header.write(dictionary)
          header.close();

  def parseDangling(self, platformName):
      logfile = open(self.platformData[platformName]['LOG'],'r')
      print "Processing: " + self.platformData[platformName]['LOG']
      for line in logfile:
          # also pull out link widths
          if(re.match('.*SizeOfVia:.*',line)):
            match = re.search(r'.*SizeOfVia:(\w+):(\d+)',line)
            if(match):
              self.platformData[platformName]['WIDTHS'][match.group(1)] = int(match.group(2))
          if(re.match("Compilation message: .*: Dangling",line)):
              match = re.search(r'.*Dangling (\w+) {(.*)} \[(\d+)\]:(\w+):(\w+):(\w+):(\d+)', line)
              if(match):
            #python groups begin at index 1  
                  print 'found connection: ' + line
                  if(match.group(1) == "Chain"):
                    print "Got chain " + match.group(3)
                    sc_type = "ChainSrc"
                  else:
                    sc_type = match.group(1)

                  self.platformData[platformName]['DANGLING'] += [DanglingConnection(sc_type, 
                                                                                match.group(2),
                                                                                match.group(3),
                                                                                match.group(4),
                                                                                match.group(5),
                                                                                match.group(6),
                                                                                match.group(7))]
                  if(match.group(1) == "Chain"):
                    self.platformData[platformName]['DANGLING'] += [DanglingConnection("ChainSink", 
                                                                                match.group(2),
                                                                                match.group(3),
                                                                                match.group(4),
                                                                                match.group(5),
                                                                                match.group(6),
                                                                                match.group(7))]

              else:
                  print "Malformed connection message: " + line
                  sys.exit(-1)
