import os
import re
import SCons.Script  

import model
from lim_graph_generator import GenerateLIMGraph
from lim_connect import LIMConnect
from lim_executable_generator import GenerateLIMExecutable

class Build(model.ProjectDependency):
    def __init__(self, moduleList):
        GenerateLIMGraph(moduleList)
        LIMConnect(moduleList)
        GenerateLIMExecutable(moduleList)



