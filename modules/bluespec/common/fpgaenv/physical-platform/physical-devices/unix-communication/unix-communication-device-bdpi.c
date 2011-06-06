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

#include <sys/select.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <errno.h>

#include "unix-communication-device-bdpi.h"

/* global table of open channel handles */
static Channel OCHT[MAX_OPEN_CHANNELS];
static Channel *freeList;
static unsigned char initialized = 0;

/* internal helper functions */
void cleanup()
{
  // need to tear down all threads and fifos here
}

/* initialize global data structures */
void comm_init(char* outgoing, char* incoming)
{
    int i;
    char buf[32];

    if (initialized) return;

    // Allows us to fork g_threads
    if(!g_thread_supported()) {
      g_thread_init(NULL);
    }

    assert(MAX_OPEN_CHANNELS >= 2);

    /* initialize free list, we'll maintain it as
     * a circular doubly linked list */
    bzero(OCHT, sizeof(Channel) * MAX_OPEN_CHANNELS);

    freeList = &OCHT[0];
    OCHT[0].prev = &OCHT[MAX_OPEN_CHANNELS - 1];
    OCHT[0].next = &OCHT[1];
    for (i = 1; i < MAX_OPEN_CHANNELS - 1; i++)
    {
        OCHT[i].tableIndex = i;
        OCHT[i].prev = &OCHT[i-1];
        OCHT[i].next = &OCHT[i+1];
    }
    OCHT[MAX_OPEN_CHANNELS - 1].prev = &OCHT[MAX_OPEN_CHANNELS - 2];
    OCHT[MAX_OPEN_CHANNELS - 1].next = &OCHT[0];

}

void process_incoming(Channel * descriptor) {
  // I assume that the sender will create the fifo for me. 
 
  // There's probably a race condition here.  We should sleep and retry for a while. 
  int infile = open(descriptor->incomingFIFO, O_RDONLY);
  if (infile < 0)
  {
    fprintf(stderr, "Error with %s\n", descriptor->incomingFIFO);
    perror("named incoming pipe (pipes/TO_FPGA)");
    exit(1);
  }

  // Clear out everything unil sync word

  do {
    CommBlock buffer;
    bytes_read = read(infile,
		      &buffer,
		      sizeof(CommBlock));
  } while (!buffer.sync)

  while(1) {
    int bytes_read;
    // this is probably inefficient but who cares.  
    CommBlock * buffer = (CommBlock*) malloc(sizeof(CommBlock));
  
    bytes_read = read(infile,
		      buffer,
		      sizeof(CommBlock));

    if(bytes_read == -1) {
      fprintf(stderr, "Error %d in unix-pipe-device-bdpi::pipe_read()\n", errno);
      exit(1);
    } else if(bytes_read == 0) {
      // looks like the other side died 
      break; // we really should not exit(0)
    }

    // push the data out.  we will free the data on deq.
    g_async_queue_push(incomingQ,buffer);     
  }

}

int send_block(int fd, CommBlock *block, Channel *channel) {
    /* send message on pipe */
  bytes_written = write(fd, block, sizeof(CommBlock));
    if (bytes_written == -1)
    {
        fprintf(stderr, "         HW side exiting (pipe closed)\n");
        // I guess we should clean ourselves
        // but i am not sure that this can ever fail    
    }
    else if (bytes_written < sizeof(CommBlock))
    {
        fprintf(stderr, "could not write complete chunk.\n");
    }
}

void process_outgoing(Channel * descriptor) {
  // It's our responsibility to unlink an existing fifo and to set it up.                                                                                           
  int outfile;

  // someone probably already set this up. 
  mkfifo(descriptor->outgoingFIFO, S_IWUSR | S_IRUSR | S_IRGRP | S_IROTH);

  int outfile = open(descriptor->outgoingFIFO, O_WRONLY);
  if (outfile < 0)
    {
      fprintf(stderr, "Error with %s\n", descriptor->outgoingFIFO);
      perror("named incoming pipe (pipes/TO_FPGA)");
      exit(1);
    }

  // send a sync word
  CommBlock syncBlock;
  syncBlock.sync = 1;  
  
  send_block(outfile, &syncBlock, descriptor);

  while(1) {
    CommBlock *block = g_async_queue_pop(channel->outgoingQ);
    send_block(outfile, block, descriptor);
    free(block);    
  }

}


/* create process and initialize data structures */
unsigned char comm_open(char* outgoing, char* incoming)
{
    int i;
    Channel *channel;

    assert(initialized == 1);

    /* try to allocate new channel from OCHT */
    if (freeList == NULL)
    {
        /* can't allocate any more channels.
         * we should return an error value to the
         * model, but for now, just crash out.. TODO */
        cleanup();
        exit(1);
    }

    /* eject one channel from free list */
    channel = freeList;
    if (channel->next == channel)
    {
        /* this was the last free channel */
        assert(channel->prev == channel);
        freeList = NULL;
    }
    else
    {
        /* update links */
        freeList->prev->next = freeList->next;
        freeList->next->prev = freeList->prev;
        freeList = freeList->next;
    }

    /* setup channel */
    assert(channel->open == 0);

    /* set up channel structures */
    channel->incomingQ = g_async_queue_new();
    channel->outgoingQ = g_async_queue_new();

    channel->incomingFIFO = (char*) malloc(strlen(incoming)*sizeof(char));
    strcopy(channel->incomingFIFO,incoming,strlen(incoming));

    channel->outgoinggFIFO = (char*) malloc(strlen(outgoing)*sizeof(char));
    strcopy(channel->outgoingFIFO,outgoing,strlen(outgoing));

    pthread_create(&(channel->incomingThread), NULL, &process_incoming,channel);
    pthread_create(&(channel->outgoingThread), NULL, &process_outgoing,channel);

    /* initialize channel */
    channel->open = 1;

    /* return handle */
    return channel->tableIndex;
}

Channel *validate_handle(unsigned char handle) 
{
    Channel *channel;
    if (! initialized)
    {
        return;
    }

    /* lookup OCHT */
    assert(handle < MAX_OPEN_CHANNELS);
    channel = &OCHT[handle];
    assert(channel->open);

    return channel;
}
 
/* read one chunk of data */
unsigned long long comm_read(unsigned char handle)
{
    Channel *channel;
    CommBlock *block;
    unsigned long long retval = 0;

    channel = validateHandle(handle);

    block = g_async_queue_pop(channel->incomingQ); 
    for (i = 0; i < BDPI_CHUNK_BYTES; i++)
    {
	unsigned int byte = block->chunk[i];
	retval |= (byte << (i * 8));
    }
    
    return retval;
}


// Return 1 if can write, 0 if can not.

unsigned char comm_can_write(unsigned char handle)
{
    return  1;
}

unsigned char comm_can_read(unsigned char handle)
{
    unsigned long long mask;  
    Channel *channel;
    CommBlock *block;

    channel = validateHandle(handle);

    return  g_async_queue_length(channel->incomingQ) > 0;
}




/* write one chunk of data */
void comm_write(unsigned char handle, unsigned long long data)
{   
    unsigned long long mask;  
    Channel *channel;
    CommBlock *block;

    channel = validateHandle(handle);

    CommBlock * buffer = (CommBlock*) malloc(sizeof(CommBlock));

    /* unpack UINT32 into byte sequence */
    mask = 0xFF;
    for (i = 0; i < BDPI_CHUNK_BYTES; i++)
    {
        unsigned char byte = (mask & data) >> (i * 8);
        block->chunk[i] = (unsigned char)byte;
        mask = mask << 8;
    }

    g_async_queue_push(channel->outgoingQ,block);     
}
