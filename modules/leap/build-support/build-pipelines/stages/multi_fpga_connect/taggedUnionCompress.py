import re
import sys
import SCons.Script
import math
import itertools
from type_parser import *
# we write to bitfile 
# we read from logfile
from danglingConnection import *
from linkType import *
from code import *

injectDebug = False

class CompressChannel():
    def __init__(self, connection, width, uniquifier):
        # what polarity are we?
        polarityType = "CONNECTION_RECV"
        polarityInst = "Recv"
        polarityDangling = "Send"

        if(connection.sc_type == 'Recv'):
            polarityType = "CONNECTION_SEND"
            polarityInst = "Send"
            polarityDangling = "Recv"

        type =  "Bit#(" + str(width) + ")";
        self.name = "c__" + connection.name + uniquifier + "__";
        self.channel = DanglingConnection(polarityDangling, 
                                          type, 
                                          -1, # okay?
                                          self.name, 
                                          connection.platform, 
                                          connection.optional,  
                                          width, 
                                          connection.modulename, 
                                          connection.chainroot,
                                          LinkType(Type("Bit",NumericType(width)),False,[]))


        self.declaration = polarityType + '#('+ type + ') ' + self.name + ' <- mkConnection' + polarityInst + '("' + self.name +'");\n'
    

# the index function tells the decompressor which 
# indices it should target
class IndexFunction(): 
    def __init__(self, members):
        
        self.definition = "\t" + "function Bit#(" + str(len(members)) + ")  indexer(idx);\n"
        self.definition += "\t" + "\t" + "Bit#(" + str(len(members)) + ") result = ?;\n"
        self.definition += "\t" + "\t" + "case(idx)\n"

        
        sortedMembers = sorted(members, key = lambda x: x.width)
        
        enables = [ 0 for member in sortedMembers]
        self.splits = []
        bitsThusFar = 0
        enableIdx = 0 # the enable index is different due to same-sized union members

        for idx in range(len(members)): 
            # remove size zero splits - they aren't needed, though we still need the index function.
            if(sortedMembers[idx].width != bitsThusFar):
                self.splits += [sortedMembers[idx].width-bitsThusFar]
                enables[enableIdx]=1
                enableIdx = enableIdx + 1

            enables.reverse()
            self.definition += "\t" + "\t" + "\t" + str(sortedMembers[idx].index) +":  result = {1'b" +  ",1'b".join(map(str,enables)) + '};\n'
            enables.reverse()

            bitsThusFar = sortedMembers[idx].width 
            
        self.definition += "\t" + "\t" + "\t" + "default: result = ?;\n"
        self.definition += "\t" + "\t" + "endcase\n"
        self.definition += "\t" + "\t" + "return result;\n"
        self.definition += "\t" + "endfunction\n"

        


class TaggedUnionDecompressor(Code):
    # maybe we can have a better interface later. 
    def __init__(self, connection):
        self.compressable = False
        type = connection.type_structure.type
        if(isinstance(type,TaggedUnion)):
            #We are inside a tagged union, so let's generate some code. 
            self.compressable = True
            self.declaration = "\nlet decompressor" + connection.name + " <- mkDecompressor" + connection.name + "();\n"
            # Do the decompressor 
            self.definition = "\n\nmodule [CONNECTED_MODULE] mkDecompressor" + connection.name + "(Empty);\n" 
            
            # we will have several input links from comms complex, and we need to spec them here

            # First channel is for the index            
            # is this TLog correct?
            width = int(math.ceil(math.log(len(type.members),2)))

            indexChannel = CompressChannel(connection,width,"Idx")
            self.channels = [indexChannel.channel]
            self.definition += "\t" + indexChannel.declaration      
            
            
#PHYSICAL_SEND#(Bit#(PHYSICAL_CONNECTION_SIZE)) send_rrr_server_TESTDRRR_resp <- mkPhysicalConnectionSend("rrr_server_TESTDRRR_resp", tagged Invalid, False, "umf::GENERIC_UMF_PACKET#(umf::GENERIC_UMF_PACKET_HEADER#(4, 8, 4, 15, 1, 0), Bit#(32))", True);

            self.definition += "\t" + "PHYSICAL_SEND#(Bit#(" + str(type.width) + ')) outputConnection <- mkPhysicalConnectionSend("' + connection.name + '", tagged Invalid, False, "' + connection.raw_type + '", True);\n' 
            self.definition += "\t" + "Wire#(Maybe#(Bit#(" + str(width) +"))) attemptInput <- mkDWire(tagged Invalid);\n"  

            # So the issue here is that members may be of various
            # sizes. One way of compressing is to sort them by size
            # this will generate several lanes, but we have to have a
            # way of deciding which lanes contain valid information.
            # Do this based on index (have to build a function for it).



            # first sort the members according to size
            indexFunction = IndexFunction(type.members);



            self.definition += indexFunction.definition

            recvGuard = []
            splitChannels = [CompressChannel(connection,indexFunction.splits[x],str(x)) for x in range(len(indexFunction.splits))]
            self.channels += map(lambda x: x.channel, splitChannels)
            for index in range(len(indexFunction.splits)):
            
                self.definition += "\t" + splitChannels[index].declaration
                self.definition += "\t" +"Wire#(Bit#(" + str(indexFunction.splits[index]) +")) inputConnectionWire" + str(index) + " <- mkDWire(0);\n" 
                recvGuard += ["(" + splitChannels[index].name + ".notEmpty() || index[" + str(index) + "] == 0)" ]
                self.definition += "\t" +"PulseWire attemptInput" + str(index) + " <- mkPulseWire;\n" 
            
                
            if(injectDebug):
                self.definition += "rule decompStatus;\n"; # Only fire if we can do something with the results
                # rule that decides which guys get enqueued
                self.definition += '$display("Decompress outputQueue %b ", outputConnection.notFull);\n';
                for channel in splitChannels:
                    self.definition += '$display("Decompress ' + channel.name + ' %b ", ' + channel.name + '.notEmpty);\n';
                    self.definition += "endrule\n\n";


            self.definition += "\t" + "rule indexDeq(outputConnection.notFull());\n"; # Only fire if we can do something with the results
            self.definition += "\t" + "\t" + "let index = indexer(" + indexChannel.name +  ".receive());\n";
            # we should only set the enables if all values are available.
            self.definition += "\t" + "\t" + "if(" + "&&".join(recvGuard) + ")\n";
            self.definition += "\t" + "\t" + "begin\n";
            if(injectDebug):
                self.definition += "\t" + "\t" + "\t" + '$display("Decompress indexDeq Fires");\n';

            self.definition += "\t" + "\t" + "\t" + "attemptInput <= tagged Valid (" + indexChannel.name +  ".receive());\n";
            self.definition += "\t" + "\t" + "\t" + indexChannel.name +  ".deq();\n";
            for index in range(len(indexFunction.splits)):
                self.definition += "\t" + "\t" + "\t" + "if(index[" + str(index) + "] == 1)\n";
                self.definition += "\t" + "\t" + "\t" + "begin\n";
                self.definition += "\t" + "\t" + "\t" + "\t" + "attemptInput" + str(index) + ".send();\n";
                self.definition += "\t" + "\t" + "\t" + "end\n";
            self.definition += "\t" + "\t" + "end\n";
            self.definition += "\t" + "endrule\n\n";

            # let's mix the results and send the up
            self.definition += "\t" + "rule mixResults(attemptInput matches tagged Valid .idx);\n";
            if(injectDebug):
                self.definition += "\t" + "\t" + '$display("Decompress mixResults Fires");\n';

            wires = ["inputConnectionWire"+str(x) for x in range(len(indexFunction.splits))]


            wires.reverse()
            

            self.definition += "\t" + "\t" + "outputConnection.send({idx," + " , ".join(wires) + "});\n";

            self.definition += "\t" + "endrule\n\n";

                
            for index in range(len(indexFunction.splits)):
                self.definition += "\t" + "rule indexDeq" + str(index) + "(attemptInput" + str(index) + ");\n";
                self.definition += "\t" + "\t" + "inputConnectionWire" + str(index) + " <= " + splitChannels[index].name + ".receive();\n" 
                self.definition += "\t" + "\t" + splitChannels[index].name + ".deq();\n" 

                self.definition += "\t" + "endrule\n\n";

            
            self.definition += "endmodule\n\n";

            indexChannel.channel.code = self

# TODO: At some point, we must take a hoist function so that we can handle non-tagged union types

class TaggedUnionCompressor(Code):
    # maybe we can have a better interface later. 
    def __init__(self, connection):
        self.compressable = False
        type = connection.type_structure.type
        if(isinstance(type,TaggedUnion)):
            #We are inside a tagged union, so let's generate some code. 
            self.compressable = True
            self.declaration = "\nlet compressor" + connection.name + " <- mkCompressor" + connection.name + "();\n"
            # Do the compressor 
            self.definition = "\n\nmodule [CONNECTED_MODULE] mkCompressor" + connection.name + " (Empty);\n" 

            #def __init__(self, sc_type, raw_type, idx, name, platform, optional, bitwidth, modulename, chainroot, type_structure):

            self.definition += "\t" + "CONNECTION_RECV#(Bit#(" + str(type.width) + ')) inputConnection <- mkPhysicalConnectionRecv("' + connection.name + '", tagged Invalid, False, "' + connection.raw_type + '");\n' 

            width = int(math.ceil(math.log(len(type.members),2)))

            indexChannel = CompressChannel(connection,width,"Idx")
            self.channels = [indexChannel.channel]
            self.definition += "\t" + indexChannel.declaration      
            
            indexFunction = IndexFunction(type.members);
            self.definition += indexFunction.definition

            splitChannels = [CompressChannel(connection,indexFunction.splits[x],str(x)) for x in range(len(indexFunction.splits))]

            for index in range(len(indexFunction.splits)):
                self.definition += "\t" + splitChannels[index].declaration
                
            self.channels += map(lambda x: x.channel, splitChannels)

            # let's demux the data and ship it out. 
            outputGuard = " && ".join([x.name+".notFull()" for x in splitChannels])
            self.definition += "\t" + "rule indexEnq(inputConnection.notEmpty());\n"; # Only fire if we can do something with the results
            #grab index
            widthRemaining = type.width - width 
            self.definition += "\t" + "\t" + "Tuple2#(Bit#(" + str(width) + "), Bit#(" + str(widthRemaining) + ")) indexSplit = split(inputConnection.receive());\n";
            self.definition += "\t" + "\t" + "let index = indexer(tpl_1(indexSplit));\n";
            self.definition += "\t" + "\t" + "inputConnection.deq();\n";
            self.definition += "\t" + "\t" + indexChannel.name + ".send(tpl_1(indexSplit));\n";
            if(injectDebug):
                self.definition += "\t" + "\t" + '$display("Compress indexEnq Fires index %b", index);\n';

            offset = 0
            for index in range(len(indexFunction.splits)):
                self.definition += "\t" + "\t" + "if(index[" + str(index) + "] == 1)\n";
                self.definition += "\t" + "\t" + "begin\n";
                nextOffset = offset + indexFunction.splits[index]
                self.definition += "\t" + "\t" + "\t" + splitChannels[index].name + ".send(tpl_2(indexSplit)[" + str(nextOffset -1) + ":" + str(offset) + "]);\n";
                offset = nextOffset 
                self.definition += "\t" + "\t" + "end\n";

            self.definition += "\t" + "endrule\n\n";

            self.definition += "endmodule\n\n";

            indexChannel.channel.code = self
