#include "awb/provides/multifpga_switch.h"

UINT32 FLOWCONTROL_LI_CHANNEL_OUT_CLASS::retryThreshold = 1000;

// Classes for handling flowcontrol
FLOWCONTROL_IN_CLASS::FLOWCONTROL_IN_CLASS(vector<LI_CHANNEL_OUT> *outChannelsInitializer,
                         tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQInitializer,
      	                 UMF_FACTORY factoryInitializer,
                         UINT64 flowcontrolChannelIDInitializer):
      LI_CHANNEL_IN_CLASS() // Perhaps a better name?
{
    outChannels = outChannelsInitializer;   
    // there is no need to keep the other variables, since flowcontrol messages do not block 
}

void FLOWCONTROL_IN_CLASS::pushUMF(UMF_MESSAGE &message) 
{

    UMF_CHUNK phyPvt = message->ExtractChunk();

    if(SWITCH_DEBUG)
    {
        cout << endl << "Incoming Provisional Flowcontrol Message length "<< dec << (UINT32) (message->GetLength()) << endl;  
        cout << "Channel ID "<< dec << message->GetChannelID() << endl;
    }
  
    UINT32 credits = phyPvt & (MULTIFPGA_FIFO_SIZES * 2 - 1);   
    phyPvt = phyPvt/(MULTIFPGA_FIFO_SIZES * 2); 
    UINT32 channel = phyPvt;

    if(SWITCH_DEBUG)
    {
        cout << "*** Credit Message" << endl;
        message->Print(cout); 
    }


    if(SWITCH_DEBUG)
    {
        cout << "Flowcontrol in Credit Message channel: " << dec << channel << " credits: " << dec << credits << endl;
    }

    delete message;
    ((FLOWCONTROL_LI_CHANNEL_OUT_CLASS*)(outChannels->at(channel)))->freeCredits(credits);
}


