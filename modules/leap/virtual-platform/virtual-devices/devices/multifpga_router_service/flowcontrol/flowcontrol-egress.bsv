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

    method Integer maxPacketSize();

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
             Bits#(umf_chunk,SizeOf#(GENERIC_UMF_PACKET_HEADER#(
                                                    umf_channel_id, umf_service_id,
                                                    umf_method_id,  umf_message_len,
                                                    umf_phy_pvt,    filler_bits))),
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
              Add#(extraServices, n_FIFOS_SAFE_SZ, umf_service_id));

    // Packets may only be sent if the receiving queue is known to have
    // buffer space. To help with timing, we calculate this buffer space
    // based on some maximum packet size. Each egress generator will tell
    // us its maximum packet size, and we will use the maximum, maximum
    // packet size to determine whether to send.  This is suboptimal, but
    // uses less hardware, since only one value needs to be stored.

    Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))) maximumPacketSize = 0;
    for (Integer s = 0; s < valueof(n); s = s + 1)
    begin   
        if(fromInteger(requestQueues[s].maxPacketSize()) > maximumPacketSize)
        begin
            maximumPacketSize = fromInteger(requestQueues[s].maxPacketSize());
        end
    end

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



    // ==============================================================
    //                          Response Rules
    // ==============================================================

    FIFOF#(Tuple2#(Bit#(umf_service_id),Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))))) creditDelay <- mkFIFOF;

    // scan channel for incoming flowcontrol headers
    // in some cases we can fit the flow control bits in the header, saving bandwidth
    if((`PACK_FLOWCONTROL == 1) && (valueof(filler_bits_r) > valueof(SizeOf#(Tuple2#(Bit#(umf_service_id), Bit#(TAdd#(1,TLog#(`MULTIFPGA_FIFO_SIZES))))
))))     
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
           
            bufferAvailable[responseActiveQueue] <= creditsNext >= maximumPacketSize + 1; // This should always be true...
            portCredits.upd(truncate(responseActiveQueue), creditsNext);
      
            if(`SWITCH_DEBUG == 1)
            begin
                $display("Got flow control body for service %d got %d credits, had %d credits, setting portCredits %d", responseActiveQueue, tpl_2(payload), currentCredits, creditsNext);
            end

            if(creditsNext < maximumPacketSize)
            begin
                $display("Setting credits to zero... this is a bug");
                $display("Switch %s For link %d creditNext %d creditsRX %d currentCredits %d", name, responseActiveQueue, creditsNext, tpl_2(payload), currentCredits);
                $finish;
            end      

            if(creditsNext > `MULTIFPGA_FIFO_SIZES)
            begin
                $display("Credits have overflowed fifo size... this is a bug %m");
                $display("Switch %s For link %d creditNext %d creditsRX %d currentCredits %d", name, responseActiveQueue, creditsNext, tpl_2(payload), currentCredits);
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
            let currentCredits = portCredits.sub(truncate(responseActiveQueue));
            let creditsNext = tpl_2(payload) + currentCredits;
            
            bufferAvailable[responseActiveQueue] <= creditsNext >= maximumPacketSize; // This should always be true...
            portCredits.upd(truncate(responseActiveQueue), creditsNext);
            if(`SWITCH_DEBUG == 1)
            begin
                $display("Got flow control body for service %d got %d credits, had %d credits, setting portCredits %d", responseActiveQueue, payload, currentCredits, creditsNext);
            end

            if(creditsNext < maximumPacketSize)
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
            bufferAvailable[s] && ! requestQueues[s].bypassFlowcontrol;

        Vector#(n, Bool) buf_avail_normal = map(bufAvailNormal, genVector());


        // Buffers available for flow control requests
        function Bool bufAvailFC(Integer s) =
            requestQueues[s].bypassFlowcontrol;

        Vector#(n, Bool) buf_avail_fc = map(bufAvailFC, genVector());


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
            let header = requestQueues[s].firstHeader;

            // We can use resize here without danger because of the
            // way we calculate the maximumPacketSize. The fromInteger in
            // that function will fail at compile time if the
            // maximumPacketSize is bigger than the number fo credits
            // available.
 
            Bit#(TAdd#(1, TLog#(`MULTIFPGA_FIFO_SIZES))) requestChunks = resize(header.numChunks) + 1; // also sending header
            Bit#(TAdd#(1, TLog#(`MULTIFPGA_FIFO_SIZES))) oldCredits = portCredits.sub(fromInteger(s));

            if(`SWITCH_DEBUG == 1)
            begin
                $display("scheduled %d", s);
            end

            requestQueues[s].deqHeader();
            // send the header packet to channelio
            write(unpack(pack(header))); // The guys above us know how to set VC, etc.

            // setup remaining chunks
            requestChunksRemaining <= header.numChunks;
            requestActiveQueue <= fromInteger(s);

            Bit#(TAdd#(1, TLog#(`MULTIFPGA_FIFO_SIZES))) newCount =  oldCredits - zeroExtendNP(requestChunks);
            portCredits.upd(fromInteger(s), newCount);
           
            bufferAvailable[s] <= newCount >= maximumPacketSize + 1; 

            if(`SWITCH_DEBUG == 1)
            begin
                $display("Setting portCredits for port %d to %d", s, newCount);
            end

            if (oldCredits < zeroExtendNP(requestChunks) && (s != 0))
            begin
                $display("Bizzarre Credit Underflow oldCredit %d messageSize %d newCount %d max %d", oldCredits, requestChunks, newCount, maximumPacketSize);
                $finish;               
            end
        endrule
    end


    // continue writing message
    rule writeRequestContinue (requestChunksRemaining != 0);
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

