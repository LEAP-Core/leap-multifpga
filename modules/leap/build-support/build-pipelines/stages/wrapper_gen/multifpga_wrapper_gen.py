import os
import sys
import re
import SCons.Script
from model import  *
from fpga_environment_parser import *
from fpgamap_parser import *
from config import *
 

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

    envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENVS')
    if(len(envFile) != 1):
      print "Found more than one environment file: " + str(envFile) + ", exiting\n"
    self.environment = parseFPGAEnvironment(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0])
    print "environment keys: " + str(self.environment.getPlatformNames)

    topo = moduleList.topologicalOrderSynth()
    # we probably want reverse topological ordering... ???? Really?

    for module in topo:
      wrapperPath = moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + module.buildPath + '/' + module.name + "_Wrapper.bsv"
      logPath = moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + module.buildPath + '/' + module.name + "_Log.bsv"
      conSizePath =  moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + module.buildPath + '/' + module.name + "_Wrapper_con_size.bsh"
      ignorePath = moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + module.buildPath + '/.ignore'

      if(getBuildPipelineDebug(moduleList) != 0):
        print "Wrapper path is " + wrapperPath
      wrapper_bsv = open(wrapperPath, 'w')
      log_bsv = open(logPath, 'w')

      ignore_bsv = open(ignorePath, 'w')
      ignore_bsv.write("// Generatef by multifpga_wrapper_gen.py\n")

      # Connection size doesn't appear on the first dependence pass, since it
      # doesn't exist until after the first build.  Finding it later results in
      # build dependence changes and rebuilding.  Ignore it, since the file will
      # change only when some other file changes.
      ignore_bsv.write(conSizePath);

      # Generate a dummy connection size file to avoid errors during dependence
      # analysis.
      if not os.path.exists(conSizePath):
        os.system('leap-connect --dummy --dynsize ' + module.name + ' ' + conSizePath)

      ignore_bsv.close();

      wrapper_bsv.write('import HList::*;\n')
      wrapper_bsv.write('import ModuleContext::*;\n')
      log_bsv.write('import HList::*;\n')
      log_bsv.write('import ModuleContext::*;\n')
      # the top module is handled specially
      if(module.name == moduleList.topModule.name):

        for wrapper in [wrapper_bsv, log_bsv]:      
          wrapper.write('// These are well-known/required leap modules\n')
          wrapper.write('// import non-synthesis public files\n')
          wrapper.write('`include "' + module.name + '.bsv"\n')
          
          wrapper.write('// import non-synthesis private files\n')

          wrapper.write('// Get defintion of TOP_LEVEL_WIRES\n')
          wrapper.write('import physical_platform::*;\n')

          wrapper.write('(* synthesize *)\n')
          wrapper.write('(* no_default_clock, no_default_reset *)\n')

        wrapper_bsv.write('module mk_model_Wrapper (TOP_LEVEL_WIRES);\n')
        log_bsv.write('module mk_model_Log (TOP_LEVEL_WIRES);\n')

        for wrapper in [wrapper_bsv, log_bsv]:      
          wrapper.write('    // instantiate own module\n')
          wrapper.write('     let m <- mkModel();\n')
          wrapper.write('    return m;\n')

          wrapper.write('endmodule\n')

      else:

        for wrapper in [wrapper_bsv, log_bsv]:      
          wrapper.write('// These are well-known/required leap modules\n')
          wrapper.write('`include "awb/provides/soft_connections.bsh"\n')
          wrapper.write('`include "awb/provides/soft_services_lib.bsh"\n')
          wrapper.write('`include "awb/provides/soft_services.bsh"\n')
          wrapper.write('`include "awb/provides/soft_services_deps.bsh"\n')
          wrapper.write('`include "awb/provides/soft_connections_debug.bsh"\n')
          wrapper.write('// import non-synthesis public files\n')
          wrapper.write('`include "' + module.name + '_compile.bsv"\n')
          wrapper.write('\n\n')

        log_bsv.write('// First pass to see how large the vectors should be\n')
        log_bsv.write('`define CON_RECV_' + module.name + ' 100\n')
        log_bsv.write('`define CON_SEND_' + module.name + ' 100\n')
        log_bsv.write('`define CON_RECV_MULTI_' + module.name + ' 50\n')
        log_bsv.write('`define CON_SEND_MULTI_' + module.name + ' 50\n')
        log_bsv.write('`define CHAINS_' + module.name + ' 50\n')
        wrapper_bsv.write('// Real build pass.  Include file built dynamically.\n')
        wrapper_bsv.write('`include "' + module.name + '_Wrapper_con_size.bsh"\n')

        for wrapper in [wrapper_bsv, log_bsv]:      
          wrapper.write('(* synthesize *)\n')
          wrapper.write('module mk_' + module.name + '_Wrapper (SOFT_SERVICES_SYNTHESIS_BOUNDARY#(`CON_RECV_' + module.name + ', `CON_SEND_' + module.name + ', `CON_RECV_MULTI_' + module.name + ', `CON_SEND_MULTI_' + module.name +', `CHAINS_' + module.name +'));\n')
          wrapper.write('  \n')
          # we need to insert the fpga platform here
          # get my parameters 

          wrapper.write('    // instantiate own module\n')
          wrapper.write('    let int_ctx0 <- initializeServiceContext();\n')
          wrapper.write('    match {.int_ctx1, .int_name1} <- runWithContext(int_ctx0, putSynthesisBoundaryID(' + str(module.synthBoundaryUID)  + '));\n');
          wrapper.write('    match {.int_ctx2, .int_name2} <- runWithContext(int_ctx1, putSynthesisBoundaryPlatform("' + self.mapping.getSynthesisBoundaryPlatform(module.name) + '"));\n')
          wrapper.write('    match {.int_ctx3, .int_name3} <- runWithContext(int_ctx2, putSynthesisBoundaryPlatformID(' + str(self.environment.getSynthesisBoundaryPlatformID(self.mapping.getSynthesisBoundaryPlatform(module.name))) + '));\n')
          wrapper.write('    // By convention, global string ID 0 (the first string) is the module name\n');
          wrapper.write('    match {.int_ctx4, .int_name4} <- runWithContext(int_ctx3, getGlobalStringUID("' + self.mapping.getSynthesisBoundaryPlatform(module.name) + ':' + module.name + '"));\n');
          wrapper.write('    match {.int_ctx5, .int_name5} <- runWithContext(int_ctx4, ' + module.synthBoundaryModule + ');\n')
          wrapper.write('    match {.final_ctx, .m_final}  <- runWithContext(int_ctx5, mkSoftConnectionDebugInfo);\n')
          wrapper.write('    let service_ifc <- exposeServiceContext(final_ctx);\n')
          wrapper.write('    interface services = service_ifc;\n')
          wrapper.write('    interface device = m_final;\n')
          wrapper.write('endmodule\n')
    
      wrapper_bsv.close()
      log_bsv.close()
