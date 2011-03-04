// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef AUTOTEST_CLIENT_SITE_TESTS_AUDIO_ALSA_CLIENT_H_
#define AUTOTEST_CLIENT_SITE_TESTS_AUDIO_ALSA_CLIENT_H_

#include <set>
#include <string>

#include "common.h"

// Alsa API forward declares.
struct _snd_pcm;

namespace autotest_client {
namespace audio {

class FrameGenerator;

class AlsaAudioClient {
 public:
  enum State {
    kCreated,
    kFailed,
    kTerminated,
    kReady,
  };

  AlsaAudioClient();
  virtual ~AlsaAudioClient();

  virtual bool Init();
  void PlayTones(int sample_rate,
                 SampleFormat format,
                 int channels,
                 const std::set<int>& active_channels,
                 FrameGenerator* generator);

  // Trivial accessors/mutators.
  virtual void set_state(State state) { state_ = state; }
  virtual State state() const { return state_; }
  virtual int last_error() const { return last_error_; }

 private:

  // Callback signaling completion of flushing of a stream.
  static void StreamFlushed(int success, void* userdata);

    _snd_pcm * pcm_out_handle_;
  unsigned int latency_ms_;

  // Our abstracted version of the connection state.
  State state_;

  // The last error reported by Alsa. Useful for debugging.
  int last_error_;
};

}  // namespace audio
}  // namespace autotest_client

#endif  // AUTOTEST_CLIENT_SITE_TESTS_AUDIO_ALSA_CLIENT_H_
