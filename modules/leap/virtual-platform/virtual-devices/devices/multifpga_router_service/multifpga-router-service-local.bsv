// This file is effectively a stub for the generated router code. 

`include "awb/provides/virtual_platform.bsh"
`include "awb/provides/virtual_devices.bsh"
`include "awb/provides/low_level_platform_interface.bsh"
`include "awb/provides/rrr.bsh"
`include "awb/provides/umf.bsh"
`include "awb/provides/channelio.bsh"
`include "awb/provides/physical_platform.bsh"
`include "awb/provides/soft_connections.bsh"
`include "awb/provides/librl_bsv_base.bsh"
`include "awb/provides/librl_bsv_storage.bsh"
`include "awb/provides/multifpga_switch.bsh"
`include "awb/provides/stats_service.bsh"
`include "awb/provides/librl_bsv_storage.bsh"
`include "awb/provides/librl_bsv_base.bsh"

`include "awb/provides/multifpga_router_service.bsh"

// At some point we're going to need flow control up here
// We may not need marsh/demarsh!!!!  If all connections are the CHUNK size!
module mkPacketizeConnectionSendMarshalled#(Connection_Send#(t_DATA) send, SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk)) port, Integer id, NumTypeParam#(bitwidth) width, STAT received) (Empty)
   provisos(Bits#(t_DATA, t_DATA_SZ),
            Div#(TSub#(t_DATA_SZ, filler_bits),SizeOf#(umf_chunk),t_NUM_CHUNKS),
            Add#(n_EXTRA_SZ_2, t_DATA_SZ, TAdd#(TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk)), filler_bits)),
            Add#(n_EXTRA_SZ, TSub#(t_DATA_SZ, filler_bits), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

    Reg#(Bool) waiting <- mkReg(True);
    Reg#(Bit#(filler_bits)) fillerBits <- mkReg(?);
 
    DEMARSHALLER#(t_NUM_CHUNKS, umf_chunk) dem <- mkSimpleDemarshaller();  

    rule sendReady(waiting || send.notFull());
      port.read_ready();
    endrule

    rule startRequest (waiting);
        GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
        //$display("Connection RX starting request dataSz: %d chunkSz: %d type:  %d listed: %d", valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) ,packet.UMF_PACKET_header.numChunks, fromInteger(valueof(t_NUM_CHUNKS)));
        waiting <= False;
        fillerBits <= packet.UMF_PACKET_header.filler;        
        received.incr();
    endrule

    rule continueRequest (!waiting);
        GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
        dem.enq(packet.UMF_PACKET_dataChunk);
        received.incr();
        //$display("Connection RX receives: %h", packet.UMF_PACKET_dataChunk);
    endrule

    // Lurking latency here...
    // Should try to fix at some point. 
    rule sendData(!waiting && send.notFull());
        dem.deq();
        send.send(unpack(truncate({pack(dem.first),fillerBits})));
        if(`SWITCH_DEBUG == 1)
          begin
            $display("Connection RX %d emits out: %h", id, dem.first);
          end
        waiting <= True;         
    endrule

endmodule

module mkPacketizeConnectionSendUnmarshalled#(Connection_Send#(t_DATA) send, SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk)) port, Integer id, NumTypeParam#(bitwidth) width, STAT received) (Empty)
   provisos(Bits#(t_DATA, t_DATA_SZ),
            Bits#(umf_chunk,umf_chunk_SZ)
            /*Add#(fill_EXTRA, filler_bits, t_DATA_SZ),
            Add#(n_EXTRA_SZ, SizeOf#(umf_chunk), t_DATA_SZ)*/);

   if(valueof(bitwidth) < valueof(filler_bits))
     begin
       //messageM("Choosing efficient small bit packetizer " + integerToString(valueof(bitwidth)) + " is less than " + integerToString(valueof(filler_bits)));
       
       rule sendReady(send.notFull());
         port.read_ready();
       endrule

       rule continueRequest(send.notFull());
         GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read(); 
         //$display("Small guy gets %h", packet.UMF_PACKET_header.filler);
         Bit#(bitwidth) value = truncateNP(packet.UMF_PACKET_header.filler);
         t_DATA data = (unpack(resize(value)));
         send.send(data);
         received.incr();

         if(`SWITCH_DEBUG == 1)
         begin
           $display("Our packet is: channel %d, service %d, method %d, message %d, phy %d, filler %d", valueof(umf_channel_id), valueof(umf_service_id), valueof(umf_method_id), valueof(umf_message_len), valueof(umf_phy_pvt), valueof(filler_bits));
           $display("Connection RX %d (HO) emits out: %h", id, data);
         end
       endrule
     end
   else
     begin
       Reg#(Bool) waiting <- mkReg(True);

       rule sendReady(waiting || send.notFull());
         port.read_ready();
       endrule

       rule startRequest (waiting);
         GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
         //$display("Connection RX starting request dataSz: %d chunkSz: %d type:  %d listed: %d", valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) ,packet.UMF_PACKET_header.numChunks, fromInteger(valueof(t_NUM_CHUNKS)));
         if(`SWITCH_DEBUG == 1)
         begin
             $display("Our packet is: channel %d, service %d, method %d, message %d, phy %d, filler %d", valueof(umf_channel_id), valueof(umf_service_id), valueof(umf_method_id), valueof(umf_message_len), valueof(umf_phy_pvt), valueof(filler_bits));
         end

         waiting <= False;
         received.incr();
       endrule

       rule continueRequest (!waiting && send.notFull());
         GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
         t_DATA data = unpack(resize(pack(packet.UMF_PACKET_dataChunk)));
         send.send(data);
         waiting <= True;
         received.incr();
         if(`SWITCH_DEBUG == 1)
         begin
             $display("Connection RX %d (S) emits out: %h", id, data);
         end
       endrule
     end
endmodule

module mkPacketizeConnectionReceiveMarshalled#(Connection_Receive#(t_DATA) recv, SWITCH_EGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk)) port, Integer id, 
                                               NumTypeParam#(bitwidth) width,
                                               STAT blocked, STAT sent) (Empty)
   provisos(Bits#(t_DATA, t_DATA_SZ),
            Div#(TSub#(t_DATA_SZ,filler_bits),SizeOf#(umf_chunk),t_NUM_CHUNKS),
            Add#(filler_EXTRA_SZ, filler_bits, t_DATA_SZ),
            Add#(n_EXTRA_SZ_2, t_DATA_SZ, TAdd#(TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk)), filler_bits)),
	    Add#(n_EXTRA_SZ, TSub#(t_DATA_SZ,filler_bits), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

   PulseWire continueRequestFired <- mkPulseWire(); 
   PulseWire startRequestFired <- mkPulseWire(); 

   MARSHALLER#(t_NUM_CHUNKS, umf_chunk) mar <- mkSimpleMarshaller();
   
   rule continueRequest (True);
        umf_chunk chunk = mar.first();
        mar.deq();
        sent.incr();
        port.write(tagged UMF_PACKET_dataChunk chunk);
        if(`SWITCH_DEBUG == 1)
          begin
            $display("Marshalled Connection TX sends: %h", chunk);
          end

        continueRequestFired.send();
   endrule

   rule checkBlocked(recv.notEmpty() && !(continueRequestFired || startRequestFired));
     blocked.incr();
   endrule

   rule startRequest (recv.notEmpty());
       sent.incr();
       startRequestFired.send();
       Tuple2#(Bit#(TSub#(t_DATA_SZ,filler_bits)),Bit#(filler_bits)) data_split = split(pack(recv.receive));
       mar.enq(unpack(zeroExtend(tpl_1(data_split))));
       GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) header = tagged UMF_PACKET_header GENERIC_UMF_PACKET_HEADER
                            {
                                filler: tpl_2(data_split),
                                phyChannelPvt: ?,
                                channelID: 0, // we use this elsewhere to refer to flow control messages
                                serviceID: fromInteger(id),
                                methodID : ?, 
                                numChunks: fromInteger(valueof(t_NUM_CHUNKS))
                            };
        port.write(header);
        recv.deq;
        if(`SWITCH_DEBUG == 1)
        begin
            $display("Connection TX %d  emits out: %h", id, recv.receive);
        end

    
   endrule
endmodule

module mkPacketizeConnectionReceiveUnmarshalled#(Connection_Receive#(t_DATA) recv, SWITCH_EGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk)) port, Integer id, NumTypeParam#(bitwidth) width,  STAT blocked, STAT sent) (Empty)
   provisos(/*Div#(SizeOf#(t_DATA),SizeOf#(umf_chunk),t_NUM_CHUNKS),*/
            Bits#(t_DATA, t_DATA_SZ),
            Bits#(umf_chunk,umf_chunk_SZ));

   // Is the bitwidth sufficient to fint into the header?
   if(valueof(bitwidth) < valueof(filler_bits))
     begin
       messageM("Choosing efficient small bit packetizer " + integerToString(valueof(bitwidth)) + " is less than " + integerToString(valueof(filler_bits)));
     
       PulseWire startRequestFired <- mkPulseWire();  
 
       rule checkBlocked(recv.notEmpty() && !(startRequestFired));
         blocked.incr();
       endrule

       rule startRequest(recv.notEmpty); 
         recv.deq;
         sent.incr();
         startRequestFired.send();
         Bit#(bitwidth) value = resize(pack(recv.receive));
         GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) header = tagged UMF_PACKET_header GENERIC_UMF_PACKET_HEADER
                            {
                                filler: zeroExtendNP(value),  // Woot
                                phyChannelPvt: ?,
                                channelID: 0, // we use this elsewhere to refer to flow control messages
                                serviceID: fromInteger(id),
                                methodID : ?,
                                numChunks: 0
                            };

          if(`SWITCH_DEBUG == 1)
          begin
              $display("Connection TX %d (HO)  emits out: %h", id, recv.receive);
              $display("Small guy sends %h", header.UMF_PACKET_header.filler);
              $display("Our packet is: channel %d, service %d, method %d, message %d, phy %d, filler %d", valueof(umf_channel_id), valueof(umf_service_id), valueof(umf_method_id), valueof(umf_message_len), valueof(umf_phy_pvt), valueof(filler_bits));
          end

          port.write(header);
        endrule
     end
   else
     begin
       Reg#(Bool) waitHeader <- mkReg(True);
       PulseWire continueRequestFired <- mkPulseWire(); 
       PulseWire startRequestFired <- mkPulseWire(); 

       rule checkBlocked(recv.notEmpty() && !(continueRequestFired || startRequestFired));
         blocked.incr();
       endrule

       rule continueRequest (!waitHeader && recv.notEmpty);
         umf_chunk chunk = unpack(resize(pack(recv.receive)));
         recv.deq();
         if(`SWITCH_DEBUG == 1)
         begin
             $display("Connection TX %d (S)  emits out: %h", id, recv.receive);
         end

         waitHeader <= True;
         port.write(tagged UMF_PACKET_dataChunk chunk);
         if(`SWITCH_DEBUG == 1)
         begin
             $display("Unmarshalled Rev Connection TX sends: %h", chunk);
         end

         sent.incr();
         continueRequestFired.send();
       endrule

       rule startRequest (recv.notEmpty && waitHeader);
         sent.incr();
         startRequestFired.send();
         if(`SWITCH_DEBUG == 1)
         begin
             $display("Unmarshalled Recv Connection TX starting request dataSz: %d chunkSz: %d  listed: %d", valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) , fromInteger(valueof(bitwidth)));
         end

         GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) header = tagged UMF_PACKET_header GENERIC_UMF_PACKET_HEADER
                            {
                                filler: ?,
                                phyChannelPvt: ?,
                                channelID: 0, // we use this elsewhere to refer to flow control messages
                                serviceID: fromInteger(id),
                                methodID : ?, 
                                numChunks: 1
                            };
          if(`SWITCH_DEBUG == 1)
          begin
              $display("Our packet is: channel %d, service %d, method %d, message %d, phy %d, filler %d", valueof(umf_channel_id), valueof(umf_service_id), valueof(umf_method_id), valueof(umf_message_len), valueof(umf_phy_pvt), valueof(filler_bits));
          end

          port.write(header);
          waitHeader <= False;
        endrule
      end
endmodule

// At some point we're going to need flow control up here
// We may not need marsh/demarsh!!!!  If all connections are the CHUNK size!
module mkPacketizeOutgoingChain#(SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk)) port, STAT received) (PHYSICAL_CHAIN_OUT)
   provisos(Div#(SizeOf#(PHYSICAL_CHAIN_DATA),SizeOf#(umf_chunk),t_NUM_CHUNKS),
            Add#(n_EXTRA_SZ, SizeOf#(PHYSICAL_CHAIN_DATA), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

    Reg#(Bool) waiting <- mkReg(True);
    DEMARSHALLER#(t_NUM_CHUNKS, umf_chunk) dem <- mkSimpleDemarshaller();  

    rule sendReady(waiting || !dem.notEmpty()); 
      port.read_ready();
    endrule

    rule startRequest (waiting);
        GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
        //$display("Chain RX starting request type:  %d listed: %d", packet.UMF_PACKET_header.numChunks, fromInteger(valueof(t_NUM_CHUNKS)));
        waiting <= False;
        received.incr();
    endrule

    rule continueRequest (!waiting);
        GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
        dem.enq(packet.UMF_PACKET_dataChunk);
        //$display("Chain RX receives: %h", packet.UMF_PACKET_dataChunk);
	received.incr();
    endrule

    let myClock <- exposeCurrentClock;
    let myReset <- exposeCurrentReset;

    interface clock = myClock;
    interface reset = myReset;

    method Action deq();
      dem.deq;
      waiting <= True;
    endmethod

    method PHYSICAL_CHAIN_DATA first = unpack(truncate(pack(dem.first)));
    method Bool notEmpty() = dem.notEmpty;

endmodule



module mkPacketizeIncomingChain#(SWITCH_EGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk)) port, Integer id,  STAT blocked, STAT sent) (PHYSICAL_CHAIN_IN)
   provisos(Div#(SizeOf#(PHYSICAL_CHAIN_DATA),SizeOf#(umf_chunk),t_NUM_CHUNKS),
	    Add#(n_EXTRA_SZ, SizeOf#(PHYSICAL_CHAIN_DATA), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

   MARSHALLER#(t_NUM_CHUNKS, umf_chunk) mar <- mkSimpleMarshaller();
   RWire#(PHYSICAL_CHAIN_DATA) tryData <- mkRWire();
   PulseWire trySuccess <- mkPulseWire();
   PulseWire continueRequestFired <- mkPulseWire(); 

   rule checkBlocked((mar.notEmpty() && (!continueRequestFired)) || (isValid(tryData.wget) && !trySuccess));
     blocked.incr();
   endrule

   rule continueRequest (True);
        umf_chunk chunk = mar.first();
        mar.deq();
        port.write(tagged UMF_PACKET_dataChunk chunk);
        sent.incr();
        continueRequestFired.send;
        //$display("Chain TX sends: %h", chunk);
   endrule

   rule startRequest (tryData.wget() matches tagged Valid .data);
       //$display("Chain TX starting request listed: %d",  fromInteger(valueof(t_NUM_CHUNKS)));
       GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) header = tagged UMF_PACKET_header GENERIC_UMF_PACKET_HEADER
                            {
                                filler: ?,
                                phyChannelPvt: ?,
                                channelID: 0, // we use this elsewhere to refer to flow control messages
                                serviceID: fromInteger(id),
                                methodID : ?,
                                numChunks: fromInteger(valueof(t_NUM_CHUNKS))
                            };
        port.write(header);
        trySuccess.send;
        sent.incr();
        mar.enq(unpack(zeroExtend(pack(data))));
   endrule

  let myClock <- exposeCurrentClock;
  let myReset <- exposeCurrentReset;

  interface clock = myClock;
  interface reset = myReset;
 
  method Bool success() = trySuccess;
  method Action try(PHYSICAL_CHAIN_DATA d);
    tryData.wset(d);     
  endmethod
endmodule
