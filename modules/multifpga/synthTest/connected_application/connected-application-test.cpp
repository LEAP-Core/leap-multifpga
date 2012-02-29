#include <stdio.h>

#include "asim/provides/stats_service.h"
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
  printf("Preparing to set up stats\n");
  fflush(stdout);  

  STATS_SERVER_CLASS::GetInstance()->SetupStats();

  for(UINT32 i = 0; i < 500; i++) {
    printf("Sending %d\n", i);
    UINT32 result = clientStub->TakeOneInput(i);
    printf("%d + 7 = %d \n", i, result);
  }

  STATS_SERVER_CLASS::GetInstance()->DumpStats();
  STATS_SERVER_CLASS::GetInstance()->EmitFile();
  STARTER_DEVICE_SERVER_CLASS::GetInstance()->End(0);
  
  return 0;
}
