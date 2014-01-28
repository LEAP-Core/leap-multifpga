#ifndef _LI_CHANNEL_COMMON_
#define _LI_CHANNEL_COMMON_

#include "awb/provides/umf.h"
#include "awb/provides/li_base_types.h"

void translateUMFMessage(LI_CHANNEL_RECV_CLASS<UMF_MESSAGE> *channel, UMF_MESSAGE element);

#endif
