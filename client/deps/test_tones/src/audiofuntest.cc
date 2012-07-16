// Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <getopt.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>

#include <set>
#include <string>

#include <fftw3.h>
#include <alsa/asoundlib.h>

#include "common.h"
#include "alsa_client.h"
#include "tone_generators.h"

/*
 * The number of upper and lower frequency
 * bins around the center frequncy for matched filter
 */
const int lo_bandwidth = 3;
const int hi_bandwidth = 3;

using autotest_client::audio::AlsaPlaybackClient;
using autotest_client::audio::AlsaCaptureClient;
using autotest_client::audio::SampleFormat;
using autotest_client::audio::CircularBuffer;
using autotest_client::audio::MultiToneGenerator;
using autotest_client::audio::AudioFunTestConfig;
using std::vector;

#ifndef max
template <typename T>
T max(T a, T b) { return a > b ? a : b; }
#endif

#ifndef min
template <typename T>
T min(T a, T b) { return a < b ? a : b; }
#endif

static struct option long_options[] = {
  {"playback-device", 1, NULL, 'o'},
  {"capture-device", 1, NULL, 'i'},
  {"tone-length", 1, NULL, 'l'},
  {"format", 1, NULL, 'f'},
  {"sample-rate", 1, NULL, 'r'},
  {"start-volume", 1, NULL, 's'},
  {"end-volume", 1, NULL, 'e'},
  {"channels", 1, NULL, 'c'},
  {"active-channels", 1, NULL, 'a'},
  {"fftsize", 1, NULL, 'n'},
  {"help", 0, NULL, 'h'},
  {"verbose", 0, NULL, 'v'}
};

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

bool ParseOptions(int argc, char* argv[], AudioFunTestConfig* config) {
  int opt = 0;
  int optindex = -1;
  while ((opt = getopt_long(argc, argv, "o:i:l:f:r:s:e:c:a:n:vh",
                            long_options,
                            &optindex)) != -1) {
    switch (opt) {
      case 'o':
        config->playback_alsa_device = std::string(optarg);
        break;

      case 'i':
        config->capture_alsa_device = std::string(optarg);
        break;

      case 'l':
        config->tone_length_sec = atof(optarg);
        break;

      case 'f':
        config->format = ParseFormat(optarg);
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

      case 'n':
        config->fftsize = atoi(optarg);
        break;

      case 'v':
        config->verbose = true;
        break;

      case 'h':
        return false;

      default:
        assert(false);
    };
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
  AudioFunTestConfig default_config;

  fprintf(out, "Usage: %s [options]\n", name);
  fprintf(out,
          "\t-i, --capture-device: "
          "Name of alsa device to use (def %s).\n",
          default_config.capture_alsa_device.c_str());
  fprintf(out,
          "\t-o, --playback-device: "
          "Name of alsa device to use (def %s).\n",
          default_config.playback_alsa_device.c_str());
  fprintf(out,
          "\t-l, --tone-length: "
          "Decimal value of tone length in secs (def %0.2lf).\n",
          default_config.tone_length_sec);
  fprintf(out,
          "\t-f, --format: "
          "Sample format {u8, s16, s24, s32} to use "
          "when talking to PA (def %s).\n",
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
          "\t-n, --fftsize: "
          "Longer fftsize has more carriers but longer latency. (def 1024)\n");
  fprintf(out,
          "\t-a, --active-channels: "
          "Comma-separated list of channels to play on. (def all channels)\n");
  fprintf(out,
          "\t-v, --verbose: "
          "Show debugging information.\n");
  fprintf(out,
          "\t-h, --help: "
          "Show this page.\n");
}

void PrintConfig(FILE* out, const AudioFunTestConfig& config) {
  fprintf(out, "Config Values:\n");

  fprintf(out, "\tCapture Alsa Device: %s\n",
          config.capture_alsa_device.c_str());
  fprintf(out, "\tPlayback Alsa Device: %s\n",
          config.playback_alsa_device.c_str());
  fprintf(out, "\tFormat: %s\n", config.format.to_string());
  fprintf(out, "\tTone Length (sec): %0.2lf\n", config.tone_length_sec);
  fprintf(out, "\tSample Rate (HZ): %d\n", config.sample_rate);
  fprintf(out, "\tStart Volume (0-1.0): %0.2lf\n", config.start_volume);
  fprintf(out, "\tEnd Volume (0-1.0): %0.2lf\n", config.end_volume);
  fprintf(out, "\tChannels: %d\n", config.channels);
  fprintf(out, "\tFFTsize: %d\n", config.fftsize);

  fprintf(out, "\tActive Channels: ");
  for (std::set<int>::const_iterator it = config.active_channels.begin();
       it != config.active_channels.end();
       ++it) {
    fprintf(out, "%d ", *it);
  }
  fprintf(out, "\n");
}

void *PlayToneThreadEntry(void *arg) {
  AlsaPlaybackClient *client = static_cast<AlsaPlaybackClient *>(arg);
  client->PlayTones();
  return 0;
}

void *CaptureThreadEntry(void *arg) {
  AlsaCaptureClient *client = static_cast<AlsaCaptureClient *>(arg);
  client->Capture();
  return 0;
}

struct Carrier {

  void InitMatchedFilter(int low, int hi, double *data) {
    double mean = 0.0;
    double std = 0.0;
    lo_bin = low;
    hi_bin = hi;
    matched_filter.clear();
    for (int b = low; b <= hi; ++b) {
      matched_filter.push_back(data[b]);
      mean += data[b];
      std += data[b] * data[b];
    }
    mean /= matched_filter.size();
    std /= matched_filter.size();
    std -= mean * mean;
    std = sqrt(std);
    for (unsigned i = 0; i < matched_filter.size(); ++i) {
      matched_filter[i] -= mean;
      matched_filter[i] /= std;
    }
  }

  double MatchedFilterConfidence(double *data) {
    double confidence = 0.0;
    double mean = 0.0;
    double std = 0.0;
    double power_ratio = 0.0;
    for (unsigned i = 0; i < matched_filter.size(); ++i) {
      double sample = data[lo_bin + i];
      confidence += sample * matched_filter[i];
      mean += sample;
      std += sample * sample;
    }
    power_ratio = data[center_bin] / mean;
    mean /= matched_filter.size();
    std = sqrt(std / matched_filter.size() - mean * mean);
    confidence /= std * matched_filter.size();
    return power_ratio * confidence;
  }

  int center_bin;
  int lo_bin;
  int hi_bin;
  vector<double> matched_filter;

};

struct LoopParam {
  LoopParam(const AlsaCaptureClient& capture_client,
            const double low_cutoff = 1600.0,
            const double hi_cutoff  = 10000.0) {
    num_frames = NumFrames(*capture_client.Buffer(), capture_client.Format(),
                           capture_client.NumChannel());
    num_freq   = num_frames / 2 + 1;
    num_bin    = num_frames / 4;
    freq_resol = 2.0 * capture_client.SampRate() / num_frames;
    bin_start  = ceil(low_cutoff/ freq_resol);
    bin_end    = ceil(hi_cutoff / freq_resol);
    if (bin_end > num_bin) bin_end = num_bin;
    num_used_bin  = bin_end - bin_start;
    carriers.resize(num_used_bin / 2);
    for (int i = 0; i < num_used_bin / 2; ++i) {
      carriers[i].center_bin = bin_start + 2 * i;
    }
    target_carrier = 0;
    hwparams = capture_client.get_hw_params();
  }
  bool SetTargetCarrier(int c) {
    if (c < 0 ||
        static_cast<unsigned>(c) >= carriers.size()) {
      return false;
    } else {
      target_carrier = c;
      frequencies.resize(1);
      frequencies[0] = carriers[target_carrier].center_bin * freq_resol;
      return true;
    }
  }
  double TargetCarrierConfidence(double *data) {
    return carriers[target_carrier].MatchedFilterConfidence(data);
  }
  int TargetCarrierCenterBin() {
    return carriers[target_carrier].center_bin;
  }
  void Print(FILE* fp) {
    snd_output_t *log;
    fprintf(fp, "LoopParam::Print()\n");
    fprintf(fp, "  num_frames = %d\n", num_frames);
    fprintf(fp, "  num_freq   = %d\n", num_freq);
    fprintf(fp, "  num_bin    = %d\n", num_bin);
    fprintf(fp, "  freq_resol = %f\n", freq_resol);
    fprintf(fp, "  bin_start  = %d\n", bin_start);
    fprintf(fp, "  bin_end    = %d\n", bin_end);
    fprintf(fp, "  num_used_bin  = %d\n", num_used_bin);
    fprintf(fp, "  targte_carrier = %d\n", target_carrier);
    fprintf(fp, "  carriers   = {\n");


    for (unsigned int i = 0; i < carriers.size(); ++i) {
      fprintf(fp, "    %d: @%d(%.f) (%d, %d): {",
              i, carriers[i].center_bin, carriers[i].center_bin * freq_resol,
              carriers[i].lo_bin, carriers[i].hi_bin);
      for (unsigned int j = 0; j < carriers[i].matched_filter.size(); ++j) {
        fprintf(fp, " %d:%.3f",
                carriers[i].lo_bin + j,
                carriers[i].matched_filter[j]);
      }
      fprintf(fp, "}\n");
    }
    fprintf(fp, "  }\n");

    fprintf(fp, "hw_params =\n");
    snd_output_stdio_attach(&log, fp, 0);
    snd_pcm_hw_params_dump(hwparams, log);
  }
  int num_frames;
  int num_freq;
  int num_bin;
  double freq_resol;
  int bin_start;
  int bin_end;
  int num_used_bin;
  vector<double> frequencies;
  vector<struct Carrier> carriers;
  int target_carrier;
  snd_pcm_hw_params_t *hwparams;
};

static double sqmag(double x[2]) {
  return x[0] * x[0] + x[1] * x[1];
}

/*
 * Estimate matched filter by giving 1 in the center
 * frequency and 0 otherwise. Then substract mean and
 * normalize variance, so the frequency response in the
 * filter has unit length (if viewed as a vector)
 */
void EstimateFilter(struct LoopParam* parm) {

  vector<struct Carrier>& carriers = parm->carriers;

  /* Create estimated filter for each carrier */
  double *double_cell = new double[parm->num_bin];
  for (int b = 0; b < parm->num_bin; ++b) {
    double_cell[b] = 0.0;
  }
  for (unsigned c = 0; c < carriers.size(); ++c) {
    int low = max(carriers[c].center_bin - lo_bandwidth, 0);
    int hi  = min(carriers[c].center_bin + hi_bandwidth, parm->num_bin - 1);
    double_cell[carriers[c].center_bin] = 1.0;
    carriers[c].InitMatchedFilter(low, hi, double_cell);
    double_cell[carriers[c].center_bin] = 0.0;
  }
  delete [] double_cell;
}

/*
 * Meausre matched filter by playing tone and capturing the
 * response in frequency domain. Only apply it in very silent
 * evironment or in the presence of static noise.
 */
void MeasureFilter(struct LoopParam* parm,
                   AlsaPlaybackClient* play_cli,
                   AlsaCaptureClient* cap_cli,
                   MultiToneGenerator* gen) {

  vector<struct Carrier>& carriers = parm->carriers;

  /* Spectrum analyzer */
  CircularBuffer<double> double_buffer(carriers.size(), parm->num_frames);
  fftw_plan plan;
  fftw_complex *spectrum = static_cast<double(*)[2]>(
      fftw_malloc(sizeof(fftw_complex) * (parm->num_freq)));

  /* Start playback and capture threads */
  pthread_t capture_thread;
  pthread_create(&capture_thread, NULL, CaptureThreadEntry, cap_cli);
  pthread_t playback_thread;
  pthread_create(&playback_thread, NULL, PlayToneThreadEntry, play_cli);

  for (unsigned c = 0; c < carriers.size(); ++c) {
    parm->frequencies.clear();
    gen->Reset(parm->frequencies);
    parm->SetTargetCarrier(c);
    gen->Reset(parm->frequencies);
    usleep(300000);  // Wait 300ms for playback to capture delay

    char *sample_cell = cap_cli->Buffer()->LockCellToRead();
    double *double_cell = double_buffer.LockCellToWrite();

    // save frequency response in double_buffer
    SampleCellToDoubleCell(static_cast<void *>(sample_cell),
                           double_cell,
                           parm->num_frames,
                           cap_cli->Format(),
                           cap_cli->NumChannel());

    cap_cli->Buffer()->UnlockCellToRead();

    plan = fftw_plan_dft_r2c_1d(parm->num_frames, double_cell, spectrum,
                                FFTW_ESTIMATE);
    fftw_execute(plan);

    for (int b = 0; b < parm->num_bin; ++b) {
      double_cell[b] = sqmag(spectrum[b]) / parm->num_frames;
    }

    double_buffer.UnlockCellToWrite();

  }
  play_cli->set_state(AlsaPlaybackClient::kTerminated);
  cap_cli->set_state(AlsaCaptureClient::kTerminated);
  void *status;
  pthread_join(playback_thread, &status);
  pthread_join(capture_thread, &status);

  /* Create matched filter for each carrier */
  for (unsigned c = 0; c < carriers.size(); ++c) {
    double *double_cell = double_buffer.LockCellToWrite();
    int low = max(carriers[c].center_bin - lo_bandwidth, 0);
    int hi  = min(carriers[c].center_bin + hi_bandwidth, parm->num_bin - 1);
    carriers[c].InitMatchedFilter(low, hi, double_cell);
    double_buffer.UnlockCellToWrite();
  }
  parm->Print(stderr);

}


int LoopControl(AudioFunTestConfig& config) {
  srand(time(NULL) + getpid());
  /* AlsaCaptureClient */
  AlsaCaptureClient capture_client(config.capture_alsa_device);
  if (!capture_client.Init(config.sample_rate,
                           config.format,
                           config.channels,
                           2,
                           config.fftsize)) {
    fprintf(stderr, "Unable to initialize AlsaCaputreClient: %d\n",
            capture_client.last_error());
    return 2;
  }
  if (config.verbose) capture_client.Print(stderr);


  /* AlsaPlaybackClient */
  AlsaPlaybackClient playback_client(config.playback_alsa_device);
  if (!playback_client.Init(config.sample_rate,
                            config.format,
                            config.channels,
                            &config.active_channels,
                            config.fftsize)) {
    fprintf(stderr, "Unable to initialize AlsaPlaybackClient: %d\n",
            playback_client.last_error());
    return 3;
  }
  if (config.verbose) playback_client.Print(stderr);

  /* Tone generator */
  MultiToneGenerator tone_generator(config.sample_rate,
                                    config.tone_length_sec);
  tone_generator.SetVolumes(config.start_volume, config.end_volume);
  playback_client.SetPlayObj(&tone_generator);

  /* Loop parameter */
  struct LoopParam loop_parm(capture_client);

  /*
  MeasureFilter(&loop_parm, &playback_client, &capture_client,
                &tone_generator);
                */
  EstimateFilter(&loop_parm);
  if (config.verbose) loop_parm.Print(stderr);

  /* Spectrum analyzer */
  CircularBuffer<double> double_buffer(1, loop_parm.num_frames);
  fftw_plan plan;
  fftw_complex *spectrum = static_cast<double(*)[2]>(
      fftw_malloc(sizeof(fftw_complex) * (loop_parm.num_freq)));

  /* Start capture and playback threads */
  playback_client.set_state(AlsaPlaybackClient::kReady);
  capture_client.set_state(AlsaCaptureClient::kReady);
  pthread_t capture_thread;
  pthread_create(&capture_thread, NULL, CaptureThreadEntry, &capture_client);
  pthread_t playback_thread;
  pthread_create(&playback_thread, NULL, PlayToneThreadEntry, &playback_client);

  loop_parm.SetTargetCarrier(rand() % loop_parm.carriers.size());
  tone_generator.Reset(loop_parm.frequencies);

  /* Start feedback */
  int success = 0, fail = 0;
  int delay = 0;
  double accum_confidence = 0.0;
  /* Analyze cell by cell */
  while(playback_client.state() ==
        autotest_client::audio::AlsaPlaybackClient::kReady) {

    char *sample_cell = capture_client.Buffer()->LockCellToRead();
    double *double_cell = double_buffer.LockCellToWrite();

    SampleCellToDoubleCell(static_cast<void *>(sample_cell),
                           double_cell,
                           loop_parm.num_frames,
                           capture_client.Format(),
                           capture_client.NumChannel());

    capture_client.Buffer()->UnlockCellToRead();

    plan = fftw_plan_dft_r2c_1d(loop_parm.num_frames, double_cell, spectrum,
                                FFTW_ESTIMATE);
    fftw_execute(plan);
    // Calculate spectrum energy
    for (int i = 0; i < loop_parm.num_bin; ++i) {
      double_cell[i] = sqmag(spectrum[i]) / loop_parm.num_frames;
    }
    double confidence = loop_parm.TargetCarrierConfidence(double_cell);
    if (confidence > 0.0) accum_confidence += confidence;
    double_buffer.UnlockCellToWrite();


    ++delay;
    if (accum_confidence >= 3.0) { // success
      ++success;
      fprintf(stderr, "O");
    } else if (delay < 15) { // accum_confidence < 3.0, delaying
      continue;
    } else { // accum_confidence < 3.0 and time out
      ++fail;
      fprintf(stderr, "X");
    }

    fprintf(stderr, ": carrier = %2d, delay = %2d, "
            "success = %3d, fail = %3d, rate = %.1f\n",
            loop_parm.target_carrier, delay, success, fail,
            100.0 * success / (success + fail));
    /* Either success or fail */
    delay = 0;
    accum_confidence = 0.0;
    int new_target_carrier;
    do {
      new_target_carrier = rand() % loop_parm.carriers.size();
    } while (new_target_carrier == loop_parm.target_carrier);
    loop_parm.SetTargetCarrier(new_target_carrier);
    tone_generator.Reset(loop_parm.frequencies);
  }
  playback_client.set_state(AlsaPlaybackClient::kTerminated);
  capture_client.set_state(AlsaCaptureClient::kTerminated);
  /* Play recorded sounds */

  void *status;
  pthread_join(playback_thread, &status);
  pthread_join(capture_thread, &status);

  return 0;

}

int main(int argc, char* argv[]) {
  AudioFunTestConfig config;

  if (!ParseOptions(argc, argv, &config)) {
    fprintf(stderr, "\n");
    PrintUsage(stderr, argv[0]);
    return 1;
  }

  PrintConfig(stderr, config);

  LoopControl(config);

  return 0;
}
