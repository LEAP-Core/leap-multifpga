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
#include "awb/provides/umf.h"
#include "awb/provides/li_base_types.h"

void translateUMFMessage(LI_CHANNEL_RECV_CLASS<UMF_MESSAGE> *channel, UMF_MESSAGE element)
{
    UMF_MESSAGE incoming;

    channel->pop(incoming);
    element->DecodeHeader(*((UMF_CHUNK*)incoming));
     
    // UMF_MESSAGE allocator expects the overloaded free list pointer to be NULL. 
    incoming->SetFreeListNext(NULL);
    delete incoming;

    // Reassemble other message components.                                                                                                                                               
    element->StartAppend();
    while(element->CanAppend())
    {
        channel->pop(incoming);
        element->AppendChunk(*((UMF_CHUNK*)incoming));

        incoming->SetFreeListNext(NULL);
        delete incoming;
    }
}


