//
// Copyright (C) 2008 Intel Corporation
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

#ifndef __UNIX_PIPE_BDPI__
#define __UNIX_PIPE_BDPI__

#include <sys/select.h>
#include <glib.h>

// Hack to get UMF_CHUNK_BYTES.  Can't use normal search hierarchy since the
// BDPI module is compiled by Bluespec.
#define AWB_DEFS_ONLY
#include "../../sw/include/asim/provides/umf.h"
#undef AWB_DEFS_ONLY

/* pipe I/O happens at the granularity of "chunks",
 * but to reduce overheads we physically do selects, reads
 * and writes at the granularity of "blocks" */
#define BDPI_CHUNK_BYTES    UMF_CHUNK_BYTES

#define PIPE_NULL           1

#define MAX_OPEN_CHANNELS   32

#define STDIN             0
#define STDOUT            1
#define BLOCK_SIZE        UMF_CHUNK_BYTES
#define SELECT_TIMEOUT    0

typedef struct _CommBlock {
  char sync;
  unsigned char chunk[UMF_CHUNK_BYTES];
} CommBlock;

typedef struct _Channel
{
    int     open;
    int     tableIndex;

    char *incomingFIFO;
    char *outgoingFIFO;

    GAsyncQueue *incomingQ;
    GAsyncQueue *outgoingQ;

    pthread_t incomingThread;
    pthread_t outgoingThread;

    struct _Channel *prev;
    struct _Channel *next;

} Channel;

/* interface methods */
void comm_init();
unsigned char comm_open(char *outgoing, char *incoming);

// Returns 65 useful bits.  The first unsigned long long is data.  The next
// bit is set for PIPE_NULL (no new data).
unsigned char comm_can_read(unsigned char handle);
unsigned long long comm_read(unsigned char handle);

// Return 1 if can write, 0 if can not.
unsigned char comm_can_write(unsigned char handle);
void comm_write(unsigned char handle, unsigned long long data);

#endif
