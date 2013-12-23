#ifndef __FLOWCONTROL_EGRESS_REGIONAL__
#define __FLOWCONTROL_EGRESS_REGIONAL__

#include <queue>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <pthread.h>

#include "platforms-module.h"
#include "pointer-ingress.h"
#include "awb/provides/umf.h"
#include "awb/provides/physical_channel.h"
#include "awb/provides/li_base_types.h"
#include "tbb/concurrent_queue.h"
#include "tbb/compat/condition_variable"
#include "tbb/atomic.h"


// For this flow control scheme, there must be a single regional lock. 
                                
class FLOWCONTROL_IN_CLASS: public FLOWCONTROL_LI_CHANNEL_IN_CLASS
{
  // there's really no better way to share the lock 
  // than to declare a friend

  friend class FLOWCONTROL_LI_CHANNEL_OUT_CLASS;

  private:
    vector<LI_CHANNEL_OUT> *outChannels;
    class tbb::atomic<UINT32> totalCredits;
    class tbb::atomic<UINT32> totalCreditsRX;
    class tbb::atomic<UINT32> totalSent;
    class std::mutex flowcontrolMutex; 
    condition_variable flowcontrolVariable; 
    UINT32 regionalReturnThreshold;    

  public:
    FLOWCONTROL_IN_CLASS(vector<LI_CHANNEL_OUT> *outChannelInitializer,
                         tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQInitializer,
      	                 UMF_FACTORY factoryInitializer,
                         UINT64 flowcontrolChannelIDInitializer);
    virtual void pushUMF(UMF_MESSAGE &message);
    void Init();
};


#endif
