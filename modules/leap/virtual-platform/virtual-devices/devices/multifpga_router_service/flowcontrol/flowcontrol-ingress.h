//
// Copyright (c) 2013, Intel Corporation
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


#ifndef __FLOWCONTROL_INGRESS__
#define __FLOWCONTORL_INGRESS__

#include <queue>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <pthread.h>

#include "asim/trace.h"

#include "platforms-module.h"
#include "awb/provides/umf.h"
#include "awb/provides/physical_channel.h"
#include "awb/provides/multifpga_switch.h"
#include "awb/provides/li_base_types.h"
#include "tbb/concurrent_queue.h"
#include "tbb/compat/condition_variable"
#include "tbb/atomic.h"


// FLOWCONTROL_OUT_CLASS --
// Implements a flow control management class for inbound LI
// channels.  Flowcontrol messages are out-bound from the FPGA, hence
// the name. This class inherits LI_CHANNEL_OUT_CLASS because it semds
// messages to the FPGA. This class has a single, thread-safe channel which
// is shared by all outbound channels.  These messages are consumed in the 
// hardwawre-side buffer switch.
//
// This class is instantiated once per physical inbound interconnect, and manages 
// all inbound channels on that interconnect.
//
class FLOWCONTROL_OUT_CLASS: public LI_CHANNEL_OUT_CLASS
{
  private:
    vector<LI_CHANNEL_IN> *inChannels;

  public:
    FLOWCONTROL_OUT_CLASS(vector<LI_CHANNEL_IN> *inChannelInitializer,  class tbb::concurrent_bounded_queue<UMF_MESSAGE> *outputQInitializer);
    void Init() {};
};

// FLOWCONTROL_LI_CHANNEL_IN_CLASS --
// Implements flow control for inbound LI channels.  The inbound
// channel using the service will acquireCredit as it processes messages,
// under the assumption that software has nearly unlimited buffering.  
// After sufficient credits are acquired, they will be freed by returning
// a flow control message to hardware. We send these messages in bulk to 
// reduce messaging overhead. Outbound messages are sent through the channel 
// provided by the FLOWCONTROL_OUT_CLASS above.
//

// Add a flow control interface to outbound channels
typedef class FLOWCONTROL_LI_CHANNEL_IN_CLASS* FLOWCONTROL_LI_CHANNEL_IN;
class FLOWCONTROL_LI_CHANNEL_IN_CLASS: public LI_CHANNEL_IN_CLASS
{
  protected:  
    // We use a atomic variable to store credits and implement a lock-free protocol.
    class tbb::atomic<UINT32> flowcontrolCredits;    
    class tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQ; // Reference to global flow control queue messages
    UINT64 flowcontrolChannelID;  // channel ID of flowcontrol queue.
    UMF_FACTORY factory; // We use this factory to produce outgoing flowcontrol messages.
    ofstream *debugLog;

  public:

    FLOWCONTROL_LI_CHANNEL_IN_CLASS(ofstream *debugLogInitializer,
                                    tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQInitializer,
				    UMF_FACTORY factoryInitializer,
                                    UINT64 flowcontrolChannelIDInitializer):
        LI_CHANNEL_IN_CLASS(),
	flowcontrolCredits()
    { 
        factory = factoryInitializer;
        flowcontrolQ = flowcontrolQInitializer;
        flowcontrolChannelID = flowcontrolChannelIDInitializer;
        flowcontrolCredits = 0;   
        debugLog = debugLogInitializer;
    };

    ~FLOWCONTROL_LI_CHANNEL_IN_CLASS() {};


    // freeCredits --
    //   returns credits to appropriate FPGA-side switch, but only if a sufficient number of
    //   credits have been accumulated. 
    void freeCredits(UINT32 serviceID)
    {

        if (SWITCH_DEBUG) {
            (*debugLog) << "Channel " << serviceID  << " has retired  " <<  flowcontrolCredits << "credits " << endl;
        }

	if (flowcontrolCredits > ((1 * MULTIFPGA_FIFO_SIZES) / 2))
	{

	    UMF_MESSAGE outMesg = factory->createUMFMessage();
	    outMesg->SetLength(sizeof(UMF_CHUNK));
	    outMesg->SetServiceID(flowcontrolChannelID);

            // Atomic read returns the old value, making this operation thread safe under idempotence.
            UINT32 creditsToReturn = flowcontrolCredits.fetch_and_store(0);                         
            UINT32 phyPvt =  (serviceID * 2 * MULTIFPGA_FIFO_SIZES) | creditsToReturn;  


            if (SWITCH_DEBUG) {
                (*debugLog) << "Credit Chunk " << phyPvt << " from service " << 
                  (serviceID * 2 * MULTIFPGA_FIFO_SIZES) << " and credits " << creditsToReturn << endl;
            }

            outMesg->AppendChunk((UINT128) phyPvt);              
	    flowcontrolQ->push(outMesg);
	}
    }

    // acquireCredits --
    //   called when channel releases message credits. 
    void acquireCredits(UINT32 creditsAcquired) {
        flowcontrolCredits.fetch_and_add(creditsAcquired);
    }

};


#endif
