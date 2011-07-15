#include <stdio.h>

#include "asim/provides/stats_device.h"
#include "asim/provides/connected_application.h"
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
  UINT32 total = 0;
  for(UINT32 i = 0; i < 50; i++) {
    UINT32 result = clientStub->TakeOneInput(i);
    printf("Single Transfer Ticks %d \n", i, result);
    total += result;
  }

  printf("Average cycle\n", total/(float)i);

  STATS_DEVICE_SERVER_CLASS::GetInstance()->DumpStats();
  STATS_DEVICE_SERVER_CLASS::GetInstance()->EmitFile();
  STARTER_DEVICE_SERVER_CLASS::GetInstance()->End(0);
  
  return 0;
}
