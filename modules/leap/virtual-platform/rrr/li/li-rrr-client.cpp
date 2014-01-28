//
// Copyright (C) 2008 Intel Corporation
//
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// as published by the Free Software Foundation; either version 2
// of the License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
//

#include <iostream>

#include "awb/provides/rrr.h"
#include "awb/provides/li_base_types.h"
#include "awb/provides/model.h" // FIXME should be project

#define CHANNEL_ID  1

using namespace std;

// global link
RRR_CLIENT RRRClient;

// instantiate global service table; this table will be
// populated by the individual services (also statically
// instantiated) before main().
//LI_CHANNEL_RECV_CLASS<UMF_MESSAGE>*             RRR_CLIENT_CLASS::clientResps[MAX_SERVICES];
//LI_CHANNEL_SEND_CLASS<UMF_MESSAGE>*             RRR_CLIENT_CLASS::clientReqs[MAX_SERVICES];
//RRR_CLIENT_STUB                                 RRR_CLIENT_CLASS::earlyConstructedClients[MAX_SERVICES];
//bool                                            RRR_CLIENT_CLASS::constructed = 0;


RRR_CLIENT_STUB_CLASS::RRR_CLIENT_STUB_CLASS(const char *serviceName, const UINT64 serviceID): 
    ServiceName(serviceName), ServiceID(serviceID) 
{
    // We're the client of the hw side server. 
    std::string inputName("rrr_server_" + ServiceName + "_resp");
    std::string outputName("rrr_server_" + ServiceName + "_req");

    inputChannel  = new LI_CHANNEL_RECV_CLASS<UMF_MESSAGE>(inputName);
    outputChannel = new LI_CHANNEL_SEND_CLASS<UMF_MESSAGE>(outputName);
}


// make request with response
UMF_MESSAGE
RRR_CLIENT_STUB_CLASS::MakeRequest(UMF_MESSAGE request)
{

    UMF_MESSAGE resp = new UMF_MESSAGE_CLASS();  // create a new umf message
    outputChannel->push(request);
    translateUMFMessage(inputChannel, resp);
    return resp;

}

// make request with no response
void
RRR_CLIENT_STUB_CLASS::MakeRequestNoResponse(UMF_MESSAGE request)
{
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
