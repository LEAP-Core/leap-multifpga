/*****************************************************************************
 *
 * Copyright (C) 2011 Intel Corporation
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 */

/******** 
 * This contains a parametric ingress switch.  Here, many outgoing connections converge and 
 * contend for outgoing bandwidth. Bandwidth is allocated only if we know that the receiving
 * switch has sufficient buffering to accept the packet. 
 *
 * This file is a loose derivative of a similar file in the RRR stack. 
 */

import Vector::*;
import FIFOF::*;

`include "awb/provides/channelio.bsh"
`include "awb/provides/rrr.bsh"
`include "awb/provides/umf.bsh"

`include "awb/rrr/service_ids.bsh"

// request/response port interfaces

interface EGRESS_SWITCH#(numeric type n);
    method Vector#(n, Bool)  fifoStatus();
    method Vector#(n, Bool)  bufferStatus();
endinterface

interface EGRESS_PACKET_GENERATOR#(type header, type body);

    method Action deqHeader();
    method header firstHeader();
    method Bool   notEmptyHeader();

    method Action deqBody();
    method body   firstBody();
    method Bool   notEmptyBody();

endinterface


// The egress switch takes two arguments - a read and a write.   The write function is a stream 
// of serialized outbound packets.  The read function takes in flow control credits from the 
// corresponding ingress switch on the other FPGA
module mkEgressSwitch#(EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                                    umf_channel_id, umf_service_id,
                                                    umf_method_id,  umf_message_len,
                                                    umf_phy_pvt,    filler_bits), 
                                                umf_chunk)  requestQueues[],

                       function ActionValue#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                     umf_channel_id_r, umf_service_id_r,
                                                                     umf_method_id_r,  umf_message_len_r,
                                                                     umf_phy_pvt_r,    filler_bits_r), 
                                                                 umf_chunk_r)) read(), 

                       function Action write(umf_chunk data)) 

    (EGRESS_SWITCH#(n)) // Module interface

    provisos(// Compute a non-zero size for the read port index
             Max#(n, 2, n_FIFOS_SAFE),
             Log#(n_FIFOS_SAFE, n_SAFE_FIFOS_SZ),
             Bits#(umf_chunk_r, umf_chunk_r_SZ),
             Bits#(umf_chunk, umf_chunk_SZ),
             Bits#(umf_chunk_r, umf_chunk_r_SZ),
             Bits#(umf_chunk,SizeOf#(GENERIC_UMF_PACKET_HEADER#(
                                                    umf_channel_id, umf_service_id,
                                                    umf_method_id,  umf_message_len,
                                                    umf_phy_pvt,    filler_bits))),
             Add#(umf_message_len, size_extra,TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))),
             Add#(chunk_extra, TAdd#(umf_service_id,TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))), umf_chunk_r_SZ),
             Add#(serviceExcess, n_SAFE_FIFOS_SZ, umf_service_id));

  // If we have no incoming links, don't bother creating a switch. 
  EGRESS_SWITCH#(n) m = ?;
  if(valueof(n) > 0)
    begin
      m <- mkFlowControlSwitchEgressNonZero(requestQueues, read, write);
    end
  return m;

endmodule

// Doesn't work if n == 0
// The read function gives us tokens from the ingress switch
// General idea here is that we can only send for non-zero values
// One issue is simplifying the arbitration logic.  On one hand, we would like to just and buffer_available and fifo_ready. That's simple.  
// But that invovlves dealing with a max sized message, which is probably easy enough.   
module mkFlowControlSwitchEgressNonZero#(EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                                    umf_channel_id, umf_service_id,
                                                    umf_method_id,  umf_message_len,
                                                    umf_phy_pvt,    filler_bits),
                                                umf_chunk)  requestQueues[],

                                         function ActionValue#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                                       umf_channel_id_r, umf_service_id_r,
                                                                                       umf_method_id_r,  umf_message_len_r,
                                                                                       umf_phy_pvt_r,    filler_bits_r), 
                                                                                   umf_chunk_r)) read(), 

                                         function Action write(umf_chunk data)) 

    (EGRESS_SWITCH#(n)) // Module interface

    provisos(  // Compute a non-zero size for the read port index
              Max#(n, 2, n_FIFOS_SAFE),
              Bits#(umf_chunk, umf_chunk_SZ),
              Bits#(umf_chunk_r, umf_chunk_r_SZ), 
              Add#(chunk_extra, TAdd#(umf_service_id,TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))), umf_chunk_r_SZ),
              Bits#(umf_chunk,SizeOf#(GENERIC_UMF_PACKET_HEADER#(
                                                    umf_channel_id, umf_service_id,
                                                    umf_method_id,  umf_message_len,
                                                    umf_phy_pvt,    filler_bits))),
              Log#(n_FIFOS_SAFE, n_FIFOS_SAFE_SZ),
              Add#(umf_message_len, size_extra,TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))),
              Add#(extraServices, n_FIFOS_SAFE_SZ, umf_service_id));

    // ==============================================================
    //                        Ports and Queues
    // ==============================================================

    // Lutram to store the pointer values
    // For now we do a 'full-knowledge' protocol, where each return token signifies return of credis
    LUTRAM#(Bit#(n_FIFOS_SAFE_SZ), Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))) portCredits <- mkLUTRAM(`MULTIFPGA_FIFO_SIZES);
    Vector#(n,Reg#(Bool)) bufferAvailable <- replicateM(mkReg(True));
    Vector#(n,Bool) requestQueuesNotEmpty = newVector();

    for (Integer s = 0; s < valueof(n); s = s + 1)
    begin   
        requestQueuesNotEmpty[s] = requestQueues[s].notEmptyHeader() || requestQueues[s].notEmptyBody();    
    end

    Reg#(Bit#(10)) count <- mkReg(0);

    rule debug(`SWITCH_DEBUG == 1);
        count <= count + 1;
        if(count == 0)
        begin
            for(Integer i = 0; i < fromInteger(valueof(n)); i = i + 1)
            begin
                $display("Egress Queue %d thinks bufferAvailable %b", i, bufferAvailable[i]);
            end
        end
    endrule

    // create request/response buffers and link them to ports



    ARBITER#(n_FIFOS_SAFE) arbiter <- mkRoundRobinArbiter();

    // === other state ===

    Reg#(Bit#(umf_message_len)) requestChunksRemaining  <- mkReg(0);
    Reg#(Bit#(TAdd#(1,umf_message_len))) requestChunks <- mkReg(0);

    Reg#(Bit#(n_FIFOS_SAFE_SZ)) requestActiveQueue  <- mkReg(0);

    Reg#(Bool) deqHeader <- mkReg(True);



    // ==============================================================
    //                          Response Rules
    // ==============================================================

    FIFOF#(Tuple2#(Bit#(umf_service_id),Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))))) creditDelay <- mkFIFOF;

    // scan channel for incoming flowcontrol headers
    // in some cases we can fit the flow control bits in the header, saving bandwidth
    if(valueof(filler_bits_r) > valueof(SizeOf#(Tuple2#(Bit#(umf_service_id), Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))))
)))     
    begin
        rule delayCredits;
            // Pick up the flow control packet header (which contains credit information in the filler bits)
            GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id_r, umf_service_id_r,
                                    umf_method_id_r,  umf_message_len_r,
                                    umf_phy_pvt_r,    filler_bits_r), 
                                umf_chunk_r) packet <- read();

            Tuple2#(Bit#(umf_service_id), Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))) payload = unpack(truncateNP(packet.UMF_PACKET_header.filler)); 
            creditDelay.enq(payload);
        endrule
 
        rule adjustCredits;
            // enqueue header in service's queue
            // set up remaining chunks
            let payload = creditDelay.first();
            creditDelay.deq();  
            let responseActiveQueue  = tpl_1(payload);
            let currentCredits = portCredits.sub(truncate(responseActiveQueue));
            let creditsNext = tpl_2(payload) + currentCredits;
            Bit#(umf_message_len)  max = maxBound;
            bufferAvailable[responseActiveQueue] <= creditsNext >= zeroExtend(max) + 1; // This should always be true...
            portCredits.upd(truncate(responseActiveQueue), creditsNext);
      
            if(`SWITCH_DEBUG == 1)
            begin
                $display("Got flow control body for service %d got %d credits, had %d credits, setting portCredits %d", responseActiveQueue, tpl_2(payload), currentCredits, creditsNext);
            end

            if(creditsNext < zeroExtend(max) && (responseActiveQueue != 0))
            begin
                $display("Setting credits to zero... this is a bug");
                $display("For link %d creditNext %d creditsRX %d currentCredits %d", responseActiveQueue, creditsNext, tpl_2(payload), currentCredits);
                $finish;
            end      

            if(creditsNext > `MULTIFPGA_FIFO_SIZES && (responseActiveQueue != 0))
            begin
                $display("Credits have overflowed fifo size... this is a bug");
                $display("For link %d creditNext %d creditsRX %d currentCredits %d", responseActiveQueue, creditsNext, tpl_2(payload), currentCredits);
                $finish;
            end      


        endrule
    end
    else // In this case, the header doesn't have enough space for flow control bits. The come in the second chunk.
    begin

        rule dropHeader (deqHeader);
            let packet <- read();
            deqHeader <= !deqHeader;
        endrule
  
        rule scan_responses (!deqHeader);
            deqHeader <= !deqHeader;
            GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id_r, umf_service_id_r,
                                    umf_method_id_r,  umf_message_len_r,
                                    umf_phy_pvt_r,    filler_bits_r), 
                                umf_chunk_r) packet <- read();

            // enqueue header in service's queue
            // set up remaining chunks
            Tuple2#(Bit#(umf_service_id), Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))) payload =  unpack(truncate(pack(packet.UMF_PACKET_dataChunk))); 
            let responseActiveQueue  = tpl_1(payload);
            let currentCredits = portCredits.sub(truncate(responseActiveQueue));
            let creditsNext = tpl_2(payload) + currentCredits;
            Bit#(umf_message_len) max = maxBound;
            bufferAvailable[responseActiveQueue] <= creditsNext >= zeroExtend(max); // This should always be true...
            portCredits.upd(truncate(responseActiveQueue), creditsNext);
            if(`SWITCH_DEBUG == 1)
            begin
                $display("Got flow control body for service %d got %d credits, had %d credits, setting portCredits %d", responseActiveQueue, payload, currentCredits, creditsNext);
            end

            if(creditsNext < zeroExtend(max))
            begin
                $display("Setting credits to zero... this is a bug");
                $finish;
            end      
        endrule
    end

    // ==============================================================
    //                          Request Rules
    // ==============================================================

    //
    // Start writing new message.  The write_request_newmsg rule is broken
    // into two parts in order to help Bluespec generate a significantly simpler
    // schedule than if the rules are combined.  Separating the rules breaks
    // the connection between arbiter input vector state and the test for
    // whether a requestQueue has data.
    //

    Wire#(Maybe#(UInt#(n_FIFOS_SAFE_SZ))) newMsgQIdx <- mkDWire(tagged Invalid);

    //
    // First half -- pick an incoming requestQueue
    // we could make this 
    //
    rule write_request_newmsg1 (requestChunksRemaining == 0);

        // arbitrate
        Bit#(n_FIFOS_SAFE) request = '0;
        for (Integer s = 0; s < valueof(n); s = s + 1)
        begin
            request[s] = pack(requestQueues[s].notEmptyHeader() && (bufferAvailable[s] || s == 0)); // Channel 0 is flow control, and has no buffer
        end

        newMsgQIdx <= arbiter.arbitrate(request); 
        if(request != 0 && `SWITCH_DEBUG == 1)
        begin
	    $display("Egress BufferAvailible %b Reqs %b", pack(readVReg(bufferAvailable)), request);
        end
    endrule

    //
    // Second half -- consume a value from the chosen responseQueue.  If the
    // rule fails to fire because the channel write port is full it will fire
    // again later after being reselected by the first half.
    //
    for (Integer s = 0; s < valueof(n); s = s + 1)
    begin	
        rule write_request_newmsg2 (newMsgQIdx matches tagged Valid .idx &&&
                                    fromInteger(s) == idx &&&
                                    requestChunksRemaining == 0 &&&
                                    !creditDelay.notEmpty());
            if(`SWITCH_DEBUG == 1)
            begin
                $display("scheduled %d", idx);
            end

            requestQueues[s].deqHeader();
            let header = requestQueues[s].firstHeader;
            // send the header packet to channelio
            write(unpack(pack(header))); // The guys above us know how to set VC, etc.

            // setup remaining chunks
            requestChunksRemaining <= header.numChunks;
            Bit#(TAdd#(1,umf_message_len)) requestChunks = zeroExtend(header.numChunks) + 1; // also sending header
            requestActiveQueue <= fromInteger(s);
           
            Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))) oldCredits = portCredits.sub(fromInteger(s)); 

            Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))) newCount =  oldCredits - zeroExtendNP(requestChunks);
            portCredits.upd(fromInteger(s),newCount);
            Bit#(umf_message_len) max = maxBound;
            bufferAvailable[fromInteger(s)] <= newCount >= zeroExtend(max) + 1; 
 
            if(`SWITCH_DEBUG == 1)
            begin
                $display("Setting portCredits for %d to %d", s, newCount);
            end

           if(oldCredits < zeroExtendNP(requestChunks) && (s != 0))
           begin
               $display("Bizzarre Credit Underflow oldCredit %d messageSize %d newCount %d max %d", oldCredits, requestChunks, newCount, max);
               $finish;               
           end

        endrule
    end  // Outgoing channel for loop


    // continue writing message
    rule write_request_continue (requestChunksRemaining != 0);
        if(`SWITCH_DEBUG == 1)
        begin
            $display("sending packet on  %d", requestActiveQueue);  
        end

        // get the next packet from the active request queue
        requestQueues[requestActiveQueue].deqBody();

        // send the packet to channelio
        write(unpack(pack(requestQueues[requestActiveQueue].firstBody)));

        // one more chunk processed
        requestChunksRemaining <= requestChunksRemaining - 1;

    endrule

    // ==============================================================
    //                        Set Interfaces
    // ==============================================================


    method fifoStatus = requestQueuesNotEmpty;
    method bufferStatus = readVReg(bufferAvailable);
endmodule


