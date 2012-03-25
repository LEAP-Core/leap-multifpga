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

# Notice that chains will have their platform direction labelled
def parseStats(filename):
  logfile = open(filename,'r')
  stats = {}
  print "Processing Stats:  " + filename
  for line in logfile:
    if(re.match('.*ROUTER_.*_SENT.*',line)):           
      match = re.search(r'.*ROUTER_(\w+)_SENT,.*,(\d+)',line)
      if(match):
        print "Stat " + match.group(1) + " got " + match.group(2)
        stats[match.group(1)] = int(match.group(2))
    
  return stats

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
          parameterFile =  platformBitfileBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/multifpga_routing.bsh'
               
          self.platformData[platform.name] = {'LOG': wrapperLog, 'BSH': parameterFile, 'DANGLING': [], 'CONNECTED': {}, 'INDEX': {}, 'WIDTHS': {}, 'INGRESS_VIAS': {}, 'EGRESS_VIAS': {}, 'INGRESS_VIAS_PASS_ONE': {}, 'EGRESS_VIAS_PASS_ONE': {}}


          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'] += [parameterFile] 
 
      subbuild = moduleList.env.Command( 
          moduleList.topModule.moduleDependency['FPGA_CONNECTION_PARAMETERS'],
          moduleList.topModule.moduleDependency['FPGA_PLATFORM_LOGS'] + [moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0]] + [moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + mappingFile[0]] + ['./site_scons/multi_fpga_connect/multiFPGAConnect.py'],
          self.synthesizeRouters
          )                   
      print "subbuild: " + str(subbuild)


      moduleList.topDependency += [subbuild]

  def assignIndices(self,sourceConn,sinkConn):
    print "Now processing connection %s between %s (%s) -> %s (%s)" % (sourceConn.name, sourceConn.platform, sourceConn.sc_type, sinkConn.platform, sinkConn.sc_type)

    sourceConn.inverse_sc_type = sinkConn.sc_type
    sinkConn.inverse_sc_type   = sourceConn.sc_type

    sourceConn.inverse_name = sinkConn.name
    sinkConn.inverse_name   = sourceConn.name

    if(sinkConn.platform in self.platformData[sourceConn.platform]['INDEX']):
      # only increment the sourceConn. 
      self.platformData[sourceConn.platform]['INDEX'][sinkConn.platform] += 1
      index = self.platformData[sourceConn.platform]['INDEX'][sinkConn.platform]
      sourceConn.idx = index 
      sinkConn.idx = index 
      print "Setting index :" + str(index)
    else:
      self.platformData[sourceConn.platform]['INDEX'][sinkConn.platform] = 0
      sourceConn.idx = 0
      sinkConn.idx = 0 
      print "Setting index :" + str(0)
    
    # Tell the sink about the source.  The sink may have been processed already
    if(sinkConn.platform in self.platformData[sourceConn.platform]['CONNECTED']):
      self.platformData[sourceConn.platform]['CONNECTED'][sinkConn.platform] += [sinkConn]
      print "Sink platform length: " + str(len(self.platformData[sourceConn.platform]['CONNECTED'][sinkConn.platform]))
    else:   
      self.platformData[sourceConn.platform]['CONNECTED'][sinkConn.platform] = [sinkConn]

    if(sourceConn.platform in self.platformData[sinkConn.platform]['CONNECTED']):
      self.platformData[sinkConn.platform]['CONNECTED'][sourceConn.platform] += [sourceConn]
      print "Source platform length: " + str(len(self.platformData[sinkConn.platform]['CONNECTED'][sourceConn.platform]))
    else:   
      self.platformData[sinkConn.platform]['CONNECTED'][sourceConn.platform] = [sourceConn]

  def connectPath(self, src, sink):

      path = self.environment.getPath(src.platform, sink.platform)

      srcs = [src]
      sinks =[]
      print "Analyzing path: " + str(path)
      for hop in path:
          print "Adding hop: " + src.name + "Hop" + hop        
            
          sinks.append(DanglingConnection("ChainRoutingRecv", src.raw_type, -1, src.name + "Routethrough" + hop, 
                                          hop, "False", src.bitwidth))
          srcs.append(DanglingConnection("ChainRoutingSend", src.raw_type, -1, src.name + "Routethrough" + hop, 
                                         hop, "False", src.bitwidth))


      sinks.append(sink)
    
      for pair in zip(srcs,sinks):
          self.assignIndices(pair[0],pair[1])
  


  def generateEgressMultiplexor(self, platform): 
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}
    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      egressVias = self.platformData[platform]['EGRESS_VIAS'][targetPlatform]
      hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
      egressMethod = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
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
          sname = 'statName("ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED", "' + via.via_method +' cycles enqueued")'
          multiplexor_definition += '\tSTAT enqueued_' + via.via_method + ' <- mkStatCounter(' + sname + ');\n'
     
      #stats for the merger
      if(GENERATE_ROUTER_STATS):
        sname = 'statName("ROUTER_' + moduleName + '_MERGED", "' + moduleName +' cycles enqueued")'
        multiplexor_definition += '\tSTAT merged_' + moduleName + ' <- mkStatCounter(' + sname + ');\n'

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
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]


  def generateEgressMultiplexorParSerial(self, platform): 
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}
    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      egressVias = self.platformData[platform]['EGRESS_VIAS'][targetPlatform]
      hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
      egressMethod = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
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
        sname = 'statName("ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED", "' + via.via_method +' cycles enqueued")'
        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += '\tSTAT enqueued_' + via.via_method + ' <- mkStatCounter(' + sname + ');\n'

      sname = 'statName("ROUTER_' + moduleName + '_MERGED", "' + moduleName +' cycles enqueued")'
      if(GENERATE_ROUTER_STATS):
        multiplexor_definition += '\tSTAT merged_' + moduleName + ' <- mkStatCounter(' + sname + ');\n'


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
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]


  def generateEgressMultiplexorSerial(self, platform): 
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}
    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      egressVias = self.platformData[platform]['EGRESS_VIAS'][targetPlatform]
      hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
      egressMethod = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
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
        if(GENERATE_ROUTER_STATS):
          sname = 'statName("ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED", "' + via.via_method +' cycles enqueued")'
          multiplexor_definition += 'STAT enqueued_' + via.via_method + ' <- mkStatCounter(' + sname + ');\n'

      if(GENERATE_ROUTER_STATS):
        sname = 'statName("ROUTER_' + moduleName + '_MERGED", "' + moduleName +' cycles enqueued")'
        multiplexor_definition += 'STAT merged_' + moduleName + ' <- mkStatCounter(' + sname + ');\n'

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
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]
            

  def generateIngressMultiplexor(self, platform):
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}
    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      ingressVias = self.platformData[platform]['INGRESS_VIAS'][targetPlatform]
      hopToTarget = self.environment.transitTablesOutgoing[platform][targetPlatform]
      ingressMethod = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'
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
          sname = 'statName("ROUTER_' + moduleName + '_' + via.via_method + '_DEQUEUED", "' + via.via_method +' cycles dequeued")'
          multiplexor_definition += '\tSTAT dequeued_' + via.via_method + ' <- mkStatCounter(' + sname + ');\n'

      if(GENERATE_ROUTER_DEBUG):   
        multiplexor_definition += '\n\tDEBUG_SCAN_FIELD_LIST via_dbg_list = List::nil;\n'
        for via in ingressVias:
          multiplexor_definition += '\tvia_dbg_list <- addDebugScanField(via_dbg_list, "' + via.via_method + ' notFull", ' + via.via_method + '_fifo.notFull);\n'
          multiplexor_definition += '\tvia_dbg_list <- addDebugScanField(via_dbg_list, "' + via.via_method + ' notEmpty", ' + via.via_method + '_fifo.notEmpty);\n'
        multiplexor_definition += '\tlet viaDbg <- mkDebugScanNode("multi-FPGA vias", via_dbg_list);\n'


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
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]

  def generateIngressMultiplexorSerial(self, platform):
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}
    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      ingressVias = self.platformData[platform]['INGRESS_VIAS'][targetPlatform]
      hopToTarget = self.environment.transitTablesOutgoing[platform][targetPlatform]
      ingressMethod = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'
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
        if(GENERATE_ROUTER_STATS):
          sname = 'statName("ROUTER_' + moduleName + '_' + via.via_method + '_DEQUEUED", "' + via.via_method +' cycles dequeued")'
          multiplexor_definition += 'STAT dequeued_' + via.via_method + ' <- mkStatCounter(' + sname + ');\n'
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
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]

    
  def synthesizeRouters(self, target, source, env):    
    self.processDanglingConnections()
    self.analyzeNetwork()
    self.generateCode()

  #First we parse the files, and then attempt to make all the connections.
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
                      if(danglingNew.isSource()):
                          self.connectPath(danglingNew,danglingOld)         
                      else:                                                   
                          self.connectPath(danglingOld,danglingNew)         

 
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

          self.connectPath(chainSrcs[i],chainSinks[i])
 

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

    # set up intermediate data structures.  We need a couple of passes to resolve link allocation. 
    egressViasInitial = {}
    ingressViasInitial = {}
    for platform in self.environment.getPlatformNames():      
      egressViasInitial[platform] = {}
      ingressViasInitial[platform] = {}
      for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
        egressViasInitial[platform][targetPlatform] = []
        ingressViasInitial[platform][targetPlatform] = []


    # let's read in a stats file
    statsFile = self.moduleList.getAllDependenciesWithPaths('GIVEN_STATS')    
    stats = {}
    print "StatsFile " + str(statsFile)
    if(len(statsFile) > 0):
      stats = parseStats(self.moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + statsFile[0])


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
        # We need two passes to fill in potentially missing links
        totalTraffic = 0;
        for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
          if(dangling.sc_type == 'Recv' or dangling.sc_type == 'ChainRoutingRecv'):
            recvs += 1 
            if(dangling.name in stats):
              dangling.activity = stats[dangling.name]
              totalTraffic += stats[dangling.name]
              print "Assigning " + platform + "->" + targetPlatform + " " + dangling.name + " " + str(stats[dangling.name])

          # only create a chain when we see the source                    
          if(dangling.sc_type == 'ChainSrc'):
            chains += 1 
            chainName = platform + "_" + targetPlatform + "_" + dangling.name
            if(chainName in stats):
              dangling.activity = stats[chainName]
              totalTraffic += stats[chainName]

        if(totalTraffic == 0):
          totalTraffic = 2*(chains+recvs)

        for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
          if(dangling.sc_type == 'Recv' or dangling.sc_type == 'ChainRoutingRecv'):
            if(not(dangling.name in stats)):
              dangling.activity = totalTraffic/(chains+recvs)
            
          # only create a chain when we see the source          
          if(dangling.sc_type == 'ChainSrc'):
            chains += 1 
            chainName = platform + "_" + targetPlatform + "_" + dangling.name
            if(not (chainName in stats)):
              dangling.activity = totalTraffic/(2*(chains+recvs))

        hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
        egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
        hopToTarget = self.environment.transitTablesOutgoing[targetPlatform][platform]
        ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'

        firstAllocationPass = True; # We can't terminate in the first pass 
        viaWidthsFinal = [] # at some point, we'll want to derive this.  
        viaLinksFinal = [] 
        viaLoadsFinal = [] 
        maxLoad = 0;

        sortedLinks = sorted(self.platformData[platform]['CONNECTED'][targetPlatform], key = lambda dangling: dangling.activity * -2048 + dangling.bitwidth) # sorted is ascending

        for link in sortedLinks:
          print "Link" + dangling.name + "activiy: " + str(dangling.activity)

        # The general strategy here is 
        # 1) hueristically pick lane widths
        # 2) Assign links to lanes using Longest Job First hueristic
        # Repeat until maximum link occupancy increases (although we might just try repeatedly and keep all the results) 

        for numberOfVias in range(1,10):
          viaLoads = []
          viaSizingIdx = 0
          viaLinks = []
          viaWidths = []
          noViasRemaining = 0
          # pick our via links deterministically
          
          for via in range(numberOfVias):
            viaLinks.append(0)
            viaLoads.append(0)
            if(via == 0):
              viaWidths.append(self.platformData[platform]['WIDTHS'][egressVia] - 1)
            else: # carve off a lane for the longest running job
              
              while(viaWidths[0] < (sortedLinks[viaSizingIdx].bitwidth + 2*(headerSize + 1))): # Give extra for header sizing - the base via should also have space
                if(viaSizingIdx + 1 == len(sortedLinks)):
                  noViasRemaining = 1
                  print "No suitable vias remain"
                  break
                else:
                  viaSizingIdx += 1

              # found minimum, ajust the top guy
              if(not noViasRemaining):
                viaWidths[0] = viaWidths[0] - (sortedLinks[viaSizingIdx].bitwidth + headerSize + 1)
                viaWidths.append(sortedLinks[viaSizingIdx].bitwidth + headerSize) # need one bit for the header
                viaSizingIdx += 1

          # We've exhausted the supply of feasible vias.
          if(noViasRemaining):
            print "There are no suitable mapping candidates"
            break

          # send/recv pairs had better be matched.
          # so let's match them up
          # need to maintain the sorted order

          platformConnectionsProvisional = []
          targetPlatformConnectionsProvisional = []
          for danglingIdx in range(len(sortedLinks)):           
            if((sortedLinks[danglingIdx].sc_type == 'Recv') or (sortedLinks[danglingIdx].sc_type == 'ChainSink') or (sortedLinks[danglingIdx].sc_type == 'ChainRoutingRecv')):
              # depending on the width of the vias, and the width of our type we get different loads on different processors
              # need to choose the minimum
              print "\n\n Analyzing " + sortedLinks[danglingIdx].name + " of width " + str(sortedLinks[danglingIdx].bitwidth)  + "\n"

              minIdx = -1 
              minLoad = 0
              for via in range(numberOfVias):
                extraChunk = 0
                if(((sortedLinks[danglingIdx].bitwidth + headerSize )%viaWidths[via]) > 0):
                  extraChunk = 1
                
                load = (sortedLinks[danglingIdx].activity * ( (sortedLinks[danglingIdx].bitwidth + headerSize )/viaWidths[via] + extraChunk)) + viaLoads[via]

                print "link " + str(via) + " of width " + str(viaWidths[via]) + " header " + str(headerSize) + " extra " + str(extraChunk) +   " starts at " + str(viaLoads[via]) + ", new load is " + str(load) + " activity: " + str(sortedLinks[danglingIdx].activity)
                # We don't do a great job here of evaluating opportunity cost.  Picking the longest running on the fastest processor 
                # might be a bad choice.
                if((load < minLoad) or (minIdx == -1)):
                  print "Setting min load as " +str(minLoad)  + " idx: " + str(via)
                  minIdx = via
                  minLoad = load
              
              viaLoads[minIdx] = minLoad
              platformConnectionsProvisional.append([sortedLinks[danglingIdx].name, sortedLinks[danglingIdx].sc_type, minIdx, viaLinks[minIdx]])
              targetPlatformConnectionsProvisional.append([sortedLinks[danglingIdx].name, sortedLinks[danglingIdx].inverse_sc_type, minIdx, viaLinks[minIdx]])  
              print "Assigning Recv " + sortedLinks[danglingIdx].name   + " Idx " + str(minIdx) + " Link " + str(viaLinks[minIdx]) + "\n"
              viaLinks[minIdx] += 1


          platformConnections = sorted(self.platformData[platform]['CONNECTED'][targetPlatform],key = lambda connection: connection.name)
          targetPlatformConnections = sorted(self.platformData[targetPlatform]['CONNECTED'][platform],key = lambda connection: connection.name)
          print "Lengths: "  + str(len(platformConnections)) + " " + str(len(targetPlatformConnections))  
          #Did we do better than last time?
          for idx in range(len(viaLoads)):
            print "Load " + str(idx) + ": " + str(viaLoads[idx]) 
          print "For " + str(len(viaLoads)) + " vias maximum load is: " + str(max(viaLoads))
          if(max(viaLoads) < maxLoad or firstAllocationPass):
            print "Better allocation with  " + str(len(viaLoads)) + " vias found."
            maxLoad = max(viaLoads)
            viaWidthsFinal = viaWidths
            viaLinksFinal = viaLinks
            viaLoadsFinal = viaLoads
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
#          else:
            #Quit while we're ahead
#            break
          firstAllocationPass = False

        self.platformData[platform]['EGRESS_VIAS'][targetPlatform] = []
        self.platformData[targetPlatform]['INGRESS_VIAS'][platform] = []

        # We don't yet have information about how to handle flowcontrol
        # But we will fill in the data structure temporarily.  
        # Once all data via assignments have been handeled, we will do flowcontrol.
        for via in range(len(viaWidthsFinal)):
          [headerType, bodyType, type] = self.generateRouterTypes(viaWidthsFinal[via], viaLinksFinal[via])

          egress = Via("egress", headerType, bodyType, type, viaWidthsFinal[via], viaLinksFinal[via], viaLinksFinal[via], 0, hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via) + '_write', 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via), -1, -1, viaLoadsFinal[via])

          ingress = Via("ingress", headerType, bodyType, type, viaWidthsFinal[via], viaLinksFinal[via], viaLinksFinal[via], 0, hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via) + '_read', 'switch_ingress_' + platform + '_from_' + targetPlatform + '_' + hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via), -1, -1, viaLoadsFinal[via])

          egressViasInitial[platform][targetPlatform].append(egress)
          ingressViasInitial[targetPlatform][platform].append(ingress) 
          print "Via pair " + egress.via_switch + ": " + str(via) + ' width: '  + str(viaWidthsFinal[via]) + ' links" ' + str(viaLinksFinal[via])



    # We finished lane allocation. 
    # Now we need to assign flow control and build the final metadata structures. 
    # We can't do this in the previous loop because the algorithm will select
    # potentially assymetric links for each target.
    ingressFlowcontrolAssignment = {}
    egressLinks = {}
    viaLoads = {}
    for platform in self.environment.getPlatformNames():
      ingressFlowcontrolAssignment[platform] = {}
      egressLinks[platform] = {}
      viaLoads[platform] = {}
      for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
        # We need to first consider the other platform's ingress.  It gets mapped to our egress
        localIngress = ingressViasInitial[platform][targetPlatform]
        localEgress = egressViasInitial[platform][targetPlatform]


        egressLinks[platform][targetPlatform] = []
        ingressFlowcontrolAssignment[platform][targetPlatform] = []
        viaLoads[platform][targetPlatform] = []
        viaLoadsOld = []
        for via in range(len(localEgress)):
          egressLinks[platform][targetPlatform].append(localEgress[via].via_links)
          viaLoads[platform][targetPlatform].append(localEgress[via].via_load)
          viaLoadsOld.append(localEgress[via].via_load)

        for ingress in localIngress:
          minIdx = -1 
          minLoad = 0
          for via in range(len(localEgress)):
            extraChunk = 0
            bitwidth = 8
            if((bitwidth + headerSize)%localEgress[via].via_width != 0):
              extraChunk = 1

            load = viaLoadsOld[via]/128 * ((bitwidth + headerSize )/localEgress[via].via_width + extraChunk) + viaLoads[platform][targetPlatform][via]
                
            # We don't do a great job here of evaluating opportunity cost.  Picking the longest running on the fastest processor 
            # might be a bad choice.
            if(load < minLoad or minIdx == -1):
              minIdx = via
              minLoad = load
               
          viaLoads[platform][targetPlatform][minIdx] = minLoad

          # after this assignment we can finalize the ingress 
          ingressFlowcontrolAssignment[platform][targetPlatform].append([minIdx, egressLinks[platform][targetPlatform][minIdx]])
          print "Assigning Flowcontrol ingress " + ingress.via_method + " to " + egressViasInitial[platform][targetPlatform][minIdx].via_method  + " Idx " + str(minIdx) + " Link " + str(egressLinks[platform][targetPlatform][minIdx]) + "\n"
          egressLinks[platform][targetPlatform][minIdx] += 1

    #And now we can finally finish the synthesized routers
    for platform in self.environment.getPlatformNames(): 
      for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():                                        
        for via in range(len(egressLinks[platform][targetPlatform])):
          egress_first_pass = egressViasInitial[platform][targetPlatform][via]
          ingress_first_pass = ingressViasInitial[targetPlatform][platform][via]

          print "Idx " + str(via) + " links " + str(len(egressLinks[platform][targetPlatform])) + " loads " + str(len(viaLoads[platform][targetPlatform]))
          [headerType, bodyType, type] = self.generateRouterTypes(egress_first_pass.via_width, egressLinks[platform][targetPlatform][via])

          egress = Via("egress", headerType, bodyType, type, egress_first_pass.via_width, egressLinks[platform][targetPlatform][via], egress_first_pass.via_links, egressLinks[platform][targetPlatform][via] - egress_first_pass.via_links, egress_first_pass.via_method, egress_first_pass.via_switch, ingressFlowcontrolAssignment[targetPlatform][platform][via][1], ingressFlowcontrolAssignment[targetPlatform][platform][via][0], viaLoads[platform][targetPlatform][via])

          ingress = Via("ingress", headerType, bodyType, type, ingress_first_pass.via_width, egressLinks[platform][targetPlatform][via], ingress_first_pass.via_links,  egressLinks[platform][targetPlatform][via] - ingress_first_pass.via_links, ingress_first_pass.via_method, ingress_first_pass.via_switch, ingressFlowcontrolAssignment[targetPlatform][platform][via][1],  ingressFlowcontrolAssignment[targetPlatform][platform][via][0], viaLoads[platform][targetPlatform][via])

          self.platformData[platform]['EGRESS_VIAS'][targetPlatform].append(egress)
          self.platformData[targetPlatform]['INGRESS_VIAS'][platform].append(ingress) 
          print "Via pair " + egress_first_pass.via_switch + ": " + str(via) + ' width: '  + str(ingress_first_pass.via_width) + ' links" ' + str(egressLinks[platform][targetPlatform][via])



         



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
          if(dangling.sc_type == 'Recv' or dangling.sc_type == 'ChainRoutingRecv'):
            recvs += 1 

          # only create a chain when we see the source
          if(dangling.sc_type == 'ChainSink'):
            print "Got chain src named: " + dangling.name
            chains += 1 

          if(dangling.sc_type == 'ChainSrc'):
            print "Got chain sink named: " + dangling.name        

          # the egress via determines the ingress via
          self.platformData[platform]['EGRESS_VIAS'][targetPlatform] = []
          self.platformData[targetPlatform]['INGRESS_VIAS'][platform] = []
            
                                         
        hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
        egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
        hopToTarget = self.environment.transitTablesOutgoing[targetPlatform][platform]
        ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'

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
          
          print "Creating Via " + 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  +str(via) + " : links " + str(viaLinks)
          self.platformData[platform]['EGRESS_VIAS'][targetPlatform].append(Via("egress", headerType, bodyType, type, viaWidth, viaLinks, viaLinks - 1, 1, hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via) + '_write', 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via), 0, via, 0))
          self.platformData[targetPlatform]['INGRESS_VIAS'][platform].append(Via("ingress", headerType, bodyType, type, viaWidth, viaLinks, viaLinks - 1, 1, hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via) + '_read', 'switch_ingress_' + platform + '_from_' + targetPlatform + '_' + hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via), 0, via, 0)) 


        # now that we have decided on the vias, we must assign links to vias
        # this nice deterministic algorithm will work - but we should be careful - the opposite side must also agree with us. 

        linkVias  = self.platformData[platform]['EGRESS_VIAS'][targetPlatform]
        linkCount = len(linkVias) # need single flow control lane

        # send/recv pairs had better be matched.
        # We want the slower chains to be evenly dispersed across the randomly assigned links
        platformConnections = self.platformData[platform]['CONNECTED'][targetPlatform]
        targetPlatformConnections = self.platformData[targetPlatform]['CONNECTED'][platform]

        # Now we assign lanes/links to ingress/egress pairs
        for danglingIdx in range(len(self.platformData[platform]['CONNECTED'][targetPlatform])):           
          # sanity check the world
          if(platformConnections[danglingIdx].sc_type == 'Recv' or platformConnections[danglingIdx].sc_type == 'ChainRoutingRecv'):              
            if((platformConnections[danglingIdx].idx != targetPlatformConnections[danglingIdx].idx) or (platformConnections[danglingIdx].sc_type != targetPlatformConnections[danglingIdx].inverse_sc_type)):
              print "Platform " + platform + " -> " + targetPlatform 
              print "Mis-matched connections: " + platformConnections[danglingIdx].name + " vs. " + targetPlatformConnections[danglingIdx].name
              print "Non-inverse connection types: " + platformConnections[danglingIdx].sc_type + " vs. " + targetPlatformConnections[danglingIdx].sc_type
              sys.exit(-1)

        
            platformConnections[danglingIdx].via_idx = linkCount % len(linkVias)
            platformConnections[danglingIdx].via_link = linkCount / len(linkVias) # Accounting for feedback
            targetPlatformConnections[danglingIdx].via_idx = linkCount % len(linkVias)
            targetPlatformConnections[danglingIdx].via_link = linkCount / len(linkVias) # Accounting for feedback

            linkCount += 1
            print "Assigning  " + platform + "->" + targetPlatform + " " + platformConnections[danglingIdx].name + "Type: " + platformConnections[danglingIdx].sc_type  + " Idx " + str(platformConnections[danglingIdx].via_idx) + " Link " + str(platformConnections[danglingIdx].via_link) + "\n"

        # This second pass is a hueristic that forces the lightly used chains to be evenly distributed 
        for danglingIdx in range(len(self.platformData[platform]['CONNECTED'][targetPlatform])):           
          # sanity check the world
          if(platformConnections[danglingIdx].sc_type == 'ChainSink'):              
            if((platformConnections[danglingIdx].idx != targetPlatformConnections[danglingIdx].idx) or (platformConnections[danglingIdx].sc_type != targetPlatformConnections[danglingIdx].inverse_sc_type)):
              print "Platform " + platform + " -> " + targetPlatform 
              print "Mis-matched connections: " + platformConnections[danglingIdx].name + " vs. " + targetPlatformConnections[danglingIdx].name
              print "Non-inverse connection types: " + platformConnections[danglingIdx].sc_type + " vs. " + targetPlatformConnections[danglingIdx].sc_type
              sys.exit(-1)

        
            platformConnections[danglingIdx].via_idx = linkCount % len(linkVias)
            platformConnections[danglingIdx].via_link = linkCount / len(linkVias) # Accounting for feedback
            targetPlatformConnections[danglingIdx].via_idx = linkCount % len(linkVias)
            targetPlatformConnections[danglingIdx].via_link = linkCount / len(linkVias) # Accounting for feedback

            linkCount += 1
            print "Assigning  " + platform + "->" + targetPlatform + " " + platformConnections[danglingIdx].name + "Type: " + platformConnections[danglingIdx].sc_type  + " Idx " + str(platformConnections[danglingIdx].via_idx) + " Link " + str(platformConnections[danglingIdx].via_link) + "\n"


        

  def generateCode(self):
      # now that everything is matched we can ostensibly generate the header file
      # header must include device mapping as well

      for platform in self.environment.getPlatformNames():
          header = open(self.platformData[platform]['BSH'],'w')
          header.write('// Generated by build pipeline\n\n')
          header.write('`include "awb/provides/common_services.bsh"\n')

          # everything down here should be code generation.  Eventually it should be split out.  
          # probably also need to instantiate stats in a different modules
          [egress_multiplexor_definition, egress_multiplexor_instantiation, egress_multiplexor_names] = self.generateEgressMultiplexor(platform) 
          [ingress_multiplexor_definition, ingress_multiplexor_instantiation, ingress_multiplexor_names] = self.generateIngressMultiplexor(platform)

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
            print  "\n\nGenerating routing code " + platform + " -> " + targetPlatform + " in " + self.platformData[platform]['BSH'] + "\n\n"
    
            egressVias = self.platformData[platform]['EGRESS_VIAS'][targetPlatform]
            ingressVias = self.platformData[platform]['INGRESS_VIAS'][targetPlatform]
            header.write('// Connection to ' + targetPlatform + ' \n')
            sends = 0
            recvs = 0
            chains = 0           

            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              print "Laying down " + dangling.inverse_name + " of type " + dangling.sc_type + " on " + dangling.platform
              if(dangling.inverse_sc_type == 'Send' or dangling.inverse_sc_type == 'ChainRoutingSend'):
                  header.write('\nCONNECTION_RECV#(Bit#(PHYSICAL_CONNECTION_SIZE)) recv_' + dangling.inverse_name + ' <- mkPhysicalConnectionRecv("' + dangling.inverse_name + '", tagged Invalid, False, "' + dangling.raw_type + '");\n')
                  if(GENERATE_ROUTER_STATS):
		    sname = 'statName("ROUTER_' + dangling.inverse_name + '_BLOCKED", "' + dangling.inverse_name + ' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) +  'cycles blocked")'
                    header.write('STAT blocked_' + dangling.inverse_name + ' <- mkStatCounter(' + sname + ');\n')

                    sname = 'statName("ROUTER_' + dangling.inverse_name + '_SENT", "' + dangling.inverse_name + ' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' cycles sent")'
                    header.write('STAT sent_' + dangling.inverse_name + ' <- mkStatCounter(' + sname + ');\n')   

                  recvs += 1 


              if(dangling.inverse_sc_type == 'Recv' or dangling.inverse_sc_type == 'ChainRoutingRecv'):
                  if(GENERATE_ROUTER_STATS):
                    sname = 'statName("ROUTER_' + dangling.inverse_name + '_RECEIVED", "' + dangling.inverse_name + ' on ingress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' received cycles")'
                    header.write('STAT received_' + dangling.inverse_name + ' <- mkStatCounter(' + sname + ');\n')

                  header.write('CONNECTION_SEND#(Bit#(PHYSICAL_CONNECTION_SIZE)) send_' + dangling.inverse_name + ' <- mkPhysicalConnectionSend("' + dangling.inverse_name + '", tagged Invalid, False, "' + dangling.raw_type + '", True);\n')
                  sends += 1

              # only create a chain when we see the source
              if(dangling.inverse_sc_type == 'ChainSink'):
                chains += 1 

                if(GENERATE_ROUTER_STATS):
                  sname = 'statName("ROUTER_' + platform + '_' + targetPlatform + '_' + dangling.inverse_name + '_RECEIVED", "' + dangling.inverse_name + ' on ingress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) +' received cycles")'
                  header.write('STAT received_' + dangling.inverse_name + ' <- mkStatCounter(' + sname + ');\n')

                # we must create a logical chain information
                chainsStr += 'let chain_' + dangling.inverse_name + ' = LOGICAL_CHAIN_INFO{logicalName: "' + dangling.inverse_name + '", logicalType: "' + \
                             dangling.raw_type + '", computePlatform: "' + platform + '", incoming: tpl_2(pack_chain_' + dangling.inverse_name + ')' +\
                             ', outgoing: unpack_chain_' + dangling.inverse_name + '};\n'
                      
                chainsStr += 'registerChain(chain_' + dangling.inverse_name + ');\n'

              if(dangling.inverse_sc_type == 'ChainSrc'):
                if(GENERATE_ROUTER_STATS):
                  sname = 'statName("ROUTER_' + platform + '_' + targetPlatform + '_' + dangling.inverse_name + '_BLOCKED", "' + dangling.inverse_name +' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' cycles blocked")'
                  header.write('STAT blocked_chain_' + dangling.inverse_name + ' <- mkStatCounter(' + sname + ');\n')

                  sname = 'statName("ROUTER_' + platform + '_' + targetPlatform + '_' + dangling.inverse_name + '_SENT", "' + dangling.inverse_name + ' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' cycles sent")'
                  header.write('STAT sent_chain_' + dangling.inverse_name + ' <- mkStatCounter(' + sname + ');\n')

            # Ingress switches now feed directly into the egress switches to save latency.  
            for via_idx in range(len(ingressVias)):
              if(ingressVias[via_idx].via_links > 0):
                header.write('INGRESS_SWITCH#(' + str(ingressVias[via_idx].via_links) + ',' + ingressVias[via_idx].via_type + ',' + egressVias[ingressVias[via_idx].via_outgoing_flowcontrol_via].via_header_type + ',' + egressVias[ingressVias[via_idx].via_outgoing_flowcontrol_via].via_body_type + ') ' + ingressVias[via_idx].via_switch + '<- mkIngressSwitch(' + str(ingressVias[via_idx].via_outgoing_flowcontrol_link) + ',' + ingress_multiplexor_names[targetPlatform] + '.' + ingressVias[via_idx].via_method  + '_first, ' + ingress_multiplexor_names[targetPlatform] + '.' + ingressVias[via_idx].via_method  + '_deq);\n\n')

            # The egress links now take as input a list of incoming connections
            # that can be manipulated like fifos.  
            egressVectors = []
            for via_idx in range(len(egressVias)):
              print "Working on " + egressVias[via_idx].via_switch + ' with Links: ' + str(egressVias[via_idx].via_links)
              egressVectors.append(["?" for x in range(egressVias[via_idx].via_links)]) # we could also do a double list comprehension.

            # the egress links need to go first, since they are provided as an argument to the 
            # switches           
            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              if(dangling.inverse_sc_type == 'Send' or dangling.inverse_sc_type == 'ChainRoutingSend'):
                packetizerType = 'Marshalled'
	        header.write('NumTypeParam#('+ str(dangling.bitwidth) +') width_recv_' + dangling.inverse_name +' = ?;\n')
                egressVectors[dangling.via_idx][dangling.via_link] = 'pack_recv_' + dangling.inverse_name
                if(dangling.bitwidth < egressVias[dangling.via_idx].via_width):
                  packetizerType = 'Unmarshalled'
                if(GENERATE_ROUTER_STATS):
                  header.write('let pack_recv_' + dangling.inverse_name + ' <- mkPacketizeConnectionReceive' + packetizerType  + '("' + dangling.inverse_name + '", recv_' + dangling.inverse_name + ',' + str(dangling.via_link) + ', width_recv_' + dangling.inverse_name +  ',blocked_'+ dangling.inverse_name +', sent_'+ dangling.inverse_name +');// Via' + str(egressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth) + '\n')
                else:
                  header.write('let pack_recv_' + dangling.inverse_name + ' <- mkPacketizeConnectionReceive' + packetizerType + '("' + dangling.inverse_name + '", recv_' + dangling.inverse_name + ',' + str(dangling.via_link) + ', width_recv_' + dangling.inverse_name + ', ?, ?); // Via' + str(egressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth) + '\n')

              if(dangling.inverse_sc_type == 'ChainSrc' ):
	        header.write('NumTypeParam#(PHYSICAL_CONNECTION_SIZE) width_chain_' + dangling.inverse_name +' = ?;\n')
	        #header.write('NumTypeParam#('+ str(dangling.bitwidth) +') width_chain_' + dangling.inverse_name +' = ?;\n')
                print "Chain Sink " + dangling.inverse_name + ": Idx " + str(dangling.via_idx) + " Link: " + str(dangling.via_link) + " Length: " + str(len(egressVectors[dangling.via_idx]))  
                egressVectors[dangling.via_idx][dangling.via_link] = 'tpl_1(pack_chain_' + dangling.inverse_name + ')'
                packetizerType = 'Marshalled'
                if(dangling.bitwidth < ingressVias[dangling.via_idx].via_width):
                  packetizerType = 'Unmarshalled'
                if(GENERATE_ROUTER_STATS):
                  header.write('let pack_chain_' + dangling.inverse_name + ' <- mkPacketizeIncomingChain' + packetizerType +'("' + dangling.inverse_name + '", ' + str(dangling.via_link) + ', width_chain_' + dangling.inverse_name + ',blocked_chain_'+ dangling.inverse_name +', sent_chain_'+ dangling.inverse_name  +');\n\n')
                else:
                  header.write('let pack_chain_' + dangling.inverse_name + ' <- mkPacketizeIncomingChain' + packetizerType + '("' + dangling.inverse_name + '", ' + str(dangling.via_link) + ', width_chain_' + dangling.inverse_name +',?,?);\n\n')

          
            # we now need switches for each via.  Need modular arithmetic here to make sure that everyone has a link.  
            # for now we will assume that flow control is twinned - that is the egress 2 uses ingress 2 for its flow control
            # this might well need to change as we introduce assymetry x_X
            # we actually should be allocating the feedback channel as part of the analysis phase, but that can happen later.             
            if (GENERATE_ROUTER_DEBUG):
              header.write('\nDEBUG_SCAN_FIELD_LIST egress_via_dbg_list = List::nil;\n')

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
                print "Idx: " + str(via_idx) + " eg vias len" + str(len(egressVias)) + " in vias len" + str(len(ingressVias))

                header.write('EGRESS_PACKET_GENERATOR#(' + egressVias[via_idx].via_header_type + ', ' +  egressVias[via_idx].via_body_type + ')links_' + egressVias[via_idx].via_switch + '[' + str(egressVias[via_idx].via_links) + '] = ' + linkArray + ';\n') 
                header.write('EGRESS_SWITCH#(' + str(egressVias[via_idx].via_links) + ') ' + egressVias[via_idx].via_switch + '<- mkEgressSwitch( links_' + egressVias[via_idx].via_switch + ', ' + ingressVias[egressVias[via_idx].via_outgoing_flowcontrol_via].via_switch + '.ingressPorts[' + str(egressVias[via_idx].via_outgoing_flowcontrol_link) +'], compose(' + egress_multiplexor_names[targetPlatform] + '.' + egressVias[via_idx].via_method + ',pack), "' + egressVias[via_idx].via_switch + '");\n')

                if(GENERATE_ROUTER_DEBUG):   
                  header.write('egress_via_dbg_list <- addDebugScanField(egress_via_dbg_list, "' + egressVias[via_idx].via_switch + ' buffer status", ' + egressVias[via_idx].via_switch + '.bufferStatus);\n')
                  header.write('egress_via_dbg_list <- addDebugScanField(egress_via_dbg_list, "' + egressVias[via_idx].via_switch + ' fifo status", ' + egressVias[via_idx].via_switch + '.fifoStatus);\n')

            if(GENERATE_ROUTER_DEBUG):   
              header.write('let egressViaDbg <- mkDebugScanNode("Multi-FPGA Router Egress VIAs", egress_via_dbg_list);\n')

            # Hook up the ingress links
            # We also want to build a listing of the mapping in an easy to consume 
            # human readable format.  Therefore, we first sort the connections by assignment.            
            # and dump a link manifest.
            maximumLinks = max(ingressVias, key = lambda via: via.via_links).via_links;
            sortedLinks = sorted(self.platformData[platform]['CONNECTED'][targetPlatform], key = lambda dangling: dangling.via_link + maximumLinks * dangling.via_idx) # sorted is ascending

            for dangling in sortedLinks:
              if(dangling.inverse_sc_type == 'Recv' or dangling.inverse_sc_type == 'ChainSink' or dangling.inverse_sc_type == 'ChainRoutingRecv'):
                header.write('// ' + dangling.inverse_name + ' via_idx: ' + str(dangling.via_idx) + ' link_idx: ' +  str(dangling.via_link) + '\n')

            # and now we actually generate the connections
            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              if(dangling.inverse_sc_type == 'Recv' or dangling.inverse_sc_type == 'ChainRoutingRecv'):
	        header.write('NumTypeParam#('+ str(dangling.bitwidth) +') width_send_' + dangling.inverse_name +' = ?;\n\n')
                packetizerType = 'Marshalled'
                if(dangling.bitwidth < ingressVias[dangling.via_idx].via_width):
                  packetizerType = 'Unmarshalled'
                if(GENERATE_ROUTER_STATS):
                  header.write('Empty unpack_send_' + dangling.inverse_name + ' <- mkPacketizeConnectionSend' + packetizerType  + '("' + dangling.inverse_name + '", send_' + dangling.inverse_name+',' + ingressVias[dangling.via_idx].via_switch  +'.ingressPorts['+str(dangling.via_link) + '], ' + str(dangling.via_link) + ', width_send_' + dangling.inverse_name+',received_'+ dangling.inverse_name +');// Via' + str(ingressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth) + '\n')
                else:
                  header.write('Empty unpack_send_' + dangling.inverse_name + ' <- mkPacketizeConnectionSend' + packetizerType  + '("' + dangling.inverse_name + '", send_' + dangling.inverse_name+',' + ingressVias[dangling.via_idx].via_switch  +'.ingressPorts['+str(dangling.via_link) + '], ' + str(dangling.via_link) + ', width_send_' + dangling.inverse_name+',?);// Via' + str(ingressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth)+ '\n')


              if(dangling.inverse_sc_type == 'ChainSink' ):
	        header.write('NumTypeParam#(PHYSICAL_CONNECTION_SIZE) width_sink_' + dangling.inverse_name +' = ?;\n')
	        #header.write('NumTypeParam#('+ str(dangling.bitwidth) +') width_sink_' + dangling.inverse_name +' = ?;\n')
                packetizerType = 'Marshalled'
                if(dangling.bitwidth < ingressVias[dangling.via_idx].via_width):
                  packetizerType = 'Unmarshalled'
                if(GENERATE_ROUTER_STATS):
                  header.write('PHYSICAL_CHAIN_OUT unpack_chain_' + dangling.inverse_name + ' <- mkPacketizeOutgoingChain' + packetizerType + '("' + dangling.inverse_name + '", ' + ingressVias[dangling.via_idx].via_switch  +'.ingressPorts['+str(dangling.via_link) + '], '  + str(dangling.via_link) + ', width_sink_' + dangling.inverse_name + ', received_' + dangling.inverse_name + ');\n\n') 
                else:
                  header.write('PHYSICAL_CHAIN_OUT unpack_chain_' + dangling.inverse_name + ' <- mkPacketizeOutgoingChain' + packetizerType + '("' + dangling.inverse_name + '", ' + ingressVias[dangling.via_idx].via_switch  +'.ingressPorts['+str(dangling.via_link) + '], '  + str(dangling.via_link) + ', width_sink_' + dangling.inverse_name + ', ?);\n\n')



          # Add in chain insertion code 
          header.write(chainsStr + '\n')

          header.write('endmodule\n')
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
