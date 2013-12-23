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
#include "awb/provides/multifpga_switch.h"
#include "pointer-ingress-regional.h"
#include "tbb/concurrent_queue.h"
#include "tbb/compat/condition_variable"
#include "tbb/atomic.h"


FLOWCONTROL_OUT_CLASS::FLOWCONTROL_OUT_CLASS(vector<LI_CHANNEL_IN> *inChannelsInitializer, class tbb::concurrent_bounded_queue<UMF_MESSAGE> *outputQInitializer):
  FLOWCONTROL_LI_CHANNEL_OUT_CLASS(outputQInitializer),
  totalCredits(),
  totalReceived()
{
    inChannels = inChannelsInitializer;   
    totalCredits = 0;
    totalReceived = 0;
    
    // Here we pick the minimum of the two expressions to ensure timely returns of data
    if((MULTIFPGA_FIFO_SIZES/2) < 
       (MULTIFPGA_FIFO_SIZES - inChannels->size() * MINIMUM_CHANNEL_BUFFER)) 
    {
        regionalReturnThreshold = MULTIFPGA_FIFO_SIZES/2;
    }
    else
    { 
        regionalReturnThreshold = MULTIFPGA_FIFO_SIZES - inChannels->size() * MINIMUM_CHANNEL_BUFFER;
    }

}


// Although this probably isn't the best interface, we call free regional
// credits when we are sending a flow control message to the other side.  
// In this case, we need to mark our own credits as being used. 
UINT32 FLOWCONTROL_OUT_CLASS::FreeRegionalCredits(UINT32 credits) 
{
    acquireCreditsFC(2);
    return totalCredits.fetch_and_add(-1*credits);
}

void FLOWCONTROL_OUT_CLASS::Init()
{

    for(vector<LI_CHANNEL_IN>::iterator channelIter = inChannels->begin(); 
        channelIter != inChannels->end();
        channelIter++)
    {                           
        ((FLOWCONTROL_LI_CHANNEL_IN_CLASS*)(*channelIter))->registerRegionalFlowcontrol(this);
    }

}

// Regional Manager has a credit queue to send back flowcontrol credits??
void FLOWCONTROL_LI_CHANNEL_IN_CLASS::freeCredits(UINT32 serviceID)
{
    if(SWITCH_DEBUG)
    {
      cout << "Channel " << serviceID << "Freeing credits: local: " << flowcontrolCredits << " regional: " << 
              regionalFlowcontrol->GetRegionalCredits() << " returnThreshold: " << regionalReturnThreshold << endl;
    }

    if(((flowcontrolCredits > 0) && (regionalFlowcontrol->GetRegionalCredits() > regionalReturnThreshold)) ||
       (flowcontrolCredits > regionalReturnThreshold / 2))
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
         
        if(SWITCH_DEBUG)
        {
   	    cout << "Setting phy pvt to " << hex << phyPvt << dec <<endl;
	}
        outMesg->AppendChunk((UINT128) phyPvt);              
        regionalFlowcontrol->FreeRegionalCredits(creditsToReturn);
        flowcontrolQ->push(outMesg);
    }
}

void FLOWCONTROL_LI_CHANNEL_IN_CLASS::acquireCredits(UINT32 creditsAcquired) 
{
    flowcontrolCredits.fetch_and_add(creditsAcquired);
    regionalFlowcontrol->AcquireRegionalCredits(creditsAcquired);
    regionalFlowcontrol->totalReceived.fetch_and_add(creditsAcquired);

    if(SWITCH_DEBUG)
    {
        cout << "Total received: " << dec << regionalFlowcontrol->totalReceived << endl;
    }

    assert(regionalFlowcontrol->totalCredits <= MULTIFPGA_FIFO_SIZES);
}

void FLOWCONTROL_LI_CHANNEL_IN_CLASS::registerRegionalFlowcontrol(class FLOWCONTROL_OUT_CLASS* regionalFlowcontrolInitializer)
{
    regionalFlowcontrol = regionalFlowcontrolInitializer;   
    regionalReturnThreshold = regionalFlowcontrol->GetRegionalReturnThreshold(); 
}

