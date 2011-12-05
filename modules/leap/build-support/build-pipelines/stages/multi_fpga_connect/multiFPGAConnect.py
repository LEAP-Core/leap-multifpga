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
from via import *

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
               
          self.platformData[platform.name] = {'LOG': wrapperLog, 'BSH': parameterFile, 'DIC': dictionaryFile, 'DANGLING': [], 'CONNECTED': {}, 'INDEX': {}, 'WIDTHS': {}, 'INGRESS_VIAS': {}, 'EGRESS_VIAS': {}}


          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'] += [parameterFile] 
 
      subbuild = moduleList.env.Command( 
          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
          moduleList.topModule.moduleDependency['FPGA_PLATFORM_LOGS'] + [moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0]] + [moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + mappingFile[0]] + [moduleList.env['DEFS']['BUILD_DIR'] + '/site_scons/multi_fpga_connect/multiFPGAConnect.py'],
          self.synthesizeRouters
          )                   
      print "subbuild: " + str(subbuild)


      moduleList.topDependency += [subbuild]

  def assignIndices(self,sourceConn,sinkConn):
    print "Now processing connection %s between %s <-> %s" % (sourceConn.name, sourceConn.platform, sinkConn.platform)
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


  def generateEgressMultiplexor(self, platform): 
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}
    multiplexor_dictionary = ""
    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      egressVias = self.platformData[platform]['EGRESS_VIAS'][targetPlatform]
      hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
      egressMethod = hopFromTarget.replace(".","_") + '_write'
      egressViaWidth = self.platformData[platform]['WIDTHS'][egressMethod]

      interfaceName = 'EgressMultiplexor_' + platform + '_to_' + targetPlatform
      moduleName = 'egressMultiplexor_' + platform + '_to_' + targetPlatform
      moduleAggregateTypeName = interfaceName +'Aggregate'

      multiplexor_definition += 'typedef struct { \n'
      for via in egressVias:
        multiplexor_definition += '\tMaybe#(Bit#(' + str(via.via_width) + '))  '  + via.via_method + '_data;\n'   
      multiplexor_definition += '} ' + moduleAggregateTypeName + ' deriving (Bits,Eq);\n\n'

      multiplexor_definition += 'interface ' + interfaceName + ';\n'

      multiplexor_names[targetPlatform] = 'inst_' + moduleName

      multiplexor_instantiation += 'let ' + multiplexor_names[targetPlatform] + ' <- ' + moduleName + '(' + hopFromTarget + '.write,\n'
      multiplexor_instantiation += '    ' + hopFromTarget + '.write_ready);\n'

      for via in egressVias:
        multiplexor_definition += '\tmethod Action ' + via.via_method + '(Bit#(' + str(via.via_width)  + ') data);\n'
 
      multiplexor_definition += '\nendinterface\n\n'

      multiplexor_definition += 'module [CONNECTED_MODULE] ' + moduleName + '#(function Action write(Bit#(' + str(egressViaWidth) +') goSteelers),\n'
      multiplexor_definition += '                           function Bool write_ready() ) (' + interfaceName + ');\n'
      # mkDwire with empty string signifier...
      for via in egressVias:
        multiplexor_definition += '  let ' + via.via_method + '_wire <- mkDWire(tagged Invalid);\n' 
        multiplexor_definition += '  let ' + via.via_method + '_pulse <- mkPulseWire();\n' 
        
        if(GENERATE_ROUTER_STATS):
          multiplexor_dictionary += ('def STATS.ROUTER.' + moduleName + '_' + via.via_method + '_ENQUEUED " ' + via.via_method +' cycles enqueued";\n')
          multiplexor_definition += '\tSTAT enqueued_' + via.via_method + ' <- mkStatCounter(`STATS_ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED);\n'
     
      #stats for the merger
      if(GENERATE_ROUTER_STATS):
        multiplexor_definition += '\tSTAT merged_' + moduleName + ' <- mkStatCounter(`STATS_ROUTER_' + moduleName + '_MERGED);\n'
        multiplexor_dictionary += ('def STATS.ROUTER.' + moduleName + '_MERGED"' + moduleName +' cycles enqueued";\n')

      multiplexor_definition += '\n\trule mergeData(\n'

      first = 1
      for via in egressVias:
        comma = ' || '
        if(first):
          comma = ' ' 
        multiplexor_definition += comma + '\n\t\t' + via.via_method + '_pulse'
        first = 0 

      multiplexor_definition += ');//Only if there\'s data...\n'
      #multiplexor_definition += '    $display("mergeData ' + moduleName  +'  fires");\n'

      if(GENERATE_ROUTER_STATS):
        multiplexor_definition += '\t\tmerged_' + moduleName + '.incr();\n'

      multiplexor_definition += '\t\twrite(zeroExtendNP(pack(' + moduleAggregateTypeName + '{\n'
      first = 1
      for via in egressVias:
        comma = ','
        if(first):
          comma = ' ' 
        multiplexor_definition += '\t\t\t' + comma + via.via_method + '_data:' + via.via_method + '_wire\n'
        first = 0
      multiplexor_definition += '\t\t})));\n'
      multiplexor_definition += '\tendrule\n\n'

      for via in egressVias:
        multiplexor_definition += '\tmethod Action ' + via.via_method + '(Bit#(' + str(via.via_width)  + ') data) if(write_ready);\n'
        #multiplexor_definition += '    $display("' + via.via_method + '_wire fires");\n'
        multiplexor_definition += '\t\t' + via.via_method + '_wire <= tagged Valid data;\n'
        multiplexor_definition += '\t\t' + via.via_method + '_pulse.send;\n'
        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += '\t\tenqueued_' + via.via_method + '.incr();\n'
        multiplexor_definition += '\tendmethod\n\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names, multiplexor_dictionary]


  def generateEgressMultiplexorParSerial(self, platform): 
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}
    multiplexor_dictionary = ""
    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      egressVias = self.platformData[platform]['EGRESS_VIAS'][targetPlatform]
      hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
      egressMethod = hopFromTarget.replace(".","_") + '_write'
      egressViaWidth = self.platformData[platform]['WIDTHS'][egressMethod]

      interfaceName = 'EgressMultiplexor_' + platform + '_to_' + targetPlatform
      moduleName = 'egressMultiplexor_' + platform + '_to_' + targetPlatform
      moduleAggregateTypeName = interfaceName +'Aggregate'

      multiplexor_definition += '\ntypedef struct { \n'
      for via in egressVias:
        multiplexor_definition += '\tMaybe#(Bit#(' + str(via.via_width) + '))  '  + via.via_method + '_data;\n'   
      multiplexor_definition += '} ' + moduleAggregateTypeName + ' deriving (Bits,Eq); \n\n'

      multiplexor_definition += 'interface ' + interfaceName + '\n;'

      multiplexor_names[targetPlatform] = 'inst_' + moduleName

      multiplexor_instantiation += 'let ' + multiplexor_names[targetPlatform] + ' <- ' + moduleName + '(' + hopFromTarget + '.write,\n'
      multiplexor_instantiation += '    ' + hopFromTarget + '.write_ready);\n'

      for via in egressVias:
        multiplexor_definition += '\tmethod Action ' + via.via_method + '(Bit#(' + str(via.via_width)  + ') data);\n\n'
 
      multiplexor_definition += 'endinterface\n\n'

      multiplexor_definition += 'module [CONNECTED_MODULE] ' + moduleName + '#(function Action write(Bit#(' + str(egressViaWidth) +') goSteelers),\n'
      multiplexor_definition += '                           function Bool write_ready() ) (' + interfaceName + ');\n'
      # mkDwire with empty string signifier...
      for via in egressVias:
        multiplexor_dictionary += ('def STATS.ROUTER.' + moduleName + '_' + via.via_method + '_ENQUEUED" ' + via.via_method +' cycles enqueued";\n')
        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += '\tSTAT enqueued_' + via.via_method + ' <- mkStatCounter(`STATS_ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED);\n'

      multiplexor_dictionary += ('def STATS.ROUTER.' + moduleName + '_MERGED"' + moduleName +' cycles enqueued";\n')
      if(GENERATE_ROUTER_STATS):
        multiplexor_definition += '\tSTAT merged_' + moduleName + ' <- mkStatCounter(`STATS_ROUTER_' + moduleName + '_MERGED);\n'


      for via in egressVias:
        multiplexor_definition += '  method Action ' + via.via_method + '(Bit#(' + str(via.via_width)  + ') data) if(write_ready);\n'
        #multiplexor_definition += '    $display("' + via.via_method + '_wire fires");\n'


        multiplexor_definition += '    write(zeroExtendNP(pack(' + moduleAggregateTypeName + '{\n'
        first = 1
        for viaOut in egressVias:
          comma = ','
          if(first):
            comma = ' ' 
          via_data = 'tagged Invalid'
          if(viaOut == via):
            via_data ='tagged Valid data'
          multiplexor_definition += '      ' + comma + viaOut.via_method + '_data:' + via_data + '\n'
          first = 0
        multiplexor_definition += '    })));\n'



        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += 'enqueued_' + via.via_method + '.incr();\n'
        multiplexor_definition += '  endmethod\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names, multiplexor_dictionary]


  def generateEgressMultiplexorSerial(self, platform): 
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}
    multiplexor_dictionary = ""
    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      egressVias = self.platformData[platform]['EGRESS_VIAS'][targetPlatform]
      hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
      egressMethod = hopFromTarget.replace(".","_") + '_write'
      egressViaWidth = self.platformData[platform]['WIDTHS'][egressMethod]

      interfaceName = 'EgressMultiplexor_' + platform + '_to_' + targetPlatform
      moduleName = 'egressMultiplexor_' + platform + '_to_' + targetPlatform
      moduleAggregateTypeName = interfaceName +'Aggregate'

      multiplexor_definition += 'typedef struct { \n'
      for via in egressVias:
        multiplexor_definition += '   Maybe#(Bit#(' + str(via.via_width) + '))  '  + via.via_method + '_data;\n'   
      multiplexor_definition += '} ' + moduleAggregateTypeName + ' deriving (Bits,Eq); \n'

      multiplexor_definition += 'interface ' + interfaceName + '\n;'

      multiplexor_names[targetPlatform] = 'inst_' + moduleName

      multiplexor_instantiation += 'let ' + multiplexor_names[targetPlatform] + ' <- ' + moduleName + '(' + hopFromTarget + '.write,\n'
      multiplexor_instantiation += '    ' + hopFromTarget + '.write_ready);\n'

      for via in egressVias:
        multiplexor_definition += '  method Action ' + via.via_method + '(Bit#(' + str(via.via_width)  + ') data);\n'
 
      multiplexor_definition += 'endinterface\n\n'

      multiplexor_definition += 'module [CONNECTED_MODULE] ' + moduleName + '#(function Action write(Bit#(' + str(egressViaWidth) +') goSteelers),\n'
      multiplexor_definition += '                           function Bool write_ready() ) (' + interfaceName + ');\n'
      # mkDwire with empty string signifier...
      for via in egressVias:
        multiplexor_dictionary += ('def STATS.ROUTER.' + moduleName + '_' + via.via_method + '_ENQUEUED" ' + via.via_method +' cycles enqueued";\n')
        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += 'STAT enqueued_' + via.via_method + ' <- mkStatCounter(`STATS_ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED);\n'

      multiplexor_dictionary += ('def STATS.ROUTER.' + moduleName + '_MERGED"' + moduleName +' cycles enqueued";\n')
      if(GENERATE_ROUTER_STATS):
        multiplexor_definition += 'STAT merged_' + moduleName + ' <- mkStatCounter(`STATS_ROUTER_' + moduleName + '_MERGED);\n'

      viaCount = 0
      for via in egressVias:
        multiplexor_definition += '  method Action ' + via.via_method + '(Bit#(' + str(via.via_width)  + ') data) if(write_ready);\n'
        #multiplexor_definition += '    $display("' + via.via_method + '_wire fires");\n'

        multiplexor_definition += '    Bit#(TLog#(TAdd#(1,' + str(len(egressVias)) + '))) tag = ' + str(viaCount) + ';\n'
        multiplexor_definition += '    write(zeroExtendNP({tag,data}));\n'
        viaCount = viaCount + 1
        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += 'enqueued_' + via.via_method + '.incr();\n'
        multiplexor_definition += '  endmethod\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names, multiplexor_dictionary]
            

  def generateIngressMultiplexor(self, platform):
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}
    multiplexor_dictionary = ""
    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      ingressVias = self.platformData[platform]['INGRESS_VIAS'][targetPlatform]
      hopToTarget = self.environment.transitTablesOutgoing[platform][targetPlatform]
      ingressMethod = hopToTarget.replace(".","_") + '_read'
      ingressViaWidth = self.platformData[platform]['WIDTHS'][ingressMethod]

      interfaceName = 'IngressMultiplexor_' + platform + '_to_' + targetPlatform
      moduleName = 'ingressMultiplexor_' + platform + '_to_' + targetPlatform
      moduleAggregateTypeName = interfaceName +'Aggregate'

      multiplexor_definition += '\n\ntypedef struct { \n'
      for via in ingressVias:
        multiplexor_definition += '\tMaybe#(Bit#(' + str(via.via_width) + '))  '  + via.via_method + '_data;\n'   
      multiplexor_definition += '} ' + moduleAggregateTypeName + ' deriving (Bits,Eq); \n'

      multiplexor_definition += 'interface ' + interfaceName + '\n;'

      multiplexor_names[targetPlatform] = 'inst_' + moduleName

      multiplexor_instantiation += 'let ' + multiplexor_names[targetPlatform] + ' <- ' + moduleName + '(' + hopToTarget + '.first,' + hopToTarget + '.deq);\n'

      for via in ingressVias:
        multiplexor_definition += '\tmethod Bit#(' + str(via.via_width) + ') ' + via.via_method + '_first();\n'
        multiplexor_definition += '\tmethod Action ' + via.via_method + '_deq();\n\n'
 
      multiplexor_definition += 'endinterface\n\n'

      multiplexor_definition += 'module [CONNECTED_MODULE] ' + moduleName + '#(function Bit#(' + str(ingressViaWidth) + ') first(), function Action deq()) (' + interfaceName + ');\n'

      # mkDwire with empty string signifier...
      for via in ingressVias:
        multiplexor_definition += '\tlet ' + via.via_method + '_fifo <- mkBypassFIFOF();\n' 

        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += '\tSTAT dequeued_' + via.via_method + ' <- mkStatCounter(`STATS_ROUTER_' + moduleName + '_' + via.via_method + '_DEQUEUED);\n'
          multiplexor_dictionary += ('def STATS.ROUTER.' + moduleName + '_' + via.via_method + '_DEQUEUED "' + via.via_method +' cycles dequeued";\n')

      if(GENERATE_ROUTER_DEBUG):   
        multiplexor_dictionary += ('def DEBUG_SCAN.ROUTER.' + moduleName + '_DEBUG "' + moduleName  +' debug";\n')
        via_full_string = ''
        via_empty_string = ''
        firstPass = True
        for via in ingressVias:
          seperator = ','
          if(firstPass):
            seperator = ''
          via_full_string += seperator + 'pack(' +via.via_method +'_fifo.notFull)'
          via_empty_string += seperator + 'pack(' +via.via_method +'_fifo.notEmpty)'
          # lay down a couple of debug scan chains here and insert crap in dictionary
          firstPass = False          
        multiplexor_definition += '\tDEBUG_SCAN#(Bit#(' + str(2*(len(ingressVias))) + ')) ' + moduleName + '_DEBUG <- mkDebugScanNode(`DEBUG_SCAN_ROUTER_' +moduleName + '_DEBUG, {' + via_full_string + ',' + via_empty_string + '});\n' 
          





      multiplexor_definition += '\n\trule sendData;\n\n'
      # multiplexor_definition += '    $display("ingress mergeData ' + moduleName  +'  fires");\n'
      multiplexor_definition += '\t\tBit#(' + str(ingressViaWidth) + ') data_uncut = first();\n'
      multiplexor_definition += '\t\tdeq();\n'
      multiplexor_definition += '\t\t' + moduleAggregateTypeName + '  data_tuple = unpack(truncateNP(data_uncut));\n'

      for via in ingressVias:
        multiplexor_definition += '\t\t' + via.via_method + '_fifo.enq(data_tuple.' + via.via_method + '_data);\n\n'

      multiplexor_definition += '\tendrule\n\n'

      for via in ingressVias:
        multiplexor_definition += '\trule deq_' + via.via_method + '(' + via.via_method + '_fifo.first() matches tagged Invalid);\n\n'
        multiplexor_definition += '\t\t' + via.via_method + '_fifo.deq();\n\n'
        multiplexor_definition += '\tendrule\n\n'

      for via in ingressVias:
        multiplexor_definition += '\tmethod Bit#(' + str(via.via_width) + ') ' + via.via_method + '_first() if (' + via.via_method + '_fifo.first() matches tagged Valid .data );\n\n'
        multiplexor_definition += '\t\treturn data;\n\n'
        multiplexor_definition += '\tendmethod\n\n'

        multiplexor_definition += '\tmethod Action ' + via.via_method + '_deq() if (' + via.via_method + '_fifo.first() matches tagged Valid .data );\n\n'
        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += '\t\tdequeued_' + via.via_method + '.incr();\n'
        multiplexor_definition += '\t\t' + via.via_method + '_fifo.deq();\n'
        multiplexor_definition += '\tendmethod\n\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names,multiplexor_dictionary]

  def generateIngressMultiplexorSerial(self, platform):
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}
    multiplexor_dictionary = ""
    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      ingressVias = self.platformData[platform]['INGRESS_VIAS'][targetPlatform]
      hopToTarget = self.environment.transitTablesOutgoing[platform][targetPlatform]
      ingressMethod = hopToTarget.replace(".","_") + '_read'
      ingressViaWidth = self.platformData[platform]['WIDTHS'][ingressMethod]

      interfaceName = 'IngressMultiplexor_' + platform + '_to_' + targetPlatform
      moduleName = 'ingressMultiplexor_' + platform + '_to_' + targetPlatform
      moduleAggregateTypeName = interfaceName +'Aggregate'

      multiplexor_definition += 'typedef struct { \n'
      for via in ingressVias:
        multiplexor_definition += '   Maybe#(Bit#(' + str(via.via_width) + '))  '  + via.via_method + '_data;\n'   
      multiplexor_definition += '} ' + moduleAggregateTypeName + ' deriving (Bits,Eq); \n'

      multiplexor_definition += 'interface ' + interfaceName + '\n;'

      multiplexor_names[targetPlatform] = 'inst_' + moduleName

      multiplexor_instantiation += 'let ' + multiplexor_names[targetPlatform] + ' <- ' + moduleName + '(' + hopToTarget + '.first,' + hopToTarget + '.deq);\n'

      for via in ingressVias:
        multiplexor_definition += '  method ActionValue#(Bit#(' + str(via.via_width) + ')) ' + via.via_method + '();\n'
 
      multiplexor_definition += 'endinterface\n\n'

      multiplexor_definition += 'module [CONNECTED_MODULE] ' + moduleName + '#(function Bit#(' + str(ingressViaWidth) + ') first(), function Action deq()) (' + interfaceName + ');\n'
      # mkDwire with empty string signifier...
      # here we make the simplifiying assumption that all the bitwidths are the same. 
      multiplexor_definition += '   Tuple2#(Bit#(TLog#(TAdd#(1,' + str(len(ingressVias)) + '))), Bit#(' + str(via.via_width) + ')) rxdata = unpack(truncateNP(first()));\n' 
      via_count = 0
      for via in ingressVias:
        multiplexor_definition += '  let ' + via.via_method + '_fifo <- mkBypassFIFOF();\n' # Bypass fifo saves latency.
        multiplexor_dictionary += ('def STATS.ROUTER.' + moduleName + '_' + via.via_method + '_DEQUEUED"' + via.via_method +' cycles dequeued";\n')
        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += 'STAT dequeued_' + via.via_method + ' <- mkStatCounter(`STATS_ROUTER_' + moduleName + '_' + via.via_method + '_DEQUEUED);\n'
        multiplexor_definition += '  rule sendData' + str(via_count) + '(tpl_1(rxdata) == ' + str(via_count) + ');\n'
        # multiplexor_definition += '    $display("ingress mergeData ' + moduleName  +'  fires");\n'
        multiplexor_definition += '      deq();\n'
        multiplexor_definition += '      ' + via.via_method + '_fifo.enq(tpl_2(rxdata));\n'
        multiplexor_definition += '  endrule\n'
        via_count += 1

      for via in ingressVias:
        multiplexor_definition += '  method ActionValue#(Bit#(' + str(via.via_width) + ')) ' + via.via_method + '();\n'
        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += 'dequeued_' + via.via_method + '.incr();\n'
        multiplexor_definition += '    ' + via.via_method + '_fifo.deq();\n'
        multiplexor_definition += '    return ' + via.via_method + '_fifo.first();\n'
        multiplexor_definition += '  endmethod\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names,multiplexor_dictionary]

    
  def synthesizeRouters(self, target, source, env):    
    self.processDanglingConnections()
    self.analyzeNetwork()
    self.generateCode()

  #First we parse the files, and then attempt to make all the connections.  Lots of dictionaries.
  def processDanglingConnections(self):
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

  def generateRouterTypes(self, viaWidth, viaLinks):

    # At some point, we can reduce the number of header bits based on 
    # what we actually assign.  This would permit us to allocate smalled link
      
    headerType = "GENERIC_UMF_PACKET_HEADER#(\n" + \
                 "             0, TLog#(TAdd#(1," + str(viaLinks) + ")) ,\n" + \
                 "             0, TLog#(TAdd#(1,TMax#(1,TDiv#(PHYSICAL_CONNECTION_SIZE," + str(viaWidth) + ")))),\n" + \
                 "             0, TSub#(" + str(viaWidth)  + ", TAdd#(TLog#(TAdd#(1," + str(viaLinks) + "))," + \
                 "TLog#(TAdd#(1,TMax#(1,TDiv#(PHYSICAL_CONNECTION_SIZE," +  str(viaWidth) + ")))))))"

    bodyType = "Bit#(" +  str(viaWidth) + ")"
      
    type = "GENERIC_UMF_PACKET#(" + headerType + ", " + bodyType + ")"

    return [headerType, bodyType, type]


  def analyzeNetwork(self):
    self.analyzeNetworkRandom()

  # This via allocation algorithm selects the "longest" job for allocation and 
  # sticks it on the least loaded processor.  There are assymmetries in this problem
  # which do not exist in the processor scheduling problem and that must be dealt with.    
  def analyzeNetworkLJF(self):



    for platform in self.environment.getPlatformNames():
      for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():

        # for this target, we assume that we have a monolithic fifo via.  
        # first, we must decide how to break up the via.  We will store that information
        # and use it later

        headerSize = 12 # simplifying assumption: headers have uniform size.  This isn't actually the case.

        # handle the connections themselves
        recvs = 0
        chains = 0           

        # let's first build up a data structure representing job
        # lengths, initializing everything to equal weight.
        # Since chains have relatively little cost, we give them much less weight than 
        # normal links
        # XXX here is where we want to look at activity factors
        for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
          if(dangling.sc_type == 'Recv'):
            recvs += 1 
            dangling.activity = 100 

          # only create a chain when we see the source
          if(dangling.sc_type == 'ChainSrc'):
            chains += 1 
            dangling.activity = 1 

        hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
        egressVia = hopFromTarget.replace(".","_") + '_write'
        hopToTarget = self.environment.transitTablesOutgoing[targetPlatform][platform]
        ingressVia = hopToTarget.replace(".","_") + '_read'

        firstAllocationPass = True; # We can't terminate in the first pass 
        viaWidthsFinal = [] # at some point, we'll want to derive this.  
        viaLinksFinal = [] 
        maxLoad = 0;

        sortedLinks = sorted(self.platformData[platform]['CONNECTED'][targetPlatform], key = lambda dangling: dangling.activity * -2048 + dangling.bitwidth) # sorted is ascending

        # The general strategy here is 
        # 1) hueristically pick lane widths
        # 2) Assign links to lanes using Longest Job First hueristic
        # Repeat until maximum link occupancy increases (although we might just try repeatedly and keep all the results) 

        # We can't allow the code to become totally assymetric yet. 
        # To make the code assymetric, ingress vias would need to handle a parametric number
        # of feed back loops. 
        for numberOfVias in [MAX_NUMBER_OF_VIAS]:
          viaLoads = []
          viaSizingIdx = 0
          viaLinks = []
          viaWidths = []
          
          # pick our via links deterministically
          for via in range(numberOfVias):
            viaLinks.append(1) # We need flow control..
            viaLoads.append(0)
            if(via == 0):
              viaWidths.append(self.platformData[platform]['WIDTHS'][egressVia] - 1)
            else: # carve off a lane for the longest running job
              while(viaWidths[0] < (sortedLinks[viaSizingIdx].bitwidth + headerSize)): # Give extra for header sizing
                viaSizingIdx += 1
              # found minimum, ajust the top guy
              viaWidths[0] = viaWidths[0] - (sortedLinks[viaSizingIdx].bitwidth + headerSize)
              viaWidths.append(sortedLinks[viaSizingIdx].bitwidth + headerSize -1) # need one bit for the header
              viaSizingIdx += 1


          # send/recv pairs had better be matched.
          # so let's match them up
          # need to maintain the sorted order

          platformConnectionsProvisional = []
          targetPlatformConnectionsProvisional = []
          for danglingIdx in range(len(sortedLinks)):           


            if((sortedLinks[danglingIdx].sc_type == 'Recv') or (sortedLinks[danglingIdx].sc_type == 'ChainSink')):
              # depending on the width of the vias, and the width of our type we get different loads on different processors
              # need to choose the minimum
              minIdx = -1 
              minLoad = 0
              for via in range(numberOfVias):
                extraChunk = 0
                if((sortedLinks[danglingIdx].bitwidth - headerSize )%viaWidths[via] > 0):
                  extraChunk = 1

                load = dangling.activity * (1 + (sortedLinks[danglingIdx].bitwidth - headerSize )/viaWidths[via] + extraChunk) + viaLoads[via]
                
                # We don't do a great job here of evaluating opportunity cost.  Picking the longest running on the fastest processor 
                # might be a bad choice.
                if(load < minLoad or minIdx == -1):
                  minIdx = via
                  minLoad = load
              
              viaLoads[minIdx] = minLoad
              platformConnectionsProvisional.append([sortedLinks[danglingIdx].name, sortedLinks[danglingIdx].sc_type, minIdx, viaLinks[minIdx]])
              targetPlatformConnectionsProvisional.append([sortedLinks[danglingIdx].name, inverseSCType(sortedLinks[danglingIdx].sc_type), minIdx, viaLinks[minIdx]])  
              print "Assigning Recv " + sortedLinks[danglingIdx].name   + " Idx " + str(minIdx) + " Link " + str(viaLinks[minIdx]) + "\n"
              viaLinks[minIdx] += 1


          platformConnections = sorted(self.platformData[platform]['CONNECTED'][targetPlatform],key = lambda connection: connection.name)
          targetPlatformConnections = sorted(self.platformData[targetPlatform]['CONNECTED'][platform],key = lambda connection: connection.name)
          print "Lengths: "  + str(len(platformConnections)) + " " + str(len(targetPlatformConnections))  
          #Did we do better than last time?
          if(maxLoad < max(viaLoads) or firstAllocationPass):
            maxLoad = max(viaLoads)
            viaWidthsFinal = viaWidths
            viaLinksFinal = viaLinks
            for provisional in platformConnectionsProvisional:
              for idx in range(len(platformConnections)): # we can probably do better than this n^2 loop. 
                # Watch out for chain Sinks and sources
                if((platformConnections[idx].name == provisional[0]) and (platformConnections[idx].sc_type == provisional[1])): 
                  platformConnections[idx].via_idx  = provisional[2]
                  platformConnections[idx].via_link = provisional[3]
                  print "Assigning egress " + platformConnections[idx].name + ' of type ' + platformConnections[idx].sc_type  +' ' + str(provisional[2]) + ' ' + str(provisional[3])
            for provisional in targetPlatformConnectionsProvisional:
              for idx in range(len(targetPlatformConnections)): # we can probably do better than this n^2 loop. 
                # Watch out for chain Sinks and sources
                if((targetPlatformConnections[idx].name == provisional[0]) and (targetPlatformConnections[idx].sc_type == provisional[1])):    
                  targetPlatformConnections[idx].via_idx  = provisional[2]
                  targetPlatformConnections[idx].via_link = provisional[3]

                  print "Assigning ingress " + targetPlatformConnections[idx].name + ' of type ' + targetPlatformConnections[idx].sc_type  +' ' + str(provisional[2]) + ' ' + str(provisional[3])
          else:
            #Quit while we're ahead
            break
          firstAllocationPass = False

        self.platformData[platform]['EGRESS_VIAS'][targetPlatform] = []
        self.platformData[targetPlatform]['INGRESS_VIAS'][platform] = []
            
                                         
        # We're dropping some bits here
        # now that we have link assignment, we can enumerate the vias
        for via in range(len(viaWidths)):
          [headerType, bodyType, type] = self.generateRouterTypes(viaWidthsFinal[via], viaLinksFinal[via])

          egress = Via("egress", headerType, bodyType, type, viaWidthsFinal[via], viaLinksFinal[via], viaLinksFinal[via] - 1, 1, hopFromTarget.replace(".","_")  + str(via) + '_write', 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_")  + str(via), 0, via)

          ingress = Via("ingress", headerType, bodyType, type, viaWidthsFinal[via], viaLinksFinal[via], viaLinksFinal[via] - 1, 1, hopToTarget.replace(".","_") + str(via) + '_read', 'switch_ingress_' + platform + '_from_' + targetPlatform + '_' + hopToTarget.replace(".","_") + str(via), 0, via)

          self.platformData[platform]['EGRESS_VIAS'][targetPlatform].append(egress)
          self.platformData[targetPlatform]['INGRESS_VIAS'][platform].append(ingress) 
          print "Via pair " + egress.via_switch + ": " + str(via) + ' width: '  + str(viaWidthsFinal[via]) + ' links" ' + str(viaLinksFinal[via])




         



  def analyzeNetworkRandom(self):

    numberOfVias = MAX_NUMBER_OF_VIAS # let's do a simple scheme with an equal number of vias.

    for platform in self.environment.getPlatformNames():
      for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
        # instantiate multiplexors - we need one per link chains
        # must necessarily have two links, one in and one out.  We
        # now have two virtual channels for flow control purposes
        # the following code is fairly wrong.  We need to
        # aggregate all virtual channels across a link.  If we
        # don't have a strongly connected FPGA graph, this code
        # will fail miserably XXX
        
        # for this target, we assume that we have a monolithic fifo via.  
        # first, we must decide how to break up the via.  We will store that information
        # and use it later

        # handle the connections themselves
        recvs = 0
        chains = 0           

        for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
          if(dangling.sc_type == 'Recv'):
            recvs += 1 

          # only create a chain when we see the source
          if(dangling.sc_type == 'ChainSrc'):
            chains += 1 
        
          # the egress via determines the ingress via
          self.platformData[platform]['EGRESS_VIAS'][targetPlatform] = []
          self.platformData[targetPlatform]['INGRESS_VIAS'][platform] = []
            
                                         
        hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
        egressVia = hopFromTarget.replace(".","_") + '_write'
        hopToTarget = self.environment.transitTablesOutgoing[targetPlatform][platform]
        ingressVia = hopToTarget.replace(".","_") + '_read'

        # We're dropping some bits here
        # this loop should be refactored to split ingress and egress
        # we need to reserve space for valid bits
        for via in range(numberOfVias):
          viaWidth = (self.platformData[platform]['WIDTHS'][egressVia] - numberOfVias) / numberOfVias
          # need to set the via widths here...
          spareLink = 0
          if(via < (recvs + chains)%numberOfVias):
            spareLink = 1
          viaLinks = ((recvs + chains)/numberOfVias) + spareLink
          viaLinks +=1 # allocate flowcontrol link
          [headerType, bodyType, type] = self.generateRouterTypes(viaWidth, viaLinks)

          self.platformData[platform]['EGRESS_VIAS'][targetPlatform].append(Via("egress", headerType, bodyType, type, viaWidth, viaLinks, viaLinks - 1, 1, hopFromTarget.replace(".","_")  + str(via) + '_write', 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_")  + str(via), 0, via))
          self.platformData[targetPlatform]['INGRESS_VIAS'][platform].append(Via("ingress", headerType, bodyType, type, viaWidth, viaLinks, viaLinks - 1, 1, hopToTarget.replace(".","_") + str(via) + '_read', 'switch_ingress_' + platform + '_from_' + targetPlatform + '_' + hopToTarget.replace(".","_") + str(via), 0, via))


        # now that we have decided on the vias, we must assign links to vias
        # this nice deterministic algorithm will work - but we should be careful - the opposite side must also agree with us. 

        linkVias  = self.platformData[platform]['EGRESS_VIAS'][targetPlatform]
        linkCount = len(linkVias) # need single flow control lane

        # send/recv pairs had better be matched.
        # so let's match them up - we need to tweak the sorting order a little
        # to induce a match.  
        platformConnections = sorted(self.platformData[platform]['CONNECTED'][targetPlatform],key = lambda connection: connection.name + connection.sc_type)
        targetPlatformConnections = sorted(self.platformData[targetPlatform]['CONNECTED'][platform],key = lambda connection: connection.name + inverseSCType(connection.sc_type)) # We want the ingress ChainSrcs to come first0
         
        # Now we assign lanes/links to ingress/egress pairs
        for danglingIdx in range(len(self.platformData[platform]['CONNECTED'][targetPlatform])):           
          # sanity check the world
          if(platformConnections[danglingIdx].sc_type == 'Recv' or platformConnections[danglingIdx].sc_type == 'ChainSink'):              
            if((platformConnections[danglingIdx].name != targetPlatformConnections[danglingIdx].name) or (platformConnections[danglingIdx].sc_type != inverseSCType(targetPlatformConnections[danglingIdx].sc_type))):
              print "Mis-matched connections: " + platformConnections[danglingIdx].name + " vs. " + targetPlatformConnections[danglingIdx].name
              print "Non-inverse connection types: " + platformConnections[danglingIdx].sc_type + " vs. " + targetPlatformConnections[danglingIdx].sc_type
              sys.exit(-1)

        
            platformConnections[danglingIdx].via_idx = linkCount % len(linkVias)
            platformConnections[danglingIdx].via_link = linkCount / len(linkVias) # Accounting for feedback
            targetPlatformConnections[danglingIdx].via_idx = linkCount % len(linkVias)
            targetPlatformConnections[danglingIdx].via_link = linkCount / len(linkVias) # Accounting for feedback

            linkCount += 1
            print "Assigning " + platformConnections[danglingIdx].name + "Type: " + platformConnections[danglingIdx].sc_type  + " Idx " + str(platformConnections[danglingIdx].via_idx) + " Link " + str(platformConnections[danglingIdx].via_link) + "\n"


        

  def generateCode(self):
      # now that everything is matched we can ostensibly generate the header file
      # header must include device mapping as well

      # we generate a set of router stats 
      dictionary = "" 

      for platform in self.environment.getPlatformNames():
          header = open(self.platformData[platform]['BSH'],'w')
          header.write('// Generated by build pipeline\n\n')
          header.write('`include "awb/provides/common_services.bsh"\n')

          if(GENERATE_ROUTER_STATS):
             header.write('`include "awb/dict/STATS_ROUTER.bsh"\n')

          if(GENERATE_ROUTER_DEBUG):
             header.write('`include "awb/dict/DEBUG_SCAN_ROUTER.bsh"\n\n')

          # everything down here should be code generation.  Eventually it should be split out.  
          # probably also need to instantiate stats in a different modules
          [egress_multiplexor_definition, egress_multiplexor_instantiation, egress_multiplexor_names, egress_multiplexor_dictionary] = self.generateEgressMultiplexor(platform) 
          [ingress_multiplexor_definition, ingress_multiplexor_instantiation, ingress_multiplexor_names, ingress_multiplexor_dictionary] = self.generateIngressMultiplexor(platform)

          dictionary += egress_multiplexor_dictionary
          dictionary += ingress_multiplexor_dictionary
          header.write(egress_multiplexor_definition + ingress_multiplexor_definition)

          # toss out the mapping functions first
          header.write('module [CONNECTED_MODULE] mkCommunicationModule#(VIRTUAL_PLATFORM vplat) (Empty);\n')

          header.write('String platformName <- getSynthesisBoundaryPlatform();\n')
          header.write('messageM("Instantiating Custom Router on " + platformName); \n')

     
          header.write(egress_multiplexor_instantiation + ingress_multiplexor_instantiation)

          # chains can and will have two different communications outlets, therefore, the chains connections
          # cannot be filled in until after all the links are instantiated
          # the chain insertion code must lexically come after the arbiter instantiation
          chainsStr = ''


          # handle the connections themselves
          for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
            egressVias = self.platformData[platform]['EGRESS_VIAS'][targetPlatform]
            ingressVias = self.platformData[platform]['INGRESS_VIAS'][targetPlatform]
            header.write('// Connection to ' + targetPlatform + ' \n')
            sends = 0
            recvs = 0
            chains = 0           

            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              if(dangling.sc_type == 'Recv'):
                  header.write('\nCONNECTION_RECV#(Bit#(PHYSICAL_CONNECTION_SIZE)) recv_' + dangling.name + ' <- mkPhysicalConnectionRecv("' + dangling.name + '", tagged Invalid, False, "' + dangling.raw_type + '");\n')
                  if(GENERATE_ROUTER_STATS):
                    header.write('STAT blocked_' + dangling.name + ' <- mkStatCounter(`STATS_ROUTER_' + dangling.name + '_BLOCKED);\n')
                    header.write('STAT sent_' + dangling.name + ' <- mkStatCounter(`STATS_ROUTER_' + dangling.name + '_SENT);\n')   
		    dictionary += ('def STATS.ROUTER.' + dangling.name + '_BLOCKED "' + dangling.name + ' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) +  'cycles blocked";\n')
                    dictionary += ('def STATS.ROUTER.' + dangling.name + '_SENT "' + dangling.name + ' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' cycles sent";\n')


                  recvs += 1 
              if(dangling.sc_type == 'Send'):
                  if(GENERATE_ROUTER_STATS):
                    header.write('STAT received_' + dangling.name + ' <- mkStatCounter(`STATS_ROUTER_' + dangling.name + '_RECEIVED);\n')
                    dictionary += ('def STATS.ROUTER.' + dangling.name + '_RECEIVED "' + dangling.name + ' on ingress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' received cycles";\n')

                  header.write('CONNECTION_SEND#(Bit#(PHYSICAL_CONNECTION_SIZE)) send_' + dangling.name + ' <- mkPhysicalConnectionSend("' + dangling.name + '", tagged Invalid, False, "' + dangling.raw_type + '");\n')

                  sends += 1
              # only create a chain when we see the source
              if(dangling.sc_type == 'ChainSrc'):
                chains += 1 

                if(GENERATE_ROUTER_STATS):
                  dictionary += ('def STATS.ROUTER.' + platform + '_' + targetPlatform + '_' + dangling.name + '_RECEIVED "' + dangling.name + ' on ingress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) +' received cycles";\n')
                  header.write('STAT received_' + dangling.name + ' <- mkStatCounter(`STATS_ROUTER_' + platform + '_' + targetPlatform + '_' + dangling.name + '_RECEIVED);\n')

                # we must create a logical chain information
                chainsStr += 'let chain_' + dangling.name + ' = LOGICAL_CHAIN_INFO{logicalName: "' + dangling.name + '", logicalType: "' + \
                             dangling.raw_type + '", computePlatform: "' + platform + '", incoming: tpl_2(pack_chain_' + dangling.name + ')' +\
                             ', outgoing: unpack_chain_' + dangling.name + '};\n'
                      
                chainsStr += 'registerChain(chain_' + dangling.name + ');\n'

              if(dangling.sc_type == 'ChainSink'):
                dictionary += ('def STATS.ROUTER.' + platform + '_' + targetPlatform + '_' + dangling.name + '_BLOCKED "' + dangling.name +' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' cycles blocked";\n')
                dictionary += ('def STATS.ROUTER.' + platform + '_' + targetPlatform + '_' + dangling.name + '_SENT "' + dangling.name + ' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' cycles sent";\n')

                if(GENERATE_ROUTER_STATS):
                    header.write('STAT blocked_' + dangling.name + ' <- mkStatCounter(`STATS_ROUTER_' + platform + '_' + targetPlatform + '_' + dangling.name + '_BLOCKED);\n')
                    header.write('STAT sent_' + dangling.name + ' <- mkStatCounter(`STATS_ROUTER_' + platform + '_' + targetPlatform + '_' + dangling.name + '_SENT);\n')

            # Ingress switches now feed directly into the egress switches to save latency.  
            for via_idx in range(len(ingressVias)):
              if(ingressVias[via_idx].via_links > 0):
                header.write('INGRESS_SWITCH#(' + str(ingressVias[via_idx].via_links) + ',' + ingressVias[via_idx].via_type + ',' + egressVias[via_idx].via_header_type + ',' + egressVias[via_idx].via_body_type + ') ' + ingressVias[via_idx].via_switch + '<- mkIngressSwitch(' + str(ingressVias[via_idx].via_outgoing_flowcontrol_link) + ',' + ingress_multiplexor_names[targetPlatform] + '.' + ingressVias[via_idx].via_method  + '_first, ' + ingress_multiplexor_names[targetPlatform] + '.' + ingressVias[via_idx].via_method  + '_deq);\n\n')

            # The egress links now take as input a list of incoming connections
            # that can be manipulated like fifos.  
            egressVectors = []
            for via_idx in range(len(egressVias)):
              print "Working on " + egressVias[via_idx].via_switch + ' with Links: ' + str(egressVias[via_idx].via_links)
              egressVectors.append(["?" for x in range(egressVias[via_idx].via_links)]) # we could also do a double list comprehension.

            # the egress links need to go first, since they are provided as an argument to the 
            # switches           
            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              if(dangling.sc_type == 'Recv'):
                packetizerType = 'Marshalled'
	        header.write('NumTypeParam#('+ str(dangling.bitwidth) +') width_recv_' + dangling.name +' = ?;\n')
                egressVectors[dangling.via_idx][dangling.via_link] = 'pack_recv_' + dangling.name
                if(dangling.bitwidth < egressVias[dangling.via_idx].via_width):
                  packetizerType = 'Unmarshalled'
                if(GENERATE_ROUTER_STATS):
                  header.write('let pack_recv_' + dangling.name + ' <- mkPacketizeConnectionReceive' + packetizerType  + '(recv_' + dangling.name + ',' + str(dangling.via_link) + ', width_recv_' + dangling.name +  ',blocked_'+ dangling.name +', sent_'+ dangling.name +');// Via' + str(egressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth) + '\n')
                else:
                  header.write('let pack_recv_' + dangling.name + ' <- mkPacketizeConnectionReceive' + packetizerType + '(recv_' + dangling.name + ',' + str(dangling.via_link) + ', width_recv_' + dangling.name + ', ?, ?); // Via' + str(egressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth) + '\n')

              if(dangling.sc_type == 'ChainSink' ):
                print "Chain Sink " + dangling.name + ": Idx " + str(dangling.via_idx) + " Link: " + str(dangling.via_link) + " Length: " + str(len(egressVectors[dangling.via_idx]))  
                egressVectors[dangling.via_idx][dangling.via_link] = 'tpl_1(pack_chain_' + dangling.name + ')'
                if(GENERATE_ROUTER_STATS):
                  header.write('let pack_chain_' + dangling.name + ' <- mkPacketizeIncomingChain(' + str(dangling.via_link) + ',blocked_'+ dangling.name +', sent_'+ dangling.name  +');\n\n')
                else:
                  header.write('let pack_chain_' + dangling.name + ' <- mkPacketizeIncomingChain(' + str(dangling.via_link) + ',?,?);\n\n')

          
            # we now need switches for each via.  Need modular arithmetic here to make sure that everyone has a link.  
            # for now we will assume that flow control is twinned - that is the egress 2 uses ingress 2 for its flow control
            # this might well need to change as we introduce assymetry x_X
            # we actually should be allocating the feedback channel as part of the analysis phase, but that can happen later.             
            for via_idx in range(len(egressVias)):
              if(egressVias[via_idx].via_links > 0):                
                # create array of links for constructor
                # we may have many flow control links
                # these no longer necessarily occur at the head of the list
                for ingressVia in ingressVias:
                  if(ingressVia.via_outgoing_flowcontrol_via == via_idx):
                    egressVectors[via_idx][ingressVia.via_outgoing_flowcontrol_link] = ingressVia.via_switch + ".flowcontrol_response"

                linkArray = "{"  
                firstPass = True
                for link_idx in range(egressVias[via_idx].via_links): # this seems off by one?
                  seperator = ',// link idx:'+ str(link_idx - 1) +'\n\t'
                  if(firstPass):
                    seperator = '\n\t';
                  linkArray += seperator + egressVectors[via_idx][link_idx]  
                  firstPass = False
                  
                linkArray += "}// link idx: " + str(egressVias[via_idx].via_links - 1)  + '\n'

                header.write('EGRESS_PACKET_GENERATOR#(' + egressVias[via_idx].via_header_type + ', ' +  egressVias[via_idx].via_body_type + ')links_' + egressVias[via_idx].via_switch + '[' + str(egressVias[via_idx].via_links) + '] = ' + linkArray + ';\n') 

                header.write('EGRESS_SWITCH#(' + str(egressVias[via_idx].via_links) + ') ' + egressVias[via_idx].via_switch + '<- mkEgressSwitch( links_' + egressVias[via_idx].via_switch + ', ' + ingressVias[via_idx].via_switch + '.ingressPorts[0], compose(' + egress_multiplexor_names[targetPlatform] + '.' + egressVias[via_idx].via_method + ',pack));\n')

                if(GENERATE_ROUTER_DEBUG):   
                  # lay down a couple of debug scan chains here and insert crap in dictionary
                  dictionary += ('def DEBUG_SCAN.ROUTER.' + egressVias[via_idx].via_switch + '_DEBUG "' + egressVias[via_idx].via_switch  +' debug";\n')
                  header.write('DEBUG_SCAN#(Bit#(' + str(2*(egressVias[via_idx].via_links)) + ')) ' + egressVias[via_idx].via_switch + '_DEBUG <- mkDebugScanNode(`DEBUG_SCAN_ROUTER_'+ egressVias[via_idx].via_switch + '_DEBUG, {pack(' + egressVias[via_idx].via_switch +'.bufferStatus), pack('+ egressVias[via_idx].via_switch + '.fifoStatus)});\n')

            # Hook up the ingress links
            # We also want to build a listing of the mapping in an easy to consume 
            # human readable format.  Therefore, we first sort the connections by assignment.            
            # and dump a link manifest.
            maximumLinks = max(ingressVias, key = lambda via: via.via_links).via_links;
            sortedLinks = sorted(self.platformData[platform]['CONNECTED'][targetPlatform], key = lambda dangling: dangling.via_link + maximumLinks * dangling.via_idx) # sorted is ascending

            for dangling in sortedLinks:
              if(dangling.sc_type == 'Send' or dangling.sc_type == 'ChainSrc' ):
                header.write('// ' + dangling.name + ' via_idx: ' + str(dangling.via_idx) + ' link_idx: ' +  str(dangling.via_link) + '\n')

            # and now we actually 
            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              if(dangling.sc_type == 'Send'):
                packetizerType = 'Marshalled'
	        header.write('NumTypeParam#('+ str(dangling.bitwidth) +') width_send_' + dangling.name +' = ?;\n\n')
                if(dangling.bitwidth < ingressVias[dangling.via_idx].via_width):
                  packetizerType = 'Unmarshalled'
                if(GENERATE_ROUTER_STATS):
                  header.write('Empty unpack_send_' + dangling.name + ' <- mkPacketizeConnectionSend' + packetizerType  + '(send_' + dangling.name+',' + ingressVias[dangling.via_idx].via_switch  +'.ingressPorts['+str(dangling.via_link) + '], ' + str(dangling.via_link) + ', width_send_' + dangling.name+',received_'+ dangling.name +');// Via' + str(ingressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth) + '\n')
                else:
                  header.write('Empty unpack_send_' + dangling.name + ' <- mkPacketizeConnectionSend' + packetizerType  + '(send_' + dangling.name+',' + ingressVias[dangling.via_idx].via_switch  +'.ingressPorts['+str(dangling.via_link) + '], ' + str(dangling.via_link) + ', width_send_' + dangling.name+',?);// Via' + str(ingressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth)+ '\n')


              if(dangling.sc_type == 'ChainSrc' ):
                if(GENERATE_ROUTER_STATS):
                  header.write('PHYSICAL_CHAIN_OUT unpack_chain_' + dangling.name + ' <- mkPacketizeOutgoingChain(' + ingressVias[dangling.via_idx].via_switch  +'.ingressPorts['+str(dangling.via_link) + '],' + 'received_' + dangling.name + ');\n\n') 
                else:
                  header.write('PHYSICAL_CHAIN_OUT unpack_chain_' + dangling.name + ' <- mkPacketizeOutgoingChain(' + ingressVias[dangling.via_idx].via_switch  +'.ingressPorts['+str(dangling.via_link) + '],?);\n\n')



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
