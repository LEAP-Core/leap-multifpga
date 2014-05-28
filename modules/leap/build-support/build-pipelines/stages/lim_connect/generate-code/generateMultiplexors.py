# python libraries
import re
import sys

# AWB dependencies
from model import  *
from li_module import *


# local files
from routerStats import *


def generateEgressMultiplexorMultiple(platform, targetPlatform, packPulseWires, moduleList, environmentGraph, platformGraph): 

    GENERATE_ROUTER_DEBUG = moduleList.getAWBParam('lim_graph_generator', 'GENERATE_ROUTER_DEBUG')
    GENERATE_ROUTER_STATS = moduleList.getAWBParam('lim_graph_generator', 'GENERATE_ROUTER_STATS')

    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}

    multiplexor_stats = RouterStats("egressMultiplexor")
    egressVias = environmentGraph.platforms[platform].getEgress(targetPlatform).logicalVias
    hopFromTarget = environmentGraph.transitTablesIncoming[platform][targetPlatform]
    egressMethod = hopFromTarget.replace(".","_").replace("[","_").replace("]","_") + '_write'
    egressViaWidth = environmentGraph.platforms[platform].getEgress(targetPlatform).width

    interfaceName = 'EgressMultiplexor_' + platform + '_to_' + targetPlatform
    moduleName = 'egressMultiplexor_' + platform + '_to_' + targetPlatform
    moduleAggregateTypeName = interfaceName +'Aggregate'

    multiplexor_definition += 'typedef struct { \n'
    for via in egressVias:
        if(packPulseWires):
            multiplexor_definition += '\nBit#(1)  '  + via.via_method + '_pulse;\n'   
        multiplexor_definition += '\nBit#(' + str(via.via_width) + ')  '  + via.via_method + '_data;\n'   

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
        multiplexor_definition += '\tlet ' + via.via_method + '_wire <- mkDWire(0);\n' 
        multiplexor_definition += '\tlet ' + via.via_method + '_pulse <- mkPulseWire();\n' 
        sum_string.append('zeroExtend(pack(' + via.via_method + '_pulse))')

        if(GENERATE_ROUTER_STATS):
            multiplexor_stats.addCounter('enqueued_' + moduleName + '_' + via.via_method,
                                         'ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED',
                                         via.via_method +' cycles enqueued')
 
    multiplexor_definition += '\tBit#(TLog#(' + str(1 + len(egressVias)) +')) totalEnqs = ' + " + ".join(sum_string) + ";\n"
          
    for enqs in range(1 + len(egressVias)):
        if(GENERATE_ROUTER_STATS):
            multiplexor_stats.addCounter('enqueued_' + moduleName + '_' + str(enqs),
                                         'ROUTER_' + moduleName + '_' + str(enqs) + '_ENQUEUED',
                                         via.via_method +' cycles that lanes enqueued')

    #stats for the merger
    if(GENERATE_ROUTER_STATS):
        multiplexor_stats.addCounter('merged_' + moduleName,
                                     'ROUTER_' + moduleName + '_MERGED',
                                     moduleName + ' cycles enqueued')

    multiplexor_definition += multiplexor_stats.genStats()
    multiplexor_definition += '\n\trule mergeData(\n'

    # TODO: replace with something more pythonic.
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
        multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('merged_' + moduleName) + ';\n'

    multiplexor_definition += '\t\twrite(zeroExtendNP(pack(' + moduleAggregateTypeName + '{\n'
    structDef = []
    for via in egressVias:
        if(packPulseWires):
            structDef.append('\t\t\t' + via.via_method + '_pulse:pack(' + via.via_method + '_pulse)\n')
        structDef.append('\t\t\t' + via.via_method + '_data:' + via.via_method + '_wire\n')

    multiplexor_definition += ",".join(structDef) 
    multiplexor_definition += '\t\t})));\n'
    multiplexor_definition += '\tendrule\n\n'

    for enqs in range(1 + len(egressVias)):

        if(GENERATE_ROUTER_STATS):

            multiplexor_definition += '\n\trule countMerges' + str(enqs) + '(totalEnqs == ' + str(enqs) + ');\n'
            multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('enqueued_' + moduleName + '_' + str(enqs)) + ';\n'
            multiplexor_definition += '\tendrule\n\n'

    for via in egressVias:
        multiplexor_definition += '\tmethod Action ' + via.via_method + '(Bit#(' + str(via.via_width)  + ') data) if(write_ready);\n'
        #multiplexor_definition += '    $display("' + via.via_method + '_wire fires");\n'
        multiplexor_definition += '\t\t' + via.via_method + '_wire <= data;\n'
        multiplexor_definition += '\t\t' + via.via_method + '_pulse.send;\n'

        if(GENERATE_ROUTER_STATS):
            multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('enqueued_' + moduleName + '_' + via.via_method) + ';\n'

        multiplexor_definition += '\tendmethod\n\n'

    multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]



def generateEgressMultiplexor(platform, targetPlatform, moduleList, environmentGraph, platformGraph): 
      egressVias = environmentGraph.platforms[platform].getEgress(targetPlatform).logicalVias

      if(len(egressVias) == 1):
          return generateEgressMultiplexorMultiple(platform, targetPlatform, False, moduleList, environmentGraph, platformGraph)
      else:
          return generateEgressMultiplexorMultiple(platform, targetPlatform, True, moduleList, environmentGraph, platformGraph)
    


def generateIngressMultiplexorMultiple(platform, targetPlatform, packPulseWires, moduleList, environmentGraph, platformGraph):

    GENERATE_ROUTER_DEBUG = moduleList.getAWBParam('lim_graph_generator', 'GENERATE_ROUTER_DEBUG')
    GENERATE_ROUTER_STATS = moduleList.getAWBParam('lim_graph_generator', 'GENERATE_ROUTER_STATS')

    multiplexor_definition = ''
    multiplexor_instantiation = ''
    multiplexor_names = {}

    multiplexor_stats = RouterStats("ingressMultiplexor")

    ingressVias = environmentGraph.platforms[platform].getIngress(targetPlatform).logicalVias
    hopToTarget = environmentGraph.transitTablesOutgoing[platform][targetPlatform]
    ingressMethod = hopToTarget.replace(".","_").replace("[","_").replace("]","_") + '_read'
    ingressViaWidth = environmentGraph.platforms[platform].getIngress(targetPlatform).width

    interfaceName = 'IngressMultiplexor_' + platform + '_to_' + targetPlatform
    moduleName = 'ingressMultiplexor_' + platform + '_to_' + targetPlatform
    moduleAggregateTypeName = interfaceName +'Aggregate'

    multiplexor_definition += '\n\ntypedef struct { \n'
    for via in ingressVias:
        if(packPulseWires):
            multiplexor_definition += '\tMaybe#(Bit#(' + str(via.via_width) + '))  '  + via.via_method + '_data;\n'   
        else:
            multiplexor_definition += '\tBit#(' + str(via.via_width) + ')  '  + via.via_method + '_data;\n'   

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
            multiplexor_stats.addCounter('dequeued_' + via.via_method,
                                         'ROUTER_' + moduleName + '_' + via.via_method + '_DEQUEUED',
                                         via.via_method + ' cycles dequeued')

    if(GENERATE_ROUTER_DEBUG):   
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
        if(packPulseWires):
            multiplexor_definition += '\trule deq_' + via.via_method + '(' + via.via_method + '_fifo.first() matches tagged Invalid);\n\n'

            multiplexor_definition += '\t\t' + via.via_method + '_fifo.deq();\n\n'
            multiplexor_definition += '\tendrule\n\n'

    for via in ingressVias:
        if(packPulseWires):
            multiplexor_definition += '\tmethod Bit#(' + str(via.via_width) + ') ' + via.via_method + '_first() if (' + via.via_method + '_fifo.first() matches tagged Valid .data );\n\n'
            multiplexor_definition += '\t\treturn data;\n\n'
        else:
            multiplexor_definition += '\tmethod Bit#(' + str(via.via_width) + ') ' + via.via_method + '_first();\n\n'
            multiplexor_definition += '\t\treturn ' + via.via_method + '_fifo.first();\n'
        multiplexor_definition += '\tendmethod\n\n'

        if(packPulseWires):
            multiplexor_definition += '\tmethod Action ' + via.via_method + '_deq() if (' + via.via_method + '_fifo.first() matches tagged Valid .data );\n\n'
        else:
            multiplexor_definition += '\tmethod Action ' + via.via_method + '_deq();\n\n'

        if(GENERATE_ROUTER_STATS):
            multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('dequeued_' + via.via_method) + ';\n'

        multiplexor_definition += '\t\t' + via.via_method + '_fifo.deq();\n'
        multiplexor_definition += '\tendmethod\n\n'

    multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]


def generateIngressMultiplexor(platform, targetPlatform, moduleList, environmentGraph, platformGraph): 
    ingressVias = environmentGraph.platforms[platform].getIngress(targetPlatform).logicalVias

    if(len(ingressVias) == 1):
        return generateIngressMultiplexorMultiple(platform, targetPlatform, False, moduleList, environmentGraph, platformGraph)
    else:
        return generateIngressMultiplexorMultiple(platform, targetPlatform, True, moduleList, environmentGraph, platformGraph)


###
###  WARNING: This code is deprecated.  It has been subsumed by the above routines.
###  WARNING: We'll retain it, but it should be deleted at some point. 
###

def generateEgressMultiplexorParSerial(platform): 
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
        if(GENERATE_ROUTER_STATS):
          multiplexor_stats.addCounter('enqueued_' + moduleName + '_' + via.via_method,
                                       'ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED',
                                       via.via_method + ' cycles enqueued')

      if(GENERATE_ROUTER_STATS):
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


        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('enqueued_'+ moduleName + '_' + via.via_method) + ';\n'

        multiplexor_definition += '  endmethod\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]


def generateEgressMultiplexorSerial(platform): 
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
        if(GENERATE_ROUTER_STATS):
          multiplexor_stats.addCounter('enqueued_' + moduleName + '_' + via.via_method,
                                       'ROUTER_' + moduleName + '_' + via.via_method + '_ENQUEUED',
                                       via.via_method + ' cycles enqueued')

      if(GENERATE_ROUTER_STATS):
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
        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('enqueued_' + moduleName + '_' + via.via_method) + ';\n'
        multiplexor_definition += '  endmethod\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]
            




def generateIngressMultiplexorSerial(platform):
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
        if(GENERATE_ROUTER_STATS):
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
        if(GENERATE_ROUTER_STATS):
          multiplexor_definition += '\t\t' + multiplexor_stats.incrCounter('dequeued_' + via.via_method) + ';\n'
        multiplexor_definition += '    ' + via.via_method + '_fifo.deq();\n'
        multiplexor_definition += '    return ' + via.via_method + '_fifo.first();\n'
        multiplexor_definition += '  endmethod\n'

      multiplexor_definition += 'endmodule\n\n'
    return [multiplexor_definition, multiplexor_instantiation, multiplexor_names]

