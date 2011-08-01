// This file is effectively a stub for the generated router code. 

`include "asim/provides/virtual_platform.bsh"
`include "asim/provides/virtual_devices.bsh"
`include "asim/provides/low_level_platform_interface.bsh"
`include "asim/provides/rrr.bsh"
`include "asim/provides/umf.bsh"
`include "asim/provides/channelio.bsh"
`include "asim/provides/physical_platform.bsh"
`include "asim/provides/soft_connections.bsh"
`include "asim/provides/librl_bsv_base.bsh"
`include "asim/provides/librl_bsv_storage.bsh"
`include "asim/provides/multifpga_switch.bsh"

`include "asim/provides/multifpga_router_service.bsh"

import Vector::*;

// some useful modules
interface MARSHALLER#(numeric type n, type data);
  method Action enq(Vector#(n,data) vec);
  method Action deq();
  method data first();
  method Bool notFull();
endinterface

interface DEMARSHALLER#(numeric type n, type data);
  method Action enq(data dat);
  method Action deq();
  method Vector#(n,data) first();
  method Bool notEmpty();
endinterface

module mkSimpleMarshaller (MARSHALLER#(n,data))
   provisos(Bits#(data, data_sz));

  Reg#(Vector#(n,data)) buffer <- mkRegU();
  Reg#(Bit#(TAdd#(1,TLog#(n)))) count <- mkReg(0);

  method Action enq(Vector#(n,data) vec) if(count == 0);
    count <= fromInteger(valueof(n));
    buffer <= vec; 
  endmethod

  method Action deq() if(count > 0);
    Vector#(1,data) dummy = newVector();
    buffer <= takeTail(append(buffer,dummy));
    count <= count - 1;
  endmethod

  method data first() if(count > 0);
    return buffer[0];
  endmethod

  method Bool notFull();
    return count == 0;
  endmethod
endmodule

module mkSimpleDemarshaller (DEMARSHALLER#(n,data))
   provisos(Bits#(data, data_sz));

  Reg#(Vector#(n,data)) buffer <- mkRegU();
  Reg#(Bit#(TAdd#(1,TLog#(n)))) count <- mkReg(0);

  method Action enq(data dat) if(count != fromInteger(valueof(n)));
    Vector#(1,data) highVal = replicate(dat);
    count <= count + 1;
    buffer <= takeTail(append(buffer,highVal));
  endmethod

  method Action deq() if(count == fromInteger(valueof(n)));
    count <= 0;
  endmethod

  method Vector#(n,data) first() if(count == fromInteger(valueof(n)));
    return buffer;
  endmethod

  method Bool notEmpty();
    return count == fromInteger(valueof(n));
  endmethod
endmodule

module mkPacketizeConnectionSend#(Connection_Send#(t_DATA) send, SWITCH_INGRESS_PORT port, NumTypeParam#(bitwidth) width) (Empty)
   provisos(Div#(SizeOf#(t_DATA),SizeOf#(UMF_CHUNK),t_NUM_CHUNKS),
            Bits#(t_DATA, t_DATA_SZ),
            Add#(fill_EXTRA, UMF_PACKET_HEADER_FILLER_BITS, t_DATA_SZ),
            Add#(n_EXTRA_SZ, t_DATA_SZ, TMul#(t_NUM_CHUNKS, SizeOf#(UMF_CHUNK))),
            Add#(n_DATA_EXTRA, SizeOf#(UMF_CHUNK), t_DATA_SZ));

  Empty m = ?;
       //messageM("Choosing packetizer numChunks: " + integerToString(valueof(t_NUM_CHUNKS))  + " width: "+ integerToString(valueof(bitwidth)) + " is less than " + integerToString(valueof(UMF_PACKET_HEADER_FILLER_BITS)));
  if(valueof(bitwidth) <= valueof(SizeOf#(UMF_CHUNK))) // don't instantiate a marshaller!
    begin
      m <- mkPacketizeConnectionSendUnmarshalled(send,port,width);
    end
  else
    begin
      m <- mkPacketizeConnectionSendMarshalled(send,port);
    end

  return m;
endmodule

// At some point we're going to need flow control up here
// We may not need marsh/demarsh!!!!  If all connections are the CHUNK size!
module mkPacketizeConnectionSendMarshalled#(Connection_Send#(t_DATA) send, SWITCH_INGRESS_PORT port) (Empty)
   provisos(Div#(SizeOf#(t_DATA),SizeOf#(UMF_CHUNK),t_NUM_CHUNKS),
            Bits#(t_DATA, t_DATA_SZ),
            Add#(n_EXTRA_SZ, t_DATA_SZ, TMul#(t_NUM_CHUNKS, SizeOf#(UMF_CHUNK))));

    Reg#(Bool) waiting <- mkReg(True);
    DEMARSHALLER#(t_NUM_CHUNKS, UMF_CHUNK) dem <- mkSimpleDemarshaller();  

    rule sendReady(waiting || send.notFull());
      port.read_ready();
    endrule

    rule startRequest (waiting);
        UMF_PACKET packet <- port.read();
        //$display("Connection RX starting request dataSz: %d chunkSz: %d type:  %d listed: %d", valueof(t_DATA_SZ), valueof(SizeOf#(UMF_CHUNK)) ,packet.UMF_PACKET_header.numChunks, fromInteger(valueof(t_NUM_CHUNKS)));
        waiting <= False;
    endrule

    rule continueRequest (!waiting);
        UMF_PACKET packet <- port.read();
        dem.enq(packet.UMF_PACKET_dataChunk);
        //$display("Connection RX receives: %h", packet.UMF_PACKET_dataChunk);
    endrule

    rule sendData(!waiting && send.notFull());
        dem.deq();
        send.send(unpack(truncate(pack(dem.first))));
        //$display("Connection RX spits out: %h", dem.first);
        waiting <= True;
    endrule

endmodule

module mkPacketizeConnectionSendUnmarshalled#(Connection_Send#(t_DATA) send, SWITCH_INGRESS_PORT port, NumTypeParam#(bitwidth) width) (Empty)
   provisos(Bits#(t_DATA, t_DATA_SZ),
            Add#(fill_EXTRA, UMF_PACKET_HEADER_FILLER_BITS, t_DATA_SZ),
            Add#(n_EXTRA_SZ, SizeOf#(UMF_CHUNK), t_DATA_SZ));

   if(valueof(bitwidth) < valueof(UMF_PACKET_HEADER_FILLER_BITS))
     begin
       //messageM("Choosing efficient small bit packetizer " + integerToString(valueof(bitwidth)) + " is less than " + integerToString(valueof(UMF_PACKET_HEADER_FILLER_BITS)));
       
       rule sendReady(send.notFull());
         port.read_ready();
       endrule
       rule continueRequest(send.notFull());
         UMF_PACKET packet <- port.read(); 
         //$display("Small guy gets %h", packet.UMF_PACKET_header.filler);
         send.send(unpack(zeroExtend(packet.UMF_PACKET_header.filler)));
       endrule
     end
   else
     begin
       Reg#(Bool) waiting <- mkReg(True);

       rule sendReady(waiting || send.notFull());
         port.read_ready();
       endrule

       rule startRequest (waiting);
         UMF_PACKET packet <- port.read();
         //$display("Connection RX starting request dataSz: %d chunkSz: %d type:  %d listed: %d", valueof(t_DATA_SZ), valueof(SizeOf#(UMF_CHUNK)) ,packet.UMF_PACKET_header.numChunks, fromInteger(valueof(t_NUM_CHUNKS)));
         waiting <= False;
       endrule

       rule continueRequest (!waiting);
         UMF_PACKET packet <- port.read();
         send.send(unpack(zeroExtend(pack(packet.UMF_PACKET_dataChunk))));
         //$display("Connection RX receives: %h", packet.UMF_PACKET_dataChunk);
         waiting <= True;
       endrule
     end
endmodule


module mkPacketizeConnectionReceive#(Connection_Receive#(t_DATA) recv, SWITCH_EGRESS_PORT port, 
                                     Integer id, NumTypeParam#(bitwidth) width) (Empty)
   provisos(Div#(SizeOf#(t_DATA),SizeOf#(UMF_CHUNK),t_NUM_CHUNKS),
            Bits#(t_DATA, t_DATA_SZ),
	    Add#(n_EXTRA_SZ, t_DATA_SZ, TMul#(t_NUM_CHUNKS, SizeOf#(UMF_CHUNK))),
            Add#(fill_EXTRA, UMF_PACKET_HEADER_FILLER_BITS, t_DATA_SZ),
            Add#(n_CHUNK_EXTRA_SZ, SizeOf#(UMF_CHUNK), t_DATA_SZ));

  Empty m = ?;
  if(valueof(bitwidth) <= valueof(SizeOf#(UMF_CHUNK))) // don't instantiate a marshaller!
    begin
      m <- mkPacketizeConnectionReceiveUnmarshalled(recv,port, id, width);
    end
  else
    begin
      m <- mkPacketizeConnectionReceiveMarshalled(recv,port,id);
    end

  return m;
endmodule


module mkPacketizeConnectionReceiveMarshalled#(Connection_Receive#(t_DATA) recv, SWITCH_EGRESS_PORT port, Integer id) (Empty)
   provisos(Div#(SizeOf#(t_DATA),SizeOf#(UMF_CHUNK),t_NUM_CHUNKS),
            Bits#(t_DATA, t_DATA_SZ),
	    Add#(n_EXTRA_SZ, t_DATA_SZ, TMul#(t_NUM_CHUNKS, SizeOf#(UMF_CHUNK))));

   MARSHALLER#(t_NUM_CHUNKS, UMF_CHUNK) mar <- mkSimpleMarshaller();

   rule continueRequest (True);
        UMF_CHUNK chunk = mar.first();
        mar.deq();
        port.write(tagged UMF_PACKET_dataChunk chunk);
        // $display("Connection TX sends: %h", chunk);
   endrule

   rule startRequest (recv.notEmpty());
       //$display("Connection TX starting request dataSz: %d chunkSz: %d  listed: %d", valueof(t_DATA_SZ), valueof(SizeOf#(UMF_CHUNK)) , fromInteger(valueof(t_NUM_CHUNKS)));
       UMF_PACKET header = tagged UMF_PACKET_header UMF_PACKET_HEADER
                            {
                                filler: ?,
                                phyChannelPvt: ?,
                                channelID: 0, // we use this elsewhere to refer to flow control messages
                                serviceID: fromInteger(id),
                                methodID : ?, 
                                numChunks: fromInteger(valueof(t_NUM_CHUNKS))
                            };
        port.write(header);
        recv.deq;
        mar.enq(unpack(zeroExtend(pack(recv.receive))));
   endrule
endmodule

module mkPacketizeConnectionReceiveUnmarshalled#(Connection_Receive#(t_DATA) recv, SWITCH_EGRESS_PORT port, Integer id, NumTypeParam#(bitwidth) width) (Empty)
   provisos(/*Div#(SizeOf#(t_DATA),SizeOf#(UMF_CHUNK),t_NUM_CHUNKS),*/
            Bits#(t_DATA, t_DATA_SZ),
            Add#(n_CHUNK_EXTRA_SZ, SizeOf#(UMF_CHUNK), t_DATA_SZ),
            Add#(fill_EXTRA, UMF_PACKET_HEADER_FILLER_BITS, t_DATA_SZ));

   // Is the bitwidth sufficient to fint into the header?
   if(valueof(bitwidth) < valueof(UMF_PACKET_HEADER_FILLER_BITS))
     begin
       //messageM("Choosing efficient small bit packetizer " + integerToString(valueof(bitwidth)) + " is less than " + integerToString(valueof(UMF_PACKET_HEADER_FILLER_BITS))); 
       rule startRequest(recv.notEmpty);
         recv.deq;
         UMF_PACKET header = tagged UMF_PACKET_header UMF_PACKET_HEADER
                            {
                                filler: truncate(pack(recv.receive)),  // Woot
                                phyChannelPvt: ?,
                                channelID: 0, // we use this elsewhere to refer to flow control messages
                                serviceID: fromInteger(id),
                                methodID : ?,
                                numChunks: 0
                            };
          //$display("Small guy sends %h", header.UMF_PACKET_header.filler);

          port.write(header);
        endrule
     end
   else
     begin
       Reg#(Bool) waitHeader <- mkReg(True);

       rule continueRequest (!waitHeader);
         UMF_CHUNK chunk = truncate(pack(recv.receive));
         recv.deq();
         waitHeader <= True;
         port.write(tagged UMF_PACKET_dataChunk chunk);
         // $display("Connection TX sends: %h", chunk);
       endrule

       rule startRequest (recv.notEmpty && waitHeader);
         //$display("Connection TX starting request dataSz: %d chunkSz: %d  listed: %d", valueof(t_DATA_SZ), valueof(SizeOf#(UMF_CHUNK)) , fromInteger(valueof(t_NUM_CHUNKS)));
         UMF_PACKET header = tagged UMF_PACKET_header UMF_PACKET_HEADER
                            {
                                filler: ?,
                                phyChannelPvt: ?,
                                channelID: 0, // we use this elsewhere to refer to flow control messages
                                serviceID: fromInteger(id),
                                methodID : ?, 
                                numChunks: 1
                            };
          port.write(header);
          waitHeader <= False;
        endrule
      end
endmodule

// At some point we're going to need flow control up here
// We may not need marsh/demarsh!!!!  If all connections are the CHUNK size!
module mkPacketizeOutgoingChain#(SWITCH_INGRESS_PORT port) (PHYSICAL_CHAIN_OUT)
   provisos(Div#(SizeOf#(PHYSICAL_CHAIN_DATA),SizeOf#(UMF_CHUNK),t_NUM_CHUNKS),
            Add#(n_EXTRA_SZ, SizeOf#(PHYSICAL_CHAIN_DATA), TMul#(t_NUM_CHUNKS, SizeOf#(UMF_CHUNK))));

    Reg#(Bool) waiting <- mkReg(True);
    DEMARSHALLER#(t_NUM_CHUNKS, UMF_CHUNK) dem <- mkSimpleDemarshaller();  

    rule sendReady(waiting || !dem.notEmpty());
      port.read_ready();
    endrule

    rule startRequest (waiting);
        UMF_PACKET packet <- port.read();
        //$display("Chain RX starting request type:  %d listed: %d", packet.UMF_PACKET_header.numChunks, fromInteger(valueof(t_NUM_CHUNKS)));
        waiting <= False;
    endrule

    rule continueRequest (!waiting);
        UMF_PACKET packet <- port.read();
        dem.enq(packet.UMF_PACKET_dataChunk);
        //$display("Chain RX receives: %h", packet.UMF_PACKET_dataChunk);
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



module mkPacketizeIncomingChain#(SWITCH_EGRESS_PORT port, Integer id) (PHYSICAL_CHAIN_IN)
   provisos(Div#(SizeOf#(PHYSICAL_CHAIN_DATA),SizeOf#(UMF_CHUNK),t_NUM_CHUNKS),
	    Add#(n_EXTRA_SZ, SizeOf#(PHYSICAL_CHAIN_DATA), TMul#(t_NUM_CHUNKS, SizeOf#(UMF_CHUNK))));

   MARSHALLER#(t_NUM_CHUNKS, UMF_CHUNK) mar <- mkSimpleMarshaller();
   RWire#(PHYSICAL_CHAIN_DATA) tryData <- mkRWire();
   PulseWire trySuccess <- mkPulseWire();

   rule continueRequest (True);
        UMF_CHUNK chunk = mar.first();
        mar.deq();
        port.write(tagged UMF_PACKET_dataChunk chunk);
        //$display("Chain TX sends: %h", chunk);
   endrule

   rule startRequest (tryData.wget() matches tagged Valid .data);
       //$display("Chain TX starting request listed: %d",  fromInteger(valueof(t_NUM_CHUNKS)));
       UMF_PACKET header = tagged UMF_PACKET_header UMF_PACKET_HEADER
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
