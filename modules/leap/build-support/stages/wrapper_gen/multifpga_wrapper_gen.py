import os
import sys
import re
import SCons.Script
from model import  *
from config import *
from fpgamap_parser import *


#this might be better implemented as a 'Node' in scons, but 
#I want to get something working before exploring that path
# This is going to recursively build all the bsvs
class WrapperGen():

  def __init__(self, moduleList):

    envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENV_MAPPINGS')
    if(len(envFile) != 1):
      print "Found more than one mapping file: " + str(envFile) + ", exiting\n"
    self.mapping = parseFPGAMap(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0])
    print "mapping keys: " + str(self.mapping.getPlatformNames)

    topo = moduleList.topologicalOrderSynth()
    # we probably want reverse topological ordering...

    for module in topo:
      wrapperPath = moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + module.buildPath + '/' + module.name + "_Wrapper.bsv"
      print "Wrapper path is " + wrapperPath + '\n'
      wrapper_bsv = open(wrapperPath, 'w')

      wrapper_bsv.write('import HList::*;\n')
      wrapper_bsv.write('import ModuleContext::*;\n')
      # the top module is handled specially
      if(module.name == moduleList.topModule.name):

        wrapper_bsv.write('// These are well-known/required leap modules\n')
        wrapper_bsv.write('// import non-synthesis public files\n')
        wrapper_bsv.write('`include "project-hybrid-main.bsv"\n')

        wrapper_bsv.write('// import non-synthesis private files\n')


        wrapper_bsv.write('// Get defintion of TOP_LEVEL_WIRES\n')
        wrapper_bsv.write('import physical_platform::*;\n')

        wrapper_bsv.write('(* synthesize *)\n')
        wrapper_bsv.write('(* no_default_clock, no_default_reset *)\n')
        wrapper_bsv.write('module mk_model_Wrapper (TOP_LEVEL_WIRES);\n')

        wrapper_bsv.write('    // instantiate own module\n')
        wrapper_bsv.write('     let m <- mkModel();\n')

        wrapper_bsv.write('    return m;\n')

        wrapper_bsv.write('endmodule\n')

      else:
      
        wrapper_bsv.write('// These are well-known/required leap modules\n')
        #      wrapper_bsv.write('`include "asim/provides/smart_synth_boundaries.bsh"\n')
        #      wrapper_bsv.write('`include "asim/provides/soft_connections_common.bsh"\n')
        wrapper_bsv.write('`include "asim/provides/soft_connections.bsh"\n')
        wrapper_bsv.write('`include "asim/provides/soft_services_lib.bsh"\n')
        wrapper_bsv.write('`include "asim/provides/soft_services.bsh"\n')
        wrapper_bsv.write('`include "asim/provides/soft_services_deps.bsh"\n')
        wrapper_bsv.write('// import non-synthesis public files\n')
        wrapper_bsv.write('`include "' + module.name + '.bsv"\n')
        wrapper_bsv.write('\n\n')
        wrapper_bsv.write('// import non-synthesis private files\n')
        wrapper_bsv.write('\n\n')
        wrapper_bsv.write('`ifndef CONNECTION_SIZES_KNOWN\n')
        wrapper_bsv.write('\n\n')
        wrapper_bsv.write('// First pass to see how large the vectors should be\n')
        wrapper_bsv.write('`define CON_RECV_' + module.name + ' 100\n')
        wrapper_bsv.write('`define CON_SEND_' + module.name + ' 100\n')
        wrapper_bsv.write('`define CON_RECV_MULTI_' + module.name + ' 50\n')
        wrapper_bsv.write('`define CON_SEND_MULTI_' + module.name + ' 50\n')
        wrapper_bsv.write('`define CHAINS_' + module.name + ' 50\n')
        wrapper_bsv.write('`else\n')
        wrapper_bsv.write('// Real build pass.  Include file built dynamically.\n')
        wrapper_bsv.write('`include "' + module.name + '_Wrapper_con_size.bsh"\n')
        wrapper_bsv.write('`endif\n')

        wrapper_bsv.write('(* synthesize *)\n')
        wrapper_bsv.write('module mk_' + module.name + '_Wrapper (SOFT_SERVICES_SYNTHESIS_BOUNDARY#(`CON_RECV_' + module.name + ', `CON_SEND_' + module.name + ', `CON_RECV_MULTI_' + module.name + ', `CON_SEND_MULTI_' + module.name +', `CHAINS_' + module.name +'));\n')
        wrapper_bsv.write('  \n')
        # we need to insert the fpga platform here
        # get my parameters 

        wrapper_bsv.write('    // instantiate own module\n')
        wrapper_bsv.write('    let ctx <- initializeServiceContext();\n')
        wrapper_bsv.write('    match {.intermediate_ctx, .m_name} <- runWithContext(ctx,putSynthesisBoundaryPlatform("' + self.mapping.getSynthesisBoundaryPlatform(module.name) + '"));\n');          
        wrapper_bsv.write('    match {.final_ctx, .m_final} <- runWithContext(intermediate_ctx, ' + module.synthBoundaryModule + ');\n')
        wrapper_bsv.write('    let service_ifc <- exposeServiceContext(final_ctx);\n')
        wrapper_bsv.write('    interface services = service_ifc;\n')
        wrapper_bsv.write('    interface device = m_final;\n')
        wrapper_bsv.write('endmodule\n')
    

      wrapper_bsv.close()
