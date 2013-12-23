#include <queue>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <pthread.h>

#include "platforms-module.h"
#include "awb/provides/umf.h"
#include "awb/provides/physical_channel.h"
#include "awb/provides/multifpga_switch.h"
#include "awb/provides/li_base_types.h"
#include "awb/provides/multifpga_switch.h"
#include "pointer-ingress-regional.h"
#include "tbb/concurrent_queue.h"
#include "tbb/compat/condition_variable"
#include "tbb/atomic.h"

// Classes for handling flowcontrol
FLOWCONTROL_IN_CLASS::FLOWCONTROL_IN_CLASS(vector<LI_CHANNEL_OUT> *outChannelsInitializer,
					   tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQInitializer,
					   UMF_FACTORY factoryInitializer,
                                           UINT64 flowcontrolChannelIDInitializer):
    FLOWCONTROL_LI_CHANNEL_IN_CLASS(flowcontrolQInitializer,
				    factoryInitializer,
                                    flowcontrolChannelIDInitializer), // Probably requires flowcontrol layer
    totalCredits(),
    totalCreditsRX(),
    totalSent(),
    flowcontrolMutex(),
    flowcontrolVariable()  
{
    outChannels = outChannelsInitializer;   
    totalCredits = 0;
    totalSent = 0;
    totalCreditsRX = 0;
}

void FLOWCONTROL_IN_CLASS::Init()
{
    for(vector<LI_CHANNEL_OUT>::iterator channelIter = outChannels->begin(); 
        channelIter != outChannels->end();
        channelIter++)
    { 
        ((FLOWCONTROL_LI_CHANNEL_OUT_CLASS*)(*channelIter))->registerRegionalFlowcontrol(this);
    }

    regionalReturnThreshold = MULTIFPGA_FIFO_SIZES - outChannels->size() * MINIMUM_CHANNEL_BUFFER;

}

// We could do something more intelligent here. 
void FLOWCONTROL_IN_CLASS::pushUMF(UMF_MESSAGE &message) 
{
    // Tell my regional manager that I am freeing credits 
    acquireCredits(2);
    UMF_CHUNK phyPvt = message->ExtractChunk();

    if(SWITCH_DEBUG)
    {
        cout << endl << "Provisional Flowcontrol Message length "<< dec << (UINT32) (message->GetLength()) << endl;  
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
        totalCreditsRX.fetch_and_add(credits);
        cout << "Flowcontrol in Credit Message channel: " << dec << channel << " credits: " << dec << credits << " total credits RX: " << dec << totalCreditsRX << endl;
    }

    ((FLOWCONTROL_LI_CHANNEL_OUT_CLASS*)(outChannels->at(channel)))->freeCredits(credits);

    freeCredits(message->GetServiceID());

    delete message;   
}


void FLOWCONTROL_LI_CHANNEL_OUT_CLASS::freeCredits(UINT32 credits) 
{
    timespec finish;

        unique_lock<std::mutex> flowcontrolLock( regionalFlowcontrol->flowcontrolMutex );

        if(SWITCH_DEBUG) 
        {
  	    cout << "Before update Credits: (regional) " << dec << regionalFlowcontrol->totalCredits << " (local): " << flowcontrolCredits << endl;
        }

        flowcontrolCredits.fetch_and_add(-1 * credits);
        regionalFlowcontrol->totalCredits.fetch_and_add(-1 * credits);


        if(SWITCH_DEBUG) 
        {
            cout << "Attempting to update credits" << dec << credits <<endl;
  	    cout << "Credits: (regional) " << dec << regionalFlowcontrol->totalCredits << " (local): " << flowcontrolCredits << endl;
        }
            

        if(TIME_SWITCH) 
        {
            clock_gettime(CLOCK_REALTIME, &finish);

            timespec temp;
            if ((finish.tv_nsec-start.tv_nsec)<0) {
                temp.tv_sec = finish.tv_sec-start.tv_sec-1;
                temp.tv_nsec = 1000000000+finish.tv_nsec-start.tv_nsec;
            } else {
                temp.tv_sec = finish.tv_sec-start.tv_sec;
                temp.tv_nsec = finish.tv_nsec-start.tv_nsec;
            }

            cout << "Seconds since credit update " << temp.tv_sec << endl;
            cout << "Nanoseconds since credit update " << temp.tv_nsec << endl;
            start = finish;
	}

        assert(regionalFlowcontrol->totalCredits > 0); 
        assert(flowcontrolCredits >= 0); 

        
        regionalFlowcontrol->flowcontrolVariable.notify_all();
            
        if(SWITCH_DEBUG) 
        {
            cout << "credits updated" << endl;
        }

}


void FLOWCONTROL_LI_CHANNEL_OUT_CLASS::acquireCredits(UINT32 messageLength)
{
    // it is possible that someone could sneak in an steal our credit even if we are woken.      
    unique_lock<std::mutex> flowcontrolLock(regionalFlowcontrol->flowcontrolMutex);
    while(((regionalFlowcontrol->totalCredits + messageLength) > (regionalFlowcontrol->regionalReturnThreshold)) && 
	  ((flowcontrolCredits + messageLength) > (MINIMUM_CHANNEL_BUFFER)))
    {
        if(SWITCH_DEBUG)
        {
  	    cout << "Channel "<< this << " Blocks for flowcontrol credits, totalCredits: " << regionalFlowcontrol->totalCredits << " channelCredits " << flowcontrolCredits << endl;
        }

        regionalFlowcontrol->flowcontrolVariable.wait(flowcontrolLock);  //Need to wait for a credit message.      

        if(SWITCH_DEBUG)
        {
            cout << "Channel "<< this << " Wakes" << endl;
        }
    }

    flowcontrolCredits.fetch_and_add(messageLength);
    regionalFlowcontrol->totalCredits.fetch_and_add(messageLength);
    regionalFlowcontrol->totalSent.fetch_and_add(messageLength);

    if(SWITCH_DEBUG)
    {
      cout << "Message Length: " << messageLength << endl;
      cout << "Total Sent: " << regionalFlowcontrol->totalSent << endl;
      cout << "Credits remaining (local): " << dec << flowcontrolCredits << " (regional): " << dec << regionalFlowcontrol->totalCredits << endl;
      cout << "Regional return threshold: " << dec << regionalFlowcontrol->regionalReturnThreshold << endl;
    }

}

// Flowcontrol will never block.  Ergo, we can send it without a credit check
void FLOWCONTROL_LI_CHANNEL_OUT_CLASS::acquireCreditsFC(UINT32 messageLength)
{
    // it is possible that someone could sneak in an steal our credit even if we are woken.      
    unique_lock<std::mutex> flowcontrolLock(regionalFlowcontrol->flowcontrolMutex);

    flowcontrolCredits.fetch_and_add(messageLength);
    regionalFlowcontrol->totalCredits.fetch_and_add(messageLength);
    regionalFlowcontrol->totalSent.fetch_and_add(messageLength);

    if(SWITCH_DEBUG)
    {
      cout << "Message Length: " << messageLength << endl;
      cout << "Total Sent: " << regionalFlowcontrol->totalSent << endl;
      cout << "Credits remaining (local): " << dec << flowcontrolCredits << " (regional): " << dec << regionalFlowcontrol->totalCredits << endl;
      cout << "Regional return threshold: " << dec << regionalFlowcontrol->regionalReturnThreshold << endl;
    }

}

void FLOWCONTROL_LI_CHANNEL_OUT_CLASS::registerRegionalFlowcontrol(class FLOWCONTROL_IN_CLASS* regionalFlowcontrolInitializer)
{
    regionalFlowcontrol = regionalFlowcontrolInitializer;   
    // At registration, we can set the local flowcontrol. 
    regionalFlowcontrol->flowcontrolMutex.lock();
    flowcontrolCredits.fetch_and_add(0);
    regionalFlowcontrol->flowcontrolMutex.unlock();        
        
}
