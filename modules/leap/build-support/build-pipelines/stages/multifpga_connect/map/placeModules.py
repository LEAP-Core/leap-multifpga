# python libraries
import re
import sys
import copy
import math
import itertools
import time
import os

# AWB dependencies
from model import  *
from fpgamap_parser import parseFPGAMap
from li_module import *
from lim_common import *

def placeModulesWithMapFile(moduleList, environmentGraph, moduleGraph):

    decorateModulesWithMapFile(moduleList, environmentGraph, moduleGraph)

    for moduleName in moduleGraph.modules:
        # have we already mapped this module?                                                               
        if(not moduleName in environmentGraph.getPlatformNames()):
            moduleObject = moduleGraph.modules[moduleName]
            attr = moduleObject.getAttribute('MAPPING')
            if(attr is None):
                print 'Unmapped module: ' + moduleName + '\n'
                exit(0)


# Places modules onto platforms using a programmer-supplied
# mapping file.  Does not check to enforce that mapping was complet.
# This allows us to use the function in the ILP code path so that programmers can 
# suggest the placement of modules. 
def decorateModulesWithMapFile(moduleList, environmentGraph, moduleGraph):

    mappingFile = moduleList.getAllDependenciesWithPaths('GIVEN_FPGAENV_MAPPINGS')

    if(len(mappingFile) != 1):
        print "Found more than one mapping file: " + str(envFile) + ", exiting\n"
        return 

    mapping = parseFPGAMap(moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + mappingFile[0])

    for moduleName in moduleGraph.modules:
        # have we already mapped this module?
        if(not moduleName in environmentGraph.getPlatformNames()):

            # It may be the case that the programmer has not specified
            # a placement for this module.  Depending on the placement
            # routine, this may be filled in later.
            platform = mapping.getSynthesisBoundaryPlatform(moduleName)
            if(platform is not None):
                moduleObject = moduleGraph.modules[moduleName]   
                moduleObject.putAttribute('MAPPING', platform)

# this function allows us to supply resource utilizations for
# different modules.
def assignResources(moduleList, environmentGraph, moduleGraph):

    # We require this extra 'S', but maybe this should not be the case.
    resourceFile = moduleList.getAllDependenciesWithPaths('GIVEN_RESOURCESS')    
    filename = ""
    if(len(resourceFile) > 0):
        filename = moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + resourceFile[0]
        # let's read in a resource file


    resources = {}

    # need to check for file existance. returning an empty resource
    # dictionary is acceptable.
    if( not os.path.exists(filename)):
        return resources

    logfile = open(filename,'r')  
    for line in logfile:
        # There are several ways that we can get resource. One way is instrumenting the router. 
        params = line.split(':')
        moduleName = params.pop(0)
        resources[moduleName] = {}
        for index in range(len(params)/2):
            resources[moduleName][params[2*index]] = float(params[2*index+1])

    return resources

# Places modules onto platforms using a programmer-supplied
# mapping file.                                                                                             
def placeModulesILP(moduleList, environmentGraph, moduleGraph):

    pipeline_debug = getBuildPipelineDebug(moduleList)

    # As a prepass, tag modules according to map file.
    decorateModulesWithMapFile(moduleList, environmentGraph, moduleGraph)
    modFile = 'placer.mod'
    modHandle = open(modFile,'w')

    # Obtain information about resource usage
    resources = assignResources(moduleList, environmentGraph, moduleGraph)
    
    # Set up variables
    
    moduleColors = {}
    edgeColorPairs = {}
    edgesByName = {}
    # each module/platform is represented by a variable.
    def getColorModule(moduleNameIn, platformNameIn):
        return 'color_' + moduleNameIn + '_is_' + platformNameIn

    def getColorEdge(edgeName, platformNameSrc, platformNameDest):
        return 'colorPair_' + edgeName + '_is_' + platformNameSrc + '_to_' + platformNameDest

    for moduleName in moduleGraph.modules:
        # some modules may be pre-assigned. 
        moduleObject = moduleGraph.modules[moduleName]   
        mapping = moduleObject.getAttribute('MAPPING')
        moduleColors[moduleName] = []
        if(mapping is None):        
            for platformName in environmentGraph.getPlatformNames():
                modHandle.write('var ' + getColorModule(moduleName, platformName) + ' binary;\n')
                moduleColors[moduleName].append(platformName)
        else:
            modHandle.write('var ' + getColorModule(moduleName, mapping) + ' = 1;\n') # Already mapped
            moduleColors[moduleName].append(mapping)

    # Now spit out edge variables. 
    # Each edge may be routed between multiple platforms. 
    for moduleName in moduleGraph.modules:
        moduleObject = moduleGraph.modules[moduleName]   
        for partnerName in moduleGraph.modules:
            if(moduleName == partnerName):
                continue
            # we use egress so that each channel is modelled once. 
            channels = egressChannelsByPartner(moduleObject, partnerName)
            sourceColors = moduleColors[moduleName]
            destColors = moduleColors[partnerName]
            for channel in channels:
                edgeColorPairs[channel.name] = (sourceColors, destColors)
                edgesByName[channel.name] = channel
                # Special case, both source and dest are mapped. 
                if(len(sourceColors) == 1 and len(destColors) ==1):
                    modHandle.write('var ' + getColorEdge(channel.name, sourceColors[0], destColors[0]) + ' = 1;\n') # Already mapped
                else:
                    for sourceColor in sourceColors:
                        for destColor in destColors:
                            modHandle.write('var ' + getColorEdge(channel.name, sourceColor, destColor) + '  binary;\n') # Already mapped

    # Minimize communications 

    modHandle.write('\n\nminimize comms: ')
    communicationsCosts =[]
    for edge in edgeColorPairs:
        colorPairs = itertools.product(edgeColorPairs[edge][0], edgeColorPairs[edge][1])        
        def defineColorPair(colorPair):
            varName = getColorEdge(edge, colorPair[0], colorPair[1])
            
            pathLength = 0
                            
            if(colorPair[0] != colorPair[1]):
                pathLength = environmentGraph.getPathLength(colorPair[0], colorPair[1])

            communicationsWeight = pathLength * edgesByName[edge].activity

            return (str(communicationsWeight) + '*' + varName)
        communicationsCosts += map(defineColorPair, colorPairs)

    modHandle.write(" + ".join(communicationsCosts) + ';\n\n')

    # Now we can build constraints. 

    # Every module must have one and only one platform assignment.                            
    for moduleName in moduleGraph.modules:
        modHandle.write('subject to module_one_color_' + moduleName + ':\n')
        def defineColor(colorName):
            return getColorModule(moduleName, colorName)
        modHandle.write(' + '.join(map(defineColor,moduleColors[moduleName])) + ' = 1;\n')

    # Every edge has one and only one color pair                           
    for edge in edgeColorPairs:
        modHandle.write('subject to edge_one_color_' + edge + ':\n')
       
        colorPairs = itertools.product(edgeColorPairs[edge][0], edgeColorPairs[edge][1])
        
        def defineColorPair(colorPair):
            return getColorEdge(edge, colorPair[0], colorPair[1])

        modHandle.write('\t' + ' + '.join(map(defineColorPair, colorPairs)) + ' = 1;\n')

    # If a module has a particular color, its edge must also have one instance of that color. 
    for moduleName in moduleGraph.modules:
        moduleObject = moduleGraph.modules[moduleName]   
        for channel in moduleObject.channels:
            for color in moduleColors[moduleName]:
                modHandle.write('subject to module_' + moduleName + 'must_color_edge_' + channel.name + '_' + color + ':\n')
                if(channel.isSource()):
                    def defineDestVal(destColor):
                        return getColorEdge(channel.name, color, destColor)
                    modHandle.write('\t' + " + ".join(map(defineDestVal,edgeColorPairs[channel.name][1])) + ' = ' + getColorModule(moduleName, color) + ';\n')
                else:
                    def defineSrcVal(srcColor):
                        return getColorEdge(channel.name, srcColor, color)
                    modHandle.write('\t' + " + ".join(map(defineSrcVal,edgeColorPairs[channel.name][0])) + ' = ' + getColorModule(moduleName, color) + ';\n')

    # Now we emit resource constraints. This is somewhat tied to the resource matrix :/
    for platformName in environmentGraph.getPlatformNames():
        # For each resource that the plaform has, we need to emit a constraint. 
        if(platformName in resources):
            for resourceCandidate in resources[platformName]:
                #The following line is a kind of hack. 
                match = re.match('^Total(.*)',resourceCandidate)
                if(match):
                    # we found a resource class that this platform cares about.
                    resourceClass = match.group(1)
                    constraints = []

                    for moduleName in moduleGraph.modules:
                        moduleObject = moduleGraph.modules[moduleName]   
                        # Can this module be on this platform (some
                        # modules are tied to specific platforms)
                        if(platformName in moduleColors[moduleName]):
                            # emit constraint if the module has a resource constraint.  
                            if(moduleName in resources):
                                if(resourceClass in resources[moduleName]):
                                    constraints.append(str(resources[moduleName][resourceClass]) + ' * ' + getColorModule(moduleName,platformName))
                    #if there are no constraints, do nothing.
                    if(len(constraints) > 0):
                        modHandle.write('subject to resource_' + resourceClass + '_platform_' + platformName +':\n')
                        modHandle.write(' + '.join(constraints) + ' <= ' + str(.6*resources[platformName][resourceCandidate]) + ';\n')
        
    modHandle.write('\n\nend;\n')
    modHandle.close()

    # now that we've written out the file, solve it. 
    # Necessary to force ply rebuild.  Sad...
    import glpk 
    example = glpk.glpk(modFile)
    example.update()
    example.solve()

    # print module names
    for moduleName in moduleColors:
        for platformName in moduleColors[moduleName]:
            colorAssignment = eval('example.' + getColorModule(moduleName,platformName))
            if(colorAssignment.value() > 0):
                moduleGraph.modules[moduleName].putAttribute('MAPPING', platformName)
                moduleGraph.modules[moduleName].id() 
                if(pipeline_debug):
                    print 'Mapping touches ' + str(id(moduleGraph.modules[moduleName])) + 'and ' + str(id(moduleGraph.modules[moduleName].attributes)) + ': ' + moduleName + " platform is  " + platformName + ' : ' + str(colorAssignment) + ' ' + str(type(colorAssignment))


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
        if(platformName in moduleGraph.modules):
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
                print "Partner module id: " + str(id(channel.partnerModule.name)) + ": " + channel.partnerModule.name + "\n"
                channel.partnerModule.id()
                print "Partner channel mapping: " + channel.partnerChannel.module.getAttribute('MAPPING') + "\n"
                print "Partner module mapping: " + channel.partnerModule.getAttribute('MAPPING') + "\n"

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

    # the platform graph doesn't have mappings yet.  trivially insert
    # them here.
    for module in platformGraph.modules.values():
        module.putAttribute('MAPPING', module.name)

    # For routing purposes, platform modules must be assigned mappings. 
    # For now, these are trivial. 
    for module in platformGraph.modules.values():
        module.putAttribute('MAPPING', module.name)

    platformGraph.healthCheck()
    moduleGraph.healthCheck()

    if(pipeline_debug):
        print "Post placement platform graph: " + str(platformGraph) + "\n"

    return platformGraph




