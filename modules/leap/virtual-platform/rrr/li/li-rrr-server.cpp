//
// Copyright (c) 2014, Intel Corporation
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
// Redistributions of source code must retain the above copyright notice, this
// list of conditions and the following disclaimer.
//
// Redistributions in binary form must reproduce the above copyright notice,
// this list of conditions and the following disclaimer in the documentation
// and/or other materials provided with the distribution.
//
// Neither the name of the Intel Corporation nor the names of its contributors
// may be used to endorse or promote products derived from this software
// without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.
//

#include <stdio.h>
#include <unistd.h>
#include <strings.h>
#include <assert.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <string.h>
#include <iostream>
#include <mutex>

#include "awb/provides/rrr.h"
#include "awb/provides/li_base_types.h"

using namespace std;

#define CHANNEL_ID    0

// instantiate global service table; this table will be
// populated by the individual services (also statically
// instantiated) before main().
RRR_SERVER_STUB RRR_SERVER_MONITOR_CLASS::ServerMap[MAX_SERVICES];
pthread_t       RRR_SERVER_MONITOR_CLASS::ServerThreads[MAX_SERVICES];
UINT64          RRR_SERVER_MONITOR_CLASS::RegistrationMask = 0;
std::mutex      RRR_SERVER_MONITOR_CLASS::globalServerMutex;
boost::asio::io_service RRR_SERVER_MONITOR_CLASS::threadPool;
boost::thread_group RRR_SERVER_MONITOR_CLASS::threads;

///
// RRR_SERVER_STUB_CLASS -
//   Constructs RRR_SERVER_STUB_CLASS, initializing half-channels to the FPGA side. 
RRR_SERVER_STUB_CLASS::RRR_SERVER_STUB_CLASS(const char *serviceName, const UINT64 serviceID): 
    ServiceName(serviceName), ServiceID(serviceID)
{

    std::string inputName("rrr_client_" + ServiceName + "_req");
    std::string outputName("rrr_client_" + ServiceName + "_resp");

    std::function<void (UMF_MESSAGE)> messageHandler = [this] (UMF_MESSAGE msg) { this->HandleMessage(msg); };

    inputChannel = new LI_CHANNEL_EXECUTE_RECV_CLASS<UMF_MESSAGE>(inputName, messageHandler, RRR_SERVER_MONITOR_CLASS::GetThreadPool());
    outputChannel = new LI_CHANNEL_SEND_CLASS<UMF_MESSAGE>(outputName);
    currentRequest = NULL;
    debugLog.open(ServiceName + ".log");
}

//
// HandleMessage - 
//  Processes an incoming message
void RRR_SERVER_STUB_CLASS::HandleMessage(UMF_MESSAGE incoming)
{
    // need a mutex in case we get back-to-back/temporally near messages.
    std::unique_lock<std::mutex> lk(serverMutex); 

    // One of several things may happen here.
    // 1) We're starting a new message.
    if (currentRequest == NULL) 
    {
        currentRequest = new UMF_MESSAGE_CLASS();  // create a new umf message
        currentRequest->DecodeHeader(*((UMF_CHUNK*)incoming));
     
        // UMF_MESSAGE allocator expects the overloaded free list pointer to be NULL. 
        incoming->SetFreeListNext(NULL);
        delete incoming;
   
        currentRequest->StartAppend();
    }

    // 2) We're assembling the message body.
    else if (currentRequest->CanAppend())
    {
        currentRequest->AppendChunk(*((UMF_CHUNK*)incoming));

        incoming->SetFreeListNext(NULL);
        delete incoming;
    }

    // have we finished the message?
    if  (!currentRequest->CanAppend()) {
        // If we've completed a message, we can process it. 

        if (DEBUG_RRR) {
            currentRequest->Print(debugLog);
        }

        UMF_MESSAGE result = Request(currentRequest);
        currentRequest = NULL;
        // not all requests produce a response. 
        if(result) 
        {
            if (DEBUG_RRR) {
                result->Print(debugLog);
            }

            outputChannel->push(result);
        }
    }        
}



// =============================
// Server Monitor static methods    
// =============================

// RegisterServer -
//  register a service with service registery.  This enables lower level channel multiplexors to make 
//  connections back to the service. 
void
RRR_SERVER_MONITOR_CLASS::RegisterServer(
    int             serviceID,
    RRR_SERVER_STUB server)
{
    if (isServerRegistered(serviceID))
    {
        fprintf(stderr,
            "software server: duplicate serviceID registration: %d\n");
        exit(1);
    }


    // set link in map table
    ServerMap[serviceID] = server;
    setServerRegistered(serviceID);


}

////
// Methods for querying the server registery. 
////
bool
RRR_SERVER_MONITOR_CLASS::isServerRegistered(
    int serviceid)
{
    UINT64 mask = UINT64(0x01) << serviceid;
    return ((RegistrationMask & mask) > 0 ? true : false);
}

void
RRR_SERVER_MONITOR_CLASS::setServerRegistered(
    int serviceid)
{
    UINT64 mask = UINT64(0x01) << serviceid;
    RegistrationMask |= mask;
}

void
RRR_SERVER_MONITOR_CLASS::unsetServerRegistered(
    int serviceid)
{
    UINT64 mask = UINT64(0x01) << serviceid;
    RegistrationMask &= (~mask);
}

// ===========================
//       regular methods
// ===========================

// constructor
RRR_SERVER_MONITOR_CLASS::RRR_SERVER_MONITOR_CLASS(
        PLATFORMS_MODULE p, 
        CHANNELIO cio) :
        PLATFORMS_MODULE_CLASS(p),
        work(threadPool)
{

}

// destructor
RRR_SERVER_MONITOR_CLASS::~RRR_SERVER_MONITOR_CLASS()
{
}

///
// Init - 
// Spawns off service threads for the software side.
// All services MUST have registered when this
// method is called
void
RRR_SERVER_MONITOR_CLASS::Init()
{
    // initialize services

    for (std::size_t i = 0; i < WORKER_THREADS; ++i) 
    {
        threads.create_thread(boost::bind(&boost::asio::io_service::run, &threadPool));
    }

    /*
    for (int i = 0; i < MAX_SERVICES; i++)
    {
        if (isServerRegistered(i))
        {
            void **threadArgs = (void**) malloc(sizeof(void*));
            threadArgs[0] = (void *)ServerMap[i]; 
            
            // set myself as the PLATFORMS_MODULE parent
            // for all services so that I can chain
            // uninit()s to them
            ServerMap[i]->Init(this);
        

    	    // spawn off Monitor/Service                                                                         
	    if (pthread_create(&ServerThreads[i],
                               NULL,
                               RRR_SERVER_MONITOR_CLASS::RRR_SERVER_THREAD,
                               threadArgs))
	    {
                perror("pthread_create, RRR_SERVER_THREAD:");
                exit(1);
	    }

	}
    }
    */

    
    PLATFORMS_MODULE_CLASS::Init();
}

/// 
// Uninit -
//  Clean up the server registery.
void
RRR_SERVER_MONITOR_CLASS::Uninit()
{
    // reset service map
    for (int i = 0; i < MAX_SERVICES; i++)
    {
        if (isServerRegistered(i))
        {
            // no need to explicitly call Uninit() on
            // services, this will happen automatically
            // when we chain the call
            ServerMap[i] = NULL;
        }
    }
    RegistrationMask = 0;

    // chain
    PLATFORMS_MODULE_CLASS::Uninit();
}

// poll
void
RRR_SERVER_MONITOR_CLASS::Poll()
{

}
