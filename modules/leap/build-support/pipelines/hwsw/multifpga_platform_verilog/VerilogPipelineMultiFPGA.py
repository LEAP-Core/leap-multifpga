import os
import re
import SCons.Script  
from iface_tool import *
from bsv_tool import *
from verilog_tool import *
from area_group_tool import  *
from wrapper_gen_tool import *
from model import  *
import li_module

class Build(ProjectDependency):
  def __init__(self, moduleList):

    #build interface first 
    WrapperGen(moduleList)
    Iface(moduleList)

    # Floor planner can influence the BSV build, and must therefore
    # run first.
    Floorplanner(moduleList)

    BSV(moduleList)
    if (not moduleList.getAWBParam('bsv_tool', 'BUILD_LOGS_ONLY')):
      Verilog(moduleList, True)
    else:
      li_module.dump_lim_graph(moduleList)
