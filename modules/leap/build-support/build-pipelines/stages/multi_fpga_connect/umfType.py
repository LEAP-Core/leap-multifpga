import sys

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
        print "TYPEBSV: " + str(self.channelIDBits) + '\n'
        return "GENERIC_UMF_PACKET_HEADER#(\n" + \
               "             " + str(self.channelIDBits) + ", " + str(self.serviceIDBits) + ",//Log links\n" + \
               "             " + str(self.methodIDBits)  + ", " + str(self.msgLengthBits) + ",//Log chunks\n" + \
               "             " + str(self.phyChannelReservedBits) + ", " + str(self.fillerBits) +")//filler width\n"

    def bodyTypeBSV(self):
        return "Bit#(" +  str(self.totalBits) + ")"
      
    def typeBSV(self): 
        return "GENERIC_UMF_PACKET#(" + self.headerTypeBSV() + ", " + self.bodyTypeBSV() + ")"


    def typeCPP(self):
        print "TYPECPP: " + str(self.channelIDBits) + '\n'
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
