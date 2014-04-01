import sys
import math

from model import  *

class UMFType():
  #GENERIC_UMF_PACKET_HEADER#(`UMF_CHANNEL_ID_BITS,`UMF_SERVICE_ID_BITS,`UMF_METHOD_ID_BITS,`UMF_MSG_LENGTH_BITS,`UMF_PHY_CHANNEL_RESERVED_BITS,UMF_PACKET_HEADER_FILLER_BITS)
    def __init__(self, channelIDBits, serviceIDBits, methodIDBits, msgLengthBits, phyChannelReservedBits, fillerBits, totalBits):
        self.channelIDBits = channelIDBits
        self.serviceIDBits = serviceIDBits
        self.methodIDBits = methodIDBits
        self.msgLengthBits = msgLengthBits
        self.phyChannelReservedBits = phyChannelReservedBits # This appears to never have been used...
        self.fillerBits = fillerBits
        self.totalBits = totalBits
        if(totalBits != channelIDBits + serviceIDBits + methodIDBits + msgLengthBits + phyChannelReservedBits + fillerBits):
            print "UMFDefinition total is not equal to the sum of the parts\n";
            exit(1)

    def headerTypeBSV(self):
        return "GENERIC_UMF_PACKET_HEADER#(\n" + \
               "             " + str(self.channelIDBits) + ", " + str(self.serviceIDBits) + ",//Log links\n" + \
               "             " + str(self.methodIDBits)  + ", " + str(self.msgLengthBits) + ",//Log chunks\n" + \
               "             " + str(self.phyChannelReservedBits) + ", " + str(self.fillerBits) +")//filler width\n"

    def bodyTypeBSV(self):
        return "Bit#(" +  str(self.totalBits) + ")"
      
    def typeBSV(self): 
        return "GENERIC_UMF_PACKET#(" + self.headerTypeBSV() + ", " + self.bodyTypeBSV() + ")"


    def typeCPP(self):
        return "UMF_MESSAGE_TEMPLATE_CLASS<" + str(self.channelIDBits) + "," + \
               str(self.serviceIDBits) + "," + str(self.methodIDBits) + "," + \
               str(self.msgLengthBits) + ">"

    def factoryClassNameCPP(self, target):
        # target can have a bunch of strange symbols in it.  
        # we convert them here. 
        targetMod = target.replace('->', '_arrow_');
        targetMod = targetMod.replace('(', '_lparen_');
        targetMod = targetMod.replace(')', '_rparen_');

        return "UMF_FACTORY_" + targetMod + "_CLASS"

    def factoryClassCPP(self, target):
              return "class " + self.factoryClassNameCPP(target) + ": public UMF_FACTORY_CLASS {\n" + \
                     "\tpublic:\n" + \
                     "\tUMF_MESSAGE createUMFMessage() {\n" + \
                     "\t\treturn new " + self.typeCPP() + "();\n" + \
                     "\t}\n" + \
                     "};\n"


# In generating router types, we want to minimize the maximum number of chunks
# In addition to the obvious throughput benefit, it also helps with flowcontrol at the 
# VC layer, since the VC layer is currently conservative about the buffering and assumes each
# packet takes the maximum number of chunks
def generateRouterTypes(viaWidth, viaLinks, maxWidth, moduleList):

    ENABLE_AGRESSIVE_UMF_PARAMETERS = moduleList.getAWBParam('multi_fpga_connect', 'ENABLE_AGRESSIVE_UMF_PARAMETERS')
    USE_DEFAULT_UMF_PARAMETERS = moduleList.getAWBParam('multi_fpga_connect', 'USE_DEFAULT_UMF_PARAMETERS')
    pipeline_debug = getBuildPipelineDebug(moduleList)

    #Should we do whatever umf tells us?
    if(USE_DEFAULT_UMF_PARAMETERS):      
        phyReserved = moduleList.getAWBParam('umf', 'UMF_PHY_CHANNEL_RESERVED_BITS')
        channelID = moduleList.getAWBParam('umf', 'UMF_CHANNEL_ID_BITS')          
        serviceID = moduleList.getAWBParam('umf', 'UMF_SERVICE_ID_BITS')          
        methodID  = moduleList.getAWBParam('umf', 'UMF_METHOD_ID_BITS')         
        msgLength = moduleList.getAWBParam('umf', 'UMF_MSG_LENGTH_BITS')          

        fillerWidth = viaWidth - phyReserved - channelID - serviceID - methodID - msgLength
        print "UMFTYPE using default: " + str(channelID) + "\n"
        return UMFType(channelID, serviceID, methodID, msgLength, phyReserved, fillerWidth, viaWidth)

    # At some point, we can reduce the number of header bits based on 
    # what we actually assign.  This would permit us to allocate smalled link
    links = max([1,int(math.ceil(math.log(viaLinks,2)))])  

    extraChunks = 1
    if(ENABLE_AGRESSIVE_UMF_PARAMETERS):
        extraChunks = 0

    # Max chunks depends on filler.  iterate till we get a fixed point.
    # iteration should converge because chunks should monotonically decrease
    # and fillerWidth should monotonically increase
    fillerWidth = -1
    fillerWidthNext = 0
    chunks = -1
    # Method dummy is a hack to support exisiting RRR method functionalities
    methodDummy = 0
    while(fillerWidth != fillerWidthNext):
        fillerWidth = fillerWidthNext
        chunks = extraChunks + int(max([1,math.ceil(math.log(1.0+math.ceil(float(max([0.0, maxWidth - fillerWidth]))/viaWidth),2))]))
        # This is a hack to force RRR UMF type and this UMF type to have similar lengths
        # what this will do is force the generated UMF type to use the same 
        # parameterization as the RRR UMF type.  We get this magic number from the umf, but
        # we should just be using it directly.      
        if(not ENABLE_AGRESSIVE_UMF_PARAMETERS):
            methodDummy = max(0,10 - chunks) # negative values make no sense      

        fillerWidthNext = viaWidth - links - chunks - methodDummy

    fillerWidth = fillerWidthNext

    if(pipeline_debug):
        print "Generating " + str(links) + " links " + str(chunks) + " chunks " + str(fillerWidth) + " filler from width " + str(viaWidth) + " calc" + str(1.0+math.ceil(float(max([0.0, maxWidth - fillerWidth]))/viaWidth)) +") max link " + str(maxWidth) + " via links " + str(viaLinks) + " method dummy " + str(methodDummy)
  
    return UMFType(0, links, methodDummy, chunks, 0, fillerWidth, viaWidth)


