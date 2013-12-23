from connection import *
from platform import *

# Import pygraph We'll need it at some point
import pygraph
try:
  from pygraph.classes.digraph import digraph
except ImportError:
  # don't need to do anything
  print "\n"
  # print "Warning you should upgrade to pygraph 1.8"
import pygraph.algorithms.sorting
import pygraph.algorithms.minmax as mm


class FPGAEnvironment(object):

    def __init__(self,platformList):
        self.platforms = {}
        for platform in platformList:
            self.addPlatform(platform)
        self.graphize()
        self.buildTransitTables()

    def addPlatform(self,platform):
        self.platforms[platform.name] = platform;

    def getPlatform(self,name):
        return self.platforms[name]

    def getPlatformNames(self):
        return self.platforms.keys()

    def getSynthesisBoundaryPlatformID(self,boundary):
        print 'Looking up: ' + boundary
        # Master platform/some FPGA must be assinged the 0 id
        # for backwards compatibility.  We achieve this by using
        # a sort function that orders by master and thence by platform 
        # type.  This is a major hack. 
        def platformSort(plat):
            if(self.platforms[plat].master):
                return 0
            elif (self.platforms[plat].platformType == 'FPGA'):
                return 1
            else:
                return 2

        return (sorted(self.platforms.keys(), key=platformSort)).index(boundary)

    # build a graph. This will make life easier
    # graph legalization consists of ensuring that if a platform claims to 
    # be connected to another platform, that platform also claims that they
    # are connected.  This is not the same a bi-directional connection, 
    # however. It serves to make sure that a directional connection has 
    # source  and sink.
    def graphize(self):
	try:
            self.graph = pygraph.digraph()
	except (NameError, AttributeError):
            self.graph = digraph()   
        
        # first, we must add all the nodes. Only then can we add all the edges
        for platform in self.platforms:
            self.graph.add_nodes([platform])

        for platform in self.platforms:
            sinks = self.platforms[platform].getSinks()
            sources = self.platforms[platform].getSources()
            for sink in sinks:
                # search for paired source - a specification is illegal if 
                # sink/source pairing is not made
                error = 0
                if(sinks[sink].endpointName in self.platforms):
                    if(platform in (self.platforms[sinks[sink].endpointName]).sources):
                        # we have a legal connection
	                try:
                            self.graph.add_edge(platform,sinks[sink].endpointName)
                        except (TypeError, ValueError):
                            self.graph.add_edge((platform,sinks[sink].endpointName))
                        #fill in the source with the sink and the sink with the source
                    else:
                        error = 1
                else:
                    error = 1

                if(error == 1):
                    print 'Illegal graph: sink ' + sinks[sink].endpointName + ' and ' + platform + ' improperly connected'
                    raise SyntaxError(sinks[sink].endpointName + ' and ' + platform + ' improperly connected')

                # although we've already added a edge for the legal connections, we need to check the reverse
                # in case some source lacks a sink
            for source in sources:
                error = 0
                if(sources[source].endpointName in self.platforms):
                    if(platform in (self.platforms[sources[source].endpointName]).sinks):
                        a = 0 # make python happy....
                        
                    else:
                        error = 1
                else:
                    error = 1

                if(error == 1):
                    print 'Illegal graph: source ' + sources[source].endpointName + ' and ' + platform + ' improperly connected'
                    raise SyntaxError(sources[source].endpointName + ' and ' + platform + ' improperly connected')

    # finds/returns the link to use on a path hop from 
    def getPathLength(self, source, sink):
        try:
            paths = pygraph.algorithms.minmax.shortest_path(self.graph,source)
        except AttributeError:
            paths = mm.shortest_path(self.graph,source)

        if(sink in paths[1]):           
            return paths[1][sink]
        else:
            return -1

    def getPath(self, source, sink):
        paths = pygraph.algorithms.minmax.shortest_path(self.graph,source)
        path = []
        hop = sink
        lastNode = sink 
        while paths[0][hop] != source:
            hop = paths[0][hop]
            path.append(hop)           
        print "getPath: " + str(path)
        path.reverse()
        return path 


    #It would be worth considering how to handle the key error
    def getPathHopFirst(self, source, sink):
        paths = pygraph.algorithms.minmax.shortest_path(self.graph,source)
        hop = sink
        lastNode = sink 
        while paths[0][hop] != source:
           
            hop = paths[0][hop]
        return hop

    def getPathHopLast(self, source, sink):
        paths = pygraph.algorithms.minmax.shortest_path(self.graph,source)
        return paths[0][sink]

        
    # returns the source string for a particular path.  This is currently the min path  
    def getPhysicalSource(self,platform,source):
        return self.platforms[platform].sources[source].physicalName

    def getPhysicalSink(self,platform,sink):
        
        return self.platforms[platform].sinks[sink].physicalName

    
    #build up a keyed dictionary of dictionaries of the single hops to next 
    #nodes nodes without a next are unlisted
    #notice that we generate a listing of all reachable nodes, 
    #not just those that we need.  bluespec will choose the ones that 
    #we need.  We use the memoized connection pointers to build the incoming 
    #list 
    def buildTransitTables(self):
        transitTablesOutgoing = {}
        transitTablesIncoming = {}
        for platformName in self.platforms:
            transitTablesOutgoing[platformName] = {}
            transitTablesIncoming[platformName] = {}

        for platformName in self.platforms:
            platform = self.platforms[platformName]

            for target in self.platforms:
                # check for a connection
                
                if(self.getPathLength(platformName, target) > 0):
                    hop = self.getPathHopFirst(platformName, target)
                    # pygraph returns something odd for paths of length one
                    
                    print platformName + ' -> ' + target + ' : ' + self.getPhysicalSink(platformName,hop)
                    transitTablesOutgoing[platformName][target] = self.getPhysicalSink(platformName,hop)

                if(self.getPathLength(target, platformName) > 0):
                    hop = self.getPathHopLast(target, platformName)

                    # also fill in our sink at the same time
                    print platformName + ' <- ' + target + ' : ' + self.getPhysicalSource(platformName,hop)
                    transitTablesIncoming[platformName][target] = self.getPhysicalSource(platformName,hop)
                    
        self.transitTablesOutgoing = transitTablesOutgoing
        self.transitTablesIncoming = transitTablesIncoming



    def __repr__(self):
        platformRepr = ''
        for platform in self.platforms:
            platformRepr = platformRepr + platform.__repr__()
        return platformRepr


