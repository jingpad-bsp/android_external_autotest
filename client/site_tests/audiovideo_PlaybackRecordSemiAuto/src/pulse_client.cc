// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "pulse_client.h"

#include <set>

#include <pulse/pulseaudio.h>

#include "tone_generators.h"

namespace autotest_client {
namespace audio {

struct WriteSampleCallbackData {
  int channels;
  SampleFormat format;
  std::set<int> active_channels;
  FrameGenerator* generator;
};

// Translates our SampleFormat type into a PulseAudio friendly format.
// This is a file-local function to avoid leaking the pa_sample_format type
// into the header.
static pa_sample_format_t SampleFormatToPulseFormat(SampleFormat format) {
  switch (format.type()) {
    case SampleFormat::kPcmU8:
      return PA_SAMPLE_U8;

    case SampleFormat::kPcmS16:
      return PA_SAMPLE_S16LE;

    case SampleFormat::kPcmS24:
      return PA_SAMPLE_S24LE;

    case SampleFormat::kPcmS32:
      return PA_SAMPLE_S32LE;

    default:
      return PA_SAMPLE_INVALID;
  };
}

PulseAudioClient::PulseAudioClient(const std::string& client_name)
    : client_name_(client_name),
      mainloop_(NULL),
      context_(NULL),
      state_(kCreated),
      last_error_(0) {
}

PulseAudioClient::~PulseAudioClient() {
  if (context_) {
    pa_context_unref(context_);
    context_ = NULL;
  }
  if (mainloop_) {
    pa_mainloop_free(mainloop_);
  }
}

bool PulseAudioClient::Init() {
  mainloop_ = pa_mainloop_new();
  context_ = pa_context_new(pa_mainloop_get_api(mainloop_),
                            client_name_.c_str());

  pa_context_set_state_callback(context_,
                                &PulseAudioClient::StateChangeCallback,
                                this);
  last_error_ = pa_context_connect(context_, NULL, PA_CONTEXT_NOFLAGS, NULL);
  if (last_error_ != 0) {
    return false;
  }

  // TODO(ajwong): Put a watchdog timeout.
  while (state() == kCreated) {
    pa_mainloop_iterate(mainloop_, 1, &last_error_);
  }

  return state() == kReady;
}

void PulseAudioClient::PlayTones(int sample_rate,
                                 SampleFormat format,
                                 int channels,
                                 const std::set<int>& active_channels,
                                 FrameGenerator* generator) {
  pa_stream* stream = NULL;
  pa_proplist* proplist = NULL;
  pa_sample_spec ss;
  pa_channel_map channel_map;

  // Configure sample and channel.
  ss.format = SampleFormatToPulseFormat(format);
  ss.rate = sample_rate;
  ss.channels = channels;
  pa_channel_map_init_auto(&channel_map, channels, PA_CHANNEL_MAP_DEFAULT);

  // Initialize write callback data.
  WriteSampleCallbackData cb_data;
  cb_data.channels = channels;
  cb_data.format = format;
  cb_data.active_channels = active_channels;
  cb_data.generator = generator;

  // Setup stream.
  proplist = pa_proplist_new();
  stream = pa_stream_new_with_proplist(
      context_, "play_tones", &ss, &channel_map, proplist);
  pa_stream_set_write_callback(stream,
                               &PulseAudioClient::WriteSampleCallback,
                               &cb_data);
  pa_stream_connect_playback(stream, NULL, NULL, PA_STREAM_NOFLAGS, NULL, NULL);

  // Run main loop until we are out of frames to generate.
  // Then drain the stream.
  while (generator->HasMoreFrames()) {
    pa_mainloop_iterate(mainloop_, 1, &last_error_);
  }
  pa_stream_drain(stream, &PulseAudioClient::StreamFlushed, mainloop_);
  pa_mainloop_run(mainloop_, &last_error_);

  // Cleanup.
  pa_stream_disconnect(stream);
  pa_stream_unref(stream);
  pa_proplist_free(proplist);
}

void PulseAudioClient::StateChangeCallback(pa_context* context,
                                           void* userdata) {
  PulseAudioClient* client = reinterpret_cast<PulseAudioClient*>(userdata);

  pa_context_state_t state = pa_context_get_state(context);
  switch (state) {
    case PA_CONTEXT_UNCONNECTED:
    case PA_CONTEXT_CONNECTING:
    case PA_CONTEXT_AUTHORIZING:
    case PA_CONTEXT_SETTING_NAME:
    default:
      // TODO(ajwong): Do we care about these states? Figure out the right
      // thing to do.
      break;

    case PA_CONTEXT_FAILED:
      client->set_state(kFailed);
      break;

    case PA_CONTEXT_TERMINATED:
      client->set_state(kTerminated);
      break;

    case PA_CONTEXT_READY:
      client->set_state(kReady);
      break;
  }
}

void PulseAudioClient::WriteSampleCallback(pa_stream* p,
                                           size_t nbytes,
                                           void* userdata) {
  WriteSampleCallbackData* cb_data =
      reinterpret_cast<WriteSampleCallbackData*>(userdata);

  void* data = NULL;
  size_t to_write = nbytes;
  pa_stream_begin_write(p, &data, &to_write);
  cb_data->generator->GetFrames(cb_data->format, cb_data->channels,
                                cb_data->active_channels, data, &to_write);
  pa_stream_write(p, data, to_write, NULL, 0, PA_SEEK_RELATIVE);
}

void PulseAudioClient::StreamFlushed(pa_stream* s, int success,
                                     void* userdata) {
  pa_mainloop* mainloop = reinterpret_cast<pa_mainloop*>(userdata);
  pa_mainloop_quit(mainloop, success);
}

}  // namespace audio
}  // namespace autotest_client
