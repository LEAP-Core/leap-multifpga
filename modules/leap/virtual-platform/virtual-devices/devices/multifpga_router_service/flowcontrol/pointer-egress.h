#ifndef __FLOWCONTROL_EGRESS__
#define __FLOWCONTROL_EGRESS__

#include <queue>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <pthread.h>

#include "platforms-module.h"
#include "awb/provides/umf.h"
#include "awb/provides/physical_channel.h"
#include "awb/provides/li_base_types.h"
#include "tbb/concurrent_queue.h"
#include "tbb/compat/condition_variable"
#include "tbb/atomic.h"

class FLOWCONTROL_IN_CLASS;

// Add a flow control interface to outbound channels
typedef class FLOWCONTROL_LI_CHANNEL_OUT_CLASS* FLOWCONTROL_LI_CHANNEL_OUT;
class FLOWCONTROL_LI_CHANNEL_OUT_CLASS: public LI_CHANNEL_OUT_CLASS
{
  friend class FLOWCONTROL_OUT_CLASS; // Needs to use special non-blocking credit scheme.

  protected:  
    class tbb::atomic<UINT32> flowcontrolCredits;    

    timespec start;
    class FLOWCONTROL_IN_CLASS* regionalFlowcontrol;
    void acquireCreditsFC(UINT32 messageLength); 

  public:

    FLOWCONTROL_LI_CHANNEL_OUT_CLASS(class tbb::concurrent_bounded_queue<UMF_MESSAGE> *outputQInitializer):
        LI_CHANNEL_OUT_CLASS(outputQInitializer),
	flowcontrolCredits()   
    { 
        clock_gettime(CLOCK_REALTIME, &start);
        flowcontrolCredits = 0;
    };

    ~FLOWCONTROL_LI_CHANNEL_OUT_CLASS() {};

    void freeCredits(UINT32 credits); 
    void acquireCredits(UINT32 messageLength);
    void registerRegionalFlowcontrol(class FLOWCONTROL_IN_CLASS* regionalFlowcontrolInitializer);

};








#endif
