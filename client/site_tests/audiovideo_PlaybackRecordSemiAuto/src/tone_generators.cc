// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "tone_generators.h"

#include <assert.h>

#include <algorithm>
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

SingleToneGenerator::SingleToneGenerator(int sample_rate, double length_sec)
    : frames_generated_(0),
      frames_wanted_(length_sec * sample_rate),
      fade_frames_(0),  // Calculated below.
      frequency_(0.0f),
      sample_rate_(sample_rate) {

  // Use a 5ms fade.
  const double kFadeTimeSec = 0.005;

  // Only fade if the fade won't take more than 1/2 the tone.
  if (length_sec > (kFadeTimeSec * 4)) {
    fade_frames_ = kFadeTimeSec * sample_rate;
  }
}

SingleToneGenerator::~SingleToneGenerator() {
}

void SingleToneGenerator::Reset(double frequency) {
  frequency_ = frequency;
  frames_generated_ = 0;
}

void SingleToneGenerator::GetFrames(SampleFormat format,
                                    int channels,
                                    const std::set<int>& active_channels,
                                    void* data,
                                    size_t* buf_size) {
  const size_t kBytesPerFrame = channels * format.bytes();
  void* cur = data;
  size_t frames = *buf_size / kBytesPerFrame;
  size_t frames_written;
  for (frames_written = 0; frames_written < frames; ++frames_written) {
    if (!HasMoreFrames()) {
      break;
    }

    double frame_magnitude = 
        GetFadeMagnitude() *
        tone_wave_.Next(sample_rate_, frequency_);
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

  *buf_size = frames_written * kBytesPerFrame;
}

bool SingleToneGenerator::HasMoreFrames() const {
  return frames_generated_ < frames_wanted_;
}

double SingleToneGenerator::GetFadeMagnitude() const {
  // Fade in.
  int frames_left = frames_wanted_ - frames_generated_;
  if (frames_generated_ < fade_frames_) {
    return sin(kHalfPi * frames_generated_ / fade_frames_);
  } else if (frames_left < fade_frames_) {
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
  tone_generator_.Reset(kNoteFrequencies[cur_note_]);
}

ASharpMinorGenerator::~ASharpMinorGenerator() {
}

void ASharpMinorGenerator::Reset() {
  cur_note_ = 0;
  tone_generator_.Reset(kNoteFrequencies[cur_note_]);
}

void ASharpMinorGenerator::GetFrames(SampleFormat format,
                                     int channels,
                                     const std::set<int>& active_channels,
                                     void* data,
                                     size_t* buf_size) {
  if (!HasMoreFrames()) {
    *buf_size = 0;
    return;
  }

  // Go to next note if necessary.
  if (!tone_generator_.HasMoreFrames()) {
    tone_generator_.Reset(kNoteFrequencies[++cur_note_]);
  }
  
  tone_generator_.GetFrames(format, channels, active_channels, data, buf_size);
}

bool ASharpMinorGenerator::HasMoreFrames() const {
  return cur_note_ < kNumNotes || tone_generator_.HasMoreFrames();
}

}  // namespace audio
}  // namespace autotest_client
