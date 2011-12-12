#include <stdio.h>

#include "asim/provides/stats_device.h"
#include "asim/provides/connected_application.h"
#include "asim/provides/clocks_device.h"
#include "asim/rrr/client_stub_TESTDRRR.h"


using namespace std;

// constructor                                                                                                                      
CONNECTED_APPLICATION_CLASS::CONNECTED_APPLICATION_CLASS(VIRTUAL_PLATFORM vp)
  
{
    clientStub = new TESTDRRR_CLIENT_STUB_CLASS(NULL);
}

// destructor                                                                                                                       
CONNECTED_APPLICATION_CLASS::~CONNECTED_APPLICATION_CLASS()
{
}

// init                                                                                                                             
void
CONNECTED_APPLICATION_CLASS::Init()
{
}

// main                                                                                                                             
int
CONNECTED_APPLICATION_CLASS::Main()
{
    // Eventually we'll call the frontend initialization here.                                                                        
    STATS_DEVICE_SERVER_CLASS::GetInstance()->SetupStats();

    UINT32 width = 0, count = 1;
    for(width = 16; width < 512; width = width * 2) {
        for(count = 1; count < 10000000; count = count * 10) {
	  OUT_TYPE_RunTest result = clientStub->RunTest(count, width);
            printf("Transfer %d in %d Ticks %d -- Tokens/s:%f\tMB/s:%f\tErrors:%d\n", 
                   count, 
                   result.cycles, 
                   count/((float)result.cycles/(MODEL_CLOCK_FREQ*1000000)), 
                   (((float)count) * width/(8000000))/((float)result.cycles/(MODEL_CLOCK_FREQ*1000000)), 
                   result.errors);         
	}
    }

    STATS_DEVICE_SERVER_CLASS::GetInstance()->DumpStats();
    STATS_DEVICE_SERVER_CLASS::GetInstance()->EmitFile();
    STARTER_DEVICE_SERVER_CLASS::GetInstance()->End(0);
  
    return 0;
}
