import os
import re
import SCons.Script  
from iface_tool import *
from bsv_tool import *
from bluesim_tool import *
from area_group_tool import  *
from software_tool import *
from wrapper_gen_tool import *
from model import  *

class Build(ProjectDependency):
    def __init__(self, moduleList):
        #build interface first 
        WrapperGen(moduleList)

        Iface(moduleList)

        # Floor planner can influence the BSV build, and must therefore
        # run first.
        if (not moduleList.getAWBParam('bsv_tool', 'BUILD_LOGS_ONLY')):
            Floorplanner(moduleList)

        bsv = BSV(moduleList)
        if not moduleList.isDependsBuild:
            if (not moduleList.getAWBParam('bsv_tool', 'BUILD_LOGS_ONLY')):
                Bluesim(moduleList)                      
            if (moduleList.getAWBParam('software_tool', 'BUILD_FIRST_PASS_SOFTWARE')):
                Software(moduleList)
              
        
