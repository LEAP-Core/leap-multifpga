#ifndef __BASIC_RRR_CLIENT__
#define __BASIC_RRR_CLIENT__

#include <queue>
#include <pthread.h>

#include "awb/provides/channelio.h"

using namespace std;

// ============== RRR client stub base class =================

// RRR_CLIENT_STUB_CLASS -
//  Implements a generic RRR client.  This class is called by a child class, which provides
//  the RRR service-specific methods and functionality.  This class forwards those requests
//  to an LI channel, which is connected to the hardware side.  Responses come back via another, 
//  paired, LI channel.  We introduce a lock on requests with reponses, although this may not be
//  absolutely necessary due to the ordering of LI channels.  
typedef class RRR_CLIENT_STUB_CLASS* RRR_CLIENT_STUB;
class RRR_CLIENT_STUB_CLASS
{
 
  protected:

    UMF_MESSAGE MakeRequest(UMF_MESSAGE);
    void MakeRequestNoResponse(UMF_MESSAGE);

    std::mutex makeRequestMutex;
    ofstream debugLog;
    UINT64 totalPackets;
    UINT64 totalChunks;

  public:
    RRR_CLIENT_STUB_CLASS(const char *serviceName, const UINT64 serviceID);

    LI_CHANNEL_RECV_CLASS<UMF_MESSAGE> *inputChannel; 
    LI_CHANNEL_SEND_CLASS<UMF_MESSAGE> *outputChannel;
    const std::string ServiceName;
    const UINT64 ServiceID;
};

// RRR_CLIENT_CLASS -
//  Takes care of plumbing an RRR client stub to the global shared resources.
typedef class RRR_CLIENT_CLASS* RRR_CLIENT;
class RRR_CLIENT_CLASS: public PLATFORMS_MODULE_CLASS
{
  private:

    // link to channelio
    CHANNELIO   channelio;

  public:

    RRR_CLIENT_CLASS(PLATFORMS_MODULE, CHANNELIO);
    ~RRR_CLIENT_CLASS();
    
    void RegisterClient(int serviceid, RRR_CLIENT_STUB client_stub);

    void Poll();
};

// globally-visible link
extern RRR_CLIENT RRRClient;

#endif
