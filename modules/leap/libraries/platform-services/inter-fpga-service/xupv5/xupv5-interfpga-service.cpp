#include "asim/provides/inter_fpga_service.h"


// ===== service instantiation =====
INTER_FPGA_DEVICE_SERVER_CLASS INTER_FPGA_DEVICE_SERVER_CLASS::instance;
 
// constructor
INTER_FPGA_DEVICE_SERVER_CLASS::INTER_FPGA_DEVICE_SERVER_CLASS() :
    firstPass(true),
    // instantiate stubs
    clientStub(new INTER_FPGA_CLIENT_STUB_CLASS(this))
{

}


// destructor
INTER_FPGA_DEVICE_SERVER_CLASS::~INTER_FPGA_DEVICE_SERVER_CLASS()
{
    Cleanup();
}


// init
void
INTER_FPGA_DEVICE_SERVER_CLASS::Init(
    PLATFORMS_MODULE     p)
{
    // set parent pointer
    parent = p;
}



// init
void
INTER_FPGA_DEVICE_SERVER_CLASS::DumpPhyStats()
{
  UINT64 status = clientStub->GetPHYStatus(0);

  UINT32 txfifo_count = (status>>16) & 0x1f;
  UINT32 txfifo_notEmpty = (status>>22) & 0x1;
  UINT32 txfifo_notFull = (status>>23) & 0x1;
  UINT32 rxfifo_count = (status>>8) & 0x1f;
  UINT32 rxfifo_notEmpty = (status>>14) & 0x1;
  UINT32 rxfifo_notFull = (status>>15) & 0x1;
  UINT32 rx_rdy = (status>>4) & 0x1;
  UINT32 tx_rdy = (status>>2) & 0x1;
  UINT32 channel_up = (status>>35) & 0x1;
  UINT32 txfifo_count_bsc = (status>>36) & 0xff;
  UINT32 rxfifo_count_bsc = (status>>44) & 0xff;

  printf("RX: %d TX: %d Sent: %d Dropped: %d PHYRX: %d, PHY_SOFT_ERR: %d\n", clientStub->GetRXCount(0), clientStub->GetTXCount(0), clientStub->GetSampleSent(0), clientStub->GetSampleDropped(0), clientStub->GetPHYRXCount(0), clientStub->GetPHYTXCount(0));
  printf("PHY STATUS:\n\t(RAW)\t\t%llx\n\t(Verilog)\ttxfifo_count: %d txfifo_notEmpty: %d txfifo_notFull: %d rxfifo_count: %d rxfifo_notEmpty: %d rxfifo_notFull: %d\n\t\t\trx_rdy: %d tx_rdy: %d channel_up: %d \n\t(BSC)\t\ttxfifo_count: %d rxfifo_count_bsc: %d\n", status, txfifo_count,txfifo_notEmpty, txfifo_notFull, rxfifo_count, rxfifo_notEmpty, rxfifo_notFull,rx_rdy,tx_rdy,channel_up,txfifo_count_bsc,rxfifo_count_bsc);
    firstPass = false;
}

// uninit: we have to write this explicitly
void
INTER_FPGA_DEVICE_SERVER_CLASS::Uninit()
{
    Cleanup();

    // chain
    PLATFORMS_MODULE_CLASS::Uninit();
}

// cleanup
void
INTER_FPGA_DEVICE_SERVER_CLASS::Cleanup()
{
    // kill stubs
    delete clientStub;
}

