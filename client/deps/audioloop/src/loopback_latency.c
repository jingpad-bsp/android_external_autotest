/* Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA
 *
 */

#include <stdio.h>
#include <stdlib.h>
#include <alsa/asoundlib.h>
#include <sys/time.h>
#include <math.h>

#include "cras_client.h"

static double phase = M_PI / 2;
static unsigned rate = 48000;
static unsigned channels = 2;
static snd_pcm_uframes_t buffer_frames = 480;
static snd_pcm_uframes_t period_size = 240;
static snd_pcm_format_t format = SND_PCM_FORMAT_S16_LE;

static int cras_put_silent = 5;
static int cras_captured_noise = 0;
static struct timeval *cras_play_time = NULL;
static struct timeval *cras_cap_time = NULL;
static int noise_threshold = 0x4000;


static void generate_sine(const snd_pcm_channel_area_t *areas,
                          snd_pcm_uframes_t offset, int count,
                          double *_phase)
{
    static double max_phase = 2. * M_PI;
    double phase = *_phase;
    double step = max_phase * 1000 / (double)rate;
    unsigned char *samples[channels];
    int steps[channels];
    unsigned int chn;
    int format_bits = snd_pcm_format_width(format);
    unsigned int maxval = (1 << (format_bits - 1)) - 1;
    int bps = format_bits / 8;  /* bytes per sample */
    int phys_bps = snd_pcm_format_physical_width(format) / 8;
    int big_endian = snd_pcm_format_big_endian(format) == 1;
    int to_unsigned = snd_pcm_format_unsigned(format) == 1;
    int is_float = (format == SND_PCM_FORMAT_FLOAT_LE ||
            format == SND_PCM_FORMAT_FLOAT_BE);

    /* Verify and prepare the contents of areas */
    for (chn = 0; chn < channels; chn++) {
        if ((areas[chn].first % 8) != 0) {
            fprintf(stderr, "areas[%i].first == %i, aborting...\n", chn,
                    areas[chn].first);
            exit(EXIT_FAILURE);
        }
        if ((areas[chn].step % 16) != 0) {
            fprintf(stderr, "areas[%i].step == %i, aborting...\n", chn, areas
                    [chn].step);
            exit(EXIT_FAILURE);
        }
        steps[chn] = areas[chn].step / 8;
        samples[chn] = ((unsigned char *)areas[chn].addr) +
                (areas[chn].first / 8) + offset * steps[chn];
    }

    /* Fill the channel areas */
    while (count-- > 0) {
        union {
            float f;
            int i;
        } fval;
        int res, i;
        if (is_float) {
            fval.f = sin(phase) * maxval;
            res = fval.i;
        } else
            res = sin(phase) * maxval;
        if (to_unsigned)
            res ^= 1U << (format_bits - 1);
        for (chn = 0; chn < channels; chn++) {
            /* Generate data in native endian format */
            if (big_endian) {
                for (i = 0; i < bps; i++)
                    *(samples[chn] + phys_bps - 1 - i) = (res >> i * 8) & 0xff;
            } else {
                for (i = 0; i < bps; i++)
                    *(samples[chn] + i) = (res >>  i * 8) & 0xff;
            }
            samples[chn] += steps[chn];
        }
        phase += step;
        if (phase >= max_phase)
            phase -= max_phase;
    }
    *_phase = phase;
}

static void config_pcm(snd_pcm_t *handle,
                       unsigned int rate,
                       unsigned int channels,
                       snd_pcm_format_t format,
                       snd_pcm_uframes_t *buffer_size,
                       snd_pcm_uframes_t *period_size)
{
    int err;
    snd_pcm_hw_params_t *hw_params;

    if ((err = snd_pcm_hw_params_malloc(&hw_params)) < 0) {
        fprintf(stderr, "cannot allocate hardware parameter structure (%s)\n",
                snd_strerror(err));
        exit(1);
    }

    if ((err = snd_pcm_hw_params_any(handle, hw_params)) < 0) {
        fprintf(stderr, "cannot initialize hardware parameter structure (%s)\n",
                snd_strerror(err));
        exit(1);
    }

    if ((err = snd_pcm_hw_params_set_access(handle, hw_params,
            SND_PCM_ACCESS_RW_INTERLEAVED)) < 0) {
        fprintf(stderr, "cannot set access type (%s)\n",
                snd_strerror(err));
        exit(1);
    }

    if ((err = snd_pcm_hw_params_set_format(handle, hw_params,
            format)) < 0) {
        fprintf(stderr, "cannot set sample format (%s)\n",
                snd_strerror(err));
        exit(1);
    }

    if ((err = snd_pcm_hw_params_set_rate_near(
            handle, hw_params, &rate, 0)) < 0) {
        fprintf(stderr, "cannot set sample rate (%s)\n",
                snd_strerror(err));
        exit(1);
    }

    if ((err = snd_pcm_hw_params_set_channels(handle, hw_params, 2)) < 0) {
        fprintf(stderr, "cannot set channel count (%s)\n",
                snd_strerror(err));
        exit(1);
    }

    if ((err = snd_pcm_hw_params_set_buffer_size_near(
            handle, hw_params, buffer_size)) < 0) {
        fprintf(stderr, "cannot set channel count (%s)\n",
                snd_strerror(err));
        exit(1);
    }

    if ((err = snd_pcm_hw_params_set_period_size_near(
            handle, hw_params, period_size, 0)) < 0) {
        fprintf(stderr, "cannot set channel count (%s)\n",
                snd_strerror(err));
        exit(1);
    }

    if ((err = snd_pcm_hw_params(handle, hw_params)) < 0) {
        fprintf(stderr, "cannot set parameters (%s)\n",
                snd_strerror(err));
        exit(1);
    }

    snd_pcm_hw_params_free(hw_params);

    if ((err = snd_pcm_prepare(handle)) < 0) {
        fprintf(stderr, "cannot prepare audio interface for use (%s)\n",
                snd_strerror(err));
        exit(1);
    }
}

static int capture_some(snd_pcm_t *pcm, short *buf, unsigned len)
{
    snd_pcm_sframes_t frames = snd_pcm_avail(pcm);
    int err;

    if (frames > 0) {
        frames = frames > len ? len : frames;

        if ((err = snd_pcm_readi(pcm, buf, frames)) != frames) {
            fprintf(stderr, "read from audio interface failed (%s)\n",
                    snd_strerror(err));
            exit(1);
        }
    }

    return (int)frames;
}

/* Looks for the first sample in buffer whose absolute value exceeds
 * noise_threshold. Returns the index of found sample in frames, -1
 * if not found. */
static int check_for_noise(short *buf, unsigned len, unsigned channels)
{
    unsigned int i;
    for (i = 0; i < len * channels; i++)
        if (abs(buf[i]) > noise_threshold)
            return i / channels;
    return -1;
}

static unsigned long subtract_timevals(const struct timeval *end,
                                       const struct timeval *beg)
{
    struct timeval diff;
    /* If end is before geb, return 0. */
    if ((end->tv_sec < beg->tv_sec) ||
            ((end->tv_sec == beg->tv_sec) && (end->tv_usec <= beg->tv_usec)))
        diff.tv_sec = diff.tv_usec = 0;
    else {
        if (end->tv_usec < beg->tv_usec) {
            diff.tv_sec = end->tv_sec - beg->tv_sec - 1;
            diff.tv_usec =
                end->tv_usec + 1000000L - beg->tv_usec;
        } else {
            diff.tv_sec = end->tv_sec - beg->tv_sec;
            diff.tv_usec = end->tv_usec - beg->tv_usec;
        }
    }
    return diff.tv_sec * 1000000 + diff.tv_usec;
}

static int cras_capture_tone(struct cras_client *client,
                             cras_stream_id_t stream_id,
                             uint8_t *samples, size_t frames,
                             const struct timespec *sample_time,
                             void *arg)
{
    assert(snd_pcm_format_physical_width(format) == 16);

    short *data = (short *)samples;
    int cap_frames_index;

    if (cras_captured_noise)
        return frames;

    if ((cap_frames_index = check_for_noise(data, frames, channels)) >= 0) {
        fprintf(stderr, "Got noise\n");
        cras_captured_noise = 1;

        struct timespec shifted_time = *sample_time;
        shifted_time.tv_nsec += 1000000000L / rate * cap_frames_index;
        while (shifted_time.tv_nsec > 1000000000L) {
            shifted_time.tv_sec++;
            shifted_time.tv_nsec -= 1000000000L;
        }
        cras_client_calc_capture_latency(&shifted_time, (struct timespec*)arg);
        cras_cap_time = (struct timeval*)malloc(sizeof(*cras_cap_time));
        gettimeofday(cras_cap_time, NULL);
    }

    return frames;
}

/* Callback for tone playback.  Playback latency will be passed
 * as arg and updated when the first tone.
 */
static int cras_play_tone(struct cras_client *client,
                          cras_stream_id_t stream_id,
                          uint8_t *samples, size_t frames,
                          const struct timespec *sample_time,
                          void *arg)
{
    snd_pcm_channel_area_t *areas;
    int chn;
    size_t sample_bytes;

    sample_bytes = snd_pcm_format_physical_width(format) / 8;

    areas = calloc(channels, sizeof(snd_pcm_channel_area_t));
    for (chn = 0; chn < channels; chn++) {
        areas[chn].addr = samples + chn * sample_bytes;
        areas[chn].first = 0;
        areas[chn].step = channels *
                snd_pcm_format_physical_width(format);
    }

    /* Write zero first at the beginning or noise got captured. */
    if (cras_put_silent-- > 0 || cras_captured_noise) {
        memset(samples, 0, sample_bytes * frames * channels);
    } else {
        generate_sine(areas, 0, frames, &phase);

        /* Update playback time and latency at first played frame. */
        if (cras_put_silent == -1) {
            cras_client_calc_playback_latency(sample_time,
                              (struct timespec*)arg);
            cras_play_time = (struct timeval*)malloc(sizeof(*cras_play_time));
            gettimeofday(cras_play_time, NULL);
        }
    }
    return frames;
}

static int stream_error(struct cras_client *client,
                        cras_stream_id_t stream_id,
                        int err,
                        void *arg)
{
    fprintf(stderr, "Stream error %d\n", err);
    return 0;
}

/* Adds stream to cras client.  */
static int cras_add_stream(struct cras_client *client,
                           struct cras_stream_params *params,
                           enum CRAS_STREAM_DIRECTION direction,
                           struct timespec *user_data)
{
    struct cras_audio_format *aud_format;
    cras_playback_cb_t aud_cb;
    cras_error_cb_t error_cb;
    size_t cb_threshold = buffer_frames / 10;
    size_t min_cb_level = buffer_frames / 10;
    int rc = 0;
    cras_stream_id_t stream_id = 0;

    aud_format = cras_audio_format_create(format, rate, channels);
    if (aud_format == NULL)
        return -ENOMEM;

    /* Create and start stream */
    aud_cb = (direction == CRAS_STREAM_OUTPUT)
            ? cras_play_tone
            : cras_capture_tone;
    error_cb = stream_error;
    params = cras_client_stream_params_create(direction,
            buffer_frames,
            cb_threshold,
            min_cb_level,
            0,
            0,
            user_data,
            aud_cb,
            error_cb,
            aud_format);
    if (params == NULL)
        return -ENOMEM;

    rc = cras_client_add_stream(client, &stream_id, params);
    if (rc < 0) {
        fprintf(stderr, "Add a stream fail.\n");
        return rc;
    }
    cras_audio_format_destroy(aud_format);
    return 0;
}

void cras_test_latency()
{
    int rc;
    struct cras_client *client = NULL;
    struct cras_stream_params *playback_params = NULL;
    struct cras_stream_params *capture_params = NULL;

    struct timespec playback_latency;
    struct timespec capture_latency;

    rc = cras_client_create(&client);
    if (rc < 0) {
        fprintf(stderr, "Create client fail.\n");
        exit(1);
    }
    rc = cras_client_connect(client);
    if (rc < 0) {
        fprintf(stderr, "Connect to server fail.\n");
        cras_client_destroy(client);
        exit(1);
    }

    cras_client_run_thread(client);
    rc = cras_add_stream(client,
                         playback_params,
                         CRAS_STREAM_OUTPUT,
                         &playback_latency);
    if (rc < 0) {
        fprintf(stderr, "Fail to add playback stream.\n");
        exit(1);
    }
    rc = cras_add_stream(client,
                         capture_params,
                         CRAS_STREAM_INPUT,
                         &capture_latency);
    if (rc < 0) {
        fprintf(stderr, "Fail to add capture stream.\n");
        exit(1);
    }

    int sleep_count = 10;
    while (sleep_count-- > 0) {
        if (cras_captured_noise)
            break;
        usleep(300000);
    }

    if (cras_cap_time && cras_play_time) {
        unsigned long latency = subtract_timevals(cras_cap_time,
                                                  cras_play_time);
        fprintf(stdout, "Measured Latency: %lu uS.\n", latency);

        latency = (playback_latency.tv_sec + capture_latency.tv_sec) * 1000000 +
                (playback_latency.tv_nsec + capture_latency.tv_nsec) / 1000;
        fprintf(stdout, "Reported Latency: %lu uS.\n", latency);
    } else {
        fprintf(stdout, "Audio not detected.\n");
    }

    /* Destruct things. */
    cras_client_stop(client);
    cras_client_stream_params_destroy(playback_params);
    cras_client_stream_params_destroy(capture_params);
    if (cras_play_time)
        free(cras_play_time);
    if (cras_cap_time)
        free(cras_cap_time);
}

void alsa_test_latency(char *play_dev, char* cap_dev)
{
    int err;
    short *play_buf;
    short *cap_buf;
    snd_pcm_t *playback_handle;
    snd_pcm_t *capture_handle;

    unsigned int num_buffers, chn;
    phase = 0;
    snd_pcm_sframes_t playback_delay_frames;
    snd_pcm_sframes_t cap_delay_frames;
    struct timeval sine_start_tv;
    snd_pcm_channel_area_t *areas;

    play_buf = calloc(buffer_frames * channels, sizeof(play_buf[0]));
    cap_buf = calloc(buffer_frames * channels, sizeof(play_buf[0]));

    if ((err = snd_pcm_open(&playback_handle, play_dev,
                SND_PCM_STREAM_PLAYBACK, 0)) < 0) {
        fprintf(stderr, "cannot open audio device %s (%s)\n",
                play_dev, snd_strerror(err));
        exit(1);
    }
    config_pcm(playback_handle, rate, channels, format, &buffer_frames,
           &period_size);

    if ((err = snd_pcm_open(&capture_handle, cap_dev,
                SND_PCM_STREAM_CAPTURE, 0)) < 0) {
        fprintf(stderr, "cannot open audio device %s (%s)\n",
                cap_dev, snd_strerror(err));
        exit(1);
    }
    config_pcm(capture_handle, rate, channels, format, &buffer_frames,
            &period_size);

    areas = calloc(channels, sizeof(snd_pcm_channel_area_t));
    for (chn = 0; chn < channels; chn++) {
        areas[chn].addr = play_buf;
        areas[chn].first = chn * snd_pcm_format_physical_width(format);
        areas[chn].step = channels * snd_pcm_format_physical_width(format);
    }

    /* Begin capture. */
    if ((err = snd_pcm_start(capture_handle)) < 0) {
        fprintf(stderr, "cannot start audio interface for use (%s)\n",
                snd_strerror(err));
        exit(1);
    }

    /* Play zeros for a half second. */
    for (num_buffers = 0; num_buffers < 50; num_buffers++) {
        if ((err = snd_pcm_writei(playback_handle, play_buf, period_size))
                != period_size) {
            fprintf(stderr, "write to audio interface failed (%s)\n",
                    snd_strerror(err));
            exit(1);
        }
        capture_some(capture_handle, cap_buf, period_size);
    }

    generate_sine(areas, 0, period_size, &phase);
    snd_pcm_delay(playback_handle, &playback_delay_frames);
    gettimeofday(&sine_start_tv, NULL);

    /* Then play a sine wave and look for it on capture.
     * This will fail for latency > 500mS. */
    for (num_buffers = 0; num_buffers < 50; num_buffers++) {
        int num_cap, noise_frames_index;

        if ((err = snd_pcm_writei(playback_handle, play_buf, period_size))
                != period_size) {
            fprintf(stderr, "write to audio interface failed (%s)\n",
                    snd_strerror(err));
            exit(1);
        }
        snd_pcm_delay(capture_handle, &cap_delay_frames);
        num_cap = capture_some(capture_handle, cap_buf, period_size);
        if (num_cap > 0 && (noise_frames_index = check_for_noise(cap_buf,
                num_cap, channels)) >= 0) {
            struct timeval cap_time;
            unsigned long latency_us;

            gettimeofday(&cap_time, NULL);

            fprintf(stderr, "Found audio\n");
            fprintf(stderr, "Played at %ld %ld, %ld delay\n",
                    sine_start_tv.tv_sec, sine_start_tv.tv_usec,
                    playback_delay_frames);
            fprintf(stderr, "Capture at %ld %ld, %ld delay sample %d\n",
                    cap_time.tv_sec, cap_time.tv_usec,
                    cap_delay_frames, noise_frames_index);

            latency_us = subtract_timevals(&cap_time, &sine_start_tv);
            fprintf(stdout, "Measured Latency: %lu uS\n", latency_us);

            latency_us = (playback_delay_frames + cap_delay_frames -
                    noise_frames_index) * 1000000 / rate;
            fprintf(stdout, "Reported Latency: %lu uS\n", latency_us);
            return;
        }
        generate_sine(areas, 0, period_size, &phase);
    }

    fprintf(stdout, "Audio not detected.\n");
    snd_pcm_close(playback_handle);
    free(play_buf);
    free(areas);
}

int main (int argc, char *argv[])
{
    int cras_only = 0;
    char *play_dev = "default";
    char *cap_dev = "default";

    int arg;
    while ((arg = getopt(argc, argv, "b:i:o:n:r:p:c")) != -1) {
    switch (arg) {
        case 'b':
            buffer_frames = atoi(optarg);
            break;
        case 'c':
            cras_only = 1;
            break;
        case 'i':
            cap_dev = optarg;
            fprintf(stderr, "Assign cap_dev %s\n", cap_dev);
            break;
        case 'n':
            noise_threshold = atoi(optarg);
            break;
        case 'r':
            rate = atoi(optarg);
            break;
        case 'o':
            play_dev = optarg;
            fprintf(stderr, "Assign play_dev %s\n", play_dev);
            break;
        case 'p':
            period_size = atoi(optarg);
            break;
        default:
            return 1;
        }
    }

    if (cras_only)
        cras_test_latency();
    else
        alsa_test_latency(play_dev, cap_dev);
    exit(0);
}
