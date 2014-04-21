# python libraries
import re
import sys
import copy
import math

# AWB dependencies
from model import  *
from li_module import *
from lim_common import *

# This function takes the object code scrubbed from the first-pass
# build and combines it with the analysis produced during LIM
# compilation to produce backend compilation flows.  Each flow will
# produce an executable for a particular platform target. 
def constructBackendBuilds(moduleList, environmentGraph, platformGraph):
    return None
