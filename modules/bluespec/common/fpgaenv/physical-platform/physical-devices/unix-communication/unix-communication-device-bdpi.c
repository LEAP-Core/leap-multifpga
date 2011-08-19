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
#include <pthread.h>
#include <glib.h>

#include "unix-communication-device-bdpi.h"

#define DEBUG_COMM 0

/* global table of open channel handles */
static Channel OCHT[MAX_OPEN_CHANNELS];
static Channel *freeList;
static unsigned char initialized = 0;

/* internal helper functions */
void cleanup_comm()
{
  // need to tear down all threads and fifos here
}

/* doesn't seem too thread safe... */
void comm_init()
{
    int i;
    char buf[32];

    if(DEBUG_COMM) {
      printf("Calling comm init\n");
      fflush(stdout);
    }

    if (initialized) return;
    initialized = 1;

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
        OCHT[i].open = 0;
    }
    OCHT[MAX_OPEN_CHANNELS - 1].prev = &OCHT[MAX_OPEN_CHANNELS - 2];
    OCHT[MAX_OPEN_CHANNELS - 1].next = &OCHT[0];

}

void process_incoming(Channel * descriptor) {
  // I assume that the sender will create the fifo for me. 
 
  // There's probably a race condition here.  We should sleep and retry for a while. 
  int infile, retries = 0;
  int bytes_read;
  CommBlock buffer;

  do {
    infile = open(descriptor->incomingFIFO, O_RDONLY);
    retries ++;
    sleep(1);
  } while (infile < 0 && retries < 120);

  if(infile < 0) {
    fprintf(stderr, "Timed out waiting for %s, transfers on this line result in deadlocks\n", descriptor->incomingFIFO);
    // This isn't necessarily an error.
    // We probably need some better phase in which we attempt to communicate with everything that 
    // should exist.
    return;
  } else {
    if(DEBUG_COMM) {
      fprintf(stderr, "Opened %s\n", descriptor->incomingFIFO);
    }
  }

  // Clear out everything unil sync word

  do {
    bytes_read = read(infile,
		      &buffer,
		      sizeof(CommBlock));
  } while ((bytes_read < sizeof(CommBlock)) || !buffer.sync);

  if(DEBUG_COMM) {
    printf("Received Sync\n");
    fflush(stdout);
  }

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
    g_async_queue_push(descriptor->incomingQ,buffer);     
  }

}

int send_block(int fd, CommBlock *block, Channel *channel) {
    /* send message on pipe */
    int bytes_written = write(fd, block, sizeof(CommBlock));
    if (bytes_written == -1)
    {
        fprintf(stderr, "HW exiting (pipe closed)\n");
        // I guess we should clean ourselves
        // The way to do this is bailing...
        // By bailing the main starter propagates through the 
        // system. 
        exit(0); 
    }
    else if (bytes_written < sizeof(CommBlock))
    {
        fprintf(stderr, "could not write complete chunk.\n");
    }

    if(DEBUG_COMM) {
      printf("Sending block\n");
      fflush(stdout);   
    }

    return bytes_written;
}

void process_outgoing(Channel * channel) {
  // It's our responsibility to unlink an existing fifo and to set it up.                                                                                           
  int outfile;

  if(DEBUG_COMM) {
    fprintf(stderr, "Attempting to open %s\n", channel->outgoingFIFO);
  }

  // someone probably already set this up. 
  mkfifo(channel->outgoingFIFO, S_IWUSR | S_IRUSR | S_IRGRP | S_IROTH);
  
  outfile = open(channel->outgoingFIFO, O_WRONLY);
  if (outfile < 0)
  {
      fprintf(stderr, "Error with %s\n", channel->outgoingFIFO);
      exit(1);
  }
  else {
    if(DEBUG_COMM) {
      fprintf(stderr, "Opened %s\n", channel->outgoingFIFO);
      fflush(stderr);
    }
  }

  // send a sync word
  CommBlock syncBlock;
  syncBlock.sync = 1;  

  if(DEBUG_COMM) {
    printf("Sending handshake\n");
    fflush(stdout);
  }

  send_block(outfile, &syncBlock, channel);

  while(1) {
    CommBlock *block = g_async_queue_pop(channel->outgoingQ);
    send_block(outfile, block, channel);
    free(block); 
  }

}


/* create process and initialize data structures */
unsigned char comm_open(char* outgoing, char* incoming)
{
    int i;
    Channel *channel;

    if(DEBUG_COMM) {
      printf("Calling comm open\n");
    }

    assert(initialized == 1);

    /* try to allocate new channel from OCHT */
    if (freeList == NULL)
    {
        /* can't allocate any more channels.
         * we should return an error value to the
         * model, but for now, just crash out.. TODO */
        fprintf(stderr, "Free list is null, bailing\n");
        cleanup_comm();
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
    strcpy(channel->incomingFIFO,incoming);

    channel->outgoingFIFO = (char*) malloc(strlen(outgoing)*sizeof(char));
    strcpy(channel->outgoingFIFO,outgoing);

    pthread_create(&(channel->incomingThread), NULL, &process_incoming,channel);
    pthread_create(&(channel->outgoingThread), NULL, &process_outgoing,channel);

    /* initialize channel */
    channel->open = 1;

    if(DEBUG_COMM) {
      printf("Finished comm open\n");
      fflush(stdout);
    }

    /* return handle */
    return channel->tableIndex;
}

Channel *validate_handle(unsigned char handle) 
{
    Channel *channel;
    if (! initialized)
    {
        printf("Handle %d not initialized\n", handle);
        fflush(stdout);
        return NULL;
    }

    /* lookup OCHT */
    if(handle >= MAX_OPEN_CHANNELS) {
      printf("Handle %d too large\n", handle);
      fflush(stdout);
      return NULL;
    }

    channel = &OCHT[handle];
    if (!channel->open) {
      printf("Handle %d not open\n", handle);
      fflush(stdout);
      return NULL;
    }

    return channel;
}
 
/* read one chunk of data */
unsigned long long comm_read(unsigned char handle)
{
    Channel *channel;
    CommBlock *block;
    unsigned long long retval = 0;
    int i;

    channel = validate_handle(handle);

    block = g_async_queue_pop(channel->incomingQ); 
    for (i = 0; i < BDPI_CHUNK_BYTES; i++)
    {
    	unsigned long long byte = block->chunk[i];
	if(DEBUG_COMM) {
	  printf("comm byte %d = %x\n", byte, block->chunk[i]);
	}

    	retval |= ((byte & 0xff) << (i * 8));
    }

    if(DEBUG_COMM) {
      printf("comm driver reading: %llx\n", retval);
    }

    return retval;
}


// Return 1 if can write, 0 if can not.

unsigned char comm_can_write(unsigned char handle)
{
    Channel *channel;
    channel = validate_handle(handle);

    if(channel == NULL) {
      // We're not open yet. 
      return 0;
    }

    // otherwise we can always write
    return  1;
}

unsigned char comm_can_read(unsigned char handle)
{
    unsigned long long mask;  
    Channel *channel;
    CommBlock *block;

    channel = validate_handle(handle);

    if(channel == NULL) {
      // We're not open yet. 
      return 0;
    }

    return  g_async_queue_length(channel->incomingQ) > 0;
}




/* write one chunk of data */
void comm_write(unsigned char handle, unsigned long long data)
{   
    unsigned long long mask;  
    Channel *channel;
    int i;
    CommBlock * buffer;

    channel = validate_handle(handle);

    buffer = (CommBlock*) malloc(sizeof(CommBlock));

    if(DEBUG_COMM) {
      printf("Attempting a write\n");
      fflush(stdout);
    }

    buffer->sync = 0;
    /* unpack UINT32 into byte sequence */
    mask = 0xFF;
    for (i = 0; i < BDPI_CHUNK_BYTES; i++)
    {
        unsigned char byte = (mask & data) >> (i * 8);
        buffer->chunk[i] = (unsigned char)byte;
        mask = mask << 8;
	if(DEBUG_COMM) {
	  printf("comm byte %d = %x\n", i, buffer->chunk[i]);
	}
    }


    if(DEBUG_COMM) {
      printf("comm driver writing: %llx\n", data);
      printf("Attempting to push\n");
      fflush(stdout);
    }

    g_async_queue_push(channel->outgoingQ,buffer);     

    if(DEBUG_COMM) {
      printf("Push succeeds\n");
      fflush(stdout);
    }
}
