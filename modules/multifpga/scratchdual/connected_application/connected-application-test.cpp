#include <stdio.h>

#include "asim/provides/stats_service.h"
#include "asim/provides/connected_application.h"



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
  // Eventually we'll call the frontend initialization here.                                                                        
  STATS_SERVER_CLASS::GetInstance()->SetupStats();
  STARTER_DEVICE_SERVER_CLASS::GetInstance()->WaitForHardware();
  STATS_SERVER_CLASS::GetInstance()->DumpStats();
  STATS_SERVER_CLASS::GetInstance()->EmitFile();
  STARTER_DEVICE_SERVER_CLASS::GetInstance()->End(0);
  
  return 0;
}
