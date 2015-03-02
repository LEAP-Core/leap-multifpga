import os
import re
import SCons.Script  
from model import  *
from wrapper_gen_tool import *
from iface_tool import *
from area_group_tool import  *
from bsv_tool import *
from fpga_program_tool import *
from software_tool import *
from synthesis_tool import  *
from post_synthesis_tool import *
import li_module

class Build(ProjectDependency):
    def __init__(self, moduleList):
        WrapperGen(moduleList)
        Iface(moduleList)

        # Floor planner can influence the BSV build, and must therefore
        # run first.
        if (not moduleList.getAWBParam('bsv_tool', 'BUILD_LOGS_ONLY')):
            Floorplanner(moduleList)

        BSV(moduleList)
        FPGAProgram(moduleList)
        Synthesize(moduleList)

        if (not moduleList.getAWBParam('bsv_tool', 'BUILD_LOGS_ONLY')):
            PostSynthesize(moduleList)
        else:
            li_module.dump_lim_graph(moduleList)

        if (moduleList.getAWBParam('software_tool', 'BUILD_FIRST_PASS_SOFTWARE')):
            Software(moduleList)
        
  
