# python libraries
import re
import sys
import copy
import math

# AWB dependencies
from model import  *
from fpgamap_parser import *
from li_module import *
from lim_common import *

# Places modules onto platforms using a programmer-supplied
# mapping file.
def placeModulesWithMapFile(moduleList, environmentGraph, moduleGraph):

    mappingFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENV_MAPPINGS')

    if(len(mappingFile) != 1):
        print "Found more than one mapping file: " + str(envFile) + ", exiting\n"

    mapping = parseFPGAMap(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + mappingFile[0])

    for moduleName in moduleGraph.modules:
        # have we already mapped this module?
        if(not moduleName in environmentGraph.getPlatformNames()):
            moduleObject = moduleGraph.modules[moduleName]   
            moduleObject.putAttribute('MAPPING', mapping.getSynthesisBoundaryPlatform(moduleName))
    return moduleGraph


# Assigns LI modules to platforms.  Currently, this is done using
# a mapping file, in which the programmer assigns specific modules
# to specific platforms.  This function produces the
# "platformGraph", a representation which views each platform a
# module with LI channels.  The "platformGraph" is progressively
# elaborated in subsequent compilation passes.
def placeModules(moduleList, environmentGraph, moduleGraph):
    
    pipeline_debug = getBuildPipelineDebug(moduleList)

    # first we need to map the platform modules (those physically tied
    # to the platform) to their platform
    for platformName in environmentGraph.getPlatformNames():          
        moduleGraph.modules[platformName].putAttribute('MAPPING', platformName)

    PLACER_ALGORITHM = moduleList.getAWBParam('lim_place_modules', 'PLACER_ALGORITHM')
    eval(PLACER_ALGORITHM + '(moduleList, environmentGraph, moduleGraph)')

    # now that we have placed the modules, we can build a new view
    # of the system, the platform graph.  In this graph we consider
    # only platforms, and their inter-platform connections.  
    platformConnections = []
    for module in moduleGraph.modules.values():
        platformMapping = module.getAttribute('MAPPING')
        for channel in module.channels:
            if(pipeline_debug):
                print "Mapper Examining Channel: " + channel.name + "\n"

            # it is possible that this channel is unassigned, if so, it is dropped.
            if(channel.partnerChannel == 'unassigned'):
                continue

            if(pipeline_debug):
                print "Partner channel: " + channel.partnerChannel.name + "\n"
                print "Partner module: " + channel.partnerModule.name + "\n"

            # we only care about inter-FPGA channels
            if(platformMapping == channel.partnerModule.getAttribute('MAPPING')):
                continue

            if(pipeline_debug):
                print "Placer Examining channel : " + channel.name + " mapped to: " + platformMapping + " partnerModule " + str(channel.partnerModule.name) + "\n"            


            # We don't actually care about specific modules here. We
            # simply re-cast the platforms as the 'modules', with
            # one 'module' per platform.  I wish python had better
            # inheritance support.
            channelCopy = channel.copy()
            channelCopy.module_name = platformMapping
            platformConnections.append(channelCopy)

        for chain in module.chains:

            if(pipeline_debug):
                print "Placer Examining chain : " + chain.name + " mapped to: " + platformMapping + "\n"            

            chainCopy = chain.copy()
            chainCopy.module_name = platformMapping
            platformConnections.append(chainCopy)
            
           
    platformGraph = LIGraph(platformConnections)

    if(pipeline_debug):
        print "Post placement platform graph: " + str(platformGraph) + "\n"

    return platformGraph




