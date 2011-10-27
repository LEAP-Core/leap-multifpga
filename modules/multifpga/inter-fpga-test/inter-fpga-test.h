#ifndef __CONNECTED_APPLICATION__
#define __CONNECTED_APPLICATION__

#include <vector>

#include "asim/provides/virtual_platform.h"

#include "awb/rrr/client_stub_INTER_FPGA_TEST.h"

typedef class DRIVER_MODULE_CLASS* DRIVER_MODULE;
class DRIVER_MODULE_CLASS : public PLATFORMS_MODULE_CLASS
{
  public:
    DRIVER_MODULE_CLASS(PLATFORMS_MODULE p) : 
        PLATFORMS_MODULE_CLASS(p) {}

    // main
    virtual void Main() {}
};


typedef class CONNECTED_APPLICATION_CLASS* CONNECTED_APPLICATION;
class CONNECTED_APPLICATION_CLASS  : public PLATFORMS_MODULE_CLASS
{
  private:

    INTER_FPGA_TEST_CLIENT_STUB clientStub;

  public:

    CONNECTED_APPLICATION_CLASS(VIRTUAL_PLATFORM vp);
    ~CONNECTED_APPLICATION_CLASS();

    // init
    void Init();

    // main
    void Main();

};

#endif
