// Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "alsa_client.h"

#include <set>

#include <alsa/asoundlib.h>

#include "tone_generators.h"

namespace autotest_client {
namespace audio {

// Translates our SampleFormat type into a Alsa friendly format.
// This is a file-local function to avoid leaking the pa_sample_format type
// into the header.
static _snd_pcm_format SampleFormatToAlsaFormat(SampleFormat format) {
  switch (format.type()) {
    case SampleFormat::kPcmU8:
      return SND_PCM_FORMAT_U8;

    case SampleFormat::kPcmS16:
      return SND_PCM_FORMAT_S16_LE;

    case SampleFormat::kPcmS24:
      return SND_PCM_FORMAT_S24_LE;

    case SampleFormat::kPcmS32:
      return SND_PCM_FORMAT_S32_LE;

    default:
      return SND_PCM_FORMAT_UNKNOWN;
  };
}

static int SampleFormatToFrameBytes(SampleFormat format, int channels) {
  switch (format.type()) {
    case SampleFormat::kPcmU8:
      return channels;

    case SampleFormat::kPcmS16:
      return channels * 2;

    case SampleFormat::kPcmS24:
      return channels * 4;

    case SampleFormat::kPcmS32:
      return channels * 4;

    default:
      return SND_PCM_FORMAT_UNKNOWN;
  };
}

AlsaAudioClient::AlsaAudioClient()
    : pcm_out_handle_(NULL),
      latency_ms_(kDefaultLatencyMs),
      state_(kCreated),
      last_error_(0),
      playback_device_("default") {
}

AlsaAudioClient::AlsaAudioClient(const std::string &playback_device)
    : pcm_out_handle_(NULL),
      latency_ms_(kDefaultLatencyMs),
      state_(kCreated),
      last_error_(0),
      playback_device_(playback_device) {
}

AlsaAudioClient::~AlsaAudioClient() {
  if (pcm_out_handle_)
    snd_pcm_close(pcm_out_handle_);
}

bool AlsaAudioClient::Init() {
  if ((last_error_ = snd_pcm_open(&pcm_out_handle_,
                                  playback_device_.c_str(),
                                  SND_PCM_STREAM_PLAYBACK,
                                  0)) < 0) {
    return false;
  }

  set_state(kReady);
  return true;
}

void AlsaAudioClient::PlayTones(int sample_rate,
                                SampleFormat format,
                                int channels,
                                const std::set<int>& active_channels,
                                FrameGenerator* generator) {
  if (state() != kReady)
    return;

  int soft_resample = 1;
  if ((last_error_ = snd_pcm_set_params(pcm_out_handle_,
                                        SampleFormatToAlsaFormat(format),
                                        SND_PCM_ACCESS_RW_INTERLEAVED,
                                        channels,
                                        sample_rate,
                                        soft_resample,
                                        latency_ms_ * 1000)) < 0) {
    return;
  }

  snd_pcm_uframes_t buffer_size = 0;
  snd_pcm_uframes_t period_size = 0;
  if ((last_error_ = snd_pcm_get_params(pcm_out_handle_, &buffer_size,
                                        &period_size)) < 0) {
    return;
  }

  if ((last_error_ = snd_pcm_prepare(pcm_out_handle_)) < 0) {
    return;
  }

  size_t chunk_size = static_cast<size_t>(period_size);
  int frame_bytes = SampleFormatToFrameBytes(format, channels);
  char* chunk = new char[chunk_size * frame_bytes];

  // Run main loop until we are out of frames to generate.
  while (generator->HasMoreFrames()) {
    size_t to_write = chunk_size * frame_bytes;
    size_t written = to_write;
    generator->GetFrames(format, channels, active_channels, chunk, &written);

    if (written < to_write)
      memset(chunk + written, 0, (to_write - written));

    last_error_ = snd_pcm_writei(pcm_out_handle_,
                                 static_cast<void *>(chunk),
                                 static_cast<snd_pcm_uframes_t>(chunk_size));
    if (last_error_ < 0)
      break;
  }

  // Sending latency_ms_ of silence to ensure above audio is heard.  The
  // snd_pcm_drain() call takes a second or more to exit for some reason.
  int silent_chunk_count = 1 + sample_rate * latency_ms_ / 1000 / chunk_size;
  memset(chunk, 0, chunk_size * frame_bytes);
  while (silent_chunk_count--) {
    last_error_ = snd_pcm_writei(pcm_out_handle_,
                                 static_cast<void *>(chunk),
                                 static_cast<snd_pcm_uframes_t>(chunk_size));
  }
  snd_pcm_drop(pcm_out_handle_);

  delete[] chunk;
}

}  // namespace audio
}  // namespace autotest_client
