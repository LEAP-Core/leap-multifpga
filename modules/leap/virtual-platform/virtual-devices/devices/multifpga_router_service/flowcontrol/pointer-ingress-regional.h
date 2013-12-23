#ifndef __FLOWCONTROL_INGRESS_REGIONAL__
#define __FLOWCONTROL_INGRESS_REGIONAL__

#include <queue>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <pthread.h>

#include "pointer-egress.h"
#include "platforms-module.h"
#include "awb/provides/umf.h"
#include "awb/provides/physical_channel.h"
#include "awb/provides/li_base_types.h"
#include "tbb/concurrent_queue.h"
#include "tbb/compat/condition_variable"
#include "tbb/atomic.h"



// Handles incoming flowcontrol messages. 
// We need to inherit the plaforms module class to get the init call.
                                
class FLOWCONTROL_OUT_CLASS: public FLOWCONTROL_LI_CHANNEL_OUT_CLASS
{
    friend class FLOWCONTROL_LI_CHANNEL_IN_CLASS;

  private:
    vector<LI_CHANNEL_IN> *inChannels;
    // Although totalCredits is shared, we do not 
    class tbb::atomic<UINT32> totalCredits;
    class tbb::atomic<UINT32> totalReceived;
    UINT32 regionalReturnThreshold;    
    
  public:
    void Init();
    FLOWCONTROL_OUT_CLASS(vector<LI_CHANNEL_IN> *inChannelInitializer,  class tbb::concurrent_bounded_queue<UMF_MESSAGE> *outputQInitializer);
    UINT32 AcquireRegionalCredits(UINT32 credits) {return totalCredits.fetch_and_add(credits);}
    UINT32 FreeRegionalCredits(UINT32 credits);
    UINT32 GetRegionalCredits() {return totalCredits;}
    UINT32 GetRegionalReturnThreshold() {return regionalReturnThreshold;}
 
};

#endif
