#ifndef __FLOWCONTROL_INGRESS__
#define __FLOWCONTORL_INGRESS__

#include <queue>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <pthread.h>

#include "platforms-module.h"
#include "awb/provides/umf.h"
#include "awb/provides/physical_channel.h"
#include "awb/provides/multifpga_switch.h"
#include "awb/provides/li_base_types.h"
#include "tbb/concurrent_queue.h"
#include "tbb/compat/condition_variable"
#include "tbb/atomic.h"



// Handles incoming flowcontrol messages. 
class FLOWCONTROL_OUT_CLASS: public LI_CHANNEL_OUT_CLASS
{
  private:
    vector<LI_CHANNEL_IN> *inChannels;

  public:
    FLOWCONTROL_OUT_CLASS(vector<LI_CHANNEL_IN> *inChannelInitializer,  class tbb::concurrent_bounded_queue<UMF_MESSAGE> *outputQInitializer);
    void Init() {};
};

// Add a flow control interface to outbound channels
typedef class FLOWCONTROL_LI_CHANNEL_IN_CLASS* FLOWCONTROL_LI_CHANNEL_IN;
class FLOWCONTROL_LI_CHANNEL_IN_CLASS: public LI_CHANNEL_IN_CLASS
{
  protected:  
    class tbb::atomic<UINT32> flowcontrolCredits;    
    class tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQ; // Reference to global flow control queue messages
    UINT64 flowcontrolChannelID;
    UMF_FACTORY factory; // We use this factory to produce outgoing flowcontrol messages.

  public:

    FLOWCONTROL_LI_CHANNEL_IN_CLASS(tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQInitializer,
				    UMF_FACTORY factoryInitializer,
                                    UINT64 flowcontrolChannelIDInitializer):
        LI_CHANNEL_IN_CLASS(),
	flowcontrolCredits()
    { 
        factory = factoryInitializer;
        flowcontrolQ = flowcontrolQInitializer;
        flowcontrolChannelID = flowcontrolChannelIDInitializer;
        flowcontrolCredits = 0;   
    };

    ~FLOWCONTROL_LI_CHANNEL_IN_CLASS() {};

    void freeCredits(UINT32 serviceID)
    {
	if(flowcontrolCredits > ((3 * MULTIFPGA_FIFO_SIZES) / 4))
	{

            if(SWITCH_DEBUG)
            {
	        cout << "Channel " << serviceID  << " sending back credits " <<  flowcontrolCredits << endl;
   	    }

	    UMF_MESSAGE outMesg = factory->createUMFMessage();
	    outMesg->SetLength(sizeof(UMF_CHUNK));
	    outMesg->SetServiceID(flowcontrolChannelID);

            // Atomic read returns the old value, making this operation thread safe under idempotence.
            UINT32 creditsToReturn = flowcontrolCredits.fetch_and_store(0);                         
            UINT32 phyPvt =  (serviceID * 2 * MULTIFPGA_FIFO_SIZES) | creditsToReturn;  
            outMesg->AppendChunk((UINT128) phyPvt);              
	    flowcontrolQ->push(outMesg);
	}
    }

    void acquireCredits(UINT32 creditsAcquired) {
        flowcontrolCredits.fetch_and_add(creditsAcquired);
    }

};


#endif
