#include <stdio.h>

#include "asim/provides/connected_application.h"
#include "asim/provides/stats_service.h"
#include "asim/provides/inter_fpga_service.h"

using namespace std;
 
// constructor
CONNECTED_APPLICATION_CLASS::CONNECTED_APPLICATION_CLASS(VIRTUAL_PLATFORM vp):
    clientStub(new INTER_FPGA_TEST_CLIENT_STUB_CLASS(this))
{

}

// destructor
CONNECTED_APPLICATION_CLASS::~CONNECTED_APPLICATION_CLASS()
{
}

// init
void
CONNECTED_APPLICATION_CLASS::Init()
{
    PLATFORMS_MODULE_CLASS::Init();
}

// main
void
CONNECTED_APPLICATION_CLASS::Main()
{

  while(1) {
    UINT32 error;
    // Dump out stats
    printf("Test stats: Correct: %llu Error: %llu Sent: %llu Returned: %llu\n", clientStub->GetCorrect(0), clientStub->GetError(0), 
                                                                                clientStub->GetSent(0), clientStub->GetReturned(0));

    while(error = clientStub->GetErrorPair(0)) {
      printf("ErrorPair: %x\n", error);
    }

    (INTER_FPGA_DEVICE_SERVER_CLASS::GetInstance())->DumpPhyStats();
    sleep(3);
  }


  printf("exiting main\n");
  // Eventually we'll call the frontend initialization here. 
  //airblueDriver->Main();
  //airblueFrontend->Main();
}
