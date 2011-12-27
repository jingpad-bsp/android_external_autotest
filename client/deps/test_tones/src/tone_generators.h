// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Various generator classes that generate sound samples for playback. Most
// derive off of FrameGenerator, and generate full frames (one sample for each
// channel) of sound.
//
// SineWaveGenerator -- Generates a single test tone for a given frequency.
// ASharpMinorGenerator -- Generates tones for the A# Harmonic Minor Scale.
//    Why choose A# Harmonic Minor?  Cause I can. (and because double-sharps
//    are cool :) )

#ifndef AUTOTEST_CLIENT_SITE_TESTS_AUDIO_TONE_GENERATORS_H_
#define AUTOTEST_CLIENT_SITE_TESTS_AUDIO_TONE_GENERATORS_H_

#include <cmath>
#include <cstdlib>

#include <set>
#include <vector>

#include "common.h"

namespace autotest_client {
namespace audio {

static const double kPi = 3.14159265358979323846264338327l;
static const double kHalfPi = kPi / 2.0f;

class FrameGenerator {
 public:
  // Fills data with up to |buf_size| bytes with of audio frames.  Only
  // complete frames are written into data (ie., the number of samples written
  // is a  multiple of the number of channels), and |buf_size| is adjusted to
  // reflect the number of bytes written into data.
  //
  // The |format|, and |channels|, parameters affet the size of a frame, and
  // the type of sample written.  The |active_channels| parameter is used to
  // select which channels have samples written into them.  If a channel is
  // not listed in |active_channels|, then it is filled with silence.  This is
  // to allow generating tones on specific channels.
  //
  // The |active_channels| set is 0 indexed.  If you have 2 channels, and you
  // want to play on all of them, make sure |active_channels| contains 0, and
  // 1.
  virtual size_t GetFrames(SampleFormat format,
                         int channels,
                         const std::set<int>& active_channels,
                         void* data,
                         size_t buf_size) = 0;

  // Returns whether or not the FrameGenerator is able to produce more frames.
  // This is used to signal when one should stop calling GetFrames().
  virtual bool HasMoreFrames() const = 0;
};

class SineWaveGenerator {
 public:
  SineWaveGenerator()
      : cur_x_(0.0f) {
  }

  // Generates a sampled sine wave, where the sine wave period is determined
  // by |frequency| and the sine wave sampling rate is determined by
  // |sample_rate| (in HZ).
  //
  // It's probably not advisable to change |sample_rate| from call to call, but
  // the API is simpler.
  double Next(int sample_rate, double frequency) {
    cur_x_ += (kPi * 2 * frequency) / sample_rate;
    return sin(cur_x_);
  }
  void Reset(double cur_x = 0.0) {
    cur_x_ = cur_x;
  }

 private:
  double cur_x_;
};


class MultiToneGenerator : public FrameGenerator {
 public:
  MultiToneGenerator(int sample_rate, double length_sec);
  virtual ~MultiToneGenerator();

  void SetVolumes(double start_vol, double end_vol);
  virtual void Reset(const std::vector<double> &frequencies,
                     bool reset_timer = false);
  virtual void Reset(const double *frequencies, unsigned int ntones,
                     bool reset_timer = false);
  virtual void Reset(double frequency, bool reset_timer = false);
  virtual size_t GetFrames(SampleFormat format,
                         int channels,
                         const std::set<int>& active_channels,
                         void* data,
                         size_t buf_size);
  virtual bool HasMoreFrames() const;

 private:
  std::vector<SineWaveGenerator> tone_wave_;

  double GetFadeMagnitude() const;

  int frames_generated_;
  int frames_wanted_;
  int fade_frames_;
  std::vector<double> frequencies_;
  int sample_rate_;
  double cur_vol_;
  double start_vol_;
  double inc_vol_;
  pthread_mutex_t param_mutex;
};


class ASharpMinorGenerator : public FrameGenerator {
 public:
  ASharpMinorGenerator(int sample_rate, double tone_length_sec);
  virtual ~ASharpMinorGenerator();

  void SetVolumes(double start_vol, double end_vol);
  virtual void Reset();
  virtual size_t GetFrames(SampleFormat format,
                         int channels,
                         const std::set<int>& active_channels,
                         void* data,
                         size_t buf_size);
  virtual bool HasMoreFrames() const;

 private:
  static const int kNumNotes = 16;
  static const double kNoteFrequencies[kNumNotes];

  MultiToneGenerator tone_generator_;
  int cur_note_;
};

}  // namespace audio
}  // namespace autotest_client

#endif  // AUTOTEST_CLIENT_SITE_TESTS_AUDIO_TONE_GENERATORS_H_
