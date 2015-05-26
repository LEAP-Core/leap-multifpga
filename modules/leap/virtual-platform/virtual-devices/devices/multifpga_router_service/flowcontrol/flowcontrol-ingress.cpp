
#include "awb/provides/multifpga_switch.h"

///
// FLOWCONTROL_OUT_CLASS -
//  A constructor for the flow control class.
FLOWCONTROL_OUT_CLASS::FLOWCONTROL_OUT_CLASS(vector<LI_CHANNEL_IN> *inChannelsInitializer, class tbb::concurrent_bounded_queue<UMF_MESSAGE> *outputQInitializer):
  LI_CHANNEL_OUT_CLASS(NULL) // Perhaps a better name?
{
    inChannels = inChannelsInitializer;   
    // Due to single-channel management, we don't need to send flowcontrol 
    // on the flow control channel.
}
