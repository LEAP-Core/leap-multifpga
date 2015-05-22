#ifndef __BASIC_RRR_SERVER__
#define __BASIC_RRR_SERVER__

#include <stdio.h>

#include "platforms-module.h"
#include "li-rrr-common.h"
#include "awb/provides/channelio.h"
#include "boost/asio.hpp"
#include "boost/thread.hpp"
#include "boost/bind.hpp"
#include <mutex>

#define MAX_SERVICES            64
#define WORKER_THREADS          1

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

///
// RRR_SERVER_STUB_CLASS -
//  Layer between server-specific method interface and the underlying
//  communications hardware.  Maintains two LI channels for communication
//  with hardware-side client. 
typedef class RRR_SERVER_STUB_CLASS* RRR_SERVER_STUB;
class RRR_SERVER_STUB_CLASS
{
  protected:
    std::mutex serverMutex;
    UMF_MESSAGE currentRequest;
    ofstream debugLog;

    void HandleMessage(UMF_MESSAGE);

  public:
    RRR_SERVER_STUB_CLASS(const char *serviceName, const UINT64 serviceID);
    const std::string ServiceName;
    const UINT64 ServiceID;

    LI_CHANNEL_EXECUTE_RECV_CLASS<UMF_MESSAGE> *inputChannel; 
    LI_CHANNEL_SEND_CLASS<UMF_MESSAGE>         *outputChannel; 

    virtual UMF_MESSAGE Request(UMF_MESSAGE)   = 0;
    virtual void        Init(PLATFORMS_MODULE) = 0;
    virtual bool        Poll(void)             = 0;
};

// ================== Basic RRR Server Monitor ==================

///
// RRR_SERVER_MONITOR_CLASS -
//  A registery for RRR software servers. This is needed to solve a dependency problem in channel construction. 
//  The software-side server threads touch both halves of the LI channel, and so both must be constructed 
//  before we spawn the thread.  This class allows servers to register, and then spawns a thread for each of the
//  servers.  TODO: use a thread pool rather than spawning a huge number of threads. 
typedef class RRR_SERVER_MONITOR_CLASS* RRR_SERVER_MONITOR;
class RRR_SERVER_MONITOR_CLASS: public PLATFORMS_MODULE_CLASS
{
  // The server stubs need to get at the global thread pool. 
  friend class RRR_SERVER_STUB_CLASS; 
   
  private:
    
    // static service table
    static RRR_SERVER_STUB ServerMap[MAX_SERVICES];
    static pthread_t       ServerThreads[MAX_SERVICES];
    
    static std::mutex globalServerMutex;

    static boost::asio::io_service threadPool;
    static boost::thread_group threads;

    // maintain a valid-mask for services that have properly
    // registered themselves. We do this because it is possible
    // to explicitly intialize a simple integer static variable
    // to 0, but not an entire array.
    static UINT64 RegistrationMask;
    
    // internal methods
    static inline bool isServerRegistered(int serviceid);
    static inline void setServerRegistered(int serviceid);
    static inline void unsetServerRegistered(int serviceid);

  protected:  
    static boost::asio::io_service *GetThreadPool() {return &threadPool;};  
    boost::asio::io_service::work work; // Creates work for the threadPool, in case no work is otherwise available.
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

/*
Create an io_service:

and some work to stop its run() function from exiting if it has nothing else to do:

Start some worker threads:


Post the tasks to the io_service so they can be performed by the worker threads:

io_service.post(boost::bind(a_long_running_task, 123));
Finally, before the program exits shut down the io_service and wait for all threads to exit:
  io_service.stop();
threads.join_all();
Edit | Attach | Print 
*/
