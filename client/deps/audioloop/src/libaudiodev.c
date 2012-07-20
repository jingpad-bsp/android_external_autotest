/*
 * Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#include <alsa/asoundlib.h>
#include <stdlib.h>
#include <stdio.h>

#include "libaudiodev.h"

#define CHANNELS 2
#define SAMPLE_RATE 44100
#define FORMAT SND_PCM_FORMAT_S16
#define NON_BLOCKING 0
#define INTERLEAVED SND_PCM_ACCESS_RW_INTERLEAVED

static size_t bits_per_sample;
static size_t bits_per_frame;
unsigned int chunk_size;

void free_device_list(audio_device_info_list_t *list) {
  int i;

  for (i=0; i < list->count; i++) {
    free((void *)list->devs[i].dev_id);
    free((void *)list->devs[i].dev_name);
    free((void *)list->devs[i].pcm_id);
    free((void *)list->devs[i].pcm_name);
  }

  free(list->devs);
  free(list);
}

int get_device_count(snd_pcm_stream_t direction) {
  int count = 0;
  int cid = -1;
  int ret;
  int dev;
  char hwname[MAX_HWNAME_SIZE];
  snd_ctl_t *handle;
  snd_ctl_card_info_t *info;

  snd_ctl_card_info_malloc(&info);

  ret = snd_card_next(&cid);
  if (ret == 0 && cid == -1) {
    printf("No %s audio devices found.\n", snd_pcm_stream_name(direction));
  }

  for (; cid != -1 && ret >= 0; ret = snd_card_next(&cid)) {
    snprintf(hwname, MAX_HWNAME_SIZE, "hw:%d", cid);

    ret = snd_ctl_open(&handle, hwname, 0);
    if (ret < 0) {
      fprintf(stderr, "Could not open card %d: %s", cid, snd_strerror(ret));
      continue;
    }

    ret = snd_ctl_card_info(handle, info);
    if (ret < 0) {
      fprintf(stderr, "Could not get info for card %d: %s",
              cid, snd_strerror(ret));
      snd_ctl_close(handle);
      continue;
    }

    dev = -1;
    ret = snd_ctl_pcm_next_device(handle, &dev);
    if (ret >= 0 && dev == -1) {
      fprintf(stderr, "Warning: No devices found on card %d\n", cid);
    }
    for (;dev != -1 && ret >= 0; ret = snd_ctl_pcm_next_device(handle, &dev)) {
      count++;
    }
    if (ret == -1) {
      fprintf(stderr, "Error reading next sound device on card %d\n", cid);
    }
    snd_ctl_close(handle);
  }
  if (ret == -1) {
    fprintf(stderr, "Error reading next sound card\n");
  }

  snd_ctl_card_info_free(info);

  return count;
}

/*
 * Refresh the list of playback or capture devices as specified by direction.
 */
audio_device_info_list_t *get_device_list(snd_pcm_stream_t direction) {
  int i = 0;
  int cid = -1;
  int ret;
  int dev;
  char hwname[MAX_HWNAME_SIZE];
  snd_ctl_t *handle;
  snd_ctl_card_info_t *info;
  snd_pcm_info_t *pcminfo;
  audio_device_info_list_t *list = (audio_device_info_list_t *)malloc(
      sizeof(audio_device_info_list_t));

  list->count = get_device_count(direction);
  list->devs = (audio_device_info_t *)malloc(
      list->count * sizeof(audio_device_info_t));

  snd_ctl_card_info_malloc(&info);
  snd_pcm_info_malloc(&pcminfo);

  ret = snd_card_next(&cid);
  if (ret == 0 && cid == -1)
    printf("No %s audio devices found.\n", snd_pcm_stream_name(direction));

  for (; cid != -1 && ret >= 0 && i < list->count; ret = snd_card_next(&cid)) {
    snprintf(hwname, MAX_HWNAME_SIZE, "hw:%d", cid);

    ret = snd_ctl_open(&handle, hwname, 0);
    if (ret < 0) {
      fprintf(stderr, "Could not open card %d: %s", cid, snd_strerror(ret));
      continue;
    }

    ret = snd_ctl_card_info(handle, info);
    if (ret < 0) {
      fprintf(stderr, "Could not get info for card %d: %s",
              cid, snd_strerror(ret));
      snd_ctl_close(handle);
      continue;
    }

    dev = -1;
    ret = snd_ctl_pcm_next_device(handle, &dev);
    if (ret >= 0 && dev == -1) {
      fprintf(stderr, "Warning: No devices found on card %d\n", cid);
    }
    for (;dev != -1 && ret >= 0; ret = snd_ctl_pcm_next_device(handle, &dev)) {
      snd_pcm_info_set_device(pcminfo, dev);
      snd_pcm_info_set_subdevice(pcminfo, 0);
      snd_pcm_info_set_stream(pcminfo, direction);
      ret = snd_ctl_pcm_info(handle, pcminfo);
      if (ret < 0) {
        fprintf(stderr, "error getting device info [%d, %d]: %s\n",
                cid, dev, snd_strerror(ret));
        continue;
      }

      list->devs[i].card = cid;
      list->devs[i].dev_no = dev;
      list->devs[i].dev_id = strdup(snd_ctl_card_info_get_id(info));
      list->devs[i].dev_name = strdup(snd_ctl_card_info_get_name(info));
      list->devs[i].pcm_id = strdup(snd_pcm_info_get_id(pcminfo));
      list->devs[i].pcm_name = strdup(snd_pcm_info_get_name(pcminfo));
      list->devs[i].audio_device.direction = direction;
      list->devs[i].audio_device.handle = NULL;
      snprintf(list->devs[i].audio_device.hwdevname, MAX_HWNAME_SIZE,
               "plughw:%d,%d", cid, dev);
      i++;
    }
    if (ret == -1) {
      fprintf(stderr, "Error reading next sound device on card %d\n", cid);
    }
    snd_ctl_close(handle);
  }
  if (i != list->count) {
    fprintf(stderr,
            "Error: expect %d sound device(s) but read only %d device(s)\n",
            list->count, i);
    list->count = i;
  }
  if (ret == -1) {
    fprintf(stderr, "Error reading next sound card\n");
  }

  snd_ctl_card_info_free(info);
  snd_pcm_info_free(pcminfo);

  return list;
}

void close_sound_handle(audio_device_t *device) {
  if (!device || !device->handle)
    return;

  snd_pcm_drop(device->handle);
  snd_pcm_close(device->handle);
  device->handle = NULL;
}

/*
 * Helper to create_sound_handle. Used to set hardware parameters like
 * sample rate, channels, interleaving, etc.
 */
static int set_hw_params(audio_device_t *device, int buffer_size,
                         snd_output_t *log) {
  snd_pcm_hw_params_t *hwparams;
  unsigned int rate_set;

  snd_pcm_hw_params_malloc(&hwparams);

  if (snd_pcm_hw_params_any(device->handle, hwparams) < 0) {
    fprintf(stderr, "No config available for PCM device %s\n",
            device->hwdevname);
    return 1;
  }
  if (snd_pcm_hw_params_set_access(device->handle, hwparams, INTERLEAVED) < 0) {
    fprintf(stderr, "Access type not available on PCM device %s\n",
            device->hwdevname);
    return 2;
  }

  if (snd_pcm_hw_params_set_format(device->handle, hwparams, FORMAT) < 0) {
    fprintf(stderr, "Could not set format for device %s\n", device->hwdevname);
    return 3;
  }

  if (snd_pcm_hw_params_set_channels(device->handle, hwparams, CHANNELS) < 0) {
    fprintf(stderr, "Could not set channel count for device %s\n",
            device->hwdevname);
    return 4;
  }

  /* Try to set rate. Check to see if rate is actually what we requested. */
  rate_set = SAMPLE_RATE;
  if (snd_pcm_hw_params_set_rate_near(device->handle,
                                      hwparams, &rate_set, 0) < 0) {
    fprintf(stderr, "Could not set bitrate near %u for PCM device %s\n",
            SAMPLE_RATE, device->hwdevname);
    return 5;
  }

  if (rate_set != SAMPLE_RATE)
    fprintf(stderr, "Warning: Actual rate(%u) != Requested rate(%u)\n",
            rate_set, SAMPLE_RATE);

  snd_pcm_hw_params_set_periods(device->handle, hwparams, 2, 0);
  snd_pcm_hw_params_set_period_size(device->handle,
                                    hwparams,
                                    buffer_size / 2,
                                    0);

  if (snd_pcm_hw_params(device->handle, hwparams) < 0) {
    fprintf(stderr, "Unable to install hw params:\n");
    snd_pcm_hw_params_dump(hwparams, log);
    return 6;
  }

  return 0;
}

/*
 * Helper to create_sound_handle. Set software parameters. There are
 * very few that are not deprecated.
 */
static int set_sw_params(audio_device_t *device, int buffer_size,
                         snd_output_t *log) {
  snd_pcm_sw_params_t *swparams;
  snd_pcm_sw_params_malloc(&swparams);
  snd_pcm_sw_params_current(device->handle, swparams);

  snd_pcm_sw_params_set_avail_min(device->handle, swparams,
                                  buffer_size / 2);
  snd_pcm_sw_params_set_start_threshold(device->handle, swparams,
                                        buffer_size / 8);

  if (snd_pcm_sw_params(device->handle, swparams) < 0) {
    fprintf(stderr, "Unable to install sw params:\n");
    snd_pcm_sw_params_dump(swparams, log);
    return 1;
  }

  return 0;
}

/*
 * Try to open a sound handle and set all required parameters.
 */
int create_sound_handle(audio_device_t *device, int buffer_size) {
  int ret;
  static snd_output_t *log;

  if (!device || device->handle)
    return 1;

  snd_output_stdio_attach(&log, stderr, 0);

  ret = snd_pcm_open(&device->handle, device->hwdevname,
                     device->direction, NON_BLOCKING);
  if (ret < 0) {
    fprintf(stderr, "Could not open sound device %s: %s\n",
            device->hwdevname, snd_strerror(ret));
    snd_output_close(log);
    return 2;
  }

  /* Try to set non-blocking mode if requested. */
  if (NON_BLOCKING) {
    ret = snd_pcm_nonblock(device->handle, 1);
    if (ret < 0)
      fprintf(stderr, "Could not set %s to non-blocking mode: %s\n",
              device->hwdevname, snd_strerror(ret));
  }

  if (set_hw_params(device, buffer_size, log) ||
      set_sw_params(device, buffer_size, log)) {
    snd_pcm_close(device->handle);
    device->handle = NULL;
    snd_output_close(log);
    return 3;
  }

  bits_per_sample = snd_pcm_format_physical_width(FORMAT);
  bits_per_frame = bits_per_sample * CHANNELS;
  chunk_size = buffer_size * 8 / bits_per_frame;

  snd_output_close(log);

  return 0;
}

ssize_t pcm_io(audio_device_t *device, unsigned char *data, size_t count) {
  ssize_t completed;
  ssize_t result = 0;
  int res;

  if (device->direction == SND_PCM_STREAM_PLAYBACK && count < chunk_size) {
    snd_pcm_format_set_silence(FORMAT, data + (count * bits_per_frame / 8),
                               (chunk_size - count) * CHANNELS);
    count = chunk_size;
  }
  while (count > 0) {
    if (device->direction == SND_PCM_STREAM_PLAYBACK) {
      completed = snd_pcm_writei(device->handle, data, count);
    } else {
      completed = snd_pcm_readi(device->handle, data, count);
    }
    if (completed == -EAGAIN) {
      snd_pcm_wait(device->handle, 1000);
    } else if (completed == -EPIPE) {
      res = snd_pcm_prepare(device->handle);
      if (res < 0) {
        fprintf(stderr, "Prepare error: %s", snd_strerror(res));
        exit(EXIT_FAILURE);
      }
    } else if (completed < 0) {
      fprintf(stderr, "I/O error in %s: %s, %lu\n",
              snd_pcm_stream_name(device->direction), snd_strerror(completed),
          (long unsigned int)completed);
    } else {
      result += completed;
      count -= completed;
      data += completed * bits_per_frame / 8;
    }
  }
  return result;
}
