#include <stdio.h>

#include "asim/provides/stats_service.h"
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
    printf("Calling Setup Stats\n");                                                   

    printf("Starting Test\n");                                                   
    OUT_TYPE_RunTest result = clientStub->RunTest(65000);

    printf("Test Complete cycles: %d, errors:%d\n", result.cycles, result.errors);

    STATS_SERVER_CLASS::GetInstance()->DumpStats();
    STATS_SERVER_CLASS::GetInstance()->EmitFile();
    STARTER_DEVICE_SERVER_CLASS::GetInstance()->End(0);
    
    return 0;
}
