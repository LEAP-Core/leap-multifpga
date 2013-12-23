#ifndef __FLOWCONTROL_INGRESS__
#define __FLOWCONTROL_INGRESS__

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

class FLOWCONTROL_OUT_CLASS;

// Add a flow control interface to outbound channels                                                                
typedef class FLOWCONTROL_LI_CHANNEL_IN_CLASS* FLOWCONTROL_LI_CHANNEL_IN;
class FLOWCONTROL_LI_CHANNEL_IN_CLASS: public LI_CHANNEL_IN_CLASS
{
  protected:

    class tbb::atomic<UINT32> flowcontrolCredits;
    class tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQ; // Reference to global flow control queue messages                                                                                                                 
    UINT64 flowcontrolChannelID;
    UMF_FACTORY factory; // We use this factory to produce outgoing flowcontrol messages.                           
    UINT32 regionalReturnThreshold;

    class FLOWCONTROL_OUT_CLASS* regionalFlowcontrol;

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

    void freeCredits(UINT32 serviceID);
    void acquireCredits(UINT32 creditsAcquired);
    void registerRegionalFlowcontrol(class FLOWCONTROL_OUT_CLASS* regionalFlowcontrolInitializer);

};


#endif
