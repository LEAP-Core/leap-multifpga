#include "asim/provides/physical_platform.h"

PHYSICAL_DEVICES_CLASS::PHYSICAL_DEVICES_CLASS(
    PLATFORMS_MODULE p) :
        PLATFORMS_MODULE_CLASS(p),
	unixPipeDevice0(this),
        unixPipeDevice1(this),
	pcieDevice0(this),
        pcieDevice1(this)
{
}

PHYSICAL_DEVICES_CLASS::~PHYSICAL_DEVICES_CLASS()
{
}
