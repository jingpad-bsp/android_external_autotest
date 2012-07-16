// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef AUTOTEST_CLIENT_SITE_TESTS_AUDIO_ALSA_CLIENT_H_
#define AUTOTEST_CLIENT_SITE_TESTS_AUDIO_ALSA_CLIENT_H_

#include <set>
#include <string>
#include <cstdio>
#include <tr1/memory>
#include <alsa/asoundlib.h>

#include "common.h"

using std::tr1::shared_ptr;

// Alsa API forward declares.
struct _snd_pcm;

namespace autotest_client {
namespace audio {

class FrameGenerator;

_snd_pcm_format SampleFormatToAlsaFormat(SampleFormat format);

/* Calculate number of bytes per frame given format and channels */
int SampleFormatToFrameBytes(SampleFormat format, int channels);

/*
 * Convert a sample cell (size = num_frames) into double cell.
 * If there are two channels, the sample will be averaged
 */
void SampleCellToDoubleCell(void *sample_cell, double *double_cell,
                            int num_frames, SampleFormat format,
                            int num_channels);

/*
 * Store captured sample data
 * Store converted double data for FFT
 * cell_[][] is a 2-D array (buffer_count_ * buffer_size_)
 */
template<typename T>
struct CircularBuffer {
 public:
  CircularBuffer(int count, int size)
      : buffer_count_(count), buffer_size_(size), write_ptr_(0), read_ptr_(0) {
    cell_ = new T*[count];
    cell_[0] = new T[count * size];
    for (int i = 1; i < count; ++i) {
      cell_[i] = cell_[i - 1] + size;
    }
    mutexes = new pthread_mutex_t[count];
    has_data = new pthread_cond_t[count];
    for (int i = 0; i < count; ++i) {
      pthread_mutex_init(&mutexes[i], NULL);
      pthread_cond_init(&has_data[i], NULL);
    }
  }

  ~CircularBuffer() {
    delete [] cell_[0];
    delete [] cell_;
    delete [] mutexes;
    delete [] has_data;
  }

  /* Lock mutex, return cell pointer
   * MUST call UnlockCellToWrite(); after work is done.
   */
  T* LockCellToWrite(int *index = NULL) {
    if (index) *index = write_ptr_;
    pthread_mutex_lock(&mutexes[write_ptr_]);
    return cell_[write_ptr_];
  }

  void UnlockCellToWrite() {
    int last = write_ptr_;
    write_ptr_ = (write_ptr_ + 1) % buffer_count_;
    pthread_cond_signal(&has_data[last]);
    pthread_mutex_unlock(&mutexes[last]);
  }

  /* Lock mutex and increment read_ptr_, return cell pointer
   * MUST call UnlockCellToRead(); after work is done.
   */
  T* LockCellToRead(int *index = NULL) {
    if (index) *index = read_ptr_;
    pthread_mutex_lock(&mutexes[read_ptr_]);
    while (read_ptr_ == write_ptr_) {
      pthread_cond_wait(&has_data[read_ptr_], &mutexes[read_ptr_]);
    }
    return cell_[read_ptr_];
  }

  void UnlockCellToRead() {
    pthread_mutex_unlock(&mutexes[read_ptr_]);
    read_ptr_ = (read_ptr_ + 1) % buffer_count_;
  }

  void SyncReadPtrToWrite() { read_ptr_ = write_ptr_; }
  bool MoreToRead() { return read_ptr_ != write_ptr_; }
  void Print(FILE *fp) {
    fprintf(fp, "    buffer_count_ = %d\n", buffer_count_);
    fprintf(fp, "    buffer_size_ = %d\n", buffer_size_);
    fprintf(fp, "    write_ptr_ = %d\n", write_ptr_);
    fprintf(fp, "    read_ptr_ = %d\n", read_ptr_);
  }
  int Count() { return buffer_count_; }
  int Size() { return buffer_size_; }

 private:
  int buffer_count_;
  int buffer_size_;
  int write_ptr_, read_ptr_;
  T** cell_;
  pthread_mutex_t *mutexes;
  pthread_cond_t *has_data;
};

inline size_t NumFrames(CircularBuffer<char> &buffers,
                        SampleFormat format,
                        int num_channels) {
  return buffers.Size() / SampleFormatToFrameBytes(format, num_channels);
}

class AlsaPlaybackClient {
 public:
  enum State {
    kCreated,
    kFailed,
    kTerminated,
    kReady,
    kComplete,
  };

  class PlaybackParam {
    friend class AlsaPlaybackClient;
    PlaybackParam() : chunk_(NULL), num_frames_(0), frame_bytes_(0) {}
    void FreeMemory() {
      if (chunk_) delete [] chunk_;
      chunk_ = NULL;
    }
    ~PlaybackParam() { FreeMemory(); }
    int Init(_snd_pcm* handle, SampleFormat format, int num_channels);
    void Print(FILE *fp);

    char *chunk_;
    size_t num_frames_;
    int frame_bytes_;
  };

  AlsaPlaybackClient();
  AlsaPlaybackClient(const std::string &playback_device);
  virtual ~AlsaPlaybackClient();

  virtual void Print(FILE *fp);
  void SetPlayObj(FrameGenerator* gen) { generator_ = gen; }
  FrameGenerator* PlayObj() { return generator_; }

  virtual bool Init(int sample_rate,
                    SampleFormat format,
                    int num_channels,
                    std::set<int>* act_chs,
                    int period_size = 0);
  virtual void PlayTones();
  virtual void Play(shared_ptr<CircularBuffer<char> > buffers);

  // Trivial accessors/mutators.
  virtual void set_state(State state) { state_ = state; }
  virtual State state() const { return state_; }
  virtual int last_error() const { return last_error_; }
  virtual int SampRate() const { return sample_rate_; }
  virtual int NumChannel() const { return num_channels_; }
  virtual SampleFormat Format() const { return format_; }
  virtual std::set<int>* ActiveChannels() const { return active_channels_; }

 private:
  static const unsigned kDefaultLatencyMs = 50;

  // Callback signaling completion of flushing of a stream.
  //static void StreamFlushed(int success, void* userdata);

  _snd_pcm* pcm_out_handle_;
  int sample_rate_;
  int num_channels_;
  SampleFormat format_;
  unsigned int latency_ms_;
  PlaybackParam pb_param_;
  std::set<int>* active_channels_;

  // Our abstracted version of the connection state.
  State state_;

  // The last error reported by Alsa. Useful for debugging.
  int last_error_;

  // The playback device to open.
  std::string playback_device_;

  // snd_pcm_set_params() argument when PlayThreadEntry() calls PlayTones()
  FrameGenerator* generator_;

};


class AlsaCaptureClient {
 public:
  enum State {
    kCreated,
    kFailed,
    kTerminated,
    kReady,
    kComplete,
  };

  AlsaCaptureClient();
  AlsaCaptureClient(const std::string &capture_device);
  virtual ~AlsaCaptureClient();

  virtual bool Init(int sample_rate, SampleFormat format, int num_channels,
                    int buffer_count, int period_size = 0);
  virtual void Print(FILE *fp);

  virtual int Capture();

  // Trivial accessors/mutators.
  virtual snd_pcm_hw_params_t *get_hw_params() const { return hwparams_; }
  virtual void set_state(State state) { state_ = state; }
  virtual State state() const { return state_; }
  virtual int last_error() const { return last_error_; }
  virtual int SampRate() const { return sample_rate_; }
  virtual int NumChannel() const { return num_channels_; }
  virtual SampleFormat Format() const { return format_; }
  virtual shared_ptr<CircularBuffer<char> > Buffer() const {
    return circular_buffer_;
  }

 private:
  static const unsigned kDefaultLatencyMs = 50;

  // Callback signaling completion of flushing of a stream.
  //static void StreamFlushed(int success, void* userdata);

  _snd_pcm* pcm_capture_handle_;
  snd_pcm_hw_params_t *hwparams_;
  unsigned int sample_rate_;
  int num_channels_;
  SampleFormat format_;
  unsigned int latency_ms_;

  // Our abstracted version of the connection state.
  State state_;

  // The last error reported by Alsa. Useful for debugging.
  int last_error_;

  // The playback device to open.
  std::string capture_device_;

  // Circular buffer to write captured data
  shared_ptr<CircularBuffer<char> > circular_buffer_;

};


}  // namespace audio
}  // namespace autotest_client

#endif  // AUTOTEST_CLIENT_SITE_TESTS_AUDIO_ALSA_CLIENT_H_
