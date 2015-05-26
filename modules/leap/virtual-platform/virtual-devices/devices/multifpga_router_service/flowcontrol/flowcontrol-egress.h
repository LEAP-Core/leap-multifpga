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

#ifndef __FLOWCONTROL_EGRESS__
#define __FLOWCONTORL_EGRESS__

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
#include "awb/provides/li_base_types.h"
#include "tbb/concurrent_queue.h"
#include "tbb/compat/condition_variable"
#include "tbb/atomic.h"

// FLOWCONTROL_IN_CLASS --
// Implements a flow control management class for outbound LI
// channels.  Flowcontrol messages are in-bound from the FPGA, hence
// the name. This class inherits LI_CHANNEL_IN_CLASS because it receives
// messages from the FPGA. These messages are special flow control
// messages, which the class then deals out to the various waiting
// threads. Incoming credit messages will update the credit count and wake any
// sleeping threads.
//
// This class is instantiated once per physical outbound interconnect, and manages 
// all outbound channels on that interconnect.
//

class FLOWCONTROL_IN_CLASS: public LI_CHANNEL_IN_CLASS
{
  private:
    vector<LI_CHANNEL_OUT> *outChannels;
    ofstream debugLog;

  public:
    FLOWCONTROL_IN_CLASS(vector<LI_CHANNEL_OUT> *outChannelInitializer,
                         tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQInitializer,
      	                 UMF_FACTORY factoryInitializer,
                         UINT64 flowcontrolChannelIDInitializer);

    virtual void pushUMF(UMF_MESSAGE &message); 
    void Init() {};
};

// FLOWCONTROL_LI_CHANNEL_OUT_CLASS --
// Implements flow control for outbound LI channels.  The outbound
// channel using the service will acquireCredit before it transmits. 
// If no or too little credit is available, the channel will
// block. Initially the channel will spin in the hope that a message
// arrives soon, but later, it will go to sleep on a condition
// variable.
//
// Incoming credit messages will freeCredits, updating the credit count and wake any
// sleeping threads.

typedef class FLOWCONTROL_LI_CHANNEL_OUT_CLASS* FLOWCONTROL_LI_CHANNEL_OUT;
class FLOWCONTROL_LI_CHANNEL_OUT_CLASS: public LI_CHANNEL_OUT_CLASS
{
  protected:  
    class tbb::atomic<UINT32> flowcontrolCredits;    
    class std::mutex flowcontrolMutex; 
    condition_variable flowcontrolVariable; 
    timespec start;
    ofstream *debugLog;

  public:

    static UINT32 retryThreshold;

    FLOWCONTROL_LI_CHANNEL_OUT_CLASS(ofstream *debugLogInitializer, class tbb::concurrent_bounded_queue<UMF_MESSAGE> *outputQInitializer):
        LI_CHANNEL_OUT_CLASS(outputQInitializer),
	flowcontrolCredits(),
        flowcontrolMutex(),
        flowcontrolVariable()  
    { 
        flowcontrolMutex.lock();
        flowcontrolCredits.fetch_and_add(MULTIFPGA_FIFO_SIZES);
        flowcontrolMutex.unlock();        
        clock_gettime(CLOCK_REALTIME, &start);
        debugLog = debugLogInitializer;
    };

    ~FLOWCONTROL_LI_CHANNEL_OUT_CLASS() {};

    // free credits may need to be overridden by route through codes. 
    void freeCredits(UINT32 credits) 
    {
        timespec finish;
        if(outputQ != NULL) // Are we a real channel, or a dummy?
	{
            if (SWITCH_DEBUG) 
            {
                (*debugLog) << "Attempting to update credits" << endl;
	    }

            flowcontrolCredits.fetch_and_add(credits);            
            unique_lock<std::mutex> flowcontrolLock( flowcontrolMutex );

            if(TIME_SWITCH) 
	    { 
                clock_gettime(CLOCK_REALTIME, &finish);

                timespec temp;
                if ((finish.tv_nsec-start.tv_nsec)<0) 
                {
                    temp.tv_sec = finish.tv_sec-start.tv_sec-1;
                    temp.tv_nsec = 1000000000+finish.tv_nsec-start.tv_nsec;
                } 
                else 
                {
                    temp.tv_sec = finish.tv_sec-start.tv_sec;
                    temp.tv_nsec = finish.tv_nsec-start.tv_nsec;
                }

                (*debugLog) << "Seconds since credit update " << temp.tv_sec << endl;
                (*debugLog) << "Nanoseconds since credit update " << temp.tv_nsec << endl;
                start = finish;

	    }

	    flowcontrolVariable.notify_all();
            
            if (SWITCH_DEBUG)  
            {
              (*debugLog) << "credits updated" << endl;
	    }
	}
    };

    void acquireCredits(UINT32 credits)
    {
        // it is possible that someone could sneak in an steal our credit even if we are woken.      
        UINT32 retries;        

        // We attempt to wait for credit before acquiring the lock and going to sleep. 
        for(retries = 0; retries < 2500; retries++) 
        {
 	    UINT32 originalCredits = flowcontrolCredits.fetch_and_add(-1 * credits);

            if(originalCredits < credits)
	    {
	        // Oops grabbed too much credit
  	        flowcontrolCredits.fetch_and_add(credits);        

                if (SWITCH_DEBUG) 
	        {
                    (*debugLog) << "Channel "<< this << " spins for flowcontrol credits" << endl;
	        }       
	    } 
            else
	    {
                // We got our credits.  We can now return. 
	        return;
	    } 
	}

        // We failed to get credit enough times that we're just going to block... 
        unique_lock<std::mutex> flowcontrolLock(flowcontrolMutex);
	while(flowcontrolCredits < credits)
	{
            if (SWITCH_DEBUG)
	    {
                (*debugLog) << "Channel "<< this << " Blocks for flowcontrol credits" << endl;
	    }
               
	    flowcontrolVariable.wait(flowcontrolLock);  //Need to wait for a credit message.      

            if (SWITCH_DEBUG)
	    {
                (*debugLog) << "Channel "<< this << " Wakes" << endl;
	    }
	}

	flowcontrolCredits.fetch_and_add(-1 * credits);

	if (SWITCH_DEBUG)
	{
            (*debugLog) << "Credits remaining: " << dec << flowcontrolCredits << endl;
	}

    };

};






#endif
