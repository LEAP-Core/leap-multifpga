from physical_via import *
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

        # Master platform/some FPGA must be assinged the 0 id
        # for backwards compatibility.  We achieve this by using
        # a sort function that orders by master and thence by platform 
        # type.  Alphabetical sorting helps make code consistent across builds. 
        # This is a major hack. 
        masterList = filter(lambda plat: self.platforms[plat].master, self.platforms.keys())
        fpgaList = filter(lambda plat: not self.platforms[plat].master and (self.platforms[plat].platformType == 'FPGA' or self.platforms[plat].platformType == 'BLUESIM'), self.platforms.keys())
        otherList =  filter(lambda plat: not (self.platforms[plat].master or self.platforms[plat].platformType == 'FPGA' or self.platforms[plat].platformType == 'BLUESIM'), self.platforms.keys())
        
        #put things in alphabetical order
        return (masterList + sorted(fpgaList) + sorted(otherList)).index(boundary)

    # build a graph. This will make life easier
    # graph legalization consists of ensuring that if a platform claims to 
    # be connected to another platform, that platform also claims that they
    # are connected.  This is not the same a bi-directional connection, 
    # however. It serves to make sure that a directional connection has 
    # ingress  and egress.
    def graphize(self):
	try:
            self.graph = pygraph.digraph()
	except (NameError, AttributeError):
            self.graph = digraph()   
        
        # first, we must add all the nodes. Only then can we add all the edges
        for platform in self.platforms:
            self.graph.add_nodes([platform])

        for platform in self.platforms:
            egresses = self.platforms[platform].getEgresses()
            ingresses = self.platforms[platform].getIngresses()
            for egress in egresses:
                # search for paired ingress - a specification is illegal if 
                # egress/ingress pairing is not made
                error = 0
                if(egresses[egress].endpointName in self.platforms):
                    if(platform in (self.platforms[egresses[egress].endpointName]).ingresses):
                        # we have a legal connection
	                try:
                            self.graph.add_edge(platform,egresses[egress].endpointName)
                        except (TypeError, ValueError):
                            self.graph.add_edge((platform,egresses[egress].endpointName))
                        #fill in the ingress with the egress and the egress with the ingress
                    else:
                        error = 1
                else:
                    error = 1

                if(error == 1):
                    print 'Illegal graph: egress ' + egresses[egress].endpointName + ' and ' + platform + ' improperly connected'
                    raise SyntaxError(egresses[egress].endpointName + ' and ' + platform + ' improperly connected')

                # although we've already added a edge for the legal connections, we need to check the reverse
                # in case some ingress lacks a egress
            for ingress in ingresses:
                error = 0
                if(ingresses[ingress].endpointName in self.platforms):
                    if(platform in (self.platforms[ingresses[ingress].endpointName]).egresses):
                        a = 0 # make python happy....
                        
                    else:
                        error = 1
                else:
                    error = 1

                if(error == 1):
                    print 'Illegal graph: ingress ' + ingresses[ingress].endpointName + ' and ' + platform + ' improperly connected'
                    raise SyntaxError(ingresses[ingress].endpointName + ' and ' + platform + ' improperly connected')

    # finds/returns the link to use on a path hop from 
    def getPathLength(self, ingress, egress):
        try:
            paths = pygraph.algorithms.minmax.shortest_path(self.graph,ingress)
        except AttributeError:
            paths = mm.shortest_path(self.graph,ingress)

        if(egress in paths[1]):           
            return paths[1][egress]
        else:
            return -1

    def getPath(self, ingress, egress):
        paths = pygraph.algorithms.minmax.shortest_path(self.graph,ingress)
        path = []
        hop = egress
        lastNode = egress

        # Adjacent platforms have None as their path.
        if(paths[0][hop] is None):
            return []

        while paths[0][hop] != ingress:
            hop = paths[0][hop]
            path.append(hop)           

        path.reverse()
        return path 


    #It would be worth considering how to handle the key error
    def getPathHopFirst(self, ingress, egress):
        paths = pygraph.algorithms.minmax.shortest_path(self.graph,ingress)
        hop = egress
        lastNode = egress 
        while paths[0][hop] != ingress:
           
            hop = paths[0][hop]
        return hop

    def getPathHopLast(self, ingress, egress):
        paths = pygraph.algorithms.minmax.shortest_path(self.graph,ingress)
        return paths[0][egress]

        
    # returns the ingress string for a particular path.  This is currently the min path  
    def getPhysicalIngress(self,platform,ingress):
        return self.platforms[platform].ingresses[ingress].physicalName

    def getPhysicalEgress(self,platform,egress):
        
        return self.platforms[platform].egresses[egress].physicalName

    
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
                    
                    transitTablesOutgoing[platformName][target] = self.getPhysicalEgress(platformName,hop)

                if(self.getPathLength(target, platformName) > 0):
                    hop = self.getPathHopLast(target, platformName)

                    # also fill in our egress at the same time
                    transitTablesIncoming[platformName][target] = self.getPhysicalIngress(platformName,hop)
                    
        self.transitTablesOutgoing = transitTablesOutgoing
        self.transitTablesIncoming = transitTablesIncoming



    def __repr__(self):
        platformRepr = ''
        for platform in self.platforms:
            platformRepr = platformRepr + platform.__repr__()
        return platformRepr


