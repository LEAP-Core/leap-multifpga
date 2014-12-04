import os
import re
import SCons.Script  
from model import  *
from lim_graph_generator import  *
from lim_connect import  *
from lim_executable_generator import  *

class Build(ProjectDependency):
    def __init__(self, moduleList):
        GenerateLIMGraph(moduleList)
        LIMConnect(moduleList)
        GenerateLIMExecutable(moduleList)



