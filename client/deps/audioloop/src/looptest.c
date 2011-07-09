/*
 * Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#include <stdio.h>
#include <signal.h>
#include <pthread.h>
#include <unistd.h>

#include "libaudiodev.h"

static unsigned int buffer_count;

static struct mutexed_buffer_s {
  unsigned char *data;
  pthread_mutex_t mutex;
  pthread_cond_t has_data;
} *buffers;

/* Termination variable. */
static int terminate;
/* Buffer currently being captured to. */
static unsigned int buf_cap;

static void *play_loop(void *arg) {
  audio_device_t * device = (audio_device_t *)arg;
  unsigned int buf_play = 0;
  while (!terminate) {
    pthread_mutex_lock(&buffers[buf_play].mutex);
    while (buf_cap == buf_play) {
      pthread_cond_wait(&buffers[buf_play].has_data, &buffers[buf_play].mutex);
    }
    pcm_io(device, buffers[buf_play].data, chunk_size);
    pthread_mutex_unlock(&buffers[buf_play].mutex);
    buf_play = (buf_play + 1) % buffer_count;
  }
  return NULL;
}

static void *cap_loop(void *arg) {
  audio_device_t *device = (audio_device_t *)arg;
  int last;
  while (!terminate) {
    pthread_mutex_lock(&buffers[buf_cap].mutex);
    pcm_io(device, buffers[buf_cap].data, chunk_size);
    last = buf_cap;
    buf_cap = (buf_cap + 1) % buffer_count;
    pthread_cond_signal(&buffers[last].has_data);
    pthread_mutex_unlock(&buffers[last].mutex);
  }
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

static void get_choice(char *direction_name, audio_device_list_t *list,
    int *choice) {
  int i;
  while (1) {
    printf("%s devices:\n", direction_name);
    if (list->count == 0) {
      printf("No devices :(\n");
      exit(EXIT_FAILURE);
    }

    for (i = 0; i < list->count; i++) {
      printf("(%d)\nCard %d: %s, %s\n  Device %d: %s [%s]", i + 1,
          list->devs[i].card, list->devs[i].dev_id,
          list->devs[i].dev_name, list->devs[i].dev_no,
          list->devs[i].pcm_id, list->devs[i].pcm_name);
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

static void init_mutexed_buffers(int size) {
  int i;
  buffers = (struct mutexed_buffer_s *)malloc(buffer_count
      * sizeof(struct mutexed_buffer_s));
  if (!buffers) {
    fprintf(stderr, "Error: Could not create audio buffer array.\n");
    exit(EXIT_FAILURE);
  }
  for (i = 0; i < buffer_count; i++) {
    pthread_mutex_init(&buffers[i].mutex, NULL);
    pthread_cond_init(&buffers[i].has_data, NULL);
    buffers[i].data = (unsigned char *)malloc(size * sizeof(char));
    if (!buffers[i].data) {
      fprintf(stderr, "Error: Could not create audio buffers.\n");
      exit(EXIT_FAILURE);
    }
  }
}

void test(int buffer_size, unsigned int ct, int pdev, int cdev) {
  pthread_t capture_thread;
  pthread_t playback_thread;
  buffer_count = ct;
  audio_device_list_t* playback_list = get_device_list(SND_PCM_STREAM_PLAYBACK);
  audio_device_list_t* capture_list = get_device_list(SND_PCM_STREAM_CAPTURE);

  if (pdev == -1) {
    get_choice("playback", playback_list, &pdev);
  } else if (pdev == 0 || pdev > playback_list->count) {
    fprintf(stderr, "Invalid choice for playback device: %d\n", pdev);
    return;
  }
  if (cdev == -1) {
    get_choice("capture", capture_list, &cdev);
  } else if (cdev == 0 || cdev > capture_list->count) {
    fprintf(stderr, "Invalid ch oice for capture device: %d\n", cdev);
    return;
  }

  init_mutexed_buffers(buffer_size);
  terminate = 0;

  signal(SIGINT, signal_handler);
  signal(SIGTERM, signal_handler);
  signal(SIGABRT, signal_handler);

  if (create_sound_handle(&(playback_list->devs[pdev - 1]), buffer_size) ||
      create_sound_handle(&(capture_list->devs[cdev - 1]), buffer_size))
    exit(EXIT_FAILURE);

  buf_cap = 0;

  pthread_create(&playback_thread, NULL, play_loop,
      &(playback_list->devs[pdev - 1]));
  pthread_create(&capture_thread, NULL, cap_loop,
      &(capture_list->devs[cdev - 1]));

  pthread_join(capture_thread, NULL);
  pthread_join(playback_thread, NULL);

  close_sound_handle(&(playback_list->devs[pdev - 1]));
  close_sound_handle(&(capture_list->devs[cdev - 1]));

  free_device_list(playback_list);
  free_device_list(capture_list);

  printf("Exiting.\n");

}

int main(int argc, char **argv) {
  int play_dev = -1;
  int cap_dev = -1;
  int count = 12;
  int size = 512;
  int arg;

  while ((arg = getopt(argc, argv, "i:o:c:s:")) != -1) {
    switch(arg) {
      case 'i':
        cap_dev = atoi(optarg);
        break;
      case 'o':
        play_dev = atoi(optarg);
        break;
      case 'c':
        count = atoi(optarg);
        break;
      case 's':
        size = atoi(optarg);
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

