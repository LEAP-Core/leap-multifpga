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

#include <iostream>

#include "awb/provides/rrr.h"
#include "awb/provides/li_base_types.h"
#include "awb/provides/model.h" // FIXME should be project

#define CHANNEL_ID  1

using namespace std;

// global link
RRR_CLIENT RRRClient;

///
// RRR_CLIENT_STUB_CLASS -
//   Implements the interface between a specific RRR serve and its underlying channels. 
//   Two channels are used, one that goes into the FPGA and one that comes out. 
RRR_CLIENT_STUB_CLASS::RRR_CLIENT_STUB_CLASS(const char *serviceName, const UINT64 serviceID): 
    ServiceName(serviceName), ServiceID(serviceID) 
{
    // We're the client of the hw side server. 
    std::string inputName("rrr_server_" + ServiceName + "_resp");
    std::string outputName("rrr_server_" + ServiceName + "_req");

    inputChannel  = new LI_CHANNEL_RECV_CLASS<UMF_MESSAGE>(inputName);
    outputChannel = new LI_CHANNEL_SEND_CLASS<UMF_MESSAGE>(outputName);

    if (DEBUG_RRR) 
    {
        debugLog.open(ServiceName + ".log");
    }
}


///
// MakeRequest -- 
// Sends a request and waits for response to come back. 
// We use a lock to ensure that requests are properly ordered.
UMF_MESSAGE
RRR_CLIENT_STUB_CLASS::MakeRequest(UMF_MESSAGE request)
{

    UMF_MESSAGE resp = new UMF_MESSAGE_CLASS();  // create a new umf message
    // Force posted-requests to be atomic. 
    std::unique_lock<std::mutex> lk(makeRequestMutex); 
    {
        if (DEBUG_RRR) {
            totalPackets++;
            debugLog <<  "Wrote Packet " << hex << totalPackets << endl;
            request->Print(debugLog);
        }

        outputChannel->push(request);
        translateUMFMessage(inputChannel, resp);       
        resp->Print(debugLog); 
    }

    return resp;

}

///
// MakeRequestNoResponse -- 
// Sends a request and returns immediately.
void
RRR_CLIENT_STUB_CLASS::MakeRequestNoResponse(UMF_MESSAGE request)
{    

    if (DEBUG_RRR) {    
        totalPackets++;
        debugLog <<  "Wrote Packet " << hex << totalPackets << endl;
        request->Print(debugLog);
    }

    outputChannel->push(request);   
    
}

// At some point, we need to memoize the client lookup. 

// constructor
RRR_CLIENT_CLASS::RRR_CLIENT_CLASS(
    PLATFORMS_MODULE p,
    CHANNELIO    cio) :
        PLATFORMS_MODULE_CLASS(p)
{

}

// destructor
RRR_CLIENT_CLASS::~RRR_CLIENT_CLASS()
{
}

// register a service
void
RRR_CLIENT_CLASS::RegisterClient(
    int             serviceID,
    RRR_CLIENT_STUB client)
{

}



// poll
void
RRR_CLIENT_CLASS::Poll()
{

}
