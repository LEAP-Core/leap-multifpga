#ifndef __BASIC_RRR_SERVER__
#define __BASIC_RRR_SERVER__

#include <stdio.h>

#include "platforms-module.h"
#include "li-rrr-common.h"
#include "awb/provides/channelio.h"

#define MAX_SERVICES            64

// ============== RRR server base class =================

typedef class RRR_SERVER_CLASS* RRR_SERVER;
class RRR_SERVER_CLASS
{
  public:
    virtual void        Init(PLATFORMS_MODULE) = 0;

    // Polling is a performance bottleneck and most servers don't need to be
    // polled.  Servers that don't need a Poll() can simply not implement
    // the method.  Servers that need to be polled must return true from
    // their Poll() method on every invocation.
    virtual bool        Poll(void) { return false; };
};

// ============== RRR server stub base class =================

typedef class RRR_SERVER_STUB_CLASS* RRR_SERVER_STUB;
class RRR_SERVER_STUB_CLASS
{
  public:
    RRR_SERVER_STUB_CLASS(const char *serviceName, const UINT64 serviceID);
    const std::string ServiceName;
    const UINT64 ServiceID;

    LI_CHANNEL_RECV_CLASS<UMF_MESSAGE> *inputChannel; 
    LI_CHANNEL_SEND_CLASS<UMF_MESSAGE> *outputChannel; 

    virtual UMF_MESSAGE Request(UMF_MESSAGE)   = 0;
    virtual void        Init(PLATFORMS_MODULE) = 0;
    virtual bool        Poll(void)             = 0;
};

// ================== Basic RRR Server Monitor ==================

typedef class RRR_SERVER_MONITOR_CLASS* RRR_SERVER_MONITOR;
class RRR_SERVER_MONITOR_CLASS: public PLATFORMS_MODULE_CLASS
{
  private:
    
    // static service table
    static RRR_SERVER_STUB ServerMap[MAX_SERVICES];
    static pthread_t       ServerThreads[MAX_SERVICES];
    
    // maintain a valid-mask for services that have properly
    // registered themselves. We do this because it is possible
    // to explicitly intialize a simple integer static variable
    // to 0, but not an entire array.
    static UINT64 RegistrationMask;
    
    // internal methods
    static inline bool isServerRegistered(int serviceid);
    static inline void setServerRegistered(int serviceid);
    static inline void unsetServerRegistered(int serviceid);
    
  public:

    // static methods used to populate service table
    static void RegisterServer(int serviceid, RRR_SERVER_STUB server_stub);
    
    // regular methods
    RRR_SERVER_MONITOR_CLASS(PLATFORMS_MODULE, CHANNELIO);
    ~RRR_SERVER_MONITOR_CLASS();
    void    Init();
    void    Uninit();
    void    Poll();
};

#endif
