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
import DReg::*;


`include "awb/provides/channelio.bsh"
`include "awb/provides/rrr_common.bsh"
`include "awb/provides/umf.bsh"
`include "awb/provides/librl_bsv_base.bsh"
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

    method Bool   bypassFlowcontrol(); // Some of these are flowcontrol, so they must be declared

endinterface


// The egress switch takes two arguments - a read and a write.   The write function is a stream 
// of serialized outbound packets.  The read function takes in flow control credits from the 
// corresponding ingress switch on the other FPGA
module mkEgressSwitch#(EGRESS_PACKET_GENERATOR#(GENERIC_UMF_PACKET_HEADER#(
                                                    umf_channel_id, umf_service_id,
                                                    umf_method_id,  umf_message_len,
                                                    umf_phy_pvt,    filler_bits), 
                                                umf_chunk)  requestQueues[],

                       SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                umf_channel_id_r, umf_service_id_r,
                                                umf_method_id_r,  umf_message_len_r,
                                                umf_phy_pvt_r,    filler_bits_r),
                                           umf_chunk_r)) flowcontrol,

                       function Action write(umf_chunk data),
                       String name,
                       Bool singleCycleArb)

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
      m <- mkFlowControlSwitchEgressNonZero(requestQueues,
                                            flowcontrol,
                                            write,
                                            name,
                                            singleCycleArb);
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

                                         SWITCH_INGRESS_PORT#(GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                                                                       umf_channel_id_r, umf_service_id_r,
                                                                                       umf_method_id_r,  umf_message_len_r,
                                                                                       umf_phy_pvt_r,    filler_bits_r), 
                                                                                   umf_chunk_r)) flowcontrol, 

                                         function Action write(umf_chunk data),
                                         String name,
                                         Bool singleCycleArb)

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

    // definition of maximum length message
    Bit#(umf_message_len)  maxMessageLength = maxBound;


    // =====
    //   Debug Registers
    // =====

    Reg#(Bit#(64)) totalSent <- mkReg(0);
    Reg#(Bit#(64)) totalCreditsReceived <- mkReg(0);

    // ==============================================================
    //                        Ports and Queues
    // ==============================================================

    // Lutram to store the pointer values
    // For now we do a 'full-knowledge' protocol, where each return token signifies return of credits
    LUTRAM#(Bit#(n_FIFOS_SAFE_SZ), Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))) portCreditsUsed <- mkLUTRAM(0);
    Vector#(n, Reg#(Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))))) portCreditsUsedDebug <- replicateM(mkReg(0));

    Reg#(Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))) totalCreditsUsed <- mkReg(0);    

    // If we have a lot of credit, all queues can contend. 
    Reg#(Bool) creditsHigh <- mkReg(False);

    Vector#(n,Reg#(Bool)) bufferAvailable <- replicateM(mkReg(True));
    Vector#(n,Bool) requestQueuesNotEmpty = newVector();

    Reg#(Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))) returnThreshold <- mkReg(fromInteger(`MULTIFPGA_FIFO_SIZES - valueof(n) * `MINIMUM_CHANNEL_BUFFER));

    for (Integer s = 0; s < valueof(n); s = s + 1)
    begin   
        requestQueuesNotEmpty[s] = requestQueues[s].notEmptyHeader() || requestQueues[s].notEmptyBody();    
    end

    Reg#(Bit#(10)) count <- mkReg(0);

    Reg#(Bool) activity <- mkDReg(False);


    function Action dumpState();
      action
        $display("Egress Queue Total Credits: %d, returnThreshold: %d, totalSent: %d, totalCreditsReceived: %d", totalCreditsUsed, returnThreshold, totalSent, totalCreditsReceived);
        for(Integer i = 0; i < fromInteger(valueof(n)); i = i + 1)
        begin
            $display("Egress Queue %d thinks bufferAvailable %b creditsUsed: %d", i, bufferAvailable[i], portCreditsUsedDebug[i]);
        end
      endaction
    endfunction

    rule debug(`SWITCH_DEBUG == 1 && activity);
        dumpState();
        if(totalCreditsUsed > `MULTIFPGA_FIFO_SIZES) 
        begin
            $display("Egress uses too many credits");
            $finish;
        end
    endrule

    rule tooManyCredits(totalCreditsUsed > `MULTIFPGA_FIFO_SIZES);
        dumpState();
        $display("Egress uses too many credits");
    endrule

    // Use a random arbiter since the arbitration runs speculatively and
    // doesn't know whether the winner gets to fire.  Given this, no arbiter
    // will be fair since even with random the relative vector position of
    // requestors may favor one over the other when only a few are firing.
    // In the long run this probably doesn't matter as long as the link stays
    // busy.
    LOCAL_ARBITER#(n) arbiter <- mkLocalRandomArbiter();


    // === other state ===

    Reg#(Bit#(umf_message_len)) requestChunksRemaining  <- mkReg(0);
    Reg#(Bit#(TAdd#(1,umf_message_len))) requestChunks <- mkReg(0);

    Reg#(Bit#(n_FIFOS_SAFE_SZ)) requestActiveQueue  <- mkReg(0);

    Reg#(Bool) deqHeader <- mkReg(True);


    // We subtract an extra credit just to make sure that the value is conservative, since the register
    // will be used to arbitrate in the next cycle. 
    rule updateCreditsHigh;
        creditsHigh <= (totalCreditsUsed < returnThreshold - zeroExtend(maxMessageLength) - 1); 
    endrule

    // ==============================================================
    //                          Response Rules
    // ==============================================================

    FIFOF#(Tuple2#(Bit#(umf_service_id),Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))))) creditDelay <- mkFIFOF;

    // scan channel for incoming flowcontrol headers
    // in some cases we can fit the flow control bits in the header, saving bandwidth
    if(valueof(filler_bits_r) > valueof(SizeOf#(Tuple2#(Bit#(umf_service_id), Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))))
)) && `PACK_FLOWCONTROL == 1)     
    begin

	rule creditReadReady (creditDelay.notFull());
 	    flowcontrol.read_ready(); // Needed for VLevelFIFO
        endrule

        rule delayCredits;
            // Pick up the flow control packet header (which contains credit information in the filler bits)
            GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id_r, umf_service_id_r,
                                    umf_method_id_r,  umf_message_len_r,
                                    umf_phy_pvt_r,    filler_bits_r), 
                                umf_chunk_r) packet <- flowcontrol.read();

            Tuple2#(Bit#(umf_service_id), Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))) payload = unpack(truncateNP(packet.UMF_PACKET_header.filler)); 
            $display("Credit Packet: %h", packet);
            $display("Credit Message: %h", payload);
            creditDelay.enq(payload);
        endrule
 
        rule adjustCredits;
            activity <= True;
            // enqueue header in service's queue
            // set up remaining chunks
            let payload = creditDelay.first();
            creditDelay.deq();  
            let responseActiveQueue  = tpl_1(payload);
            let currentCredits = portCreditsUsed.sub(truncate(responseActiveQueue));
            let creditsNext = currentCredits - tpl_2(payload);
            let totalCreditsNext = totalCreditsUsed - tpl_2(payload); 
            totalCreditsReceived <= totalCreditsReceived + zeroExtendNP(tpl_2(payload));

            // Channel has guaranteed buffer, if it is under the minimum channel threshold
            bufferAvailable[responseActiveQueue] <= (creditsNext < min(0,`MINIMUM_CHANNEL_BUFFER - zeroExtend(maxMessageLength))); 

            portCreditsUsed.upd(truncate(responseActiveQueue), creditsNext);
            portCreditsUsedDebug[responseActiveQueue] <= creditsNext;
            totalCreditsUsed <= totalCreditsNext;

            if(`SWITCH_DEBUG == 1)
            begin
                $display("Got flowcontrol body for service %d got %d credits, had %d credits, setting portCredits %d", responseActiveQueue, tpl_2(payload), currentCredits, creditsNext);
            end

            if(tpl_2(payload) > `MULTIFPGA_FIFO_SIZES)
            begin
                $display("pointer-egress Got too many credits: %d", tpl_2(payload));
                $finish;
            end

            if(creditsNext > currentCredits)
            begin
                $display("Setting credits to zero... this is a bug");
                $display("Switch %s For link %d creditNext %d creditsRX %d currentCredits %d", name, responseActiveQueue, creditsNext, tpl_2(payload), currentCredits);
                dumpState();
                $finish;
            end      

        endrule
    end
    else // In this case, the header doesn't have enough space for flow control bits. The come in the second chunk.
    begin

        // We appear always ready to read....
        // it might be that we want a fifo here also just to simplfy things. 
	rule creditReadReady;
 	    flowcontrol.read_ready();
        endrule

        rule dropHeader (deqHeader);
            let packet <- flowcontrol.read();
            deqHeader <= !deqHeader;
        endrule
  
        rule scan_responses (!deqHeader);
            activity <= True;
            deqHeader <= !deqHeader;
            GENERIC_UMF_PACKET#(GENERIC_UMF_PACKET_HEADER#(
                                    umf_channel_id_r, umf_service_id_r,
                                    umf_method_id_r,  umf_message_len_r,
                                    umf_phy_pvt_r,    filler_bits_r), 
                                umf_chunk_r) packet <- flowcontrol.read();

            // enqueue header in service's queue
            // set up remaining chunks
            Tuple2#(Bit#(umf_service_id), Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES)))) payload =  unpack(truncate(pack(packet.UMF_PACKET_dataChunk))); 
            let responseActiveQueue  = tpl_1(payload);
            let currentCredits = portCreditsUsed.sub(truncate(responseActiveQueue));
            let creditsNext = currentCredits - tpl_2(payload);
            let totalCreditsUsedNext = totalCreditsUsed - tpl_2(payload);	 
            totalCreditsUsed <= totalCreditsUsedNext;
            totalCreditsReceived <= totalCreditsReceived + zeroExtendNP(tpl_2(payload));
            
            // Channel has guaranteed buffer, if it is under the minimum channel threshold
            bufferAvailable[responseActiveQueue] <= (creditsNext < min(0,`MINIMUM_CHANNEL_BUFFER - zeroExtend(maxMessageLength))); 

            portCreditsUsed.upd(truncate(responseActiveQueue), creditsNext);
            portCreditsUsedDebug[responseActiveQueue] <= creditsNext;

            if(`SWITCH_DEBUG == 1)
            begin
                $display("Got flowcontrol body for service %d got %d credits, had %d credits, setting portCredits %d", responseActiveQueue, tpl_2(payload), currentCredits, creditsNext);
            end

            if(tpl_2(payload) > `MULTIFPGA_FIFO_SIZES)
            begin
                $display("pointer-egress Got too many credits: %d", tpl_2(payload));
                $finish;
            end

            if(creditsNext > currentCredits)
            begin
                $display("Setting credits to zero... this is a bug");
                $display("Switch %s For link %d creditNext %d creditsRX %d currentCredits %d", name, responseActiveQueue, creditsNext, tpl_2(payload), currentCredits);
                dumpState();
                $finish;
            end      

        endrule
    end

    // ==============================================================
    //                          Request Rules
    // ==============================================================

    //
    // Start writing new message.  The write_request_newmsg rule is broken
    // into two parts for timing.  For large numbers of incoming ports, the
    // cost of MUXing input values to the output port is too large for
    // arbitration and MUXing in a single cycle.
    //

    FLOWCONTROL_ARBITER_IDX#(n) newMsgQIdx <-
        singleCycleArb ? mkFlowControlArbIdxSingleCycle() :
                         mkFlowControlArbIdxMultiCycle();


    //
    // First half -- pick an incoming requestQueue.
    //
    rule writeRequestNewmsg1 (True);

        // Incoming channel has a request and the channel isn't locked
        function Bool hasRequest(Integer s) =
            requestQueues[s].notEmptyHeader() &&
            newMsgQIdx.notLocked(fromInteger(s));

        Vector#(n, Bool) has_request = map(hasRequest, genVector());

        // Buffers available for normal requests
        function Bool bufAvailNormal(Integer s) =
            (creditsHigh || bufferAvailable[s]) && !requestQueues[s].bypassFlowcontrol;

        Vector#(n, Bool) buf_avail_normal = map(bufAvailNormal, genVector());

        // Flow control is always sendable.
        function Bool bypassFlowcontrol(Integer s) =
           requestQueues[s].bypassFlowcontrol;

        Vector#(n, Bool) buf_avail_fc = map(bypassFlowcontrol, genVector());
    

        // Generate the request vectors
        let req_normal = zipWith(\&& , has_request, buf_avail_normal);
        let req_fc = zipWith(\&& , has_request, buf_avail_fc);


        // Flow control requests have priority
        Vector#(n, Bool) reqs;
        if (pack(req_fc) != 0)
        begin
            reqs = req_fc;

            if (`SWITCH_DEBUG != 0)
            begin
                $display("FC wins right to arb");
            end
        end
        else
        begin
            reqs = req_normal;

            if (`SWITCH_DEBUG != 0 && (pack(req_normal) != 0))
            begin
                $display("Normal wins right to arb");
            end
        end


        // Pick a winner.
        let winner <- arbiter.arbitrate(reqs, False);
        newMsgQIdx.setWinner(winner);

        if (winner matches tagged Valid .idx &&& `SWITCH_DEBUG == 1)
        begin
	    $display("Egress BufferAvailible %b Reqs %b choosing %d", pack(readVReg(bufferAvailable)), pack(reqs), idx);
        end
    endrule


    //
    // Second half -- consume a value from the chosen responseQueue.  If the
    // rule fails to fire because the channel write port is full it will fire
    // again later after being reselected by the first half.
    //
    // This second half runs a cycle later for timing -- the MUX of input
    // sources is too large to run in one cycle along with arbitration.
    //
    for (Integer s = 0; s < valueOf(n); s = s + 1)
    begin	
        rule writeRequestNewmsg2 (newMsgQIdx.getWinner() matches tagged Valid .idx &&&
                                  idx == fromInteger(s) &&&
                                  requestChunksRemaining == 0 &&&
                                  !creditDelay.notEmpty() &&&
                                  deqHeader);
            activity <= True;
            let header = requestQueues[s].firstHeader;
            Bit#(TAdd#(1, TLog#(`MULTIFPGA_FIFO_SIZES))) requestChunks = zeroExtend(header.numChunks) + 1; // also sending header
            Bit#(TAdd#(1, TLog#(`MULTIFPGA_FIFO_SIZES))) oldCredits = portCreditsUsed.sub(fromInteger(s));

            if(`SWITCH_DEBUG == 1)
            begin
                $display("scheduled %d", s);
            end

            requestQueues[s].deqHeader();
            // send the header packet to channelio
            write(unpack(pack(header))); // The guys above us know how to set VC, etc.
            totalSent <= totalSent + 1;
            // setup remaining chunks
            requestChunksRemaining <= header.numChunks;
            requestActiveQueue <= fromInteger(s);

            Bit#(TAdd#(1, TLog#(`MULTIFPGA_FIFO_SIZES))) creditsNext =  oldCredits + zeroExtendNP(requestChunks);
            Bit#(TAdd#(1, TLog#(`MULTIFPGA_FIFO_SIZES))) totalCreditsUsedNext =  totalCreditsUsed + zeroExtendNP(requestChunks);	
            
            // Channel has guaranteed buffer, if it is under the minimum channel threshold
            bufferAvailable[fromInteger(s)] <= (creditsNext < min(0,`MINIMUM_CHANNEL_BUFFER - zeroExtend(maxMessageLength))); 


            totalCreditsUsed <= totalCreditsUsedNext;
            portCreditsUsed.upd(fromInteger(s), creditsNext);
            portCreditsUsedDebug[fromInteger(s)] <= creditsNext;

            if(`SWITCH_DEBUG == 1)
            begin
                $display("Setting portCredits for port %d from %d to %d totalCredits", s, oldCredits, creditsNext);
            end

        endrule
    end


    // continue writing message
    rule writeRequestContinue (requestChunksRemaining != 0);
        activity <= True;
        if(`SWITCH_DEBUG == 1)
        begin
            $display("sending packet on  %d", requestActiveQueue);  
        end

        // get the next packet from the active request queue
        requestQueues[requestActiveQueue].deqBody();

        // send the packet to channelio
        write(unpack(pack(requestQueues[requestActiveQueue].firstBody)));
        totalSent <= totalSent + 1;

        // one more chunk processed
        requestChunksRemaining <= requestChunksRemaining - 1;

    endrule

    // ==============================================================
    //                        Set Interfaces
    // ==============================================================


    method fifoStatus = requestQueuesNotEmpty;
    method bufferStatus = readVReg(bufferAvailable);
endmodule



// ========================================================================
//
// Flow control arbiter presents an interface that can be used either for
// same cycle or next cycle arbitration.
//
// ========================================================================

interface FLOWCONTROL_ARBITER_IDX#(numeric type n);
    method Action setWinner(Maybe#(LOCAL_ARBITER_CLIENT_IDX#(n)) winner);
    method Maybe#(LOCAL_ARBITER_CLIENT_IDX#(n)) getWinner();

    //
    // notLocked() indicates whether a request may fire for a given
    // port this cycle.
    //
    method Bool notLocked(LOCAL_ARBITER_CLIENT_IDX#(n) s);
endinterface


//
// mkFlowControlArbIdxSingleCycle --
//     Consumer of arbitration fires in the same cycle as the arbiter.
//
module mkFlowControlArbIdxSingleCycle
    // Interface:
    (FLOWCONTROL_ARBITER_IDX#(n));

    Wire#(Maybe#(LOCAL_ARBITER_CLIENT_IDX#(n))) newMsgQIdx <- mkDWire(tagged Invalid);

    method Action setWinner(Maybe#(LOCAL_ARBITER_CLIENT_IDX#(n)) winner);
        newMsgQIdx <= winner;
    endmethod

    method Maybe#(LOCAL_ARBITER_CLIENT_IDX#(n)) getWinner() = newMsgQIdx;
    method Bool notLocked(LOCAL_ARBITER_CLIENT_IDX#(n) s) = True;
endmodule


//
// mkFlowControlArbIdxMultiCycle --
//     Consumer of arbitration fires in the cycle after the arbiter.
//     Arbitration is pipelined, though the same input may not win in
//     consecutive cycles to simplify credit accounting.
//
module mkFlowControlArbIdxMultiCycle
    // Interface:
    (FLOWCONTROL_ARBITER_IDX#(n));

    Reg#(Maybe#(LOCAL_ARBITER_CLIENT_IDX#(n))) newMsgQIdx <- mkDReg(tagged Invalid);

    method Action setWinner(Maybe#(LOCAL_ARBITER_CLIENT_IDX#(n)) winner);
        newMsgQIdx <= winner;
    endmethod

    method Maybe#(LOCAL_ARBITER_CLIENT_IDX#(n)) getWinner() = newMsgQIdx;

    // Can't win in back-to-back cycles
    method Bool notLocked(LOCAL_ARBITER_CLIENT_IDX#(n) s) =
        ! (isValid(newMsgQIdx) && (validValue(newMsgQIdx) == s));
endmodule

