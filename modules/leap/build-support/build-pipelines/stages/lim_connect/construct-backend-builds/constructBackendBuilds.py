# python libraries
import re
import sys
import copy
import math
import cPickle as pickle

# AWB dependencies
from model import  *
from li_module import *
from lim_common import *
from lim_graph_generator import *
from lim_executable_generator import *


# This function takes the object code scrubbed from the first-pass
# build and combines it with the analysis produced during LIM
# compilation to produce backend compilation flows.  Each flow will
# produce an executable for a particular platform target. 
def constructBackendBuilds(moduleList, environmentGraph, platformGraph, moduleGraph):
    
    # We'll be writing the .awb files and object code to a new backed
    # directory.
    
    # look at each platform seperately. 
    for platformName in platformGraph.modules:

        APM_NAME = moduleList.env['DEFS']['APM_NAME']
        platformBitfileBuildDir = 'multi_fpga/' + makePlatformBitfileName(platformName,APM_NAME) + '/pm/'
        liFile = platformBitfileBuildDir + '/lim.li'


        platformBuildGraph = LIGraph([])
        platformModules = []
        # now we need to add the mapped modules and their sources.
        for moduleName in moduleGraph.modules:
            module = moduleGraph.modules[moduleName]
            if(module.getAttribute('MAPPING') == platformName and \
               not moduleName == platformName): # The platform module will be compiled again (sadly)
                # The module copy will un-match all channels/chains.                 
                platformModules.append(module.copy())

        platformBuildGraph.mergeModules(platformModules)

        pickleHandle = open(liFile, 'wb')
        pickle.dump(platformBuildGraph, pickleHandle, protocol=-1)
        pickleHandle.close()

