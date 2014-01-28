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


//
RRR_SERVER_STUB_CLASS::RRR_SERVER_STUB_CLASS(const char *serviceName, const UINT64 serviceID): 
    ServiceName(serviceName), ServiceID(serviceID)
{

    std::string inputName("rrr_client_" + ServiceName + "_req");
    std::string outputName("rrr_client_" + ServiceName + "_resp");

    inputChannel = new LI_CHANNEL_RECV_CLASS<UMF_MESSAGE>(inputName);
    outputChannel = new LI_CHANNEL_SEND_CLASS<UMF_MESSAGE>(outputName);

}


// =============================
// Server Monitor static methods    
// =============================

void * RRR_SERVER_THREAD(void *argv)
{
  
    void **args = (void **) argv;
    const RRR_SERVER_STUB server = (RRR_SERVER_STUB) args[0];

    // Loop forever, relying on blocking I/O
    while(1) 
    {
        UMF_MESSAGE request = new UMF_MESSAGE_CLASS();  // create a new umf message
        translateUMFMessage(server->inputChannel, request);
        // call service and obtain result
        UMF_MESSAGE result = server->Request(request);
        // not all requests produce a response. 
        if(result) 
	{
            server->outputChannel->push(result);
        }
    }

    return NULL;
}


// register a service 
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
        PLATFORMS_MODULE_CLASS(p)
{

}

// destructor
RRR_SERVER_MONITOR_CLASS::~RRR_SERVER_MONITOR_CLASS()
{
}

// init: all services MUST have registered when this
// method is called
void
RRR_SERVER_MONITOR_CLASS::Init()
{
    // initialize services
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
                               RRR_SERVER_THREAD,
                               threadArgs))
	    {
                perror("pthread_create, RRR_SERVER_THREAD:");
                exit(1);
	    }

	}
    }

    
    PLATFORMS_MODULE_CLASS::Init();
}

// uninit: override
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
