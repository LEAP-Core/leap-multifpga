#ifndef __PHYSICAL_PLATFORM__
#define __PHYSICAL_PLATFORM__

#include "awb/provides/physical_channel.h"
#include "platforms-module.h"
#include "asim/provides/physical_platform_utils.h"

// ====================================================
//             Simulation Physical Platform
// ====================================================

// This class is a collection of all physical devices
// present on the Simulation Physical Platform
typedef class PHYSICAL_DEVICES_CLASS* PHYSICAL_DEVICES;
class PHYSICAL_DEVICES_CLASS: public PLATFORMS_MODULE_CLASS
{
    private:
        PCIE_BLUENOC_PHYSICAL_CHANNEL_CLASS pcieDevice0;
        PCIE_BLUENOC_PHYSICAL_CHANNEL_CLASS pcieDevice1;

    public:
        // constructor-destructor
        PHYSICAL_DEVICES_CLASS(PLATFORMS_MODULE);
        ~PHYSICAL_DEVICES_CLASS();

        // accessors to individual devices
        PHYSICAL_CHANNEL GetPCIEDevice0() { return &pcieDevice0; }
        PHYSICAL_CHANNEL GetPCIEDevice1() { return &pcieDevice1; }
	PHYSICAL_CHANNEL GetLegacyPhysicalChannel() { 
            pcieDevice0.RegisterLogicalDeviceName("Legacy");
            return &pcieDevice0; 
        }
};

#endif
