import os
import re
import SCons.Script  

import model
from lim_graph_generator import MultiFPGAGenerateLogfile
from lim_connect import MultiFPGAConnect
from lim_executable_generator import MultiFPGAGenerateBitfile

class Build(model.ProjectDependency):
    def __init__(self, moduleList):
        MultiFPGAGenerateLogfile(moduleList)
        MultiFPGAConnect(moduleList)
        MultiFPGAGenerateBitfile(moduleList)



