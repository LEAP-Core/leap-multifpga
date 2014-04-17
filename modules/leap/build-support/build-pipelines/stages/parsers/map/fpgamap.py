# this should probably be a seperate build pipeline stage. 

class FPGAMap(object):

    def __init__(self,mappings):
        self.mapping = {}
        for entry in mappings:
            self.mapping[entry[0]] = entry[1]

    def addSynthesisBoundaryMapping(self,boundary,platform):
        self.mapping[boundary] = platform

    def getSynthesisBoundaryPlatform(self,boundary):
        if(boundary in self.mapping):
            return self.mapping[boundary]
        else:
            return None

    def getPlatformNames(self):
        return self.mapping.keys()

    def getPlatformSynthesisBoundaries(self):
        keys = self.mapping.keys()
        result = []
        for boundary in keys:
            if(self.mapping[boundary] == platform):
                result.append(boundary)
        return result

    # build a graph. This will make life easier
    # graph legalization consists of ensuring that if a platform claims to 
