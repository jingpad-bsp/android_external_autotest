/*
 * Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#include <stdio.h>
#include <signal.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>

#include "libaudiodev.h"

typedef struct {
  unsigned char *data;
} audio_buffer;

static int verbose = 0;

static int buffer_count;  // Total number of buffer
static pthread_mutex_t buf_mutex;  // This protects the variables below
audio_buffer *buffers;
static int write_index;  // buffer should be written next
static int read_index;  // buffer should be read next
static int write_available;  // number of buffers can be write
static int read_available;  // number of buffers can be read
static pthread_cond_t has_data;
static struct timespec cap_start_time, play_start_time;
static int total_cap_frames, total_play_frames;

/* Termination variable. */
static int terminate;

static void set_current_time(struct timespec *ts) {
  clock_gettime(CLOCK_MONOTONIC, ts);
}

// Returns the time since the given time in nanoseconds.
static long long since(struct timespec *ts) {
  struct timespec now;
  clock_gettime(CLOCK_MONOTONIC, &now);
  long long t = now.tv_sec - ts->tv_sec;
  t *= 1000000000;
  t += (now.tv_nsec - ts->tv_nsec);
  return t;
}

static void update_stat() {
  if (verbose) {
    double cap_rate = total_cap_frames * 1e9 / since(&cap_start_time);
    double play_rate = total_play_frames * 1e9 / since(&play_start_time);
    printf("Buffer: %d/%d, Capture: %d, Play: %d    \r", read_available, buffer_count,
           (int) cap_rate, (int) play_rate);
  }
}

static void *play_loop(void *arg) {
  audio_device_t *device = (audio_device_t *)arg;
  int buf_play;

  pthread_mutex_lock(&buf_mutex);
  // Wait until half of the buffers are filled.
  while (!terminate && read_available < buffer_count / 2) {
    pthread_cond_wait(&has_data, &buf_mutex);
  }

  // Now start playing
  set_current_time(&play_start_time);
  total_play_frames = 0;
  while (!terminate) {
    while (read_available == 0) {
      pthread_cond_wait(&has_data, &buf_mutex);
    }
    buf_play = read_index;
    read_index = (read_index + 1) % buffer_count;
    read_available--;

    pthread_mutex_unlock(&buf_mutex);
    pcm_io(device, buffers[buf_play].data, chunk_size);
    pthread_mutex_lock(&buf_mutex);

    total_play_frames += chunk_size;
    write_available++;
    update_stat();
  }
  pthread_mutex_unlock(&buf_mutex);

  return NULL;
}

static void *cap_loop(void *arg) {
  audio_device_t *device = (audio_device_t *)arg;
  int buf_cap;

  pthread_mutex_lock(&buf_mutex);
  total_cap_frames = 0;
  set_current_time(&cap_start_time);
  while (!terminate) {
    // If we have no more buffer to write, drop the oldest one
    if (write_available == 0) {
      read_index = (read_index + 1) % buffer_count;
      read_available--;
    } else {
      write_available--;
    }
    buf_cap = write_index;
    write_index = (write_index + 1) % buffer_count;

    pthread_mutex_unlock(&buf_mutex);
    pcm_io(device, buffers[buf_cap].data, chunk_size);
    pthread_mutex_lock(&buf_mutex);

    total_cap_frames += chunk_size;
    read_available++;
    pthread_cond_signal(&has_data);
    update_stat();
  }
  pthread_mutex_unlock(&buf_mutex);

  return NULL;
}

static void signal_handler(int signal) {
  printf("Signal Caught.\n");

  terminate = 1;
}

static void dump_line(FILE *fp) {
  int ch;
  while ((ch = fgetc(fp)) != EOF && ch != '\n') {}
}

static void get_choice(char *direction_name, audio_device_info_list_t *list,
    int *choice) {
  int i;
  while (1) {
    printf("%s devices:\n", direction_name);
    if (list->count == 0) {
      printf("No devices :(\n");
      exit(EXIT_FAILURE);
    }

    for (i = 0; i < list->count; i++) {
      printf("(%d)\nCard %d: %s, %s\n  Device %d: %s [%s], %s", i + 1,
          list->devs[i].card, list->devs[i].dev_id,
          list->devs[i].dev_name, list->devs[i].dev_no,
          list->devs[i].pcm_id, list->devs[i].pcm_name,
          list->devs[i].audio_device.hwdevname);
      printf("\n");
    }
    printf("\nChoose one(1 - %d): ",  list->count);

    if (scanf("%d", choice) == 0) {
      dump_line(stdin);
      printf("\nThat was an invalid choice.\n");
    } else if (*choice > 0 && *choice <= list->count) {
      break;
    } else {
      printf("\nThat was an invalid choice.\n");
    }
  }
}

static void init_buffers(int size) {
  int i;
  buffers = (audio_buffer *)malloc(buffer_count * sizeof(audio_buffer));
  if (!buffers) {
    fprintf(stderr, "Error: Could not create audio buffer array.\n");
    exit(EXIT_FAILURE);
  }
  pthread_mutex_init(&buf_mutex, NULL);
  pthread_cond_init(&has_data, NULL);
  for (i = 0; i < buffer_count; i++) {
    buffers[i].data = (unsigned char *)malloc(size);
    if (!buffers[i].data) {
      fprintf(stderr, "Error: Could not create audio buffers.\n");
      exit(EXIT_FAILURE);
    }
  }
  read_index = write_index = 0;
  read_available = 0;
  write_available = buffer_count;
}

void test(int buffer_size, unsigned int ct, char *pdev_name, char *cdev_name) {
  pthread_t capture_thread;
  pthread_t playback_thread;
  buffer_count = ct;

  audio_device_info_list_t *playback_list = NULL;
  audio_device_info_list_t *capture_list = NULL;

  // Actual playback and capture devices we use to loop. Their
  // pcm handle will be closed in close_sound_handle.
  audio_device_t playback_device;
  audio_device_t capture_device;

  if (pdev_name) {
    playback_device.direction = SND_PCM_STREAM_PLAYBACK;
    playback_device.handle = NULL;
    strcpy(playback_device.hwdevname, pdev_name);
  } else {
    playback_list = get_device_list(SND_PCM_STREAM_PLAYBACK);
    int pdev;
    get_choice("playback", playback_list, &pdev);
    playback_device = playback_list->devs[pdev - 1].audio_device;
  }

  if (cdev_name) {
    capture_device.direction = SND_PCM_STREAM_CAPTURE;
    capture_device.handle = NULL;
    strcpy(capture_device.hwdevname, cdev_name);
  } else {
    capture_list = get_device_list(SND_PCM_STREAM_CAPTURE);
    int cdev;
    get_choice("capture", capture_list, &cdev);
    capture_device = capture_list->devs[cdev - 1].audio_device;
  }

  init_buffers(buffer_size);
  terminate = 0;

  signal(SIGINT, signal_handler);
  signal(SIGTERM, signal_handler);
  signal(SIGABRT, signal_handler);

  if (create_sound_handle(&playback_device, buffer_size) ||
      create_sound_handle(&capture_device, buffer_size))
    exit(EXIT_FAILURE);

  pthread_create(&playback_thread, NULL, play_loop, &playback_device);
  pthread_create(&capture_thread, NULL, cap_loop, &capture_device);

  pthread_join(capture_thread, NULL);
  pthread_join(playback_thread, NULL);

  close_sound_handle(&playback_device);
  close_sound_handle(&capture_device);

  if (playback_list)
    free_device_list(playback_list);
  if (capture_list)
    free_device_list(capture_list);

  printf("Exiting.\n");
}

int main(int argc, char **argv) {
  char *play_dev = NULL;
  char *cap_dev = NULL;
  int count = 100;
  int size = 1024;
  int arg;

  while ((arg = getopt(argc, argv, "i:o:c:s:v")) != -1) {
    switch(arg) {
      case 'i':
        cap_dev = optarg;
        break;
      case 'o':
        play_dev = optarg;
        break;
      case 'c':
        count = atoi(optarg);
        break;
      case 's':
        size = atoi(optarg);
        break;
      case 'v':
        verbose = 1;
        break;
      case '?':
        if (optopt == 'i' || optopt == 'o' || optopt == 'c' || optopt == 's') {
          fprintf(stderr, "Option -%c requires an argument.\n", optopt);
        } else {
          fprintf(stderr, "Unknown Option -%c.\n", optopt);
        }
      default:
        return 1;
    }
  }

  test(size, count, play_dev, cap_dev);
  return 0;
}
