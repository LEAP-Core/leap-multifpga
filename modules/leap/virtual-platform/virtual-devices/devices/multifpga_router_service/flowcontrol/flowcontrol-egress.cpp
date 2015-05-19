#include "awb/provides/multifpga_switch.h"

UINT32 FLOWCONTROL_LI_CHANNEL_OUT_CLASS::retryThreshold = 1000;

/// 
// FLOWCONTROL_IN_CLASS -
//  Constructs instance of FLOWCONTROL_IN_CLASS. This class receives flowcontrol messages from 
//  the hardware layer and multiplexes them among the software-side channels.
FLOWCONTROL_IN_CLASS::FLOWCONTROL_IN_CLASS(vector<LI_CHANNEL_OUT> *outChannelsInitializer,
                         tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQInitializer,
      	                 UMF_FACTORY factoryInitializer,
                         UINT64 flowcontrolChannelIDInitializer):
      LI_CHANNEL_IN_CLASS() // Perhaps a better name?
{
    outChannels = outChannelsInitializer;   
    debugLog.open("flowcontrol_in." + to_string(flowcontrolChannelIDInitializer) + ".log");
    // there is no need to keep the other variables, since flowcontrol messages do not block 
}

///
// pushUMF -  
//  Actually revceives a flowcontrol message. We inspect the message and update the 
//  flow control credits for the appropriate software-side channel.
void FLOWCONTROL_IN_CLASS::pushUMF(UMF_MESSAGE &message) 
{

    UMF_CHUNK phyPvt = message->ExtractChunk();

    if(SWITCH_DEBUG)
    {
        debugLog << endl << "Incoming Provisional Flowcontrol Message length "<< dec << (UINT32) (message->GetLength()) << endl;  
        debugLog << "Channel ID "<< dec << message->GetChannelID() << endl;
    }
  
    UINT32 credits = phyPvt & (MULTIFPGA_FIFO_SIZES * 2 - 1);   
    phyPvt = phyPvt/(MULTIFPGA_FIFO_SIZES * 2); 
    UINT32 channel = phyPvt;

    if(SWITCH_DEBUG)
    {
        debugLog << "*** Credit Message" << endl;
        message->Print(debugLog); 
    }


    if(SWITCH_DEBUG)
    {
        debugLog << "Flowcontrol in Credit Message channel: " << dec << channel << " credits: " << dec << credits << endl;
    }

    delete message;
    ((FLOWCONTROL_LI_CHANNEL_OUT_CLASS*)(outChannels->at(channel)))->freeCredits(credits);
}


