import os
from li_module import *

# Notice that chains will have their platform direction labelled
def parseStats(statsFile):
    # let's read in a stats file

    stats = {}
    print "StatsFile " + str(statsFile)

    # need to check for file existance. returning an empty stats
    # dictionary is acceptable.
    if( not os.path.exists(statsFile)):
        return stats

    logfile = open(statsFile,'r')  
    print "Processing Stats:  " + filename
    for line in logfile:
        # There are several ways that we can get stats. One way is instrumenting the router. 
        if(re.match('.*ROUTER_.*_SENT.*',line)):
            #We may have a chunked pattern.   
            match = re.search(r'.*ROUTER_(\w+)(_chunk_\d+)_SENT,.*,(\d+)',line)
            if(match):
                #print "Stat Match Chunk" + match.group(1) + " got " + match.group(3) + " from " + line
                stats[match.group(1)] = int(match.group(3))
                stats[match.group(1)+match.group(2)] = int(match.group(3))
                continue

            match = re.search(r'.*ROUTER_(\w+)_SENT,.*,(\d+)',line)
            if(match):
                #print "Stat Match " + match.group(1) + " got " + match.group(2) + " from " + line
                stats[match.group(1)] = int(match.group(2))

        # TODO: a second way is instrumenting the LI channels directly. 

    return stats


# Given a stats asssignment, this function will give all dangling
# connections in the design a weight.  If no stat exists, then the
# weight will be the average of the weights that do exist.  If no
# stats file exists, then the weight will be set to a constant and
# preference give to non-chains
# We seem to match only out bound channels. 
def assignActivity(moduleList, moduleGraph):

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
            # An activity less than 0 means that we have not seen this
            # channel before.
            if(channel.activity < 0):
                channel.activity = (float(totalTraffic)/(2*(channels)))  # no stat?  Make connections better than chains
                
        for chain in moduleGraph.modules[moduleName].chains:
            if(chain.activity < 0):
                chain.activity = (float(totalTraffic)/(2*(channels))) * 0.1  # no stat?  Make connections better than chains

          # only create a chain when we see the sink                                                                                                               
#          if(dangling.sc_type == 'ChainSink'):
#  
#            chains += 1
#            chainName = platform + "_" + targetPlatform + "_" + dangling.name
#            if(chainName in stats):
#              dangling.activity = stats[chainName]
#              totalTraffic += stats[chainName]
#              print "Assigning Load " + platform + "->" + targetPlatform + " " + chainName + " " + str(stats[chainName])
#            else:
#               match = re.search(r'(\w+)(_chunk_\d+)',chainName)
#                if(match and (match.group(1) in stats)):   
#                    dangling.activity = stats[match.group(1)]
#                    totalTraffic += stats[match.group(1)]
#                    print "Assigning Load (Chunk match) " + platform + "->" + targetPlatform + " " + dangling.name + " " + str(stats[match.group(1)])                    
#
#        if(totalTraffic == 0):
#          totalTraffic = 2*(chains+recvs)
# 
#        print "Total traffic is: " + str(totalTraffic)
#
#        # assign some value to 
#        for dangling in self.platformData[platform]['CONNECTED'][targetPlatform]:
#          if(dangling.sc_type == 'Recv' or dangling.sc_type == 'ChainRoutingRecv'):
#            if(dangling.activity < 0):
#              dangling.activity = float(totalTraffic)/(chains+recvs)
#              print "Defaulting Load " + platform + "->" + targetPlatform + " " + dangling.name + " " + str(dangling.activity)

          # only create a chain when we see the source                                                                                                                                                                                       
#          if(dangling.sc_type == 'ChainSink'):         
#            chainName = platform + "_" + targetPlatform + "_" + dangling.name
#            if(dangling.activity < 0):
#              dangling.activity = (float(totalTraffic)/(2*(chains+recvs))) * 0.1  # no stat?  Make connections better than chains
#              print "Defaulting Load " + platform + "->" + targetPlatform + " " + chainName + " " + str(dangling.activity)
