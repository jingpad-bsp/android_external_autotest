// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef AUTOTEST_CLIENT_SITE_TESTS_AUDIO_PULSE_CLIENT_H_
#define AUTOTEST_CLIENT_SITE_TESTS_AUDIO_PULSE_CLIENT_H_

#include <set>
#include <string>

#include "common.h"

// PulseAudio API forward declares.
extern "C" {
struct pa_context;
struct pa_mainloop;
struct pa_mainloop_api;
struct pa_stream;
}  // extern "C"

namespace autotest_client {
namespace audio {

class FrameGenerator;

class PulseAudioClient {
 public:
  enum State {
    kCreated,
    kFailed,
    kTerminated,
    kReady,
  };

  explicit PulseAudioClient(const std::string& client_name);
  virtual ~PulseAudioClient();

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
  // Used by PulseAudio mainloop to nofity this class of changes in the
  // PulseAudio connection.
  static void StateChangeCallback(pa_context* context, void* userdata);

  // Used by PulseAudio to request more audio samples.
  static void WriteSampleCallback(pa_stream* p, size_t nbytes, void* userdata);

  // Callback signaling completion of flushing of a stream.
  static void StreamFlushed(pa_stream* s, int success, void* userdata);

  // The name registered with PulseAudio.
  std::string client_name_;

  // The PulseAudio mainloop instance to use for managing PA tasks.
  pa_mainloop* mainloop_;

  // The connection context to PulseAudio.
  pa_context* context_;

  // Our abstracted version of the connection state. 
  State state_;

  // The last error reported by PulseAudio. Useful for debugging.
  int last_error_;
};

}  // namespace audio
}  // namespace autotest_client

#endif  // AUTOTEST_CLIENT_SITE_TESTS_AUDIO_PULSE_CLIENT_H_
