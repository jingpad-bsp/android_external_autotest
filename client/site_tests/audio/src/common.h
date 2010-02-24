// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef AUTOTEST_CLIENT_SITE_TESTS_AUDIO_COMMON_H_
#define AUTOTEST_CLIENT_SITE_TESTS_AUDIO_COMMON_H_

#include <assert.h>

#include <set>

namespace autotest_client {
namespace audio {

class SampleFormat {
 public:
  enum Type {
    kPcmInvalid,
    kPcmU8,
    kPcmS16,
    kPcmS24,
    kPcmS32,
  };

  SampleFormat()
      : type_(kPcmInvalid) {
  }

  explicit SampleFormat(Type type)
      : type_(type) {
  }

  void set_type(Type type) { type_ = type; }
  Type type() const { return type_; }

  const char* to_string() const {
    switch (type_) {
      case kPcmU8:
        return "u8";
      case kPcmS16:
        return "s16";
      case kPcmS24:
        return "s24";
      case kPcmS32:
        return "s32";
      default:
        assert(false);
    }
  }

  size_t bytes() const {
    switch (type_) {
      case kPcmU8:
        return 1;
      case kPcmS16:
        return 2;
      case kPcmS24:
        return 3;
      case kPcmS32:
        return 4;
      default:
        assert(false);
    }
  }

 private:
  Type type_;
};

// All samples are linear, and little-endian.
struct TestConfig {
  enum TestType {
    kInvalid,
    kASharpMinorScale,
    kSingleTone,
  };

  TestConfig() 
      : type(kInvalid),
        format(SampleFormat::kPcmS16),
        tone_length_sec(0.3f),
        frequency(440.0f),  // Middle-A
        sample_rate(44100),
        start_volume(1.0f),
        end_volume(1.0f),
        channels(2) {
  }

  TestType type;
  SampleFormat format;
  double tone_length_sec;
  double frequency;
  int sample_rate;
  double start_volume;  // TODO(ajwong): Figure out units, and use this value.
  double end_volume;
  int channels;
  std::set<int> active_channels;
};

}  // namespace audio
}  // namespace autotest_client

#endif  // AUTOTEST_CLIENT_SITE_TESTS_AUDIO_COMMON_H_
