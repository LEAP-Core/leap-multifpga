// This file is effectively a stub for the generated router code. 

`include "asim/provides/virtual_platform.bsh"
`include "asim/provides/virtual_devices.bsh"
`include "asim/provides/low_level_platform_interface.bsh"
`include "asim/provides/rrr.bsh"
`include "asim/provides/rrr_common.bsh"
`include "asim/provides/umf.bsh"
`include "asim/provides/channelio_common.bsh"
`include "asim/provides/physical_platform.bsh"
`include "asim/provides/soft_connections.bsh"

`include "asim/provides/multifpga_router_service.bsh"

// some useful modules


// At some point we're going to need flow control up here

module mkPacketizeConnectionSend#(Connection_Send#(t_DATA) send, SERVER_REQUEST_PORT port) (Empty)
   provisos(Div#(SizeOf#(t_DATA),SizeOf#(UMF_CHUNK),t_NUM_CHUNKS),
            Bits#(t_DATA, t_DATA_SZ));
   DEMARSHALLER#(UMF_CHUNK, t_DATA) dem <- mkDeMarshaller();  

    rule startRequest (True);
        $display("Send starting request");
        UMF_PACKET packet <- port.read();
        dem.start(fromInteger(valueof(t_NUM_CHUNKS)));
    endrule

    rule continueRequest (True);
        UMF_PACKET packet <- port.read();
        dem.insert(packet.UMF_PACKET_dataChunk);
    endrule

    rule sendData;
        let retval <- dem.readAndDelete();
        send.send(retval);
    endrule

endmodule

module mkPacketizeConnectionReceive#(Connection_Receive#(t_DATA) recv, CLIENT_REQUEST_PORT port, Integer id) (Empty)
   provisos(Div#(SizeOf#(t_DATA),SizeOf#(UMF_CHUNK),t_NUM_CHUNKS),
            Bits#(t_DATA, t_DATA_SZ),
            Add#(t_XXX, TLog#(t_NUM_CHUNKS), 15));

   MARSHALLER#(t_DATA, UMF_CHUNK) mar <- mkMarshaller();

   rule continueRequest (True);
        UMF_CHUNK chunk = mar.first();
        mar.deq();
        port.write(tagged UMF_PACKET_dataChunk chunk);
   endrule

   rule startRequest;
       $display("Receive starting request");
       UMF_PACKET header = tagged UMF_PACKET_header UMF_PACKET_HEADER
                            {
                                filler: ?,
                                phyChannelPvt: ?,
                                channelID: ?,
                                serviceID: fromInteger(id),
                                methodID : ?,
                                numChunks: fromInteger(valueof(t_NUM_CHUNKS))
                            };
        port.write(header);
        recv.deq;
        mar.enq(recv.receive, fromInteger(valueof(t_NUM_CHUNKS)));
   endrule
endmodule


`ifdef ROUTING_KNOWN
    `include "multifpga_routing.bsh"
`else
    // define a null routing module
     module [CONNECTED_MODULE] mkCommunicationModule#(VIRTUAL_PLATFORM vplat) (Empty);
         // Intentionally empty
     endmodule
`endif
 
//XXX insert module for creating umf packets here.



module [CONNECTED_MODULE] mkMultifpgaRouterServices#(VIRTUAL_PLATFORM vplat) (Empty);
  let m <- mkCommunicationModule(vplat);
endmodule 