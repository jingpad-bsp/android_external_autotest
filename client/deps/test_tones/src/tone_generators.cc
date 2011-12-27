// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "tone_generators.h"

#include <assert.h>
#include <cstdio>
#include <limits>

namespace autotest_client {
namespace audio {

namespace {

template <typename T>
void* WriteSample(void* data, double magnitude) {
  // Handle unsigned.
  if (std::numeric_limits<T>::min() == 0) {
    magnitude += 1.0;
    magnitude /= 2.0;
  }

  T* sample_data = reinterpret_cast<T*>(data);
  *sample_data = magnitude * std::numeric_limits<T>::max();
  return sample_data + 1;
}

void* WriteSampleForFormat(void* data, double magnitude, SampleFormat format) {
  if (format.type() == SampleFormat::kPcmU8) {
    return WriteSample<unsigned char>(data, magnitude);

  } else if (format.type() == SampleFormat::kPcmS16) {
    return WriteSample<int16_t>(data, magnitude);

  } else if (format.type() == SampleFormat::kPcmS24) {
    unsigned char* sample_data = reinterpret_cast<unsigned char*>(data);
    int32_t value = magnitude * (1 << 23);  // 1 << 23 24-bit singed max().
    sample_data[0] = value & 0xff;
    sample_data[1] = (value >> 8) & 0xff;
    sample_data[2] = (value >> 16) & 0xff;
    return sample_data + 3;

  } else if (format.type() == SampleFormat::kPcmS32) {
    return WriteSample<int32_t>(data, magnitude);
  }

  // Return NULL, which should crash the caller.
  assert(false);
  return NULL;
}

}  // namespace


MultiToneGenerator::MultiToneGenerator(int sample_rate, double length_sec)
    : frames_generated_(0),
      frames_wanted_(length_sec * sample_rate),
      fade_frames_(0),  // Calculated below.
      sample_rate_(sample_rate),
      cur_vol_(1.0),
      start_vol_(1.0),
      inc_vol_(0.0) {

  // Use a fade of 2.5ms at both the start and end of a tone .
  const double kFadeTimeSec = 0.005;

  // Only fade if the fade won't take more than 1/2 the tone.
  if (length_sec > (kFadeTimeSec * 4)) {
    fade_frames_ = kFadeTimeSec * sample_rate;
  }

  frequencies_.clear();
  pthread_mutex_init(&param_mutex, NULL);
}

MultiToneGenerator::~MultiToneGenerator() {
  pthread_mutex_destroy(&param_mutex);
}

void MultiToneGenerator::SetVolumes(double start_vol, double end_vol) {
  pthread_mutex_lock(&param_mutex);
  cur_vol_ = start_vol_ = start_vol;
  inc_vol_ = (end_vol - start_vol) / frames_wanted_;
  pthread_mutex_unlock(&param_mutex);
}

void MultiToneGenerator::Reset(const std::vector<double> &frequencies,
                               bool reset_timer) {
  pthread_mutex_lock(&param_mutex);
  frequencies_ = frequencies;
  if (reset_timer) {
    frames_generated_ = 0;
    cur_vol_ = start_vol_;
  }
  pthread_mutex_unlock(&param_mutex);
}

void MultiToneGenerator::Reset(const double *frequency, unsigned int ntones,
                               bool reset_timer) {
  pthread_mutex_lock(&param_mutex);
  frequencies_.resize(ntones);
  for (unsigned int i = 0; i < ntones; ++i) {
    frequencies_[i] = frequency[i];
  }
  if (reset_timer) {
    frames_generated_ = 0;
    cur_vol_ = start_vol_;
  }
  pthread_mutex_unlock(&param_mutex);
}

void MultiToneGenerator::Reset(double frequency, bool reset_timer) {
  pthread_mutex_lock(&param_mutex);
  frequencies_.resize(1);
  frequencies_[0] = frequency;
  if (reset_timer) {
    frames_generated_ = 0;
    cur_vol_ = start_vol_;
  }
  pthread_mutex_unlock(&param_mutex);
}

size_t MultiToneGenerator::GetFrames(SampleFormat format,
                                   int channels,
                                   const std::set<int>& active_channels,
                                   void* data,
                                   size_t buf_size) {
  const size_t kBytesPerFrame = channels * format.bytes();
  void* cur = data;
  size_t frames = buf_size / kBytesPerFrame;
  size_t frames_written;
  pthread_mutex_lock(&param_mutex);
  tone_wave_.resize(frequencies_.size());
  for (frames_written = 0; frames_written < frames; ++frames_written) {
    if (!HasMoreFrames()) {
      break;
    }

    double frame_magnitude = 0;
    for (unsigned int f = 0; f < frequencies_.size(); ++f) {
      frame_magnitude += tone_wave_[f].Next(sample_rate_, frequencies_[f]);
    }
    frame_magnitude *= GetFadeMagnitude() * cur_vol_;
    if (frequencies_.size() > 1) {
      frame_magnitude /= static_cast<double>(frequencies_.size());
    }
    //printf("%f\n", frame_magnitude);
    cur_vol_ += inc_vol_;
    for (int c = 0; c < channels; ++c) {
      if (active_channels.find(c) != active_channels.end()) {
        cur = WriteSampleForFormat(cur, frame_magnitude, format);
      } else {
        // Silence the non-active channels.
        cur = WriteSampleForFormat(cur, 0.0f, format);
      }
    }

    ++frames_generated_;
  }
  pthread_mutex_unlock(&param_mutex);
  return frames_written * kBytesPerFrame;
}

bool MultiToneGenerator::HasMoreFrames() const {
  return frames_generated_ < frames_wanted_;
}

double MultiToneGenerator::GetFadeMagnitude() const {
  int frames_left = frames_wanted_ - frames_generated_;
  if (frames_generated_ < fade_frames_) { // Fade in.
    return sin(kHalfPi * frames_generated_ / fade_frames_);
  } else if (frames_left < fade_frames_) { // Fade out.
    return sin(kHalfPi * frames_left / fade_frames_);
  } else {
    return 1.0f;
  }
}

// A# minor harmoic scale is: A#, B# (C), C#, D#, E# (F), F#, G## (A).
const double ASharpMinorGenerator::kNoteFrequencies[] = {
  466.16, 523.25, 554.37, 622.25, 698.46, 739.99, 880.00, 932.33,
  932.33, 880.00, 739.99, 698.46, 622.25, 554.37, 523.25, 466.16,
};

ASharpMinorGenerator::ASharpMinorGenerator(int sample_rate,
                                           double tone_length_sec)
    : tone_generator_(sample_rate, tone_length_sec),
      cur_note_(0) {
  tone_generator_.Reset(kNoteFrequencies[cur_note_], true);
}

ASharpMinorGenerator::~ASharpMinorGenerator() {
}

void ASharpMinorGenerator::SetVolumes(double start_vol, double end_vol) {
  tone_generator_.SetVolumes(start_vol, end_vol);
}

void ASharpMinorGenerator::Reset() {
  cur_note_ = 0;
  tone_generator_.Reset(kNoteFrequencies[cur_note_], true);
}

size_t ASharpMinorGenerator::GetFrames(SampleFormat format,
                                     int channels,
                                     const std::set<int>& active_channels,
                                     void* data,
                                     size_t buf_size) {
  if (!HasMoreFrames()) {
    return 0;
  }

  // Go to next note if necessary.
  if (!tone_generator_.HasMoreFrames()) {
    tone_generator_.Reset(kNoteFrequencies[++cur_note_], true);
  }

  return tone_generator_.GetFrames(format,
                                   channels,
                                   active_channels,
                                   data,
                                   buf_size);
}

bool ASharpMinorGenerator::HasMoreFrames() const {
  return cur_note_ < kNumNotes - 1 || tone_generator_.HasMoreFrames();
}

}  // namespace audio
}  // namespace autotest_client
