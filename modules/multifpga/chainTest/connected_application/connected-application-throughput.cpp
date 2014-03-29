#include <stdio.h>

#include "asim/provides/stats_service.h"
#include "asim/provides/connected_application.h"
#include "asim/provides/clocks_device.h"


using namespace std;

// constructor                                                                                                                      
CONNECTED_APPLICATION_CLASS::CONNECTED_APPLICATION_CLASS(VIRTUAL_PLATFORM vp)
  
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
}

// main                                                                                                                             
int
CONNECTED_APPLICATION_CLASS::Main()
{  
    sleep(10);

    STATS_SERVER_CLASS::GetInstance()->DumpStats();
    STATS_SERVER_CLASS::GetInstance()->EmitFile();
    STARTER_DEVICE_SERVER_CLASS::GetInstance()->End(0);
  
    return 0;
}
