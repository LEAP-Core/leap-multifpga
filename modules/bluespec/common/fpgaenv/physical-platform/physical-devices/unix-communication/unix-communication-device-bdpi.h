//
// Copyright (c) 2014, Intel Corporation
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
// Redistributions of source code must retain the above copyright notice, this
// list of conditions and the following disclaimer.
//
// Redistributions in binary form must reproduce the above copyright notice,
// this list of conditions and the following disclaimer in the documentation
// and/or other materials provided with the distribution.
//
// Neither the name of the Intel Corporation nor the names of its contributors
// may be used to endorse or promote products derived from this software
// without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.
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
#define BDPI_CHUNK_BYTES    8

#define PIPE_NULL           1

#define MAX_OPEN_CHANNELS   32

#define STDIN             0
#define STDOUT            1
#define BLOCK_SIZE        BDPI_CHUNK_BYTES
#define SELECT_TIMEOUT    0

typedef struct _CommBlock {
  char sync;
  unsigned char chunk[BDPI_CHUNK_BYTES];
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
