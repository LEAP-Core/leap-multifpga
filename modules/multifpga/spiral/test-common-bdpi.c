//
// Copyright (C) 2012 Intel Corporation
//
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// as published by the Free Software Foundation; either version 2
// of the License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
//

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "test-common-bdpi.h"

unsigned int delay(unsigned int incoming)
{
 
    float num = (float) incoming;
    int i;

    static double delay = -1.0;
    if (delay == -1.0) {
        char* delay_str = getenv("DELAY");
        if (delay_str) {
            delay = strtod(delay_str, NULL);
	}

        if (delay == -1.0) {
	    delay = 0;
	}
	printf("Set delay to %f", delay);
   }

    for(i = 0; i < delay; i++) {
        num = cos(num);
    }

    return (unsigned int) num;
}