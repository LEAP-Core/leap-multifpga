#include "awb/provides/physical_platform.h"

PHYSICAL_DEVICES_CLASS::PHYSICAL_DEVICES_CLASS(
    PLATFORMS_MODULE p) :
    PLATFORMS_MODULE_CLASS(p),
    deviceSwitch("Dummy")    // Dummy device ID (no physical channel)
{
}

PHYSICAL_DEVICES_CLASS::~PHYSICAL_DEVICES_CLASS()
{
}
