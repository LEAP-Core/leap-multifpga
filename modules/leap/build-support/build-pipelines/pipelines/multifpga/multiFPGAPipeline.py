import os
import re
import SCons.Script  
from model import  *
from multi_fpga_log_generator import  *
from multi_fpga_connect import  *

class Build(ProjectDependency):
  def __init__(self, moduleList):
    MultiFPGAGenerateLogfile(moduleList)
    MultiFPGAConnect(moduleList)



