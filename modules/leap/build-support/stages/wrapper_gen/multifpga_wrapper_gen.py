import os
import sys
import re
import SCons.Script
from model import  *
from config import *
import ply.yacc as yacc
import ply.lex as lex
from fpgamaplex import *
from fpgamapparse import *

#this might be better implemented as a 'Node' in scons, but 
#I want to get something working before exploring that path
# This is going to recursively build all the bsvs
class WrapperGen():

  def __init__(self, moduleList):

    # build the compiler
    lex.lex()
    yacc.yacc()

    envFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENV_MAPPINGS')
    if(len(envFile) != 1):
      print "Found more than one mapping file: " + str(envFile) + ", exiting\n"
    mappingDescription = (open(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0], 'r')).read()
    #print "opened env file: " + moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + envFile[0] + " -> " + environmentDescription
    self.mapping = yacc.parse(mappingDescription)
    # at some point we should square the mapping and environment files to make sure that no extra/
    print "mapping keys: " + str(environment.getPlatformNames)

    topo = moduleList.topologicalOrderSynth()
    # we probably want reverse topological ordering...
    for module in topo:
      wrapperPath = module.buildPath + '/' + module.wrapperName()
      wrapper_bsv = open(wrapperPath, 'w')
      wrapper_bsv.write('// These are well-known/required leap modules')
      wrapper_bsv.write('`include "asim/provides/smart_synth_boundaries.bsh"')
      wrapper_bsv.write('// import non-synthesis public files')
      wrapper_bsv.write('`include "' + module.name + '.bsv"')
      wrapper_bsv.write('\n')
      wrapper_bsv.write('// import non-synthesis private files')
      wrapper_bsv.write('\n')
      wrapper_bsv.write('`ifndef CONNECTION_SIZES_KNOWN')
      wrapper_bsv.write('\n')
      wrapper_bsv.write('// First pass to see how large the vectors should be')
      wrapper_bsv.write('`define CON_RECV_' + module.name + ' 100')
      wrapper_bsv.write('`define CON_SEND_' + module.name + ' 100')
      wrapper_bsv.write('`define CON_RECV_MULTI_' + module.name + ' 50')
      wrapper_bsv.write('`define CON_SEND_MULTI_' + module.name + ' 50')
      wrapper_bsv.write('`else')
      wrapper_bsv.write('// Real build pass.  Include file built dynamically.')
      wrapper_bsv.write('`include "' + module.name() + '_Wrapper_con_size.bsh"')
      wrapper_bsv.write('`endif')

      wrapper_bsv.write('(* synthesize *)')
      wrapper_bsv.write('module mk_' + module.name() + '_Wrapper (SOFT_SERVICES_SYNTHESIS_BOUNDARY#(`CON_RECV_' + module.name() + ', `CON_SEND_' + module.name() + ', `CON_RECV_MULTI_' + module.name() + ', `CON_SEND_MULTI_' + module.name() + '));')
      wrapper_bsv.write('  ')
      # we need to insert the fpga platform here
      # get my parameters 
      #wrapper_bsv.write('     messageM("SynthBoundary:'+ module.name +'");')
      wrapper_bsv.write('    // instantiate own module')
      wrapper_bsv.write('    let m <- instantiateSmartBoundary(' + module.synthBoundaryModule + ');')
      wrapper_bsv.write('    ')
      wrapper_bsv.write('    return m;')
      wrapper_bsv.write('\n')
      wrapper_bsv.write('endmodule')
    
      module.moduleDependency['BSV'] = module.moduleDependency['BSV'] + wrapperPath

