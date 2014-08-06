//
// Copyright (c) 2014, Intel Corporation
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
// Redistributions of source code must retain the above copyright notice, this
// list of conditions and the following disclaimer.
//
// Redistributions in binary form must reproduce the above copyright notice,
// this list of conditions and the following disclaimer in the documentation
// and/or other materials provided with the distribution.
//
// Neither the name of the Intel Corporation nor the names of its contributors
// may be used to endorse or promote products derived from this software
// without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.
//


/******** 
 * This file contains the glue modules for connecting user connections (i.e. sends and receives)
 * to the multiplexed interFPGA communication complex.  This code is used by the multifpga_routing.bsh
 * file generated at compile time and should not appear in user applications. 
 *
 */

import Vector::*;

`include "awb/provides/umf.bsh"
`include "awb/provides/channelio.bsh"
`include "awb/provides/physical_platform.bsh"
`include "awb/provides/soft_connections.bsh"
`include "awb/provides/librl_bsv_base.bsh"
`include "awb/provides/librl_bsv_storage.bsh"
`include "awb/provides/multifpga_switch.bsh"
`include "awb/provides/stats_service.bsh"
`include "awb/provides/multifpga_router_service.bsh"

typedef function m#(Empty) f(PHYSICAL_SEND#(PHYSICAL_CHAIN_DATA) send) SEND_PACKETIZER_CONSTRUCTOR#(type m);
typedef function m#(t) f(Connection_Receive#(PHYSICAL_CHAIN_DATA) recv) RECV_PACKETIZER_CONSTRUCTOR#(type m, type t);

// *******
// * Point to Point Code
// *
// * The following are flavors of point to point links that plug in to the multiplexed inter-fpga communication complex.
// * Different implementations are needed to deal with narrow-data width optimizations - the provisos for the different 
// * cases are impossible to resolve into a unified set.  Notice that Send/Receive polarity is reversed - it is the opposite
// * the user code.  
// *******


module mkPacketizeConnectionSendNoPack#(String name, 
                                        SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                                         umf_channel_id, umf_service_id,
                                                                                         umf_method_id,  umf_message_len,
                                                                                         umf_phy_pvt,    filler_bits), 
                                                                     umf_chunk)) port, 
                                        Integer id, 
                                        NumTypeParam#(bitwidth) width, 
                                        function Action statIncrReceived(), 
                                        PHYSICAL_SEND#(t_DATA) send) (Empty)
   provisos(Bits#(t_DATA, t_DATA_SZ),
            Div#(bitwidth,SizeOf#(umf_chunk),t_NUM_CHUNKS),
            Add#(n_EXTRA_SZ_2, bitwidth, TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))),
            Add#(TAdd#(t_NUM_CHUNKS,1), 0, t_WORD_CHUNKS), // we already add the header in here..
            Add#(TMul#(t_WORD_CHUNKS,`CON_BUFFERING), 0, t_BUFFER_CHUNKS),
            Add#(n_EXTRA_SZ_2, bitwidth, TAdd#(SizeOf#(umf_chunk), TMul#(TSub#(t_NUM_CHUNKS, 1), SizeOf#(umf_chunk)))),
            Add#(n_EXTRA_SZ, bitwidth, TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

     Reg#(Bool) waiting <- mkReg(True);
 
     COUNTER#(TLog#(TAdd#(1,t_BUFFER_CHUNKS))) tokens <- mkLCounter(0);

     DEMARSHALLER#(umf_chunk, Vector#(TSub#(t_NUM_CHUNKS,1), umf_chunk)) dem <- mkSimpleDemarshaller();  

     if(`MARSHALLING_DEBUG == 1)
     begin
         rule view(tokens.value > 0);
             $display("%s has value %d a multiple of %d? %d filler 0chunks %d width", 
                      name, tokens.value, valueof(t_WORD_CHUNKS), 
                      valueof(t_NUM_CHUNKS), valueof(SizeOf#(umf_chunk)));
         endrule
     end

     (* execution_order = "sendReady, enqTok" *) 

     rule sendReady(tokens.value < fromInteger(valueof(t_BUFFER_CHUNKS)));
         port.read_ready();
     endrule

     rule enqTok(port.read_allocated());
         if(`MARSHALLING_DEBUG == 1)
         begin
             $display("%s has value up by %d?", name, 1);
         end

         tokens.up();
     endrule

     rule returnTokens(send.dequeued);
         if(`MARSHALLING_DEBUG == 1)
         begin
   	     $display("%s has value down by %d?", name, valueof(t_WORD_CHUNKS));
         end

         tokens.downBy(fromInteger(valueof(t_WORD_CHUNKS)));
     endrule

     rule startRequest (waiting);
         GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                             umf_channel_id, umf_service_id,
                             umf_method_id,  umf_message_len,
                             umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
         if(`MARSHALLING_DEBUG == 1)
         begin
             $display("Send NoPack %s Data Header: %h", name, pack(packet));
             $display("NoPack Connection %s RX starting request dataSz: %d chunkSz: %d type:  %d listed: %d", name, valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) ,packet.UMF_PACKET_header.numChunks, fromInteger(valueof(t_NUM_CHUNKS)));
         end

         if(packet.UMF_PACKET_header.numChunks != fromInteger(valueof(t_NUM_CHUNKS)))
         begin
             $display("Send NoPack Connection %s RX starting request header: %h dataSz: %d chunkSz: %d header chunks:  %d expected chunks: %d", name, packet.UMF_PACKET_header, valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) ,packet.UMF_PACKET_header.numChunks, fromInteger(valueof(t_NUM_CHUNKS)));
	     $finish;
         end

         waiting <= False;
         statIncrReceived();
    endrule


    if(valueof(t_NUM_CHUNKS) > 1)
    begin
        rule continueRequest (!waiting && !dem.notEmpty());
            GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                               umf_channel_id, umf_service_id,
                               umf_method_id,  umf_message_len,
                               umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
            dem.enq(packet.UMF_PACKET_dataChunk);
            statIncrReceived();
            if(`MARSHALLING_DEBUG == 1)
            begin
                $display("Send NoPack %s Data Packet: %h", name, pack(packet));
                $display("Connection RX %s receives: %h", name, packet.UMF_PACKET_dataChunk);
            end
        endrule

        // Lurking latency here...
        // Should try to fix at some point.    
        rule sendData(!waiting && dem.notEmpty());
            GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                               umf_channel_id, umf_service_id,
                               umf_method_id,  umf_message_len,
                              umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
            dem.deq();

            if(!send.notFull)
            begin
	        $display("%s Attempting to send to full send!", name);
    	        $finish;
            end

            Bit#(bitwidth) truncatedData = truncate({pack(packet.UMF_PACKET_dataChunk),pack(dem.first)});
            send.send(unpack(zeroExtendNP(truncatedData)));
            if(`MARSHALLING_DEBUG == 1)
            begin
                $display("Data Packet: %h", pack(packet));
  

                $display("Connection %s RX %d emits out: %h", name, id, truncatedData);
            end

            waiting <= True;         
        endrule
    end
    else // No demarshaller necessary.
    begin
          rule sendDataShort(!waiting);
            GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                               umf_channel_id, umf_service_id,
                               umf_method_id,  umf_message_len,
                              umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();

            if(!send.notFull)
            begin
	        $display("%s Attempting to send to full send!", name);
    	        $finish;
            end

            Bit#(bitwidth) truncatedData = truncateNP(pack(packet.UMF_PACKET_dataChunk));
            send.send(unpack(zeroExtendNP(truncatedData)));
            if(`MARSHALLING_DEBUG == 1)
            begin
                $display("Data Packet: %h", pack(packet));
                $display("Connection %s RX %d emits out: %h", name, id, truncatedData);
            end

             waiting <= True;         
        endrule
    end
endmodule

module mkPacketizeConnectionSendMarshalled#(String name, 
                                            SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                                         umf_channel_id, umf_service_id,
                                                                                         umf_method_id,  umf_message_len,
                                                                                         umf_phy_pvt,    filler_bits), 
                                                                     umf_chunk)) port, 
                                            Integer id, 
                                            NumTypeParam#(bitwidth) width, 
                                            function Action statIncrReceived(),
                                            PHYSICAL_SEND#(t_DATA) send) (Empty)
   provisos(Bits#(t_DATA, t_DATA_SZ),
            Div#(TSub#(bitwidth, filler_bits),SizeOf#(umf_chunk),t_NUM_CHUNKS),
            Add#(n_EXTRA_SZ_2, bitwidth, TAdd#(TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk)), filler_bits)),
            Add#(TAdd#(t_NUM_CHUNKS,1), 0, t_WORD_CHUNKS), // we already add the header in here..
            Add#(TMul#(t_WORD_CHUNKS,`CON_BUFFERING), 0, t_BUFFER_CHUNKS),
            Add#(n_EXTRA_SZ_2, bitwidth, TAdd#(SizeOf#(umf_chunk), TAdd#(TMul#(TSub#(t_NUM_CHUNKS, 1), SizeOf#(umf_chunk)),filler_bits))),
            Add#(n_EXTRA_SZ, TSub#(bitwidth, filler_bits), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

     Reg#(Bool) waiting <- mkReg(True);
     Reg#(Bit#(filler_bits)) fillerBits <- mkReg(?);
 
     COUNTER#(TLog#(TAdd#(1,t_BUFFER_CHUNKS))) tokens <- mkLCounter(0);

     DEMARSHALLER#(umf_chunk, Vector#(TSub#(t_NUM_CHUNKS,1), umf_chunk)) dem <- mkSimpleDemarshaller();  

     if(`MARSHALLING_DEBUG == 1)
     begin
         rule view(tokens.value > 0);
             $display("%s has value %d a multiple of %d? %d filler %d chunks %d width", 
                      name, tokens.value, valueof(t_WORD_CHUNKS), valueof(filler_bits), 
                      valueof(t_NUM_CHUNKS), valueof(SizeOf#(umf_chunk)));
         endrule
     end

     (* execution_order = "sendReady, enqTok" *) 

     rule sendReady(tokens.value < fromInteger(valueof(t_BUFFER_CHUNKS)));
         port.read_ready();
     endrule

     rule enqTok(port.read_allocated());
         if(`MARSHALLING_DEBUG == 1)
         begin
             $display("%s has value up by %d?", name, 1);
         end

         tokens.up();
     endrule

     rule returnTokens(send.dequeued);
         if(`MARSHALLING_DEBUG == 1)
         begin
   	     $display("%s has value down by %d?", name, valueof(t_WORD_CHUNKS));
         end

         tokens.downBy(fromInteger(valueof(t_WORD_CHUNKS)));
     endrule

     rule startRequest (waiting);
         GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                             umf_channel_id, umf_service_id,
                             umf_method_id,  umf_message_len,
                             umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
         if(`MARSHALLING_DEBUG == 1)
         begin
             $display("Marshalled Connection %s RX starting request dataSz: %d chunkSz: %d type:  %d listed: %d", name, valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) ,packet.UMF_PACKET_header.numChunks, fromInteger(valueof(t_NUM_CHUNKS)));
         end

         if(packet.UMF_PACKET_header.numChunks != fromInteger(valueof(t_NUM_CHUNKS)))
         begin
             $display("Marshalled Connection %s RX starting request dataSz: %d chunkSz: %d header chunks:  %d expected chunks: %d", name, valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) ,packet.UMF_PACKET_header.numChunks, fromInteger(valueof(t_NUM_CHUNKS)));
	     $finish;
         end

         waiting <= False;
         fillerBits <= packet.UMF_PACKET_header.filler;        
         statIncrReceived();
    endrule

    rule continueRequest (!waiting && !dem.notEmpty());
        GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
        dem.enq(packet.UMF_PACKET_dataChunk);
        statIncrReceived();
        if(`MARSHALLING_DEBUG == 1)
        begin
            $display("Connection RX %s receives: %h", name, packet.UMF_PACKET_dataChunk);
        end

    endrule

    // Lurking latency here...
    // Should try to fix at some point.    
    rule sendData(!waiting && dem.notEmpty());
        GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
        dem.deq();

        if(!send.notFull)
        begin
	    $display("%s Attempting to send to full send!", name);
	    $finish;
        end

        Bit#(bitwidth) truncatedData = truncate({pack(packet.UMF_PACKET_dataChunk),pack(dem.first),fillerBits});
        send.send(unpack(zeroExtendNP(truncatedData)));
        if(`MARSHALLING_DEBUG == 1)
        begin
            $display("Connection %s RX %d emits out: %h", name, id, dem.first);
        end

        waiting <= True;         
    endrule
endmodule

module mkPacketizeConnectionSendPartialMarshalled#(String name, 
                                                   SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                                                umf_channel_id, umf_service_id,
                                                                                                umf_method_id,  umf_message_len,
                                                                                                umf_phy_pvt,    filler_bits), 
                                                                            umf_chunk)) port, 
                                                   Integer id, 
                                                   NumTypeParam#(bitwidth) width, 
                                                   function Action statIncrReceived(),
                                                   PHYSICAL_SEND#(t_DATA) send) (Empty)
    provisos(Bits#(t_DATA, t_DATA_SZ),
             Add#(n_EXTRA_SZ_2, bitwidth, TAdd#(SizeOf#(umf_chunk),filler_bits)));

     Reg#(Bool) waiting <- mkReg(True);
     Reg#(Bit#(filler_bits)) fillerBits <- mkReg(?);
 
     COUNTER#(TLog#(TAdd#(1,TMul#(2,`CON_BUFFERING)))) tokens <- mkLCounter(0);

     if(`MARSHALLING_DEBUG == 1)
     begin
         rule view(tokens.value > 0);
             $display("%s has value %d a multiple of %d? %d filler %d chunks %d width", 
                      name, tokens.value, 2, valueof(filler_bits), 1, 
                      valueof(SizeOf#(umf_chunk)));
         endrule
     end

     (* execution_order = "sendReady, enqTok" *) 

     rule sendReady(tokens.value < 2 * `CON_BUFFERING);
         port.read_ready();
     endrule

     rule enqTok(port.read_allocated());
         if(`MARSHALLING_DEBUG == 1)
         begin
             $display("%s has value up by %d?", name, 1);
         end

         tokens.up();
     endrule

     rule returnTokens(send.dequeued);
         if(`MARSHALLING_DEBUG == 1)
         begin
             $display("%s has value down by %d?", name, 2);
         end

         tokens.downBy(2);
     endrule


     rule startRequest (waiting);
         GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                             umf_channel_id, umf_service_id,
                             umf_method_id,  umf_message_len,
                             umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();

         if(`MARSHALLING_DEBUG == 1)
         begin
             $display("Partial Marshall Connection %s RX starting request dataSz: %d chunkSz: %d type:  %d listed: %d", name, valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) ,packet.UMF_PACKET_header.numChunks, 1);
         end

         if(packet.UMF_PACKET_header.numChunks != 1)
         begin
             $display("Partial Marshall Connection %s RX starting request dataSz: %d chunkSz: %d type:  %d listed: %d", name, valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) ,packet.UMF_PACKET_header.numChunks, 1);
	     $finish;
         end

         waiting <= False;
         fillerBits <= packet.UMF_PACKET_header.filler;        
         statIncrReceived();
    endrule

    rule sendData(!waiting);
        GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();
       

        if(!send.notFull)
        begin
	    $display("%s Attempting to send to full send!", name);
	    $finish;
        end

        Bit#(bitwidth) truncatedData = truncate({pack(packet.UMF_PACKET_dataChunk),fillerBits});
        send.send(unpack(zeroExtendNP(truncatedData)));
        if(`MARSHALLING_DEBUG == 1)
        begin
            $display("Connection %s RX %d emits out: %h", name, id, truncatedData);
        end

        waiting <= True;         
    endrule

endmodule



module mkPacketizeConnectionSendUnmarshalled#(String name, 				       
                                              SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                                           umf_channel_id, umf_service_id,
                                                                                           umf_method_id,  umf_message_len,
                                                                                           umf_phy_pvt,    filler_bits), 
                                                                       umf_chunk)) port, 
                                              Integer id, 
                                              NumTypeParam#(bitwidth) width, 
                                              function Action statIncrReceived(),
                                              PHYSICAL_SEND#(t_DATA) send) (Empty)
    provisos(Bits#(t_DATA, t_DATA_SZ),
             Bits#(umf_chunk,umf_chunk_SZ));

    // If we can fit the data payload into the leftover header bits, we will do that. 
    // If we can't (but the bitwidth is small enough to fit in a single data chunk, 
    // we don't need to instantiate a marshaller
    COUNTER#(TLog#(TAdd#(1,`CON_BUFFERING))) tokens <- mkLCounter(0);
 
    if(`MARSHALLING_DEBUG == 1)
    begin
        rule view(tokens.value > 0);
            $display("%s has value %d a multiple of %d?", name, tokens.value, 1);
        endrule
    end

    (* execution_order = "sendReady, enqTok" *) 
 
    rule sendReady(tokens.value < `CON_BUFFERING);
        port.read_ready();
    endrule

    rule enqTok(port.read_allocated());
        if(`MARSHALLING_DEBUG == 1)
        begin
            $display("%s has value up by %d?", name, 1);
        end 

        tokens.up();
    endrule

    rule returnTokens(send.dequeued);
        if(`MARSHALLING_DEBUG == 1)
        begin
	    $display("%s has value down by %d?", name, 1);
        end

        tokens.downBy(1);
    endrule


    rule continueRequest(send.notFull());
        GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                umf_channel_id, umf_service_id,
                                umf_method_id,  umf_message_len,
                                umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read(); 

        t_DATA data = unpack(resize(packet.UMF_PACKET_header.filler));
        send.send(data);
        statIncrReceived();

        if(`MARSHALLING_DEBUG == 1)
        begin
            $display("Connection %s RX packet is: channel %d, service %d, method %d, message %d, phy %d, filler %d", 
                     name, valueof(umf_channel_id), valueof(umf_service_id), valueof(umf_method_id), 
                     valueof(umf_message_len), valueof(umf_phy_pvt), valueof(filler_bits));
            $display("Connection %s RX %d (HO) emits out: %h", name, id, data);
        end

         if(packet.UMF_PACKET_header.numChunks != 0)
         begin
             $display("Unmarshalled Connection %s RX starting request dataSz: %d chunkSz: %d type:  %d listed: %d", name, valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) ,packet.UMF_PACKET_header.numChunks, 0);
	     $finish;
         end

        endrule

endmodule


// ********
// *
// * Receive endpoints
// *
// ********

module mkPacketizeConnectionReceiveNoPack#(String name,
                                           Integer id, 
                                           NumTypeParam#(bitwidth) width,
                                           function Action statIncrBlocked(), 
                                           function Action statIncrSent(),
                                           Connection_Receive#(t_DATA) recv) 
    (EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id, umf_service_id,
                                    umf_method_id,  umf_message_len,
                                    umf_phy_pvt,    filler_bits),
                                umf_chunk)) // Interface
    provisos(Bits#(t_DATA, t_DATA_SZ),             
             Div#(bitwidth,SizeOf#(umf_chunk),t_NUM_CHUNKS),
             
             // this proviso allows us to stuff payload bits into the packet header which sometimes saves a 
             // a cycle
             Add#(n_EXTRA_SZ, bitwidth, TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

    PulseWire continueRequestFired <- mkPulseWire(); 
    PulseWire startRequestFired <- mkPulseWire(); 

    // Strong assumption that the marshaller holds only one data at a time
    MARSHALLER#(umf_chunk, Vector#(t_NUM_CHUNKS, umf_chunk)) mar <- mkSimpleMarshaller();

    Bit#(bitwidth) truncatedData = truncateNP(pack(recv.receive));
   
    method Action deqHeader() if(recv.notEmpty() && !mar.notEmpty());
        recv.deq;
        statIncrSent();
        mar.enq(unpack(zeroExtend(truncatedData)));
        startRequestFired.send();
        if(`MARSHALLING_DEBUG == 1)
        begin
            $display("ReceiveNoPack got %h", recv.receive);

            $display("Connection %s TX %d            chunks %d       emits out: %h", name, id, valueof(t_NUM_CHUNKS), recv.receive);
            $display("              umf_chunk %d     filler_bits %d", valueof(SizeOf#(umf_chunk)), valueof(filler_bits));
            $display("              extra_sz %d      data_sz %d", valueof(n_EXTRA_SZ), valueof(t_DATA_SZ));
        end
    endmethod

    method GENERIC_UMF_PACKET_HEADER#(
               umf_channel_id, umf_service_id,
               umf_method_id,  umf_message_len,
               umf_phy_pvt,    filler_bits) firstHeader() if(recv.notEmpty() && !mar.notEmpty());

        return GENERIC_UMF_PACKET_HEADER
               {
                   filler: ?,
                   phyChannelPvt: ?,
                   channelID: ?, // we use this elsewhere to refer to flow control messages
                   serviceID: fromInteger(id),
                   methodID : 0, 
                   numChunks: fromInteger(valueof(t_NUM_CHUNKS))
               };


    endmethod

    method Bool notEmptyHeader;
        return recv.notEmpty();
    endmethod
 
    method Action deqBody();
        mar.deq();
        statIncrSent();
        if(`MARSHALLING_DEBUG == 1)
        begin
            $display("Connection %s TX sends: %h", name, mar.first);
        end
        continueRequestFired.send();
    endmethod

    method firstBody = mar.first;

    method notEmptyBody = mar.notEmpty;

    method bypassFlowcontrol = False;

    method Integer maxPacketSize = valueof(t_NUM_CHUNKS);

endmodule


// These guys need a FOF interface
// This one requires some thought 
module mkPacketizeConnectionReceiveMarshalled#(String name,
                                               Integer id, 
                                               NumTypeParam#(bitwidth) width,
                                               function Action statIncrBlocked(), 
                                               function Action statIncrSent(),
                                               Connection_Receive#(t_DATA) recv) 
    (EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id, umf_service_id,
                                    umf_method_id,  umf_message_len,
                                    umf_phy_pvt,    filler_bits),
                                umf_chunk)) // Interface
    provisos(Bits#(t_DATA, t_DATA_SZ),             
             Div#(TSub#(bitwidth,filler_bits),SizeOf#(umf_chunk),t_NUM_CHUNKS),
             Add#(filler_EXTRA_SZ, filler_bits, bitwidth),

             // this proviso allows us to stuff payload bits into the packet header which sometimes saves a 
             // a cycle
             Add#(n_EXTRA_SZ_2, bitwidth, TAdd#(TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk)), filler_bits)), 
	     Add#(n_EXTRA_SZ, TSub#(bitwidth,filler_bits), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

    PulseWire continueRequestFired <- mkPulseWire(); 
    PulseWire startRequestFired <- mkPulseWire(); 

    // Strong assumption that the marshaller holds only one data at a time
    MARSHALLER#(umf_chunk, Vector#(t_NUM_CHUNKS, umf_chunk)) mar <- mkSimpleMarshaller();

    Bit#(bitwidth) truncatedData = truncateNP(pack(recv.receive));

    Tuple2#(Bit#(TSub#(bitwidth,filler_bits)),Bit#(filler_bits)) data_split = split(truncatedData);
   
    method Action deqHeader() if(recv.notEmpty() && !mar.notEmpty());
        recv.deq;
        mar.enq(unpack(zeroExtend(tpl_1(data_split))));
        statIncrSent();
        startRequestFired.send();
        if(`MARSHALLING_DEBUG == 1)
        begin
            $display("ReceiveMarshalled got %h", recv.receive);
            $display("Connection %s TX %d            chunks %d       emits out: %h", name, id, valueof(t_NUM_CHUNKS), recv.receive);
            $display("              umf_chunk %d     filler_bits %d", valueof(SizeOf#(umf_chunk)), valueof(filler_bits));
            $display("              extra_sz %d     extra_sz_2 %d    data_sz %d", valueof(n_EXTRA_SZ), valueof(n_EXTRA_SZ_2), valueof(t_DATA_SZ));
        end
    endmethod

    method GENERIC_UMF_PACKET_HEADER#(
               umf_channel_id, umf_service_id,
               umf_method_id,  umf_message_len,
               umf_phy_pvt,    filler_bits) firstHeader() if(recv.notEmpty() && !mar.notEmpty());

        return GENERIC_UMF_PACKET_HEADER
               {
                   filler: tpl_2(data_split),
                   phyChannelPvt: ?,
                   channelID: ?, // we use this elsewhere to refer to flow control messages
                   serviceID: fromInteger(id),
                   methodID : 0, 
                   numChunks: fromInteger(valueof(t_NUM_CHUNKS))
               };


    endmethod

    method Bool notEmptyHeader;
        return recv.notEmpty();
    endmethod
 
    method Action deqBody();
        mar.deq();
        statIncrSent();
        if(`MARSHALLING_DEBUG == 1)
        begin
            $display("Connection %s TX sends: %h", name, mar.first);
        end
        continueRequestFired.send();
    endmethod

    method firstBody = mar.first;

    method notEmptyBody = mar.notEmpty;

    method bypassFlowcontrol = False;

    method Integer maxPacketSize = valueof(t_NUM_CHUNKS);

endmodule


// Actually this is insufficiently aggressive
module mkPacketizeConnectionReceiveUnmarshalled#(String name,
                                                 Integer id, 
                                                 NumTypeParam#(bitwidth) width,  
                                                 function Action statIncrBlocked(), 
                                                 function Action statIncrSent(),
                                                 Connection_Receive#(t_DATA) recv) 

    (EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id, umf_service_id,
                                    umf_method_id,  umf_message_len,
                                    umf_phy_pvt,    filler_bits),
                                umf_chunk)) // Interface

    provisos(Bits#(t_DATA, t_DATA_SZ),
             Bits#(umf_chunk,umf_chunk_SZ));


    if(`MARSHALLING_DEBUG == 1)
    begin
        rule view(recv.notEmpty);
            $display("%s TX (HO) has data, but does not send", name);
        endrule
    end

    EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id, umf_service_id,
                                    umf_method_id,  umf_message_len,
                                    umf_phy_pvt,    filler_bits),
                                umf_chunk) unmarshalled = ?;
    
    // If the payload bitwidth is small, fit it in the header
    // Otherwise, we need will get one payload chunk
    messageM(" Unmarshalled Recv #" + integerToString(id) + " bitwidth " + integerToString(valueof(bitwidth)) + " filler " + integerToString(valueof(filler_bits)));

    PulseWire startRequestFired <- mkPulseWire();  
 
    rule checkBlocked(recv.notEmpty() && !(startRequestFired));
        statIncrBlocked();
    endrule

    function GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits) firstHeader;

	    
         // The following blob instantiates a packet header. 
         return GENERIC_UMF_PACKET_HEADER
                {
                    filler: resize(pack(recv.receive)),  // Woot
                    phyChannelPvt: ?,
                    channelID: ?, // we use this elsewhere to refer to flow control messages
                    serviceID: fromInteger(id),
                    methodID : 0,
                    numChunks: 0
                };
     endfunction

     function Action deqHeader();
     action
         recv.deq;
         statIncrSent();
         startRequestFired.send();

         if(`MARSHALLING_DEBUG == 1)
         begin
             $display("Connection %s TX %d (HO)  emits out: %h", name, id, recv.receive);
             $display("Connection %s TX Our packet is: channel %d, service %d, method %d, message %d, phy %d, filler %d", 
                      name, valueof(umf_channel_id), valueof(umf_service_id), valueof(umf_method_id), valueof(umf_message_len), 
                      valueof(umf_phy_pvt), valueof(filler_bits));
         end
     endaction
     endfunction 

     unmarshalled = interface EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                                           umf_channel_id, umf_service_id,
                                                           umf_method_id,  umf_message_len,
                                                           umf_phy_pvt,    filler_bits),
                                                       umf_chunk);
                        method notEmptyHeader = recv.notEmpty;
                        method deqHeader = deqHeader;
                        method firstHeader = firstHeader;

                        method Action deqBody();          
                            $display("Warning Unmarshalled Deq Body called");
                        endmethod

                        method firstBody = ?;

                        method notEmptyBody = True;

                        method bypassFlowcontrol = False;

                        method Integer maxPacketSize = 0;
                    endinterface;

    return unmarshalled;

endmodule



// *******
// *
// * Chain Code
// *
// *******

module [m] mkPacketizeOutgoingChainHelper#(SEND_PACKETIZER_CONSTRUCTOR#(m) mkSendPacketizer)
    (PHYSICAL_CHAIN_OUT)
    provisos(IsModule#(m, mType));

    // We need a clock and reset due to MCD code
    let myClock <- exposeCurrentClock;
    let myReset <- exposeCurrentReset;

    let outfifo <- mkSizedFIFOF(2);
    let sendDequeue <- mkPulseWire();

    let send = interface PHYSICAL_SEND#(PHYSICAL_CHAIN_DATA);
                   method Action send(PHYSICAL_CHAIN_DATA data);
                       outfifo.enq(data);
                   endmethod

		   method Bool notFull(); 
		       return outfifo.notFull();
		   endmethod

		   method Bool dequeued(); 
		       return sendDequeue;
		   endmethod

               endinterface;

    let sendPacketizer <- mkSendPacketizer(send);

    interface clock = myClock;
    interface reset = myReset;

    method Action deq();
        outfifo.deq();
        sendDequeue.send();
    endmethod 

    method first = outfifo.first();
    method notEmpty = outfifo.notEmpty();

endmodule

module mkPacketizeOutgoingChainNoPack#(String name,
                                 SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                          umf_channel_id, umf_service_id,
                                                                          umf_method_id,  umf_message_len,
                                                                          umf_phy_pvt,    filler_bits), umf_chunk)) port,
                                 Integer id,
                                 NumTypeParam#(bitwidth) width,
                                 function Action statIncrReceived())
    (PHYSICAL_CHAIN_OUT) // module interface
    provisos(Bits#(umf_chunk, umf_chunk_SZ),
             Div#(bitwidth,SizeOf#(umf_chunk),t_NUM_CHUNKS),
             Add#(n_EXTRA_SZ_2, bitwidth, TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))),
             Add#(TAdd#(t_NUM_CHUNKS,1), 0, t_WORD_CHUNKS), // we already add the header in here..
             Add#(TMul#(t_WORD_CHUNKS,`CON_BUFFERING), 0, t_BUFFER_CHUNKS),
             Mul#(t_NUM_CHUNKS, umf_chunk_SZ, TAdd#(umf_chunk_SZ,TMul#(TSub#(t_NUM_CHUNKS, 1), umf_chunk_SZ))),
             Add#(n_EXTRA_SZ_2, bitwidth, TAdd#(SizeOf#(umf_chunk), TMul#(TSub#(t_NUM_CHUNKS, 1), SizeOf#(umf_chunk)))),
             Add#(n_EXTRA_SZ, bitwidth, TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

    let packetizer <- mkPacketizeOutgoingChainHelper(mkPacketizeConnectionSendNoPack(name, port, id, width, statIncrReceived));
    return packetizer;

endmodule

module mkPacketizeOutgoingChainMarshalled#(String name, 
                                 SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                          umf_channel_id, umf_service_id,
                                                                          umf_method_id,  umf_message_len,
                                                                          umf_phy_pvt,    filler_bits), umf_chunk)) port, 
                                 Integer id, 
                                 NumTypeParam#(bitwidth) width, 
                                 function Action statIncrReceived()) 
    (PHYSICAL_CHAIN_OUT) // module interface 

    provisos (Bits#(umf_chunk, umf_chunk_SZ),
              Div#(TSub#(bitwidth, filler_bits),SizeOf#(umf_chunk),t_NUM_CHUNKS),
              Add#(n_EXTRA_SZ_2, bitwidth, TAdd#(TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk)), filler_bits)),
              Add#(n_EXTRA_SZ_2, bitwidth, TAdd#(SizeOf#(umf_chunk), TAdd#(TMul#(TSub#(t_NUM_CHUNKS, 1), SizeOf#(umf_chunk)),filler_bits))),
              Add#(n_EXTRA_SZ, TSub#(bitwidth, filler_bits), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))),
              // These provisos are suspicious.
              Add#(TMul#(TSub#(t_NUM_CHUNKS, 1), umf_chunk_SZ), umf_chunk_SZ, TMul#(t_NUM_CHUNKS, umf_chunk_SZ)),
              Mul#(t_NUM_CHUNKS, umf_chunk_SZ, TAdd#(TMul#(TSub#(t_NUM_CHUNKS, 1),umf_chunk_SZ), umf_chunk_SZ)));

    let packetizer <-  mkPacketizeOutgoingChainHelper(mkPacketizeConnectionSendMarshalled(name, port, id, width, statIncrReceived));
    return packetizer;

endmodule


module mkPacketizeOutgoingChainPartialMarshalled#(String name,
                                 SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                          umf_channel_id, umf_service_id,
                                                                          umf_method_id,  umf_message_len,
                                                                          umf_phy_pvt,    filler_bits), umf_chunk)) port,
                                 Integer id,
                                 NumTypeParam#(bitwidth) width,
                                 function Action statIncrReceived())
    (PHYSICAL_CHAIN_OUT) // module interface
    provisos(Add#(n_EXTRA_SZ_2, bitwidth, TAdd#(SizeOf#(umf_chunk),filler_bits)));

    let packetizer <-  mkPacketizeOutgoingChainHelper(mkPacketizeConnectionSendPartialMarshalled(name, port, id, width, statIncrReceived));
    return packetizer;

endmodule


module mkPacketizeOutgoingChainUnmarshalled#(String name, 
                                 SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                          umf_channel_id, umf_service_id,
                                                                          umf_method_id,  umf_message_len,
                                                                          umf_phy_pvt,    filler_bits), umf_chunk)) port, 
                                 Integer id, 
                                 NumTypeParam#(bitwidth) width, 
                                 function Action statIncrReceived()) 
    (PHYSICAL_CHAIN_OUT) // module interface 

    provisos (Bits#(umf_chunk, umf_chunk_SZ));

    let packetizer <-  mkPacketizeOutgoingChainHelper(mkPacketizeConnectionSendUnmarshalled(name, port, id, width, statIncrReceived));
    return packetizer;

endmodule


module [m] mkPacketizeIncomingChainHelper#(RECV_PACKETIZER_CONSTRUCTOR#(m, EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                          umf_channel_id, umf_service_id,
                                          umf_method_id,  umf_message_len,
                                          umf_phy_pvt,    filler_bits),
                 umf_chunk)) mkRecvPacketizer) 
    (Tuple2#(EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                          umf_channel_id, umf_service_id,
                                          umf_method_id,  umf_message_len,
                                          umf_phy_pvt,    filler_bits),
                 umf_chunk),
             PHYSICAL_CHAIN_IN)) // Module interface
    provisos(IsModule#(m, mType));	 

    // Egress interface to be filled in

    let myClock <- exposeCurrentClock;
    let myReset <- exposeCurrentReset;

    RWire#(PHYSICAL_CHAIN_DATA) tryData <- mkRWire();
    PulseWire trySuccess <- mkPulseWire();
    Bool tryValid = isValid(tryData.wget());
    
    let recv = interface Connection_Receive#(PHYSICAL_CHAIN_DATA);
                   method PHYSICAL_CHAIN_DATA receive() if(tryData.wget matches tagged Valid .data);
                       return data;    
                   endmethod

		   method Action deq if(tryValid);
		       trySuccess.send;
                   endmethod

		   method Bool notEmpty(); 
		       return tryValid;
		   endmethod

               endinterface;


    let egress_packet_generator <- mkRecvPacketizer(recv);


    let physical_chain_in = interface PHYSICAL_CHAIN_IN;
                                interface clock = myClock;
                                interface reset = myReset;
 
                                method Bool success() = trySuccess;

                                method Bool dequeued() = trySuccess; 

                                method Action try(PHYSICAL_CHAIN_DATA d);
                                   tryData.wset(d);     
                                endmethod
                            endinterface;

   return tuple2(egress_packet_generator, physical_chain_in);
endmodule

module mkPacketizeIncomingChainNoPack#(String name,
                                 Integer id,  
                                 NumTypeParam#(bitwidth) width,
                                 function Action statIncrBlocked(), 
                                 function Action statIncrSent()) 
    (Tuple2#(EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                          umf_channel_id, umf_service_id,
                                          umf_method_id,  umf_message_len,
                                          umf_phy_pvt,    filler_bits),
                 umf_chunk),
             PHYSICAL_CHAIN_IN)) // Module interface

    provisos (Bits#(umf_chunk, umf_chunk_SZ),
              Div#(bitwidth,SizeOf#(umf_chunk),t_NUM_CHUNKS),

              // this proviso allows us to stuff payload bits into the packet header which sometimes saves a
              // a cycle
              Add#(n_EXTRA_SZ, bitwidth, TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

    let packetizer <- mkPacketizeIncomingChainHelper(mkPacketizeConnectionReceiveNoPack(name, id, width, statIncrBlocked, statIncrSent));
    return packetizer;

endmodule

module mkPacketizeIncomingChainMarshalled#(String name,
                                 Integer id,  
                                 NumTypeParam#(bitwidth) width,
                                 function Action statIncrBlocked(), 
                                 function Action statIncrSent()) 
    (Tuple2#(EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                          umf_channel_id, umf_service_id,
                                          umf_method_id,  umf_message_len,
                                          umf_phy_pvt,    filler_bits),
                 umf_chunk),
             PHYSICAL_CHAIN_IN)) // Module interface

    provisos (Bits#(umf_chunk, umf_chunk_SZ),
              Bits#(PHYSICAL_CHAIN_DATA, t_PHYSICAL_CHAIN_DATA_SZ),
              Div#(TSub#(bitwidth,filler_bits),SizeOf#(umf_chunk),t_NUM_CHUNKS),
              Add#(filler_EXTRA_SZ, filler_bits, bitwidth),

              // this proviso allows us to stuff payload bits into the packet header which sometimes saves a
              // a cycle
              Add#(n_EXTRA_SZ_2, bitwidth, TAdd#(TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk)), filler_bits)),
              Add#(n_EXTRA_SZ, TSub#(bitwidth,filler_bits), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

    let packetizer <- mkPacketizeIncomingChainHelper(mkPacketizeConnectionReceiveMarshalled(name, id, width, statIncrBlocked, statIncrSent));
    return packetizer;

endmodule


module mkPacketizeIncomingChainUnmarshalled#(String name,
                                 Integer id,  
                                 NumTypeParam#(bitwidth) width,
                                 function Action statIncrBlocked(), 
                                 function Action statIncrSent()) 
    (Tuple2#(EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                          umf_channel_id, umf_service_id,
                                          umf_method_id,  umf_message_len,
                                          umf_phy_pvt,    filler_bits),
                 umf_chunk),
             PHYSICAL_CHAIN_IN)) // Module interface

    provisos (Bits#(umf_chunk, umf_chunk_SZ),
              Bits#(PHYSICAL_CHAIN_DATA, t_PHYSICAL_CHAIN_DATA_SZ));

    let packetizer <- mkPacketizeIncomingChainHelper(mkPacketizeConnectionReceiveUnmarshalled(name, id, width, statIncrBlocked, statIncrSent));
    return packetizer;

endmodule





