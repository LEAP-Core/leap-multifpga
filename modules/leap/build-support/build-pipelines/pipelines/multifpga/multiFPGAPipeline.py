import os
import re
import SCons.Script  
from model import  *
from multifpga_parse_tool import  *

class Build(ProjectDependency):
  def __init__(self, moduleList):
    ParseMultiFPGA(moduleList)



