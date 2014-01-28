#ifndef __BASIC_RRR_CLIENT__
#define __BASIC_RRR_CLIENT__

#include <queue>
#include <pthread.h>

#include "awb/provides/channelio.h"

using namespace std;

// ============== RRR client stub base class =================

typedef class RRR_CLIENT_STUB_CLASS* RRR_CLIENT_STUB;
class RRR_CLIENT_STUB_CLASS
{
  protected:

    UMF_MESSAGE MakeRequest(UMF_MESSAGE);
    void MakeRequestNoResponse(UMF_MESSAGE);

  public:
    RRR_CLIENT_STUB_CLASS(const char *serviceName, const UINT64 serviceID);

    LI_CHANNEL_RECV_CLASS<UMF_MESSAGE> *inputChannel; 
    LI_CHANNEL_SEND_CLASS<UMF_MESSAGE> *outputChannel;
    const std::string ServiceName;
    const UINT64 ServiceID;
};


typedef class RRR_CLIENT_CLASS* RRR_CLIENT;
class RRR_CLIENT_CLASS: public PLATFORMS_MODULE_CLASS
{
  private:

    // link to channelio
    CHANNELIO   channelio;
    //    static LI_CHANNEL_RECV_CLASS<UMF_MESSAGE> *clientResps[MAX_SERVICES];
    //static LI_CHANNEL_SEND_CLASS<UMF_MESSAGE> *clientReqs[MAX_SERVICES];
    //static RRR_CLIENT_STUB earlyConstructedClients[MAX_SERVICES];
    //static bool constructed;

  public:

    RRR_CLIENT_CLASS(PLATFORMS_MODULE, CHANNELIO);
    ~RRR_CLIENT_CLASS();
    
    void RegisterClient(int serviceid, RRR_CLIENT_STUB client_stub);

    void Poll();
};

// globally-visible link
extern RRR_CLIENT RRRClient;

#endif
