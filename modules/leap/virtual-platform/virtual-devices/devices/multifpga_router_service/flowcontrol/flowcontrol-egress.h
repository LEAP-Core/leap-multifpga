#ifndef __FLOWCONTROL_EGRESS__
#define __FLOWCONTORL_EGRESS__

#include <queue>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <pthread.h>

#include "platforms-module.h"
#include "awb/provides/umf.h"
#include "awb/provides/physical_channel.h"
#include "awb/provides/li_base_types.h"
#include "tbb/concurrent_queue.h"
#include "tbb/compat/condition_variable"
#include "tbb/atomic.h"


// Handles incoming flowcontrol messages. 
class FLOWCONTROL_IN_CLASS: public LI_CHANNEL_IN_CLASS
{
  private:
    vector<LI_CHANNEL_OUT> *outChannels;

  public:
    FLOWCONTROL_IN_CLASS(vector<LI_CHANNEL_OUT> *outChannelInitializer,
                         tbb::concurrent_bounded_queue<UMF_MESSAGE> *flowcontrolQInitializer,
      	                 UMF_FACTORY factoryInitializer,
                         UINT64 flowcontrolChannelIDInitializer);

    virtual void pushUMF(UMF_MESSAGE &message); 
    void Init() {};
};

// Add a flow control interface to outbound channels
typedef class FLOWCONTROL_LI_CHANNEL_OUT_CLASS* FLOWCONTROL_LI_CHANNEL_OUT;
class FLOWCONTROL_LI_CHANNEL_OUT_CLASS: public LI_CHANNEL_OUT_CLASS
{
  protected:  
    class tbb::atomic<UINT32> flowcontrolCredits;    
    class std::mutex flowcontrolMutex; 
    condition_variable flowcontrolVariable; 
    timespec start;

  public:

    static UINT32 retryThreshold;

    FLOWCONTROL_LI_CHANNEL_OUT_CLASS(class tbb::concurrent_bounded_queue<UMF_MESSAGE> *outputQInitializer):
        LI_CHANNEL_OUT_CLASS(outputQInitializer),
	flowcontrolCredits(),
        flowcontrolMutex(),
        flowcontrolVariable()  
    { 
        flowcontrolMutex.lock();
        flowcontrolCredits.fetch_and_add(MULTIFPGA_FIFO_SIZES);
        flowcontrolMutex.unlock();        
        clock_gettime(CLOCK_REALTIME, &start);
    };

    ~FLOWCONTROL_LI_CHANNEL_OUT_CLASS() {};

    // free credits may need to be overridden by route through codes. 
    void freeCredits(UINT32 credits) 
    {
        timespec finish;
        if(outputQ != NULL) // Are we a real channel, or a dummy?
	{
            if(SWITCH_DEBUG) 
            {
                cout << "Attempting to update credits" << endl;
	    }

            flowcontrolCredits.fetch_and_add(credits);            
            unique_lock<std::mutex> flowcontrolLock( flowcontrolMutex );

            if(TIME_SWITCH) 
	    { 
                clock_gettime(CLOCK_REALTIME, &finish);

                timespec temp;
                if ((finish.tv_nsec-start.tv_nsec)<0) 
                {
                    temp.tv_sec = finish.tv_sec-start.tv_sec-1;
                    temp.tv_nsec = 1000000000+finish.tv_nsec-start.tv_nsec;
                } 
                else 
                {
                    temp.tv_sec = finish.tv_sec-start.tv_sec;
                    temp.tv_nsec = finish.tv_nsec-start.tv_nsec;
                }

                cout << "Seconds since credit update " << temp.tv_sec << endl;
                cout << "Nanoseconds since credit update " << temp.tv_nsec << endl;
                start = finish;

	    }

            //assert(credits < MULTIFPGA_FIFO_SIZES); 
        
	    flowcontrolVariable.notify_all();
            
            if(SWITCH_DEBUG) 
            {
                cout << "credits updated" << endl;
	    }
	}
    };

    void acquireCredits(UINT32 credits)
    {
        // it is possible that someone could sneak in an steal our credit even if we are woken.      
        UINT32 retries;        

        for(retries = 0; retries < 2500; retries++) 
        {
 	    UINT32 originalCredits = flowcontrolCredits.fetch_and_add(-1 * credits);

            if(originalCredits < credits)
	    {
	        // Oops grabbed too much credit
  	        flowcontrolCredits.fetch_and_add(credits);        

	        if(SWITCH_DEBUG)
	        {
	            cout << "Channel "<< this << " spins for flowcontrol credits" << endl;
	        }       
	    } 
            else
	    {
	      if(retries > 0) 
                {
		  //      cout << "Channel "<< this << " spins " << retries << endl;
		}
	        return;
	    } 
	}

	//   	cout << "Channel "<< this << " spins " << retries << endl;
        // We failed to get credit enough times that we're just going to block... 
        unique_lock<std::mutex> flowcontrolLock(flowcontrolMutex);
	while(flowcontrolCredits < credits)
	{
	    if(SWITCH_DEBUG)
	    {
	        cout << "Channel "<< this << " Blocks for flowcontrol credits" << endl;
	    }
               
	    flowcontrolVariable.wait(flowcontrolLock);  //Need to wait for a credit message.      

            if(SWITCH_DEBUG)
	    {
	        cout << "Channel "<< this << " Wakes" << endl;
	    }
	}

	flowcontrolCredits.fetch_and_add(-1 * credits);

	if(SWITCH_DEBUG)
	{
	    cout << "Credits remaining: " << dec << flowcontrolCredits << endl;
	}

    };

};






#endif
