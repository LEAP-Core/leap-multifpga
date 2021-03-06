#ifndef __PHYSICAL_PLATFORM__
#define __PHYSICAL_PLATFORM__

#include "platforms-module.h"
#include "default-switches.h"

// ====================================================
//             Simulation Physical Platform
// ====================================================

// This class is a collection of all physical devices
// present on the Simulation Physical Platform
typedef class PHYSICAL_DEVICES_CLASS* PHYSICAL_DEVICES;
class PHYSICAL_DEVICES_CLASS: public PLATFORMS_MODULE_CLASS
{
    private:
        BASIC_COMMAND_SWITCH_STRING_CLASS    deviceSwitch; // needed to keep the command line parsers happy.
    public:
        // constructor-destructor
        PHYSICAL_DEVICES_CLASS(PLATFORMS_MODULE);
        ~PHYSICAL_DEVICES_CLASS();


};

#endif
