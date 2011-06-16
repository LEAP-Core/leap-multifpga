
#ifndef __CONNECTED_APPLICATION__
#define __CONNECTED_APPLICATION__

#include <glib.h>

#include "awb/provides/virtual_platform.h"
#include "asim/rrr/client_stub_TESTDRRR.h"


// Default software does nothing and immediately returns 0;

typedef class CONNECTED_APPLICATION_CLASS* CONNECTED_APPLICATION;
class CONNECTED_APPLICATION_CLASS
{
   private:
    TESTDRRR_CLIENT_STUB clientStub;

  public:
    CONNECTED_APPLICATION_CLASS(VIRTUAL_PLATFORM vp);
    ~CONNECTED_APPLICATION_CLASS();
    void Init();
    int Main();
};


#endif
