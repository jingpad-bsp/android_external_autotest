/*
 * Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#ifndef LIBAUDIODEV_H_
#define LIBAUDIODEV_H_

#include <alsa/asoundlib.h>

#define MAX_HWNAME_SIZE 16

typedef struct audio_device_s {
  snd_pcm_t *handle;
  snd_pcm_stream_t direction;
  char hwdevname[MAX_HWNAME_SIZE];
} audio_device_t;

typedef struct audio_device_info_s {
  audio_device_t audio_device;
  unsigned int card;
  unsigned int dev_no;
  const char *dev_id;
  const char *dev_name;
  const char *pcm_id;
  const char *pcm_name;
} audio_device_info_t;

typedef struct audio_device_info_list_s {
  audio_device_info_t *devs;
  int count;
} audio_device_info_list_t;

extern unsigned int chunk_size;

/*
 * Get the list of devices in the direction specified by |direction|
 */
audio_device_info_list_t* get_device_list(snd_pcm_stream_t direction);

/*
 * Free the list of audio devices. Avoiding memory leaks is good.
 */
void free_device_list(audio_device_info_list_t *list);

/*
 * Open a sound handle for |device| and set required hardware and software
 * parameters. Returns 0 on successful creation, and an error code otherwise.
 *
 * |buffer_size| is the buffer size intended for use with this handle.
 *
 */
int create_sound_handle(audio_device_t *device, int buffer_size);

/*
 * Close the sound handle acquired for |device|.
 */
void close_sound_handle(audio_device_t *device);

/*
 *
 * Make an I/O call on |device|. The appropriate direction
 * is automatically determined based on the type. It reads/writes
 * |count| bytes from/to |data|
 *
 * |data| MUST be big enough to hold one chunk in case of playback.
 *
 * returns the number of bytes successfully written/read.
 */
ssize_t pcm_io(audio_device_t *device, unsigned char *data, size_t count);

#endif
