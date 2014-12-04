import os
import re

import model

# Notice that chains will have their platform direction labelled
def parseStats(statsFile, debug=False):
    # let's read in a stats file

    stats = {}

    # need to check for file existance. returning an empty stats
    # dictionary is acceptable.
    if( not os.path.exists(statsFile)):
        return stats

    if(debug):
        print "Parsing activity statistics file: " + statsFile

    logfile = open(statsFile,'r')  
    for line in logfile:
        # There are several ways that we can get stats. One way is instrumenting the router. 
        if(re.match('^TRAFFIC_',line)):
            #We may have a chunked pattern.   
            if(debug):
                print "ACTIVITY match: " + line

            match = re.match('^TRAFFIC_(\w+)_from_(\w+),.*,(\d+)',line)

            if(match):
                if(debug):
                    print "ACTIVITY setting:  " + match.group(1) +  " to " + match.group(3)

                stats[match.group(1)] = int(match.group(3))

        # TODO: a second way is instrumenting the LI channels directly. 

    return stats


# Given a stats asssignment, this function will give all dangling
# connections in the design a weight.  If no stat exists, then the
# weight will be the average of the weights that do exist.  If no
# stats file exists, then the weight will be set to a constant and
# preference give to non-chains
# We seem to match only out bound channels. 
def assignActivity(moduleList, moduleGraph):

    pipeline_debug = model.getBuildPipelineDebug(moduleList)

    statsFile = moduleList.getAllDependenciesWithPaths('GIVEN_STATS')    
    filename = ""
    if(len(statsFile) > 0):
        filename = moduleList.env['DEFS']['ROOT_DIR_HW'] + '/' + statsFile[0]
        # let's read in a stats file
    stats = parseStats(filename)

    # handle the connections themselves
    channels = 0
    chains = 0           
    totalTraffic = 0;


    def printActivity(classStr, channel):
        if(pipeline_debug):
            print "ACTIVITY: " + classStr + " " + channel.module.name + "->" + channel.partnerChannel.module.name + " " + channel.name + " " + str(channel.activity) + "\n"
        

    # In some cases, due to pre-existing partitioning, there may be a
    # mismatch between the stats file and the partitioning. .  To make
    # things more usable we will also match non-chunks
    def chunkMatch(connection):
        match = re.search(r'(\w+)(_chunk_\d+)', connection.name)
        if(match and (match.group(1) in stats)):      
            connection.activity = stats[match.group(1)]
            totalTraffic += stats[match.group(1)]
            printActivity("Assigning Loads(chunk)", connection)                    


    for moduleName in moduleGraph.modules.keys():
        if(pipeline_debug):
            print "examining: " + moduleName + "\n"
         
        for channel in moduleGraph.modules[moduleName].channels:
            if(channel.sc_type == 'Recv'):
                  channels += 1
                  if(channel.name in stats):
                      channel.activity = stats[channel.name]
                      channel.partnerChannel.activity = channel.activity
                      totalTraffic += stats[channel.name]
                      printActivity("Assigning Load ", channel)                    
                  else:
                      chunkMatch(channel)

    # Give a sensical default for channel traffic, if undefined.
    if(totalTraffic == 0):
        totalTraffic = 2*(channels)

    for moduleName in moduleGraph.modules.keys():
        for channel in moduleGraph.modules[moduleName].channels:
            # This use of 1 as a default is somewhat kludgy.
            if(channel.activity <= 1):
                channel.activity = (float(totalTraffic)/(2*(channels)))  # no stat?  Make connections better than chains
                printActivity("Assigning Load (default) ", channel)                    
                
        for chain in moduleGraph.modules[moduleName].chains:
            if(chain.activity < 0):
                chain.activity = (float(totalTraffic)/(2*(channels))) * 0.1  # no stat?  Make connections better than chains


