import re
import sys
import SCons.Script
import math
import itertools
from model import  *
from fpga_environment_parser import *
from type_parser import *
from fpgamap_parser import *
# we write to bitfile 
# we read from logfile
from multi_fpga_generate_bitfile import *
from multi_fpga_log_generator import *
from danglingConnection import *
from via import *
from viaAssignment import *
from linkAssignment import *
from linkType import *
from taggedUnionCompress import *

##
## Manage generation of statistics within a module by collecting counter names
## and then providing methods to emit a statistics node.
##
class RouterStats:
    """Manage router statistics within a generated Bluespec module."""

    def __init__(self,name):
        self.name = name
        self.counters = list()

    def addCounter(self, name, tag, descr):
        """Add a new counter.  The 'name' field will be used to reference the
           counter (using stats.incr(name)).  The 'tag' and 'descr' fields are
           passed to statName()."""
        self.counters.append([ name, tag, descr ])

    def genStats(self):
        """Return the Bluespec to generate the statistics node and counters."""

        if (len(self.counters) == 0):
            return ''

        # First generate the set of IDs
        s = '\n\tSTAT_ID ' + self.name + 'statIDs[' + str(len(self.counters)) + '] = {\n'
        idx = 0
        for cnt in self.counters:
            s += '\t\tstatName("' + cnt[1] + '", "' + cnt[2] + '")'
            if ((idx + 1) != len(self.counters)):
                s += ','
            s += '\n'
            idx += 1
        s += '\t};'

        # Generate Bluespec names corresponding to the ID array
        s += '\n'
        idx = 0
        for cnt in self.counters:
            s += '\tlet ' + cnt[0] + ' = ' + str(idx) + ';\n'
            idx += 1

        # Generate the statistics node
        s += '\n\tSTAT_VECTOR#(' + str(len(self.counters)) + ') ' + self.name + 'stats <- mkStatCounter_Vector(' + self.name + 'statIDs);\n\n'

        return s

    def incrCounter(self, name):
        """Emit a string with the Bluespec code that increments a counter."""
        return  self.name + 'stats.incr_NB(' + name + ')'

class MultiFPGAConnect():

  def __init__(self, moduleList):
      def makePlatformConfigPath(name):
          config_dir = 'multi_fpga/apm-local/'
          if not os.path.exists(config_dir): os.makedirs(config_dir)
          return config_dir + name

      self.moduleList = moduleList
      self.ANALYZE_NETWORK = moduleList.getAWBParam('multi_fpga_connect', 'ANALYZE_NETWORK')
      self.MAX_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MAX_NUMBER_OF_VIAS')
      self.ENABLE_TYPE_COMPRESSION = moduleList.getAWBParam('multi_fpga_connect', 'ENABLE_TYPE_COMPRESSION')
      self.MIN_NUMBER_OF_VIAS = moduleList.getAWBParam('multi_fpga_connect', 'MIN_NUMBER_OF_VIAS')
      self.GENERATE_ROUTER_DEBUG = moduleList.getAWBParam('multi_fpga_log_generator', 'GENERATE_ROUTER_DEBUG')
      self.GENERATE_ROUTER_STATS = moduleList.getAWBParam('multi_fpga_log_generator', 'GENERATE_ROUTER_STATS')
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
          platformLogPath = makePlatformConfigPath(makePlatformLogName(platform.name,APM_NAME))
          platformLogBuildDir = 'multi_fpga/' + makePlatformLogName(platform.name,APM_NAME) + '/pm'

          platformBitfileAPMName = makePlatformBitfileName(platform.name,APM_NAME) + '.apm'
          platformBitfilePath = makePlatformConfigPath(makePlatformBitfileName(platform.name,APM_NAME))
          platformBitfileBuildDir = 'multi_fpga/' + makePlatformBitfileName(platform.name,APM_NAME) + '/pm/'

          wrapperLog =  platformLogBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/.bsc/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '_Wrapper.log'
          parameterFile =  platformBitfileBuildDir +'/'+ moduleList.env['DEFS']['ROOT_DIR_HW']+ '/' + moduleList.env['DEFS']['ROOT_DIR_MODEL'] + '/multifpga_routing.bsh'
               

          # We need to build up some context to give bluetcl the right search paths for when
          # we go to inspect the types.  Each platform can have a different hierarchy.
          allModules = [moduleList.topModule] + moduleList.topModule.moduleDependency['PLATFORM_HIERARCHIES'][platformName].synthBoundaries() + moduleList.synthBoundaries()
          bluetclPaths = ''

          for boundary in allModules:
              bluetclPaths += platformLogBuildDir + '/hw/' + boundary.buildPath + '/.bsc/:'

          # need ifc as well
          bluetclPaths += platformLogBuildDir + '/iface/build/hw/.bsc/'
          

          self.platformData[platform.name] = {'LOG': wrapperLog, 'BSH': parameterFile, 'BLUETCL': bluetclPaths, 'DANGLING': [], 'CONNECTED': {}, 'INDEX': {}, 'WIDTHS': {}, 'INGRESS_VIAS': {}, 'EGRESS_VIAS': {}, 'INGRESS_VIAS_PASS_ONE': {}, 'EGRESS_VIAS_PASS_ONE': {}, 'TYPES':{}}


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
                                          hop, "False", src.bitwidth, "RouteThrough", "RouteThrough", src.type_structure))
          srcs.append(DanglingConnection("ChainRoutingSend", src.raw_type, -1, src.name + "Routethrough" + hop, 
                                         hop, "False", src.bitwidth, "RouteThrough", "RouteThroug\
h", src.type_structure))


      sinks.append(sink)
    
      for pair in zip(srcs,sinks):
          self.assignIndices(pair[0],pair[1])
  


  def generateEgressMultiplexor(self, platform): 
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}

    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      multiplexor_stats = RouterStats("egressMultiplexor")
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

      # Instantiate various statistics at the merger. 
      # mkDwire with empty string signifier...
      sum_string = []
      for via in egressVias:
        multiplexor_definition += '\tlet ' + via.via_method + '_wire <- mkDWire(tagged Invalid);\n' 
        multiplexor_definition += '\tlet ' + via.via_method + '_pulse <- mkPulseWire();\n' 
        sum_string.append('zeroExtend(pack(' + via.via_method + '_pulse))')

        if(self.GENERATE_ROUTER_STATS):
          multiplexor_stats.addCounter('enqueued_' + moduleName + '_' + via.via_method,
                                       'ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED',
                                       via.via_method +' cycles enqueued')
 
      multiplexor_definition += '\tBit#(TLog#(' + str(1 + len(egressVias)) +')) totalEnqs = ' + " + ".join(sum_string) + ";\n"
          
      for enqs in range(1 + len(egressVias)):
        if(self.GENERATE_ROUTER_STATS):
          multiplexor_stats.addCounter('enqueued_' + moduleName + '_' + str(enqs),
                                       'ROUTER_' + moduleName + '_' + str(enqs) + '_ENQUEUED',
                                       via.via_method +' cycles that lanes enqueued')

      #stats for the merger
      if(self.GENERATE_ROUTER_STATS):
        multiplexor_stats.addCounter('merged_' + moduleName,
                                     'ROUTER_' + moduleName + '_MERGED',
                                     moduleName + ' cycles enqueued')

      multiplexor_definition += multiplexor_stats.genStats()
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

      if(self.GENERATE_ROUTER_STATS):
        multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('merged_' + moduleName) + ';\n'

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

      for enqs in range(1 + len(egressVias)):

        if(self.GENERATE_ROUTER_STATS):

          multiplexor_definition += '\n\trule countMerges' + str(enqs) + '(totalEnqs == ' + str(enqs) + ');\n'
          multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('enqueued_' + moduleName + '_' + str(enqs)) + ';\n'
          multiplexor_definition += '\tendrule\n\n'

      for via in egressVias:
        multiplexor_definition += '\tmethod Action ' + via.via_method + '(Bit#(' + str(via.via_width)  + ') data) if(write_ready);\n'
        #multiplexor_definition += '    $display("' + via.via_method + '_wire fires");\n'
        multiplexor_definition += '\t\t' + via.via_method + '_wire <= tagged Valid data;\n'
        multiplexor_definition += '\t\t' + via.via_method + '_pulse.send;\n'
        if(self.GENERATE_ROUTER_STATS):
          multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('enqueued_' + moduleName + '_' + via.via_method) + ';\n'
        multiplexor_definition += '\tendmethod\n\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]


  def generateEgressMultiplexorParSerial(self, platform): 
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}

    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      multiplexor_stats = RouterStats("egressMultiplexor")

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
        if(self.GENERATE_ROUTER_STATS):
          multiplexor_stats.addCounter('enqueued_' + moduleName + '_' + via.via_method,
                                       'ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED',
                                       via.via_method + ' cycles enqueued')

      if(self.GENERATE_ROUTER_STATS):
        multiplexor_stats.addCounter('merged_' + moduleName,
                                     'ROUTER_' + moduleName + '_MERGED',
                                     moduleName + ' cycles enqueued')

      multiplexor_definition += multiplexor_stats.genStats()


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


        if(self.GENERATE_ROUTER_STATS):
          multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('enqueued_'+ moduleName + '_' + via.via_method) + ';\n'

        multiplexor_definition += '  endmethod\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]


  def generateEgressMultiplexorSerial(self, platform): 
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}

    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      multiplexor_stats = RouterStats("egressMultiplexor")
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
        if(self.GENERATE_ROUTER_STATS):
          multiplexor_stats.addCounter('enqueued_' + moduleName + '_' + via.via_method,
                                       'ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED',
                                       via.via_method + ' cycles enqueued')

      if(self.GENERATE_ROUTER_STATS):
        multiplexor_stats.addCounter('merged_' + moduleName,
                                     'ROUTER_' + moduleName + '_MERGED',
                                     moduleName + ' cycles enqueued')

      multiplexor_definition += multiplexor_stats.genStats()

      viaCount = 0
      for via in egressVias:
        multiplexor_definition += '  method Action ' + via.via_method + '(Bit#(' + str(via.via_width)  + ') data) if(write_ready);\n'
        #multiplexor_definition += '    $display("' + via.via_method + '_wire fires");\n'

        multiplexor_definition += '    Bit#(TLog#(TAdd#(1,' + str(len(egressVias)) + '))) tag = ' + str(viaCount) + ';\n'
        multiplexor_definition += '    write(zeroExtendNP({tag,data}));\n'
        viaCount = viaCount + 1
        if(self.GENERATE_ROUTER_STATS):
          multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('enqueued_' + moduleName + '_' + via.via_method) + ';\n'
        multiplexor_definition += '  endmethod\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]
            

  def generateIngressMultiplexor(self, platform):
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}

    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      multiplexor_stats = RouterStats("ingressMultiplexor")

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

        if(self.GENERATE_ROUTER_STATS):
          multiplexor_stats.addCounter('dequeued_' + via.via_method,
                                       'ROUTER_' + moduleName + '_' + via.via_method + '_DEQUEUED',
                                       via.via_method + ' cycles dequeued')

      if(self.GENERATE_ROUTER_DEBUG):   
        multiplexor_definition += '\n\tDEBUG_SCAN_FIELD_LIST via_dbg_list = List::nil;\n'
        for via in ingressVias:
          multiplexor_definition += '\tvia_dbg_list <- addDebugScanField(via_dbg_list, "' + via.via_method + ' notFull", ' + via.via_method + '_fifo.notFull);\n'
          multiplexor_definition += '\tvia_dbg_list <- addDebugScanField(via_dbg_list, "' + via.via_method + ' notEmpty", ' + via.via_method + '_fifo.notEmpty);\n'
        multiplexor_definition += '\tlet viaDbg <- mkDebugScanNode("multi-FPGA vias", via_dbg_list);\n'

      multiplexor_definition += multiplexor_stats.genStats()

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
        if(self.GENERATE_ROUTER_STATS):
          multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('dequeued_' + via.via_method) + ';\n'
        multiplexor_definition += '\t\t' + via.via_method + '_fifo.deq();\n'
        multiplexor_definition += '\tendmethod\n\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]

  def generateIngressMultiplexorSerial(self, platform):
    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}

    for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
      multiplexor_stats = RouterStats("ingressMultiplexor")

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

      for via in ingressVias:
        multiplexor_definition += '  let ' + via.via_method + '_fifo <- mkBypassFIFOF();\n' # Bypass fifo saves latency.
        if(self.GENERATE_ROUTER_STATS):
          multiplexor_stats.addCounter('dequeued_' + via.via_method,
                                       'ROUTER_' + moduleName + '_' + via.via_method + '_DEQUEUED',
                                       via.via_method + ' cycles dequeued')

      multiplexor_definition += multiplexor_stats.genStats()

      via_count = 0
      for via in ingressVias:
        multiplexor_definition += '  rule sendData' + str(via_count) + '(tpl_1(rxdata) == ' + str(via_count) + ');\n'
        # multiplexor_definition += '    $display("ingress mergeData ' + moduleName  +'  fires");\n'
        multiplexor_definition += '      deq();\n'
        multiplexor_definition += '      ' + via.via_method + '_fifo.enq(tpl_2(rxdata));\n'
        multiplexor_definition += '  endrule\n'
        via_count += 1

      for via in ingressVias:
        multiplexor_definition += '  method ActionValue#(Bit#(' + str(via.via_width) + ')) ' + via.via_method + '();\n'
        if(self.GENERATE_ROUTER_STATS):
          multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('dequeued_' + via.via_method) + ';\n'
        multiplexor_definition += '    ' + via.via_method + '_fifo.deq();\n'
        multiplexor_definition += '    return ' + via.via_method + '_fifo.first();\n'
        multiplexor_definition += '  endmethod\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]

    
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

  # Notice that chains will have their platform direction labelled
  def parseStats(self):
    # let's read in a stats file
    statsFile = self.moduleList.getAllDependenciesWithPaths('GIVEN_STATS')    
    stats = {}
    print "StatsFile " + str(statsFile)
    if(len(statsFile) > 0):
      filename = self.moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + statsFile[0]
      logfile = open(filename,'r')  
      print "Processing Stats:  " + filename
      for line in logfile:
        if(re.match('.*ROUTER_.*_SENT.*',line)):
          #We may have a chunked pattern.   
          match = re.search(r'.*ROUTER_(\w+)(_chunk_\d+)_SENT,.*,(\d+)',line)
          if(match):
              #print "Stat Match Chunk" + match.group(1) + " got " + match.group(3) + " from " + line
              stats[match.group(1)] = int(match.group(3))
              stats[match.group(1)+match.group(2)] = int(match.group(3))
              continue

          match = re.search(r'.*ROUTER_(\w+)_SENT,.*,(\d+)',line)
          if(match):
              #print "Stat Match " + match.group(1) + " got " + match.group(2) + " from " + line
              stats[match.group(1)] = int(match.group(2))

    return stats


  def generateRouterTypes(self, viaWidth, viaLinks, maxWidth):

    # At some point, we can reduce the number of header bits based on 
    # what we actually assign.  This would permit us to allocate smalled link
    links = max([1,int(math.ceil(math.log(viaLinks,2)))])  
    # Max chunks depends on filler.  iterate till we get a fixed point.
    # iteration should converge because chunks should monotonically decrease
    # and fillerWidth should monotonically increase
    fillerWidth = -1
    fillerWidthNext = 0
    chunks = -1

    while(fillerWidth != fillerWidthNext):
        fillerWidth = fillerWidthNext
        chunks = int(max([1,math.ceil(math.log(1.0+math.ceil(float(max([0.0, maxWidth - fillerWidth]))/viaWidth),2))]))
        fillerWidthNext = viaWidth - links - chunks

    fillerWidth = fillerWidthNext
    print "Generating " + str(links) + " links " + str(chunks) + " chunks " + str(fillerWidth) + " filler from width " + str(viaWidth) + " calc" + str(1.0+math.ceil(float(max([0.0, maxWidth - fillerWidth]))/viaWidth)) +") max link " + str(maxWidth) + " via links " + str(viaLinks) 
  
    headerType = "GENERIC_UMF_PACKET_HEADER#(\n" + \
                 "             0, " + str(links) + ",// Log links ( "+ str(viaLinks) +")\n" + \
                 "             0, " + str(chunks) + ",//Log chunks\n" + \
                 "             0, " + str(fillerWidth) +")//filler width\n"

    bodyType = "Bit#(" +  str(viaWidth) + ")"
      
    type = "GENERIC_UMF_PACKET#(" + headerType + ", " + bodyType + ")"

    return [headerType, bodyType, type, fillerWidth]


  # Having a large, conservative header size can cause us to weight 
  # lanes incorrectly during LJF operation.  As a result, we will now 
  # maintain provisional header widths and do a hill climb until we get 
  # feasible header sizes.  This will put much tighter bounds on our header 
  # sizings
  def allocateLJF(self, platformLinks, targetLinks, vias):
      return self.allocateLJFWithHeaders(platformLinks, targetLinks, vias, [1 for via in vias]);

  def allocateLJFWithHeaders(self, platformLinks, targetLinks, vias, headers):
    #first sort the links on both sides
    links = sorted(platformLinks, key = lambda dangling: dangling.activity * -2048 + dangling.bitwidth) # sorted is ascending    
    platformConnectionsProvisional = []
    targetPlatformConnectionsProvisional = []
    #since we can recurse, we should copy our inputs
    viasRollback = copy.deepcopy(vias)
    # do I need to rename all the links to be sorted?  Probably...
    maxLinkWidth = [-1 for via in vias]
    for danglingIdx in range(len(links)):           
      if((links[danglingIdx].sc_type == 'Recv') or (links[danglingIdx].sc_type == 'ChainSink') or (links[danglingIdx].sc_type == 'ChainRoutingRecv')):
        # depending on the width of the vias, and the width of our type we get different loads on different processors
        # need to choose the minimum

        print "\n\n Analyzing   " + links[danglingIdx].name + " of width " + str(links[danglingIdx].bitwidth)  + " raw load: " + str(links[danglingIdx].activity) + "\n"
        
        minIdx = -1 
        minLoad = 0        
        
        for via in range(len(vias)):
          extraChunk = 0
          viaWidth = vias[via].width
          viaLoad = vias[via].load
          headerSize = headers[via] # reserve some space for the header.  we may actually find that this sizing is wrong.
          if(((links[danglingIdx].bitwidth + headerSize )%viaWidth) > 0):
            extraChunk = 1
          chunks = (links[danglingIdx].bitwidth + headerSize )/viaWidth + extraChunk       
          load = links[danglingIdx].activity * chunks + viaLoad
          
          # We don't do a great job here of evaluating opportunity cost.  Picking the longest running on the fastest processor 
          # might be a bad choice.
          if((load < minLoad) or (minIdx == -1)):
            #print "Setting min load as " +str(minLoad)  + " idx: " + str(via)
            minIdx = via
            minLoad = load
           
        vias[minIdx].load = minLoad
        if(links[danglingIdx].bitwidth > maxLinkWidth[minIdx]):
          maxLinkWidth[minIdx] = links[danglingIdx].bitwidth
        # XXX what are these doing?  
        platformConnectionsProvisional.append(LinkAssignment(links[danglingIdx].name, links[danglingIdx].sc_type, minIdx, vias[minIdx].links))
        targetPlatformConnectionsProvisional.append(LinkAssignment(links[danglingIdx].inverse_name, links[danglingIdx].inverse_sc_type, minIdx, vias[minIdx].links))  
        print "Assigning Recv " + links[danglingIdx].name   + " Via " + str(minIdx) + " Link " + str(vias[minIdx].links) + " Load " + str(vias[minIdx].load) + "\n"
        print "Vias are " +  str(vias) + "\n"
        vias[minIdx].links += 1

    #do we have a legal assingment (i.e., were our header sizes okay?)
    needRecurse = False
    headersNext = []
    for via in range(len(vias)):
        [headerType, bodyType, type, fillerWidth] = self.generateRouterTypes(vias[via].width, vias[via].links, maxLinkWidth[via])
        headerActual = vias[via].width - fillerWidth
        #To ensure termination, we require monotonically increasing
        #header sizes 
        headersNext.append(max([headerActual,headers[via]]))
        if(headers[via] < headerActual):
            needRecurse = True
              
    if(not needRecurse):
        print "NoRecurse Assigned " + str(vias) + "\n"
        return [vias, platformConnectionsProvisional, targetPlatformConnectionsProvisional]
    else:
        print "Recursing with header: " + str(headersNext) + "\n"
        return self.allocateLJFWithHeaders(platformLinks, targetLinks, viasRollback, headersNext)

  def assignLinks(self, provisionalAssignments, provisionalTargetAssignments, platformConnections, targetPlatformConnections):
    for provisional in provisionalAssignments:
      assigned = False
      for idx in range(len(platformConnections)): # we can probably do better than this n^2 loop. 
        # Watch out for chain Sinks and sources
          print "Examining: " + platformConnections[idx].name + " " + provisional.name
          if((platformConnections[idx].name == provisional.name) and (platformConnections[idx].sc_type == provisional.sc_type)): 
              assigned = True
              platformConnections[idx].via_idx  = provisional.via_idx
              platformConnections[idx].via_link = provisional.via_link
              print "Assigning egress " + platformConnections[idx].name + ' of type ' + platformConnections[idx].sc_type  +' ' + str(provisional.via_idx) + ' ' + str(provisional.via_link)
      if(not assigned):
          exit(0)
    for provisional in provisionalTargetAssignments:
      assigned = False
      for idx in range(len(targetPlatformConnections)): # we can probably do better than this n^2 loop. 
        # Watch out for chain Sinks and sources
        print "Examining: " + targetPlatformConnections[idx].name + " " + provisional.name
        if((targetPlatformConnections[idx].name == provisional.name) and (targetPlatformConnections[idx].sc_type == provisional.sc_type)):    
            assigned = True
            targetPlatformConnections[idx].via_idx  = provisional.via_idx
            targetPlatformConnections[idx].via_link = provisional.via_link

            print "Assigning ingress " + targetPlatformConnections[idx].name + ' of type ' + targetPlatformConnections[idx].sc_type  +' ' + str(provisional.via_idx) + ' ' + str(provisional.via_link)
      if(not assigned):
          exit(0)

  # Given a stats asssignment, this function will give all dangling
  # connections in the design a weight.  If no stat exists, then the
  # weight will be the average of the weights that do exist.  If no
  # stats file exists, then the weight will be set to a constant and
  # preference give to non-chains
  def assignActivity(self, stats):
    # handle the connections themselves
    recvs = 0
    chains = 0           

    for platform in self.environment.getPlatformNames():
      for targetPlatform in self.platformData[platform]['CONNECTED'].keys():
        totalTraffic = 0;
        for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
          if(dangling.sc_type == 'Recv' or dangling.sc_type == 'ChainRoutingRecv'):
            recvs += 1
            if(dangling.name in stats):
                dangling.activity = stats[dangling.name]
                totalTraffic += stats[dangling.name]
                print "Assigning Load " + platform + "->" + targetPlatform + " " + dangling.name + " " + str(stats[dangling.name])
            else:
                #In some we may have the wrong number of chunks.  To make things more usable
                #we will also match non-chunks 
                match = re.search(r'(\w+)(_chunk_\d+)',dangling.name)
                if(match and (match.group(1) in stats)):      
                    dangling.activity = stats[match.group(1)]
                    totalTraffic += stats[match.group(1)]
                    print "Assigning Load (Chunk match) " + platform + "->" + targetPlatform + " " + dangling.name + " " + str(stats[match.group(1)])                    
          # only create a chain when we see the sink                                                                                                               
          if(dangling.sc_type == 'ChainSink'):
  
            chains += 1
            chainName = platform + "_" + targetPlatform + "_" + dangling.name
            if(chainName in stats):
              dangling.activity = stats[chainName]
              totalTraffic += stats[chainName]
              print "Assigning Load " + platform + "->" + targetPlatform + " " + chainName + " " + str(stats[chainName])
            else:
                match = re.search(r'(\w+)(_chunk_\d+)',chainName)
                if(match and (match.group(1) in stats)):   
                    dangling.activity = stats[match.group(1)]
                    totalTraffic += stats[match.group(1)]
                    print "Assigning Load (Chunk match) " + platform + "->" + targetPlatform + " " + dangling.name + " " + str(stats[match.group(1)])                    

        if(totalTraffic == 0):
          totalTraffic = 2*(chains+recvs)
 
        print "Total traffic is: " + str(totalTraffic)

        # assign some value to 
        for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
          if(dangling.sc_type == 'Recv' or dangling.sc_type == 'ChainRoutingRecv'):
            if(dangling.activity < 0):
              dangling.activity = float(totalTraffic)/(chains+recvs)
              print "Defaulting Load " + platform + "->" + targetPlatform + " " + dangling.name + " " + str(dangling.activity)

          # only create a chain when we see the source                                                                                                                                                                                       
          if(dangling.sc_type == 'ChainSink'):         
            chainName = platform + "_" + targetPlatform + "_" + dangling.name
            if(dangling.activity < 0):
              dangling.activity = (float(totalTraffic)/(2*(chains+recvs))) * 0.1  # no stat?  Make connections better than chains
              print "Defaulting Load " + platform + "->" + targetPlatform + " " + chainName + " " + str(dangling.activity)


  def analyzeNetwork(self):
      eval('self.' + self.ANALYZE_NETWORK + '()')

  def generateViaLJF(self, platform, targetPlatform):
      firstAllocationPass = True; # We can't terminate in the first pass 
      viaWidthsFinal = [] # at some point, we'll want to derive this. 
      viasFinal = []   
      maxLoad = 0;
      headerSize = 12 # simplifying assumption: headers have uniform size.  This isn't actually the case.

      hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
      egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
      hopToTarget = self.environment.transitTablesOutgoing[targetPlatform][platform]
      ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'

      sortedLinks = sorted(self.platformData[platform]['CONNECTED'][targetPlatform], key = lambda dangling: dangling.activity * -2048 + dangling.bitwidth) # sorted is ascending

      for numberOfVias in range(self.MIN_NUMBER_OF_VIAS,self.MAX_NUMBER_OF_VIAS+1):
          viaSizingIdx = 0          
          noViasRemaining = 0
          # pick our via links deterministically
          viaWidths = []
          for via in range(numberOfVias):
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
          platformConnections = sorted(self.platformData[platform]['CONNECTED'][targetPlatform],key = lambda connection: connection.name)
          targetPlatformConnections = sorted(self.platformData[targetPlatform]['CONNECTED'][platform],key = lambda connection: connection.name)

          vias = [ViaAssignment(width, 0, 0) for width in viaWidths]
          [viasProvisional, platformConnectionsProvisional, targetPlatformConnectionsProvisional] = self.allocateLJF(platformConnections, targetPlatformConnections , vias)


          platformConnections = sorted(self.platformData[platform]['CONNECTED'][targetPlatform],key = lambda connection: connection.name)
          targetPlatformConnections = sorted(self.platformData[targetPlatform]['CONNECTED'][platform],key = lambda connection: connection.name)          
     
          if(max([via.load for via in viasProvisional]) < maxLoad or firstAllocationPass):
            print "Better allocation with  " + str(len(viasProvisional)) + " vias found."
            maxLoad = max([via.load for via in viasProvisional])
            viasFinal = viasProvisional
            self.assignLinks(platformConnectionsProvisional, targetPlatformConnectionsProvisional, platformConnections, targetPlatformConnections)
#          else:
            #Quit while we're ahead
#            break
          firstAllocationPass = False

      return viasFinal



  # The general strategy here is 
  # 1) hueristically pick lane widths
  # 2) Assign links to lanes using Longest Job First hueristic
  # Repeat until maximum link occupancy increases (although we might just try repeatedly and keep all the results) 

  def generateViaCombinational(self, platform, targetPlatform):
      firstAllocationPass = True; # We can't terminate in the first pass 
      viaWidthsFinal = [] # at some point, we'll want to derive this. 
      viasFinal = []   
      maxLoad = 0;
      headerSize = 7 # simplifying assumption: headers have uniform size.  This isn't actually the case.

      hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
      egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
      hopToTarget = self.environment.transitTablesOutgoing[targetPlatform][platform]
      ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'

      sortedLinks = sorted(self.platformData[platform]['CONNECTED'][targetPlatform], key = lambda dangling: dangling.activity * -2048 + dangling.bitwidth) # sorted is ascending
        

      for numberOfVias in range(self.MIN_NUMBER_OF_VIAS,self.MAX_NUMBER_OF_VIAS + 1):
          viaSizingIdx = 0          
          noViasRemaining = 0
          # pick our via links deterministically
          viaWidths = []
          viaOptions = [] 
          if(numberOfVias > 1):
              viaOptions = itertools.combinations(sortedLinks,numberOfVias - 1) # we always have the base via..
          for allocation in viaOptions:
            #is it legal?
            baseViaWidth = self.platformData[platform]['WIDTHS'][egressVia] - (sum(map(lambda x: x.bitwidth, allocation)) + (1+numberOfVias)*(headerSize + 1)) 
            if(baseViaWidth > 0):
              viaWidths = map(lambda x: x.bitwidth + headerSize, allocation) + [baseViaWidth+headerSize]
            else:
              continue


            # send/recv pairs had better be matched.
            # so let's match them up
            # need to maintain the sorted order
            platformConnections = sorted(self.platformData[platform]['CONNECTED'][targetPlatform],key = lambda connection: connection.name)
            targetPlatformConnections = sorted(self.platformData[targetPlatform]['CONNECTED'][platform],key = lambda connection: connection.name)

            vias = [ViaAssignment(width, 0, 0) for width in viaWidths]
            [viasProvisional, platformConnectionsProvisional, targetPlatformConnectionsProvisional] = self.allocateLJF(platformConnections, targetPlatformConnections , vias)


            platformConnections = sorted(self.platformData[platform]['CONNECTED'][targetPlatform],key = lambda connection: connection.name)
            targetPlatformConnections = sorted(self.platformData[targetPlatform]['CONNECTED'][platform],key = lambda connection: connection.name)          
            
            if(max([via.load for via in viasProvisional]) < maxLoad or firstAllocationPass):
              print "Better allocation with  " + str(len(viasProvisional)) + " vias found."
              maxLoad = max([via.load for via in viasProvisional])
              viasFinal = viasProvisional
              self.assignLinks(platformConnectionsProvisional, targetPlatformConnectionsProvisional, platformConnections, targetPlatformConnections)

            firstAllocationPass = False

      print "Combinational returns " + str(viasFinal) + "\n"
      return viasFinal


  def analyzeNetworkNonuniform(self, allocateFunction):

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
    stats = self.parseStats()
    self.assignActivity(stats)

    for platform in self.environment.getPlatformNames():
      for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():

        # for this target, we assume that we have a monolithic fifo via.  
        # first, we must decide how to break up the via.  We will store that information
        # and use it later

        viasFinal = allocateFunction(platform, targetPlatform)
        #end here 
        headerSize = 7 # simplifying assumption: headers have uniform size.  This isn't actually the case.
        hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
        egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
        hopToTarget = self.environment.transitTablesOutgoing[targetPlatform][platform]
        ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'

        self.platformData[platform]['EGRESS_VIAS'][targetPlatform] = []
        self.platformData[targetPlatform]['INGRESS_VIAS'][platform] = []

        # We don't yet have information about how to handle flowcontrol
        # But we will fill in the data structure temporarily.  
        # Once all data via assignments have been handeled, we will do flowcontrol.
        for via in range(len(viasFinal)):

          # let's find the maximum width guy so that we calculate the types correctly. 
          viaConnections = filter(lambda connection: connection.via_idx == via,self.platformData[platform]['CONNECTED'][targetPlatform])
          maxWidth = max(map(lambda connection: connection.bitwidth,viaConnections))

          [headerType, bodyType, type, fillerWidth] = self.generateRouterTypes(viasFinal[via].width, viasFinal[via].links, maxWidth)

          egress = Via(platform,targetPlatform,"egress", headerType, bodyType, type, viasFinal[via].width, viasFinal[via].links, viasFinal[via].links, 0, hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via) + '_write', 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via), -1, -1, viasFinal[via].load, fillerWidth)

          ingress = Via(targetPlatform,platform,"ingress", headerType, bodyType, type, viasFinal[via].width, viasFinal[via].links, viasFinal[via].links, 0, hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via) + '_read', 'switch_ingress_' + platform + '_from_' + targetPlatform + '_' + hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via), -1, -1, viasFinal[via].load, fillerWidth)

          egressViasInitial[platform][targetPlatform].append(egress)
          ingressViasInitial[targetPlatform][platform].append(ingress) 
          print "Via pair " + egress.via_switch + ": " + str(via) + ' width: '  + str(viasFinal[via].width) + ' links" ' + str(viasFinal[via].links)



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
                
            # We don't do a great job here of evaluating opportunity
            # cost.  Picking the longest running on the fastest
            # processor might be a bad choice.
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

          # let's find the maximum width guy so that we calculate the types correctly. 
          viaConnections = filter(lambda connection: connection.via_idx == via,self.platformData[platform]['CONNECTED'][targetPlatform])
          maxWidth = max(map(lambda connection: connection.bitwidth,viaConnections)) # notice that we are not taking in to account the flow control bits here. We might well want to do that at some point. 


          print "Idx " + str(via) + " links " + str(len(egressLinks[platform][targetPlatform])) + " loads " + str(len(viaLoads[platform][targetPlatform]))
          [headerType, bodyType, type, fillerWidth] = self.generateRouterTypes(egress_first_pass.via_width, egressLinks[platform][targetPlatform][via], maxWidth) 

          egress = Via(platform,targetPlatform,"egress", headerType, bodyType, type, egress_first_pass.via_width, egressLinks[platform][targetPlatform][via], egress_first_pass.via_links, egressLinks[platform][targetPlatform][via] - egress_first_pass.via_links, egress_first_pass.via_method, egress_first_pass.via_switch, ingressFlowcontrolAssignment[targetPlatform][platform][via][1], ingressFlowcontrolAssignment[targetPlatform][platform][via][0], viaLoads[platform][targetPlatform][via],fillerWidth)
 
          ingress = Via(targetPlatform,platform,"ingress", headerType, bodyType, type, ingress_first_pass.via_width, egressLinks[platform][targetPlatform][via], ingress_first_pass.via_links,  egressLinks[platform][targetPlatform][via] - ingress_first_pass.via_links, ingress_first_pass.via_method, ingress_first_pass.via_switch, ingressFlowcontrolAssignment[targetPlatform][platform][via][1],  ingressFlowcontrolAssignment[targetPlatform][platform][via][0], viaLoads[platform][targetPlatform][via],fillerWidth)

          self.platformData[platform]['EGRESS_VIAS'][targetPlatform].append(egress)
          self.platformData[targetPlatform]['INGRESS_VIAS'][platform].append(ingress) 
          print "Via pair " + egress_first_pass.via_switch + ": " + str(via) + ' width: '  + str(ingress_first_pass.via_width) + ' links" ' + str(egressLinks[platform][targetPlatform][via])


  def analyzeNetworkComb(self):
      self.analyzeNetworkNonuniform(self.generateViaCombinational)

  def analyzeNetworkLJF(self):
      self.analyzeNetworkNonuniform(self.generateViaLJF)

  def analyzeNetworkCompletelyRandom(self):
      self.analyzeNetworkUniform(False)

  def analyzeNetworkRandom(self):
      self.analyzeNetworkUniform(True)

  def analyzeNetworkUniform(self, useActivity):

    # let's do a simple scheme with an equal number of vias.
    numberOfVias = self.MAX_NUMBER_OF_VIAS
    stats = self.parseStats()
    if(useActivity):
      self.assignActivity(stats)

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
        
        self.platformData[platform]['EGRESS_VIAS'][targetPlatform] = []
        self.platformData[targetPlatform]['INGRESS_VIAS'][platform] = []
            
                                         
        hopFromTarget = self.environment.transitTablesIncoming[platform][targetPlatform]
        egressVia = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
        hopToTarget = self.environment.transitTablesOutgoing[targetPlatform][platform]
        ingressVia = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'

        # send/recv pairs had better be matched.
        # We want the slower chains to be evenly dispersed across the randomly assigned links
        platformConnections = self.platformData[platform]['CONNECTED'][targetPlatform]
        targetPlatformConnections = self.platformData[targetPlatform]['CONNECTED'][platform]
        viaWidth = (self.platformData[platform]['WIDTHS'][egressVia] - numberOfVias) / numberOfVias

        #We already assign the flow control link to zero, so we must initialize the 
        #via assignment to have one link already gone
        vias = [ViaAssignment(viaWidth, 0, 1) for via in range(numberOfVias)]
        [viasProvisional, platformConnectionsProvisional, targetPlatformConnectionsProvisional] = self.allocateLJF(platformConnections, targetPlatformConnections , vias)
        self.assignLinks(platformConnectionsProvisional, targetPlatformConnectionsProvisional, platformConnections, targetPlatformConnections)
        # Now that we have an assignment of links, we can calculate the via types. 
        # We're dropping some bits here
        # this loop should be refactored to split ingress and egress
        # we need to reserve space for valid bits
        for via in range(numberOfVias):
          # need to set the via widths here...
          viaLinks = viasProvisional[via].links
          print "Uniform Via " + str(via) + " links " + str(viasProvisional[via].links)
          # let's find the maximum width guy so that we calculate the types correctly. 
          viaConnections = filter(lambda connection: connection.via_idx == via,self.platformData[platform]['CONNECTED'][targetPlatform])
          maxWidth = viaWidth
          if(len(viaConnections) > 0):
            maxWidth = max(map(lambda connection: connection.bitwidth,viaConnections)) # notice that we are not taking in to account the flow control bits here. We might well want to do that at some point. 

          [headerType, bodyType, type, fillerWidth] = self.generateRouterTypes(viaWidth, viaLinks, maxWidth)
          
          print "Creating Via " + 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  +str(via) + " : links " + str(viaLinks)
          self.platformData[platform]['EGRESS_VIAS'][targetPlatform].append(Via(platform,targetPlatform,"egress", headerType, bodyType, type, viaWidth, viaLinks, viaLinks - 1, 1, hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via) + '_write', 'switch_egress_' + platform + '_to_' + targetPlatform + '_' +hopFromTarget.replace(".","_").replace("[","_").replace("]","_")  + str(via), 0, via, 0, fillerWidth))
          self.platformData[targetPlatform]['INGRESS_VIAS'][platform].append(Via(targetPlatform,platform,"ingress", headerType, bodyType, type, viaWidth, viaLinks, viaLinks - 1, 1, hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via) + '_read', 'switch_ingress_' + platform + '_from_' + targetPlatform + '_' + hopToTarget.replace(".","_").replace("[","_").replace("]","_") + str(via), 0, via, 0, fillerWidth)) 

        

  def generateCode(self):
      # now that everything is matched we can ostensibly generate the header file
      # header must include device mapping as well

      for platform in self.environment.getPlatformNames():
          header = open(self.platformData[platform]['BSH'],'w')
          header.write('// Generated by build pipeline\n\n')
          header.write('`include "awb/provides/common_services.bsh"\n')
          header.write('`include "awb/provides/librl_bsv_base.bsh"\n')
          header.write('`include "awb/provides/soft_connections.bsh"\n')
          header.write('import GetPut::*;\n')
          header.write('import Connectable::*;\n')

          # With compress connections, we need other bo to be imported
          if(self.ENABLE_TYPE_COMPRESSION):
              for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
                  for dep in list(set(flatten(map(lambda dangling: dangling.type_structure.dependencies, \
                                  self.platformData[platform]['CONNECTED'][targetPlatform])))):
                      header.write('`include "awb/provides/' + dep + '.bsh"\n')

          # Dangling Connections for this platform may have some definitions.  We insert them here.
          for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
              for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
                  header.write(dangling.code.definition)

          # everything down here should be code generation.  Eventually it should be split out.  
          # probably also need to instantiate stats in a different modules
          [egress_multiplexor_definition, egress_multiplexor_instantiation, egress_multiplexor_names] = self.generateEgressMultiplexor(platform) 
          [ingress_multiplexor_definition, ingress_multiplexor_instantiation, ingress_multiplexor_names] = self.generateIngressMultiplexor(platform)

          header.write(egress_multiplexor_definition + ingress_multiplexor_definition)

          # toss out the mapping functions first
          header.write('module [CONNECTED_MODULE] mkCommunicationModule#(VIRTUAL_PLATFORM vplat) (Empty);\n')

          header.write('String platformName <- getSynthesisBoundaryPlatform();\n')
          header.write('messageM("Instantiating Custom Router on " + platformName); \n')

          # Dangling Connections for this platform may have some declarations.  We insert them here.
          for targetPlatform in  self.platformData[platform]['CONNECTED'].keys():
              for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
                  header.write(dangling.code.declaration)
     
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
            stats = RouterStats( "router" + platform + "_" + targetPlatform)

            for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
              print "Laying down " + dangling.inverse_name + " of type " + dangling.sc_type + " on " + dangling.platform
              if(dangling.inverse_sc_type == 'Send' or dangling.inverse_sc_type == 'ChainRoutingSend'):
                  if(self.ENABLE_TYPE_COMPRESSION and dangling.type_structure.compressable):
                          header.write('\nCONNECTION_RECV#(' +  dangling.raw_type + ') recv_uncompressed_' + dangling.inverse_name + ' <- mkPhysicalConnectionRecv("' + dangling.inverse_name + '", tagged Invalid, False, "' + dangling.raw_type + '");\n')
                          #header.write('COMPRESSION_ENCODER#(' + dangling.raw_type + ',enc_type_'+ dangling.inverse_name +') recv_' + dangling.inverse_name + '_compressed <- mkCompressor();\n')
                          header.write('let recv_' + dangling.inverse_name + '_compressed <- mkCompressor();\n')
                          header.write('Put#('+ dangling.raw_type + ') put_' + dangling.inverse_name + '_compressed = toPut(recv_' + dangling.inverse_name + '_compressed);\n')
                          header.write('mkConnection(put_' + dangling.inverse_name + '_compressed, toGet(recv_uncompressed_' + dangling.inverse_name + '));\n')
                          header.write('let recv_' + dangling.inverse_name +' = toConnectionRecv(recv_' + dangling.inverse_name + '_compressed);\n\n')
                  else:
                      header.write('\nCONNECTION_RECV#(Bit#(PHYSICAL_CONNECTION_SIZE)) recv_' + dangling.inverse_name + ' <- mkPhysicalConnectionRecv("' + dangling.inverse_name + '", tagged Invalid, False, "' + dangling.raw_type + '");\n')
                  if(self.GENERATE_ROUTER_STATS):
                    stats.addCounter('blocked_' + dangling.inverse_name,
                                     'ROUTER_' + dangling.inverse_name + '_BLOCKED',
                                     dangling.inverse_name + ' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + 'cycles blocked')

                    stats.addCounter('sent_' + dangling.inverse_name,
                                     'ROUTER_' + dangling.inverse_name + '_SENT',
                                     dangling.inverse_name + ' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' cycles sent') 
             
                  recvs += 1 



              if(dangling.inverse_sc_type == 'Recv' or dangling.inverse_sc_type == 'ChainRoutingRecv'):
                  if(self.GENERATE_ROUTER_STATS > 1):
                    stats.addCounter('received_' + dangling.inverse_name,
                                     'ROUTER_' + dangling.inverse_name + '_RECEIVED',
                                     dangling.inverse_name + ' on ingress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' received cycles')

                  if(self.ENABLE_TYPE_COMPRESSION and dangling.type_structure.compressable):
                      header.write('PHYSICAL_SEND#(' +  dangling.raw_type + ') send_uncompressed_' + dangling.inverse_name + ' <- mkPhysicalConnectionSend("' + dangling.inverse_name + '", tagged Invalid, False, "' + dangling.raw_type + '", True);\n')
                      
                      header.write('let send_' + dangling.inverse_name + '_decompressed <- mkDecompressor();\n')
                      header.write('Get#('+ dangling.raw_type + ') get_' + dangling.inverse_name + '_decompressed = toGet(send_' + dangling.inverse_name + '_decompressed);\n')
                      header.write('mkConnection(get_' + dangling.inverse_name + '_decompressed, toPut(send_uncompressed_' + dangling.inverse_name + '));\n')
                      header.write('let send_' + dangling.inverse_name + ' <- mkPhysicalSend(send_' + dangling.inverse_name + '_decompressed);\n\n')
                  else:
                      header.write('PHYSICAL_SEND#(Bit#(PHYSICAL_CONNECTION_SIZE)) send_' + dangling.inverse_name + ' <- mkPhysicalConnectionSend("' + dangling.inverse_name + '", tagged Invalid, False, "' + dangling.raw_type + '", True);\n')
                  sends += 1

              # only create a chain when we see the source
              if(dangling.inverse_sc_type == 'ChainSink'):
                chains += 1 

                if(self.GENERATE_ROUTER_STATS > 1):
                  stats.addCounter('received_' + dangling.inverse_name,
                                   'ROUTER_' + platform + '_' + targetPlatform + '_' + dangling.inverse_name + '_RECEIVED',
                                   dangling.inverse_name + ' on ingress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) +' received cycles')

                # we must create a logical chain information
                chainsStr += 'let chain_' + dangling.inverse_name + ' = ' + \
                             'LOGICAL_CHAIN_INFO{logicalName: "' + dangling.inverse_name + '", ' + \
                             'logicalType: "' + dangling.raw_type + '", computePlatform: "' + platform + '", ' + \
                             'incoming: tpl_2(pack_chain_' + dangling.inverse_name + '), ' + \
                             'outgoing: unpack_chain_' + dangling.inverse_name + ', ' + \
                             'moduleNameIncoming: "router", moduleNameOutgoing: "router"' + \
                             '};\n'
                      
                chainsStr += 'registerChain(chain_' + dangling.inverse_name + ');\n'

              if(dangling.inverse_sc_type == 'ChainSrc'):

                if(self.GENERATE_ROUTER_STATS):
                  stats.addCounter('blocked_chain_' + dangling.inverse_name,
                                   'ROUTER_' + platform + '_' + targetPlatform + '_' + dangling.inverse_name + '_BLOCKED',
                                   dangling.inverse_name + ' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' cycles blocked')

                  stats.addCounter('sent_chain_' + dangling.inverse_name,
                                   'ROUTER_' + platform + '_' + targetPlatform + '_' + dangling.inverse_name + '_SENT',
                                   dangling.inverse_name + ' on egress' + str(dangling.via_idx) + ' link ' + str(dangling.via_link) + ' cycles sent')

            header.write(stats.genStats())

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
                if(dangling.bitwidth <= egressVias[dangling.via_idx].via_filler_width):            
                  packetizerType = 'Unmarshalled'

                header.write('// Via' + str(egressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth) + '\n')
                header.write('let pack_recv_' + dangling.inverse_name + ' <- mkPacketizeConnectionReceive' + packetizerType + '(\n')
                header.write('\t"' + dangling.inverse_name + '",\n')
                header.write('\trecv_' + dangling.inverse_name + ',\n')
                header.write('\t' + str(dangling.via_link) + ',\n')
                header.write('\twidth_recv_' + dangling.inverse_name + ',\n')
                if(self.GENERATE_ROUTER_STATS):
                  header.write('\t' + stats.incrCounter('blocked_' + dangling.inverse_name) + ',\n')
                  header.write('\t' + stats.incrCounter('sent_' + dangling.inverse_name) + ');\n\n')
                else:
                  header.write('\t?, ?);\n\n')


              if(dangling.inverse_sc_type == 'ChainSrc' ):
                header.write('// Via' + str(egressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth) + '\n')
	        #header.write('NumTypeParam#(PHYSICAL_CONNECTION_SIZE) width_chain_' + dangling.inverse_name +' = ?;\n')
	        header.write('NumTypeParam#('+ str(dangling.bitwidth) +') width_chain_' + dangling.inverse_name +' = ?;\n')
                egressVectors[dangling.via_idx][dangling.via_link] = 'tpl_1(pack_chain_' + dangling.inverse_name + ')'
                packetizerType = 'Marshalled'
                if(dangling.bitwidth <= egressVias[dangling.via_idx].via_filler_width):
                  packetizerType = 'Unmarshalled'

                print "Chain Sink " + dangling.inverse_name + ": Idx " + str(dangling.via_idx) + " Link: " + str(dangling.via_link) + " Length: " + str(len(egressVectors[dangling.via_idx]))  
                print "Choosing Incoming Marshalling with " + str(egressVias[dangling.via_idx].via_filler_width) +   " + " + str(egressVias[dangling.via_idx].via_width) + "(" +  str(egressVias[dangling.via_idx].via_width + egressVias[dangling.via_idx].via_filler_width) + ") < " + str(dangling.bitwidth) + " = " + packetizerType

                header.write('let pack_chain_' + dangling.inverse_name + ' <- mkPacketizeIncomingChain' + packetizerType + '(\n')
                header.write('\t"' + dangling.inverse_name + '",\n')
                header.write('\t' + str(dangling.via_link) + ',\n')
                header.write('\twidth_chain_' + dangling.inverse_name + ',\n')
                if(self.GENERATE_ROUTER_STATS):
                  header.write('\t' + stats.incrCounter('blocked_chain_' + dangling.inverse_name) + ',\n')
                  header.write('\t' + stats.incrCounter('sent_chain_' + dangling.inverse_name) + ');\n\n')
                else:
                  header.write('\t?, ?);\n\n')

          
            # we now need switches for each via.  Need modular arithmetic here to make sure that everyone has a link.  
            # for now we will assume that flow control is twinned - that is the egress 2 uses ingress 2 for its flow control
            # this might well need to change as we introduce assymetry x_X
            # we actually should be allocating the feedback channel as part of the analysis phase, but that can happen later.             
            if (self.GENERATE_ROUTER_DEBUG):
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

                # If there are few enough incoming ports then router arbitration
                # can be done in a single cycle.  Otherwise, use multiple cycles.
                single_cycle_arb = 'True'
                if (egressVias[via_idx].via_links > 10):
                  single_cycle_arb = 'False'

                header.write('EGRESS_SWITCH#(' + str(egressVias[via_idx].via_links) + ') ' + egressVias[via_idx].via_switch + '<- mkEgressSwitch( links_' + egressVias[via_idx].via_switch + ', ' + ingressVias[egressVias[via_idx].via_outgoing_flowcontrol_via].via_switch + '.ingressPorts[' + str(egressVias[via_idx].via_outgoing_flowcontrol_link) +'], compose(' + egress_multiplexor_names[targetPlatform] + '.' + egressVias[via_idx].via_method + ',pack), "' + egressVias[via_idx].via_switch + '", ' + single_cycle_arb + ');\n')

                if(self.GENERATE_ROUTER_DEBUG):   
                  header.write('egress_via_dbg_list <- addDebugScanField(egress_via_dbg_list, "' + egressVias[via_idx].via_switch + ' buffer status", ' + egressVias[via_idx].via_switch + '.bufferStatus);\n')
                  header.write('egress_via_dbg_list <- addDebugScanField(egress_via_dbg_list, "' + egressVias[via_idx].via_switch + ' fifo status", ' + egressVias[via_idx].via_switch + '.fifoStatus);\n')

            if(self.GENERATE_ROUTER_DEBUG):   
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
                if(dangling.bitwidth <= ingressVias[dangling.via_idx].via_width + ingressVias[dangling.via_idx].via_filler_width):            
                  packetizerType = 'PartialMarshalled'
                if(dangling.bitwidth <= ingressVias[dangling.via_idx].via_filler_width):
                  packetizerType = 'Unmarshalled'

                header.write('// Via' + str(ingressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth) + '\n')
                header.write('Empty unpack_send_' + dangling.inverse_name + ' <- mkPacketizeConnectionSend' + packetizerType  + '(\n')
                header.write('\t"' + dangling.inverse_name + '",\n')
                header.write('\tsend_' + dangling.inverse_name + ',\n')
                header.write('\t' + ingressVias[dangling.via_idx].via_switch + '.ingressPorts[' + str(dangling.via_link) + '],\n')
                header.write('\t' + str(dangling.via_link) + ',\n')
                header.write('\twidth_send_' + dangling.inverse_name + ',\n')
                if(self.GENERATE_ROUTER_STATS > 1):
                  header.write('\t' + stats.incrCounter('received_' + dangling.inverse_name) + ');\n\n')
                else:
                  header.write('\t?);\n\n')


              if(dangling.inverse_sc_type == 'ChainSink' ):
                print "My type: " + dangling.sc_type
                print "My raw type: " + dangling.raw_type
                print "My name: " + dangling.name
	        header.write('NumTypeParam#('+ str(dangling.bitwidth) +') width_sink_' + dangling.inverse_name +' = ?;\n')
                packetizerType = 'Marshalled'
                header.write('// Via' + str(ingressVias[dangling.via_idx].via_width) + ' mine:' + str(dangling.bitwidth) + '\n')
                if(dangling.bitwidth <= (ingressVias[dangling.via_idx].via_width + ingressVias[dangling.via_idx].via_filler_width)): 
                  print "Chain check PartialMarshalled passed"
                  packetizerType = 'PartialMarshalled'
                if(dangling.bitwidth <= ingressVias[dangling.via_idx].via_filler_width):            
                  packetizerType = 'Unmarshalled'

                print "Choosing Marshalling with " + str(ingressVias[dangling.via_idx].via_filler_width) +   " + " + str(ingressVias[dangling.via_idx].via_width) + "(" +  str(ingressVias[dangling.via_idx].via_width + ingressVias[dangling.via_idx].via_filler_width) + ") < " + str(dangling.bitwidth) + " = " + packetizerType

                header.write('PHYSICAL_CHAIN_OUT unpack_chain_' + dangling.inverse_name + ' <- mkPacketizeOutgoingChain' + packetizerType + '(\n')
                header.write('\t"' + dangling.inverse_name + '",\n')
                header.write('\t' + ingressVias[dangling.via_idx].via_switch + '.ingressPorts[' + str(dangling.via_link) + '],\n')
                header.write('\t' + str(dangling.via_link) + ',\n')
                header.write('\twidth_sink_' + dangling.inverse_name + ',\n')
                if(self.GENERATE_ROUTER_STATS > 1):
                  header.write('\t' + stats.incrCounter('received_' + dangling.inverse_name) + ');\n\n')
                else:
                  header.write('\t?);\n\n')


          # Add in chain insertion code 
          header.write(chainsStr + '\n')

          header.write('endmodule\n')
          header.close();

  def parseDangling(self, platformName):
      logfile = open(self.platformData[platformName]['LOG'],'r')
      parser = TypeParser()

      compressInstanceTypes = {}
      #we will build up a list of compressors by examining all bo
      if(self.ENABLE_TYPE_COMPRESSION):
          for module in self.moduleList.moduleList: 
              print "Examining " + module.name
              command = 'bluetcl ./hw/model/dumpStructures.tcl ' + module.name + ' Compress -p ' + self.platformData[platformName]['BLUETCL']
              print command + "\n"
                          

              tclIn = os.popen(command)
              typeclassRaw = tclIn.read()
              compressable = False
              print "TypeclassRaw:   " + typeclassRaw + "\n"
              typeclass = "None"
              try:
                  typeclass = parser.parseType(typeclassRaw) 
                  for instance in typeclass.instances:
                      if(not (str(instance) in compressInstanceTypes)):
                          print "Adding instance: " + str(instance)

                          compressInstanceTypes[str(instance)] = instance
                                  
              except TypeError:
                  #We need something here even though we don't handle the exception
                  print "No compress typeclass found for " + str(module.name)



      print "Processing: " + self.platformData[platformName]['LOG']
      for line in logfile:
          # also pull out link widths
          if(re.match('.*SizeOfVia:.*',line)):
            match = re.search(r'.*SizeOfVia:(\w+):(\d+)',line)
            if(match):
              self.platformData[platformName]['WIDTHS'][match.group(1)] = int(match.group(2))
          if(re.match("Compilation message: .*: Dangling",line)):
              match = re.search(r'.*Dangling (\w+) {(.*)} \[(\d+)\]:(\w+):(\w+):(\w+):(\d+):(\w+):(\w+)', line)
              if(match):
            #python groups begin at index 1  
                  print 'found connection: ' + line
                  if(match.group(1) == "Chain"):
                    print "Got chain " + match.group(3)
                    sc_type = "ChainSrc"
                  else:
                    sc_type = match.group(1)

                  type = LinkType("None",False,[])
                  if(self.ENABLE_TYPE_COMPRESSION):
                      # construct a tagged union structure for this type!                  
                      baseType =  parser.parseType(match.group(2))
                      typeRefs = flatten(baseType.getTypeRefs())


                      def resolveType(typeRef):
                          type = typeRef.name
                          print "Adding ref: " + str(type)
                          # Anonymous structs may have dollar signs in them.  
                          type.replace('$','\$')

                          command = 'bluetcl ./hw/model/dumpStructures.tcl ' + typeRef.namespace + ' ' + type  +  ' -p ' + self.platformData[platformName]['BLUETCL']
                          print command + "\n"
                      
                          tclIn = os.popen(command)
                          raw = tclIn.read()
                          print "Parsing: " + raw
                          refType = parser.parseType(raw)
                          #check in the type ref's bo or in the link's bo or in the top level bo for a 
                          #compressable definition
                          
                          #Did we actually get a non-reference type?
                          if(isinstance(refType, TypeRef)):
                              print "Resolve type recurses\n"  
                              return resolveType(refType)
                          return refType

                      def getDependencies(type):
                          print "Deps: " + str(type.getTypeRefs())
                          print "Deps: " + str(flatten(type.getTypeRefs()))
                          return map(lambda ref: ref.namespace, flatten(type.getTypeRefs())) 

                      # this function looks in a bo file for a
                      # definition of the compressable type class.  If
                      # it finds such a definition 
                      def checkCompressable(type):
                          print "checkCompressable " + str(type)
                          compressable = False
                          instanceDeps = []
                          # Let's look for the Compress typeclass
                          for instance in compressInstanceTypes.values():
                              print "instance: " + str(instance)
                              instanceType = instance.params[0]
                              
                              if(isinstance(instance.params[0],TypeRef)):
                                  #need to dereference types
                                 
                                  if(str(instance.params[0]) in self.platformData[platformName]['TYPES']):
                                      instanceType = self.platformData[platformName]['TYPES'][str(instance.params[0])].type
                                      instanceDeps = self.platformData[platformName]['TYPES'][str(instance.params[0])].dependencies 
                                  else:
                                      instanceType = resolveType(instance.params[0])
                                      # We found a new type.  Memoize it!
                                      print "New instanceType " + str(instanceType)
                                      print "Deps: " + str(getDependencies(instanceType)) 
                                      instanceDeps =  getDependencies(instanceType) + [instance.params[0].namespace]
                                      self.platformData[platformName]['TYPES'][str(instanceType)] = LinkType(instanceType, True, instanceDeps)
                              print "\n\nStarting comparison:  " + str(instanceType)
                              ## == for types is a unification
                              if(instanceType == type):
                                  compressable = True
                                  print "Found a compressable type  " + str(instanceType)
                                  break
                              print "Type comparison failed"
                          if(not compressable):
                              print "Uncompressable type: " + str(type)     
      
                          return [compressable,instanceDeps] 
                      #end checkCompressable

                      
                      #Let's resolve all the type references for fun and profit
                      for ref in typeRefs:
                          print "Handling ref: " + str(ref)
                          if(str(ref) in self.platformData[platformName]['TYPES']):
                              continue
                         
                          print "Adding: " + str(ref)

                          refType = resolveType(ref)
                          [compressable, compressionDeps] = checkCompressable(refType)
                          deps = getDependencies(baseType) + getDependencies(ref)
                          if(compressable):
                              deps += compressionDeps
                          self.platformData[platformName]['TYPES'][str(ref)] = LinkType(refType,compressable,deps)
                         
                          print "parse: " + str(self.platformData[platformName]['TYPES'][str(ref)])
  
                      #Was the original type a reference? If it was, then our loop recovered its type.
                      if(isinstance(baseType,TypeRef)):
                          type = self.platformData[platformName]['TYPES'][str(baseType)] 
                      
                      #If we got no type refs, then this is a base
                      #class. We already parsed it but we may need to
                      #do some level of type binding
                      if(len(list(typeRefs)) == 0):
                          print "Handling baseType: " + str(baseType)

                          if(str(baseType) in self.platformData[platformName]['TYPES']):
                              type = self.platformData[platformName]['TYPES'][str(baseType)] 
                          else:
                              [compressable, compressionDeps] = checkCompressable(baseType)
                              deps = getDependencies(baseType)
                              if(compressable):
                                  deps += compressionDeps
                              type = LinkType(baseType, compressable, deps)
                              self.platformData[platformName]['TYPES'][str(baseType)] = type



                  parentConnection = DanglingConnection(sc_type, 
                                                        match.group(2),
                                                        match.group(3),
                                                        match.group(4),      
                                                        match.group(5),
                                                        match.group(6),
                                                        match.group(7),
                                                        match.group(8),
                                                        match.group(9),
                                                        type)
                           
                  # can we automatically compress?
                  if(isinstance(type.type,TaggedUnion) and self.ENABLE_TYPE_COMPRESSION and (sc_type == 'Recv' or sc_type == 'Send')):
                      compressor = []
                      if(sc_type == 'Recv'):
                          compressor = TaggedUnionCompressor(parentConnection)
                      else:
                          compressor = TaggedUnionDecompressor(parentConnection)
                      
                      # The compressor generates a bunch of
                      # connections.  Add them now. The parent
                      # connection is effectively dead at this point,
                      # as it will be subsumed in the compression code
                      self.platformData[platformName]['DANGLING'] += compressor.channels

                  else: # can't do anything with this link
                      self.platformData[platformName]['DANGLING'] += [parentConnection]

                  if(match.group(1) == "Chain"):
                    self.platformData[platformName]['DANGLING'] += [DanglingConnection("ChainSink", 
                                                                                match.group(2),
                                                                                match.group(3),
                                                                                match.group(4),
                                                                                match.group(5),
                                                                                match.group(6),
                                                                                match.group(7),
                                                                                match.group(8),
                                                                                match.group(9),
                                                                                type)]

              else:
                  print "Malformed connection message: " + line
                  sys.exit(-1)
