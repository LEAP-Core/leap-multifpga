#ifndef __PHYSICAL_PLATFORM__
#define __PHYSICAL_PLATFORM__

#include "awb/provides/physical_channel.h"
#include "platforms-module.h"

// ====================================================
//             Simulation Physical Platform
// ====================================================

// This class is a collection of all physical devices
// present on the Simulation Physical Platform
typedef class PHYSICAL_DEVICES_CLASS* PHYSICAL_DEVICES;
class PHYSICAL_DEVICES_CLASS: public PLATFORMS_MODULE_CLASS
{
    private:
        SIM_PHYSICAL_CHANNEL_CLASS unixPipeDevice0;
        SIM_PHYSICAL_CHANNEL_CLASS unixPipeDevice1;

    public:
        // constructor-destructor
        PHYSICAL_DEVICES_CLASS(PLATFORMS_MODULE);
        ~PHYSICAL_DEVICES_CLASS();

        // accessors to individual devices
        PHYSICAL_CHANNEL GetUNIXPipeDevice0() { return &unixPipeDevice0; }
        PHYSICAL_CHANNEL GetUNIXPipeDevice1() { return &unixPipeDevice1; }
	PHYSICAL_CHANNEL GetLegacyPhysicalChannel() 
        { 
            unixPipeDevice0.RegisterLogicalDeviceName("Legacy");
            return &unixPipeDevice0; 
        }
};

#endif
