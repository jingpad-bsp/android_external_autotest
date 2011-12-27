// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Simple playback test drivers.  Plays test tones using the native Alsa
// API allowing for configuration of volume, frequency, channels of output,
// etc.  See the output of PrintUsage() for instructions on how to use.

#include <getopt.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <set>
#include <string>

#include "common.h"
#include "alsa_client.h"
#include "tone_generators.h"

using autotest_client::audio::ASharpMinorGenerator;
using autotest_client::audio::AlsaPlaybackClient;
using autotest_client::audio::SampleFormat;
using autotest_client::audio::MultiToneGenerator;
using autotest_client::audio::TestConfig;

static struct option long_options[] = {
  {"test-type", 1, NULL, 't'},
  {"alsa-device", 1, NULL, 'd'},
  {"tone-length", 1, NULL, 'l'},
  {"frequency", 1, NULL, 'h'},
  {"format", 1, NULL, 'f'},
  {"sample-rate", 1, NULL, 'r'},
  {"start-volume", 1, NULL, 's'},
  {"end-volume", 1, NULL, 'e'},
  {"channels", 1, NULL, 'c'},
  {"active-channels", 1, NULL, 'a'},
};

TestConfig::TestType ParseTestType(const char* option) {
  if (strcmp(option, "scale") == 0) {
    return TestConfig::kASharpMinorScale;
  } else if (strcmp(option, "tone") == 0) {
    return TestConfig::kSingleTone;
  }
  return TestConfig::kInvalid;
}

void ParseActiveChannels(char* arg, std::set<int>* channel_list) {
  char* tok = strtok(arg, ",");
  do {
    channel_list->insert(atoi(tok));
  } while ((tok = strtok(NULL, ",")) != NULL);
}

SampleFormat ParseFormat(const char* arg) {
  if (strcmp(arg, "u8") == 0) {
    return SampleFormat(SampleFormat::kPcmU8);
  } else if (strcmp(arg, "s16") == 0) {
    return SampleFormat(SampleFormat::kPcmS16);
  } else if (strcmp(arg, "s24") == 0) {
    return SampleFormat(SampleFormat::kPcmS24);
  } else if (strcmp(arg, "s32") == 0) {
    return SampleFormat(SampleFormat::kPcmS32);
  } else {
    return SampleFormat(SampleFormat::kPcmInvalid);
  }
}

bool ParseOptions(int argc, char* argv[], TestConfig* config) {
  int opt = 0;
  int optindex = -1;
  while ((opt = getopt_long(argc, argv, "t:d:l:f:h:r:s:e:c:a:",
                            long_options,
                            &optindex)) != -1) {
    switch (opt) {
      case 't':
        config->type = ParseTestType(optarg);
        break;

      case 'd':
        config->alsa_device = std::string(optarg);
        break;

      case 'l':
        config->tone_length_sec = atof(optarg);
        break;

      case 'f':
        config->format = ParseFormat(optarg);
        break;

      case 'h':
        config->frequency = atof(optarg);
        break;

      case 'r':
        config->sample_rate = atoi(optarg);
        break;

      case 's':
        config->start_volume = atof(optarg);
        break;

      case 'e':
        config->end_volume = atof(optarg);
        break;

      case 'c':
        config->channels = atoi(optarg);
        break;

      case 'a':
        ParseActiveChannels(optarg, &config->active_channels);
        break;

      default:
        assert(false);
    };
  }

  if (config->type == TestConfig::kInvalid) {
    fprintf(stderr, "Test type must be \"scale\" or \"tone\"\n");
    return false;
  }

  // Avoid overly short tones.
  if (config->tone_length_sec < 0.01) {
    fprintf(stderr, "Tone length too short. Must be 0.01s or greater.\n");
    return false;
  }

  // Normalize the active channel set to explicitly list all channels.
  if (config->active_channels.empty()) {
    for (int i = 0; i < config->channels; ++i) {
      config->active_channels.insert(i);
    }
  }

  return true;
}

void PrintUsage(FILE* out, const char* name) {
  TestConfig default_config;

  fprintf(out, "Usage: %s [options]\n", name);
  fprintf(out, "\t-t, --test-type: \"scale\" or \"tone\"\n");
  fprintf(out, "\t-d, --alsa-device: "
               "Name of alsa device to use (def %s).\n",
               default_config.alsa_device.c_str());
  fprintf(out,
          "\t-l, --tone-length: "
          "Decimal value of tone length in secs (def %0.2lf).\n",
          default_config.tone_length_sec);
  fprintf(out,
          "\t-h, --frequency: "
          "Tone frequency in HZ (def %0.2lf). Used if -T tone.\n",
          default_config.frequency);
  fprintf(out,
          "\t-f, --format: "
          "Sample format to use when talking to PA (def %s).\n",
          default_config.format.to_string());
  fprintf(out,
          "\t-r, --sample-rate: "
          "Sample rate of generated wave in HZ (def %d).\n",
          default_config.sample_rate);
  fprintf(out,
          "\t-s, --start-volume: "
          "Decimal value of start volume (def %0.2lf).\n",
          default_config.start_volume);
  fprintf(out,
          "\t-e, --end-volume: "
          "Decimal value of end volume (def %0.2lf).\n",
          default_config.end_volume);
  fprintf(out,
          "\t-c, --channels: "
          "The number of channels (def %d).\n",
          default_config.channels);
  fprintf(out,
          "\t-a, --active-channels: "
          "Comma-separated list of channels to play on. (def all channels)\n");
  fprintf(out, "\nThe volume of the sample will be a linear ramp over the "
          "duration of playback. The tone length, in scale mode, is the "
          "length of each individual tone in the scale.\n\n");
}

void PrintConfig(FILE* out, const TestConfig& config) {
  fprintf(out, "Config Values:\n");
  if (config.type == TestConfig::kASharpMinorScale) {
    fprintf(out, "\tType: A#Minor Scale\n");
  } else if (config.type == TestConfig::kSingleTone) {
    fprintf(out, "\tType: Single Tone\n");
    fprintf(out, "\tFrequency: %0.2lf\n", config.frequency);
  }

  fprintf(out, "\tAlsa Device: %s\n", config.alsa_device.c_str());
  fprintf(out, "\tFormat: %s\n", config.format.to_string());
  fprintf(out, "\tTone Length (sec): %0.2lf\n", config.tone_length_sec);
  fprintf(out, "\tSample Rate (HZ): %d\n", config.sample_rate);
  fprintf(out, "\tStart Volume (0-1.0): %0.2lf\n", config.start_volume);
  fprintf(out, "\tEnd Volume (0-1.0): %0.2lf\n", config.end_volume);
  fprintf(out, "\tChannels: %d\n", config.channels);

  fprintf(out, "\tActive Channels: ");
  for (std::set<int>::const_iterator it = config.active_channels.begin();
       it != config.active_channels.end();
       ++it) {
    fprintf(out, "%d ", *it);
  }
  fprintf(out, "\n");
}

int main(int argc, char* argv[]) {
  TestConfig config;

  if (!ParseOptions(argc, argv, &config)) {
    fprintf(stderr, "\n");  // Newline before usage.
    PrintUsage(stderr, argv[0]);
    return 1;
  }

  PrintConfig(stdout, config);

  AlsaPlaybackClient client(config.alsa_device);
  if (!client.Init(config.sample_rate,
                   config.format,
                   config.channels,
                   &config.active_channels)) {
    fprintf(stderr, "Unable to initialize Alsa: %d\n",
            client.last_error());
    return 1;
  }

  if (config.type == TestConfig::kASharpMinorScale) {
    ASharpMinorGenerator scale_generator(config.sample_rate,
                                         config.tone_length_sec);
    scale_generator.SetVolumes(config.start_volume, config.end_volume);
    client.SetPlayObj(&scale_generator);
    client.PlayTones();
  } else {
    MultiToneGenerator tone_generator(config.sample_rate,
                                       config.tone_length_sec);
    tone_generator.SetVolumes(config.start_volume, config.end_volume);
    tone_generator.Reset(config.frequency);
    client.SetPlayObj(&tone_generator);
    client.PlayTones();
  }

  return 0;
}
