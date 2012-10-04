// Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


#include <set>
#include <limits>

#include "alsa_client.h"
#include "tone_generators.h"


namespace autotest_client {
namespace audio {

// Translates our SampleFormat type into a Alsa friendly format.
// This is a file-local function to avoid leaking the pa_sample_format type
// into the header.
_snd_pcm_format SampleFormatToAlsaFormat(SampleFormat format) {
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

int SampleFormatToFrameBytes(SampleFormat format, int channels) {
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

template<typename T>
double SampleToMagnitude(T sample) {
  double val = static_cast<double>(sample) / std::numeric_limits<T>::max();
  if (std::numeric_limits<T>::min() == 0) {
    val = val * 2.0 - 1.0;
  }
  return val;
}

void SampleCellToDoubleCell(void *sample_cell,
                            double *double_cell,
                            int num_frames,
                            SampleFormat format,
                            int num_channels) {
  if (format.type() == SampleFormat::kPcmU8) {
    unsigned char *ptr = static_cast<unsigned char*>(sample_cell);
    for (int n = 0; n < num_frames; n++) {
      double_cell[n] = 0.0;
      for (int c = 0; c < num_channels; c++) {
        double_cell[n] += SampleToMagnitude<unsigned char>(ptr[n]);
      }
      if (num_channels > 1) double_cell[n] /= num_channels;
    }

  } else if (format.type() == SampleFormat::kPcmS16) {
    int16_t *ptr = static_cast<int16_t*>(sample_cell);
    for (int n = 0; n < num_frames; n++) {
      double_cell[n] = 0.0;
      for (int c = 0; c < num_channels; c++) {
        double_cell[n] += SampleToMagnitude<int16_t>(ptr[n]);
      }
      if (num_channels > 1) double_cell[n] /= num_channels;
    }

  } else if (format.type() == SampleFormat::kPcmS24) {
    unsigned char *ptr = static_cast<unsigned char*>(sample_cell);
    for (int n = 0; n < num_frames; n++) {
      double_cell[n] = 0.0;
      for (int c = 0; c < num_channels; c++) {
        int32_t value = 0;
        for (int i = 0; i < 3; i++) {
          value <<= 8;
          value |= ptr[3 * n + 2 - i];
        }
        double_cell[n] += static_cast<double>(value) / (1 << 23);
      }
      if (num_channels > 1) double_cell[n] /= num_channels;
    }

  } else if (format.type() == SampleFormat::kPcmS32) {
    int32_t *ptr = static_cast<int32_t*>(sample_cell);
    for (int n = 0; n < num_frames; n++) {
      double_cell[n] = 0.0;
      for (int c = 0; c < num_channels; c++) {
        double_cell[n] += SampleToMagnitude<int32_t>(ptr[n]);
      }
      if (num_channels > 1) double_cell[n] /= num_channels;
    }

  }
}

int AlsaPlaybackClient::PlaybackParam::Init(_snd_pcm* handle,
                                            SampleFormat format,
                                            int num_channels) {
  int last_error;
  FreeMemory();
  snd_pcm_uframes_t buffer_size = 0;
  snd_pcm_uframes_t period_size = 0;
  if ((last_error = snd_pcm_get_params(handle, &buffer_size,
                                       &period_size)) < 0) {
    return last_error;
  }
  num_frames_  = static_cast<size_t>(period_size);
  frame_bytes_ = SampleFormatToFrameBytes(format, num_channels);
  chunk_       = new char[num_frames_ * frame_bytes_];
  return 0;
}

void AlsaPlaybackClient::PlaybackParam::Print(FILE *fp) {
  fprintf(fp, "    num_frames_  = %d\n", static_cast<int>(num_frames_));
  fprintf(fp, "    frame_bytes_ = %d\n", frame_bytes_);
}

AlsaPlaybackClient::AlsaPlaybackClient()
  : pcm_out_handle_(NULL),
  sample_rate_(64000),
  num_channels_(2),
  format_(SampleFormat::kPcmS32),
  latency_ms_(kDefaultLatencyMs),
  state_(kCreated),
  last_error_(0),
  playback_device_("default") {
}

AlsaPlaybackClient::AlsaPlaybackClient(const std::string &playback_device)
  : pcm_out_handle_(NULL),
  sample_rate_(64000),
  num_channels_(2),
  format_(SampleFormat::kPcmS32),
  latency_ms_(kDefaultLatencyMs),
  state_(kCreated),
  last_error_(0),
  playback_device_(playback_device) {
}

AlsaPlaybackClient::~AlsaPlaybackClient() {
  if (pcm_out_handle_)
    snd_pcm_close(pcm_out_handle_);
}

bool AlsaPlaybackClient::Init(int sample_rate, SampleFormat format,
                              int num_channels, std::set<int>* act_chs,
                              int period_size) {
  sample_rate_ = sample_rate;
  format_ = format;
  num_channels_ = num_channels;
  active_channels_ = act_chs;

  /* Open pcm handle */
  if (pcm_out_handle_)
    snd_pcm_close(pcm_out_handle_);
  if ((last_error_ = snd_pcm_open(&pcm_out_handle_,
                                  playback_device_.c_str(),
                                  SND_PCM_STREAM_PLAYBACK,
                                  0)) < 0) {
    pcm_out_handle_ = NULL;
    return false;
  }

  /* Calculate latency */
  if (period_size > 0) {
    latency_ms_ = 4000 * period_size / sample_rate;
  }

  /* Set format, access, num_channels, sample rate */
  char const* hwdevname = playback_device_.c_str();
  unsigned int rate_set;
  int soft_resample = 1;
  snd_pcm_hw_params_t *hwparams_;

  snd_pcm_hw_params_malloc(&hwparams_);

  if ((last_error_ = snd_pcm_hw_params_any(pcm_out_handle_, hwparams_)) < 0) {
    fprintf(stderr, "No config available for PCM device %s\n",
            hwdevname);
    goto set_hw_err;
  }

  if ((last_error_ = snd_pcm_hw_params_set_rate_resample(pcm_out_handle_,
      hwparams_, soft_resample)) < 0) {
    fprintf(stderr, "Resampling not available on PCM device %s\n",
            hwdevname);
    goto set_hw_err;
  }

  if ((last_error_ = snd_pcm_hw_params_set_access(pcm_out_handle_, hwparams_,
      SND_PCM_ACCESS_RW_INTERLEAVED)) < 0) {
    fprintf(stderr, "Access type not available on PCM device %s\n",
            hwdevname);
    goto set_hw_err;
  }

  if ((last_error_ = snd_pcm_hw_params_set_format(pcm_out_handle_, hwparams_,
      SampleFormatToAlsaFormat(format))) < 0) {
    fprintf(stderr, "Could not set format for device %s\n", hwdevname);
    goto set_hw_err;
  }

  if ((last_error_ = snd_pcm_hw_params_set_channels(pcm_out_handle_, hwparams_,
      num_channels)) < 0) {
    fprintf(stderr, "Could not set channel count for device %s\n",
            hwdevname);
    goto set_hw_err;
  }

  rate_set = static_cast<unsigned int>(sample_rate);
  if ((last_error_ = snd_pcm_hw_params_set_rate_near(pcm_out_handle_,
      hwparams_, &rate_set, 0)) < 0) {
    fprintf(stderr, "Could not set bitrate near %u for PCM device %s\n",
            sample_rate, hwdevname);
    goto set_hw_err;
  }

  if (rate_set != static_cast<unsigned int>(sample_rate))
    fprintf(stderr, "Warning: Actual rate(%u) != Requested rate(%u)\n",
            rate_set,
            sample_rate);

  snd_pcm_hw_params_set_periods(pcm_out_handle_, hwparams_, 2, 0);
  snd_pcm_hw_params_set_period_size(pcm_out_handle_,
                                    hwparams_,
                                    period_size * num_channels,
                                    0);

  if ((last_error_ = snd_pcm_hw_params(pcm_out_handle_, hwparams_)) < 0) {
    fprintf(stderr, "Unable to install hw params\n");
    goto set_hw_err;
  }


  /* Init playback parameter (a buffer with num_frame_ and frame_bytes) */
  if ((last_error_ = pb_param_.Init(pcm_out_handle_, format_,
                                    num_channels_)) < 0) {
    return false;
  }
  set_state(kReady);

set_hw_err:
  if (hwparams_)
    snd_pcm_hw_params_free(hwparams_);
  return last_error_ == 0;
}

void AlsaPlaybackClient::Play(shared_ptr<CircularBuffer<char> > buffers) {
  if (state() != kReady)
    return;

  if ((last_error_ = snd_pcm_prepare(pcm_out_handle_)) < 0) {
    return;
  }

  fprintf(stderr, "Start playback recorded data\n");

  int num_frames = NumFrames(*buffers, format_, num_channels_);

  char* cell_to_read;

  do {
    cell_to_read = buffers->LockCellToRead();

    last_error_ = snd_pcm_writei(pcm_out_handle_,
                                 static_cast<void *>(cell_to_read),
                                 static_cast<snd_pcm_uframes_t>(num_frames));
    buffers->UnlockCellToRead();
    if (last_error_ < 0)
      break;
  } while (state() == kReady /*&& buffers->MoreToRead()*/);

  // Sending latency_ms_ of silence to ensure above audio is heard.  The
  // snd_pcm_drain() call takes a second or more to exit for some reason.
  int silent_chunk_count =
      1 + sample_rate_ * latency_ms_ / 1000 / pb_param_.num_frames_;
  memset(pb_param_.chunk_, 0, pb_param_.num_frames_ * pb_param_.frame_bytes_);
  while (silent_chunk_count--) {
    last_error_ = snd_pcm_writei(
        pcm_out_handle_,
        static_cast<void *>(pb_param_.chunk_),
        static_cast<snd_pcm_uframes_t>(pb_param_.num_frames_));
  }
  set_state(kComplete);
  fprintf(stderr, "Stop playback recorded data\n");
  snd_pcm_drop(pcm_out_handle_);
}

void AlsaPlaybackClient::PlayTones() {
  if (state() != kReady)
    return;


  if ((last_error_ = snd_pcm_prepare(pcm_out_handle_)) < 0) {
    return;
  }

  fprintf(stderr, "Start play tone\n");
  // Run main loop until we are out of frames to generate.
  while (state() == kReady && generator_->HasMoreFrames()) {
    size_t to_write = pb_param_.num_frames_ * pb_param_.frame_bytes_;
    size_t written = to_write;
    written = generator_->GetFrames(format_, num_channels_, *active_channels_,
                                    pb_param_.chunk_, to_write);

    if (written < to_write)
      memset(pb_param_.chunk_ + written, 0, (to_write - written));

    last_error_ = snd_pcm_writei(
        pcm_out_handle_,
        static_cast<void *>(pb_param_.chunk_),
        static_cast<snd_pcm_uframes_t>(pb_param_.num_frames_));
    if (last_error_ < 0)
      break;
  }

  // Sending latency_ms_ of silence to ensure above audio is heard.  The
  // snd_pcm_drain() call takes a second or more to exit for some reason.
  int silent_chunk_count =
      1 + sample_rate_ * latency_ms_ / 1000 / pb_param_.num_frames_;
  memset(pb_param_.chunk_, 0, pb_param_.num_frames_ * pb_param_.frame_bytes_);
  while (silent_chunk_count--) {
    last_error_ = snd_pcm_writei(
        pcm_out_handle_,
        static_cast<void *>(pb_param_.chunk_),
        static_cast<snd_pcm_uframes_t>(pb_param_.num_frames_));
  }
  set_state(kComplete);
  snd_pcm_drop(pcm_out_handle_);
  fprintf(stderr, "Stop play tone\n");
}

void AlsaPlaybackClient::Print(FILE *fp) {
  fprintf(fp, "AlsaPlaybackClient::Print()\n");
  fprintf(fp, "  sample_rate_  = %d\n", sample_rate_);
  fprintf(fp, "  num_channels_ = %d\n", num_channels_);
  fprintf(fp, "  format_       = %s\n", format_.to_string());
  fprintf(fp, "  latency_ms_   = %u\n", latency_ms_);
  fprintf(fp, "  buffersize    = %.1fms\n",
          1e3 * pb_param_.num_frames_ / sample_rate_);
  fprintf(fp, "  pb_param_ = {\n");
  pb_param_.Print(fp);
  fprintf(fp, "  }\n");
}

AlsaCaptureClient::AlsaCaptureClient()
  : pcm_capture_handle_(NULL),
    sample_rate_(64000),
    num_channels_(2),
    format_(SampleFormat::kPcmS32),
    latency_ms_(kDefaultLatencyMs),
    state_(kCreated),
    last_error_(0),
    capture_device_("default") {
}

AlsaCaptureClient::AlsaCaptureClient(const std::string &capture_device)
  : pcm_capture_handle_(NULL),
    sample_rate_(64000),
    num_channels_(2),
    format_(SampleFormat::kPcmS32),
    latency_ms_(kDefaultLatencyMs),
    state_(kCreated),
    last_error_(0),
    capture_device_(capture_device) {
}

AlsaCaptureClient::~AlsaCaptureClient() {
  if (pcm_capture_handle_)
    snd_pcm_close(pcm_capture_handle_);
  if (hwparams_)
    snd_pcm_hw_params_free(hwparams_);
}

bool AlsaCaptureClient::Init(int sample_rate, SampleFormat format,
                             int num_channels, int buffer_count,
                             int period_size) {

  sample_rate_ = sample_rate;
  format_ = format;
  num_channels_ = num_channels;
  /* Create cpature device handle */
  if (pcm_capture_handle_)
    snd_pcm_close(pcm_capture_handle_);

  last_error_ = snd_pcm_open(&pcm_capture_handle_,
                             capture_device_.c_str(),
                             SND_PCM_STREAM_CAPTURE, 0);
  if (last_error_ < 0) {
    pcm_capture_handle_ = NULL;
    return false;
  }

  /* Calculate latency */
  if (period_size > 0) {
    latency_ms_ = 4000 * period_size / sample_rate;
  }

  /* Set format, access, num_channels, sample rate, period, resample */
  char const* hwdevname = capture_device_.c_str();

  unsigned int rate_set;

  snd_pcm_hw_params_malloc(&hwparams_);

  if (snd_pcm_hw_params_any(pcm_capture_handle_, hwparams_) < 0) {
    fprintf(stderr, "No config available for PCM device %s\n",
            hwdevname);
    return false;
  }

  int soft_resample = 1;
  if (snd_pcm_hw_params_set_rate_resample(pcm_capture_handle_, hwparams_,
      soft_resample) < 0) {
    fprintf(stderr, "Resampling not available on PCM device %s\n",
            hwdevname);
    return false;
  }

  if (snd_pcm_hw_params_set_access(pcm_capture_handle_, hwparams_,
      SND_PCM_ACCESS_RW_INTERLEAVED) < 0) {
    fprintf(stderr, "Access type not available on PCM device %s\n",
            hwdevname);
    return false;
  }

  if (snd_pcm_hw_params_set_format(pcm_capture_handle_, hwparams_,
      SampleFormatToAlsaFormat(format)) < 0) {
    fprintf(stderr, "Could not set format for device %s\n", hwdevname);
    return false;
  }

  if (snd_pcm_hw_params_set_channels(pcm_capture_handle_, hwparams_,
         num_channels) < 0) {
    fprintf(stderr, "Could not set channel count for device %s\n",
            hwdevname);
    return false;
  }

  rate_set = static_cast<unsigned int>(sample_rate);
  if (snd_pcm_hw_params_set_rate_near(pcm_capture_handle_,
                                      hwparams_,
                                      &rate_set,
                                      0) < 0) {
    fprintf(stderr, "Could not set bitrate near %u for PCM device %s\n",
            sample_rate, hwdevname);
    return false;
  }

  if (rate_set != static_cast<unsigned int>(sample_rate))
    fprintf(stderr, "Warning: Actual rate(%u) != Requested rate(%u)\n",
            rate_set,
            sample_rate);

  snd_pcm_hw_params_set_periods(pcm_capture_handle_, hwparams_, 2, 0);
  snd_pcm_hw_params_set_period_size(pcm_capture_handle_,
                                    hwparams_,
                                    period_size * num_channels,
                                    0);

  if (snd_pcm_hw_params(pcm_capture_handle_, hwparams_) < 0) {
    fprintf(stderr, "Unable to install hw params\n");
    return false;
  }

  set_state(kReady);

  /* Setup circular buffer */
  snd_pcm_uframes_t actual_buffer_size = 0;
  snd_pcm_uframes_t actual_period_size = 0;
  if ((last_error_ = snd_pcm_get_params(
      pcm_capture_handle_, &actual_buffer_size, &actual_period_size)) < 0) {
    return false;
  }
  circular_buffer_.reset(
      new CircularBuffer<char>(buffer_count,
      actual_period_size * SampleFormatToFrameBytes(format, num_channels)));
  return true;
}


int AlsaCaptureClient::Capture() {
  ssize_t completed;
  int res;
  size_t num_frames = NumFrames(*circular_buffer_, format_, num_channels_);

  if (state() != kReady)
    return 1;
  if ((last_error_ = snd_pcm_prepare(pcm_capture_handle_)) < 0) {
    return 2;
  }

  fprintf(stderr, "Start capturing data\n");
  // Keep capturing until state() is not kReady
  res = snd_pcm_prepare(pcm_capture_handle_);
  if (res < 0) {
    fprintf(stderr, "Prepare error: %s", snd_strerror(res));
    return 3;
  }
  char* cell_to_write;
  while (state() == kReady) {
    snd_pcm_wait(pcm_capture_handle_, 100);

    cell_to_write = circular_buffer_->LockCellToWrite();
    completed = snd_pcm_readi(pcm_capture_handle_,
                              cell_to_write,
                              num_frames);
    circular_buffer_->UnlockCellToWrite();

    if (completed < 0) {
      fprintf(stderr, "I/O error in %s: %s, %lu\n",
              snd_pcm_stream_name(SND_PCM_STREAM_CAPTURE),
              snd_strerror(completed),
              (long unsigned int)completed);
      return 4;
    }
  }
  fprintf(stderr, "Stop capturing data\n");
  snd_pcm_drop(pcm_capture_handle_);
  return 0;
}

void AlsaCaptureClient::Print(FILE *fp) {
  fprintf(fp, "AlsaCaptureClient::Print()\n");
  fprintf(fp, "  sample_rate_  = %d\n", sample_rate_);
  fprintf(fp, "  num_channels_ = %d\n", num_channels_);
  fprintf(fp, "  format_       = %s\n", format_.to_string());
  fprintf(fp, "  latency_ms_   = %u\n", latency_ms_);
  fprintf(fp, "  circular_buffer_:{\n");
  circular_buffer_->Print(fp);
  fprintf(fp, "  }\n");
}

}  // namespace audio
}  // namespace autotest_client
