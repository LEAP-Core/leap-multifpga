//
// Copyright (C) 2011 Massachusetts Institute of Technology
//
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// as published by the Free Software Foundation; either version 2
// of the License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
//


/******** 
 * This file contains the glue modules for connecting user connections (i.e. sends and receives)
 * to the multiplexed interFPGA communication complex.  This code is used by the multifpga_routing.bsh
 * file generated at compile time and should not appear in user applications. 
 *
 */

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

// *******
// * Point to Point Code
// *
// * The following are flavors of point to point links that plug in to the multiplexed inter-fpga communication complex.
// * Different implementations are needed to deal with narrow-data width optimizations - the provisos for the different 
// * cases are impossible to resolve into a unified set.  Notice that Send/Receive polarity is reversed - it is the opposite
// * the user code.  
// *******

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
             Bits#(umf_chunk,umf_chunk_SZ));

    // If we can fit the data payload into the leftover header bits, we will do that. 
    // If we can't (but the bitwidth is small enough to fit in a single data chunk, 
    // we don't need to instantiate a marshaller
    if(valueof(bitwidth) < valueof(filler_bits))
    begin       
        rule sendReady(send.notFull());
            port.read_ready();
        endrule

        rule continueRequest(send.notFull());
            GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                umf_channel_id, umf_service_id,
                                umf_method_id,  umf_message_len,
                                umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read(); 

            Bit#(bitwidth) value = truncateNP(packet.UMF_PACKET_header.filler);
            t_DATA data = (unpack(resize(value)));
            send.send(data);
            received.incr();

            if(`SWITCH_DEBUG == 1)
            begin
                $display("Our packet is: channel %d, service %d, method %d, message %d, phy %d, filler %d", 
                         valueof(umf_channel_id), valueof(umf_service_id), valueof(umf_method_id), 
                         valueof(umf_message_len), valueof(umf_phy_pvt), valueof(filler_bits));
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

// These guys need a FOF interface
// This one requires some thought 
module mkPacketizeConnectionReceiveMarshalled#(Connection_Receive#(t_DATA) recv,                                             
                                               Integer id, 
                                               NumTypeParam#(bitwidth) width,
                                               STAT blocked, 
                                               STAT sent) 
    (EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id, umf_service_id,
                                    umf_method_id,  umf_message_len,
                                    umf_phy_pvt,    filler_bits),
                                umf_chunk)) // Interface
    provisos(Bits#(t_DATA, t_DATA_SZ),
             Div#(TSub#(t_DATA_SZ,filler_bits),SizeOf#(umf_chunk),t_NUM_CHUNKS),
             Add#(filler_EXTRA_SZ, filler_bits, t_DATA_SZ),

             // this proviso allows us to stuff payload bits into the packet header which sometimes saves a 
             // a cycle
             Add#(n_EXTRA_SZ_2, t_DATA_SZ, TAdd#(TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk)), filler_bits)), 
	     Add#(n_EXTRA_SZ, TSub#(t_DATA_SZ,filler_bits), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

    PulseWire continueRequestFired <- mkPulseWire(); 
    PulseWire startRequestFired <- mkPulseWire(); 

    // Strong assumption that the marshaller holds only one data at a time
    MARSHALLER#(t_NUM_CHUNKS, umf_chunk) mar <- mkSimpleMarshaller();

    Tuple2#(Bit#(TSub#(t_DATA_SZ,filler_bits)),Bit#(filler_bits)) data_split = split(pack(recv.receive));
   
    method Action deqHeader() if(recv.notEmpty());
        recv.deq;
        mar.enq(unpack(zeroExtend(tpl_1(data_split))));
        sent.incr();
        startRequestFired.send();
        if(`SWITCH_DEBUG == 1)
        begin
            $display("Connection TX %d  emits out: %h", id, recv.receive);
        end
    endmethod

    method GENERIC_UMF_PACKET_HEADER#(
               umf_channel_id, umf_service_id,
               umf_method_id,  umf_message_len,
               umf_phy_pvt,    filler_bits) firstHeader() if(recv.notEmpty());

        return GENERIC_UMF_PACKET_HEADER
               {
                   filler: tpl_2(data_split),
                   phyChannelPvt: ?,
                   channelID: ?, // we use this elsewhere to refer to flow control messages
                   serviceID: fromInteger(id),
                   methodID : ?, 
                   numChunks: fromInteger(valueof(t_NUM_CHUNKS))
               };


    endmethod

    method Bool notEmptyHeader;
        return recv.notEmpty();
    endmethod
 
    method Action deqBody();
        mar.deq();
        sent.incr();
        if(`SWITCH_DEBUG == 1)
        begin
            $display("Marshalled Connection TX sends: %h", mar.first);
        end
        continueRequestFired.send();
    endmethod

    method firstBody = mar.first;

    method notEmptyBody = mar.notEmpty;

endmodule

// Actually this is insufficiently aggressive
module mkPacketizeConnectionReceiveUnmarshalled#(Connection_Receive#(t_DATA) recv, 
                                                 Integer id, 
                                                 NumTypeParam#(bitwidth) width,  
                                                 STAT blocked, 
                                                 STAT sent) 

    (EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id, umf_service_id,
                                    umf_method_id,  umf_message_len,
                                    umf_phy_pvt,    filler_bits),
                                umf_chunk)) // Interface

    provisos(Bits#(t_DATA, t_DATA_SZ),
             Bits#(umf_chunk,umf_chunk_SZ));

    EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id, umf_service_id,
                                    umf_method_id,  umf_message_len,
                                    umf_phy_pvt,    filler_bits),
                                umf_chunk) unmarshalled = ?;
    
    // If the payload bitwidth is small, fit it in the header
    // Otherwise, we need will get one payload chunk
    if(valueof(bitwidth) < valueof(filler_bits))
    begin
        
        PulseWire startRequestFired <- mkPulseWire();  
 
        rule checkBlocked(recv.notEmpty() && !(startRequestFired));
            blocked.incr();
        endrule

        function GENERIC_UMF_PACKET_HEADER#(
                           umf_channel_id, umf_service_id,
                           umf_method_id,  umf_message_len,
                           umf_phy_pvt,    filler_bits) firstHeader;

            Bit#(bitwidth) value = resize(pack(recv.receive));

            // The following blob instantiates a packet header. 
            return GENERIC_UMF_PACKET_HEADER
                   {
                       filler: zeroExtendNP(value),  // Woot
                       phyChannelPvt: ?,
                       channelID: ?, // we use this elsewhere to refer to flow control messages
                       serviceID: fromInteger(id),
                       methodID : ?,
                       numChunks: 0
                   };
        endfunction

        function Action deqHeader();
        action
            recv.deq;
            sent.incr();
            startRequestFired.send();

            if(`SWITCH_DEBUG == 1)
            begin
                $display("Connection TX %d (HO)  emits out: %h", id, recv.receive);
                $display("Our packet is: channel %d, service %d, method %d, message %d, phy %d, filler %d", 
                         valueof(umf_channel_id), valueof(umf_service_id), valueof(umf_method_id), valueof(umf_message_len), 
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
                       endinterface;
    end
    else
    begin
        Reg#(Bool) waitHeader <- mkReg(True);
        PulseWire continueRequestFired <- mkPulseWire(); 
        PulseWire startRequestFired <- mkPulseWire(); 

        rule checkBlocked(recv.notEmpty() && !(continueRequestFired || startRequestFired));
            blocked.incr();
        endrule

        unmarshalled = interface EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                                              umf_channel_id, umf_service_id,
                                                              umf_method_id,  umf_message_len,
                                                              umf_phy_pvt,    filler_bits),
                                                          umf_chunk);

                           method notEmptyHeader = recv.notEmpty && waitHeader;
                           method Action deqHeader() if(recv.notEmpty && waitHeader);
                               sent.incr();
                               startRequestFired.send();

                               if(`SWITCH_DEBUG == 1)
                               begin
                                   $display("Unmarshalled Recv Connection TX starting request dataSz: %d chunkSz: %d  listed: %d", 
                                            valueof(t_DATA_SZ), valueof(SizeOf#(umf_chunk)) , fromInteger(valueof(bitwidth)));
                               end 

                               waitHeader <= False;                                    
                           endmethod

                           method GENERIC_UMF_PACKET_HEADER#(
                                      umf_channel_id, umf_service_id,
                                      umf_method_id,  umf_message_len,
                                      umf_phy_pvt,    filler_bits) firstHeader() if(recv.notEmpty && waitHeader);
                                return GENERIC_UMF_PACKET_HEADER
                                       {
                                           filler: ?,
                                           phyChannelPvt: ?,
                                           channelID: ?, // we use this elsewhere to refer to flow control messages
                                           serviceID: fromInteger(id),
                                           methodID : ?, 
                                           numChunks: 1
                                       };
       
                           endmethod

                           method notEmptyBody = !waitHeader && recv.notEmpty;

                           method Action deqBody() if(!waitHeader && recv.notEmpty);
                               recv.deq();
			       if(`SWITCH_DEBUG == 1)
                               begin
                                   $display("Connection TX %d (S)  emits out: %h", id, recv.receive);
                               end

                               waitHeader <= True;
			       sent.incr();
                               continueRequestFired.send();
                           endmethod

                           method umf_chunk firstBody() if(!waitHeader && recv.notEmpty);
                               return unpack(resize(pack(recv.receive)));
                           endmethod

                       endinterface; 
    end

    return unmarshalled;

endmodule


// *******
// * Chain Code
// *
// * Chains don't need particularly high performance, so their code is less optimized as compared to
// * the point to point links.
// *******


module mkPacketizeOutgoingChain#(SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                          umf_channel_id, umf_service_id,
                                                                          umf_method_id,  umf_message_len,
                                                                          umf_phy_pvt,    filler_bits), umf_chunk)) port, 
                                                      STAT received) 
    (PHYSICAL_CHAIN_OUT) // module interface 

    provisos(Div#(SizeOf#(PHYSICAL_CHAIN_DATA),SizeOf#(umf_chunk),t_NUM_CHUNKS),
             Add#(n_EXTRA_SZ, SizeOf#(PHYSICAL_CHAIN_DATA), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

    // We need a clock and reset due to MCD code
    let myClock <- exposeCurrentClock;
    let myReset <- exposeCurrentReset;

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
        waiting <= False;
        received.incr();
    endrule

    rule continueRequest (!waiting);
        GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                            umf_channel_id, umf_service_id,
                            umf_method_id,  umf_message_len,
                            umf_phy_pvt,    filler_bits), umf_chunk) packet <- port.read();

        dem.enq(packet.UMF_PACKET_dataChunk);   
	received.incr();
    endrule

 
    interface clock = myClock;
    interface reset = myReset;

    method Action deq();
        dem.deq;
        waiting <= True;
    endmethod

    method PHYSICAL_CHAIN_DATA first = unpack(truncate(pack(dem.first)));
    method Bool notEmpty() = dem.notEmpty;

endmodule



module mkPacketizeIncomingChain#(Integer id,  
                                 STAT blocked, 
                                 STAT sent) 
    (Tuple2#(EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                          umf_channel_id, umf_service_id,
                                          umf_method_id,  umf_message_len,
                                          umf_phy_pvt,    filler_bits),
                 umf_chunk),
             PHYSICAL_CHAIN_IN)) // Module interface

    provisos(Div#(SizeOf#(PHYSICAL_CHAIN_DATA),SizeOf#(umf_chunk),t_NUM_CHUNKS),
	     Add#(n_EXTRA_SZ, SizeOf#(PHYSICAL_CHAIN_DATA), TMul#(t_NUM_CHUNKS, SizeOf#(umf_chunk))));

    // Egress interface to be filled in

    let myClock <- exposeCurrentClock;
    let myReset <- exposeCurrentReset;

    MARSHALLER#(t_NUM_CHUNKS, umf_chunk) mar <- mkSimpleMarshaller();
    RWire#(PHYSICAL_CHAIN_DATA) tryData <- mkRWire();
    PulseWire trySuccess <- mkPulseWire();
    PulseWire continueRequestFired <- mkPulseWire(); 

    rule checkBlocked((mar.notEmpty() && (!continueRequestFired)) || (isValid(tryData.wget) && !trySuccess));
        blocked.incr();
    endrule

    let egress_packet_generator = interface EGRESS_PACKET_GENERATOR;
                                      method notEmptyHeader = isValid(tryData.wget());
                                      method Action deqHeader() if(tryData.wget() matches tagged Valid .data);
                                          trySuccess.send;
                                          sent.incr();
                                          mar.enq(unpack(zeroExtend(pack(data))));         
                                      endmethod
                                      method GENERIC_UMF_PACKET_HEADER#(
                                                 umf_channel_id, umf_service_id,
                                                 umf_method_id,  umf_message_len,
                                                 umf_phy_pvt,    filler_bits) firstHeader() if(tryData.wget() matches tagged Valid .data);
                                          return GENERIC_UMF_PACKET_HEADER
                                                 {
                                                     filler: ?,
                                                     phyChannelPvt: ?,
                                                     channelID: ?, // we use this elsewhere to refer to flow control messages
                                                     serviceID: fromInteger(id),
                                                     methodID : ?,
                                                     numChunks: fromInteger(valueof(t_NUM_CHUNKS))
                                                 };
 
                                      endmethod
 
                                      method notEmptyBody = mar.notEmpty();
                                      method Action deqBody();
                                          mar.deq();           
                                          sent.incr();
                                          continueRequestFired.send;        
                                      endmethod
                                      method firstBody = mar.first;
                                  endinterface;

   let physical_chain_in = interface PHYSICAL_CHAIN_IN;
                               interface clock = myClock;
                               interface reset = myReset;
 
                               method Bool success() = trySuccess;

                               method Action try(PHYSICAL_CHAIN_DATA d);
                                   tryData.wset(d);     
                               endmethod
                           endinterface;

   return tuple2(egress_packet_generator, physical_chain_in);
endmodule
