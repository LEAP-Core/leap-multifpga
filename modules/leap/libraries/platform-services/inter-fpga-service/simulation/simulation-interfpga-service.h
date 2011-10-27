#ifndef XUPV5_INTER_FPGA_SERVICE
#define XUPV5_INTER_FPGA_SERVICE

#include "platforms-module.h"
#include "awb/provides/rrr.h"

typedef class INTER_FPGA_DEVICE_SERVER_CLASS* INTER_FPGA_DEVICE_SERVER;
typedef class INTER_FPGA_DEVICE_SERVER_CLASS* INTER_FPGA_SERVER;

class INTER_FPGA_DEVICE_SERVER_CLASS:public PLATFORMS_MODULE_CLASS
{
  private:
    // self-instantiation
    static INTER_FPGA_DEVICE_SERVER_CLASS instance;

  public:
    INTER_FPGA_DEVICE_SERVER_CLASS();
    ~INTER_FPGA_DEVICE_SERVER_CLASS();

    // static methods
    static INTER_FPGA_DEVICE_SERVER GetInstance() { return &instance; }

    // required RRR methods
    void Init(PLATFORMS_MODULE) {}
    void Uninit() {}
    void Cleanup() {}

    // RRR server methods
    void DumpPhyStats() {}
};

// all functionalities of the stats controller are completely implemented
// by the INTER_FPGA_DEVICE_SERVER class
typedef INTER_FPGA_DEVICE_SERVER_CLASS INTER_FPGA_DEVICE_CLASS;

#endif
