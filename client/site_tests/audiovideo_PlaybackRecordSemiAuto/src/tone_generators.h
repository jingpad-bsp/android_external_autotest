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

#include <math.h>
#include <stdlib.h>

#include <set>

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
  virtual void GetFrames(SampleFormat format,
                         int channels,
                         const std::set<int>& active_channels,
                         void* data,
                         size_t* buf_size) = 0;

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

 private:
  double cur_x_;
};

class SingleToneGenerator : public FrameGenerator {
 public:
  SingleToneGenerator(int sample_rate, double length_sec);
  virtual ~SingleToneGenerator();
  virtual void Reset(double frequency);
  virtual void GetFrames(SampleFormat format,
                         int channels,
                         const std::set<int>& active_channels,
                         void* data,
                         size_t* buf_size);
  virtual bool HasMoreFrames() const;

 private:
  SineWaveGenerator tone_wave_;

  double GetFadeMagnitude() const;

  int frames_generated_;
  int frames_wanted_;
  int fade_frames_;
  double frequency_;
  int sample_rate_;
};

class ASharpMinorGenerator : public FrameGenerator {
 public:
  ASharpMinorGenerator(int sample_rate, double tone_length_sec);
  virtual ~ASharpMinorGenerator();

  virtual void Reset();
  virtual void GetFrames(SampleFormat format,
                         int channels,
                         const std::set<int>& active_channels,
                         void* data,
                         size_t* buf_size);
  virtual bool HasMoreFrames() const;

 private:
  static const int kNumNotes = 16;
  static const double kNoteFrequencies[kNumNotes];

  SingleToneGenerator tone_generator_;
  int cur_note_;
};

}  // namespace audio
}  // namespace autotest_client

#endif  // AUTOTEST_CLIENT_SITE_TESTS_AUDIO_TONE_GENERATORS_H_
