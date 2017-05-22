// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <getopt.h>

#include <cmath>
#include <limits>
#include <memory>
#include <string>
#include <unordered_map>

#include "camera_characteristics.h"
#include "common_types.h"
#include "media_v4l2_device.h"

static void PrintUsage(int argc, char** argv) {
  printf("Usage: %s [options]\n\n"
         "Options:\n"
         "--help               Print usage\n"
         "--device=DEVICE_NAME Video device name [/dev/video]\n"
         "--usb-info=VID:PID   Device vendor id and product id\n",
         argv[0]);
}

static const char short_options[] = "?d:u:";
static const struct option
long_options[] = {
        { "help",     no_argument,       NULL, '?' },
        { "device",   required_argument, NULL, 'd' },
        { "usb-info", required_argument, NULL, 'u' },
        { 0, 0, 0, 0 }
};

int RunTest(V4L2Device* device, V4L2Device::IOMethod io,
            uint32_t buffers, uint32_t capture_time_in_sec, uint32_t width,
            uint32_t height, uint32_t pixfmt, float fps) {
  int32_t retcode = 0;
  if (!device->InitDevice(io, width, height, pixfmt, fps))
    retcode = 1;

  if (!retcode && !device->StartCapture())
    retcode = 2;

  if (!retcode && !device->Run(capture_time_in_sec))
    retcode = 3;

  if (!retcode && !device->StopCapture())
    retcode = 4;

  if (!retcode && !device->UninitDevice())
    retcode = 5;

  return retcode;
}

bool GetSupportedFormats(
    V4L2Device* device, SupportedFormats* supported_formats) {
  supported_formats->clear();

  SupportedFormat format;
  uint32_t num_format = 0;
  device->EnumFormat(&num_format, false);
  for (uint32_t i = 0; i < num_format; ++i) {
    if (!device->GetPixelFormat(i, &format.fourcc)) {
      printf("[Error] Get format error\n");
      return false;
    }
    uint32_t num_frame_size;
    if (!device->EnumFrameSize(format.fourcc, &num_frame_size, false)) {
      printf("[Error] Enumerate frame size error\n");
      return false;
    };

    for (uint32_t j = 0; j < num_frame_size; ++j) {
      if (!device->GetFrameSize(j, format.fourcc, &format.width,
                                &format.height)) {
        printf("[Error] Get frame size error\n");
        return false;
      };
      uint32_t num_frame_rate;
      if (!device->EnumFrameInterval(format.fourcc, format.width,
                                     format.height, &num_frame_rate, false)) {
        printf("[Error] Enumerate frame interval error\n");
        return false;
      };

      format.frame_rates.clear();
      float frame_rate;
      for (uint32_t k = 0; k < num_frame_rate; ++k) {
        if (!device->GetFrameInterval(k, format.fourcc, format.width,
                                      format.height, &frame_rate)) {
          printf("[Error] Get frame interval error\n");
          return false;
        };
        // All supported resolution should have at least 1 fps.
        if (frame_rate < 1.0) {
          printf("[Error] Frame rate should be at least 1.\n");
          return false;
        }
        format.frame_rates.push_back(frame_rate);
      }
      supported_formats->push_back(format);
    }
  }
  return true;
}

SupportedFormat GetMaximumResolution(const SupportedFormats& formats) {
  SupportedFormat max_format;
  memset(&max_format, 0, sizeof(max_format));
  for (const auto& format : formats) {
    if (format.width >= max_format.width &&
        format.height >= max_format.height) {
      max_format = format;
    }
  }
  return max_format;
}

// Find format according to width and height. If multiple formats support the
// same resolution, choose V4L2_PIX_FMT_MJPEG first.
const SupportedFormat* FindFormatByResolution(const SupportedFormats& formats,
                                              uint32_t width,
                                              uint32_t height) {
  const SupportedFormat* result_format = nullptr;
  for (const auto& format : formats) {
    if (format.width == width && format.height == height) {
      if (!result_format || format.fourcc == V4L2_PIX_FMT_MJPEG) {
        result_format = &format;
      }
    }
  }
  return result_format;
}

bool TestIO(const std::string& dev_name) {
  uint32_t buffers = 4;
  uint32_t width = 640;
  uint32_t height = 480;
  uint32_t pixfmt = V4L2_PIX_FMT_YUYV;
  float fps = 30.0;
  uint32_t time_to_capture = 3;  // The unit is second.
  bool check_1280x960 = false;

  std::unique_ptr<V4L2Device> device(
      new V4L2Device(dev_name.c_str(), buffers));

  if (!device->OpenDevice())
    return false;

  v4l2_capability cap;
  if (!device->ProbeCaps(&cap))
    return false;

  if (cap.capabilities & V4L2_CAP_STREAMING) {
    int mmap_ret = RunTest(device.get(), V4L2Device::IO_METHOD_MMAP, buffers,
        time_to_capture, width, height, pixfmt, fps);
    int userp_ret = RunTest(device.get(), V4L2Device::IO_METHOD_USERPTR,
        buffers, time_to_capture, width, height, pixfmt, fps);
    if (mmap_ret && userp_ret) {
      printf("[Error] Stream I/O failed.\n");
      return false;
    }
  } else {
    printf("[Error] Streaming capability is mandatory.\n");
    return false;
  }

  device->CloseDevice();
  return true;
}

// Test all required resolutions with 30 fps.
bool TestResolutions(const std::string& dev_name,
                     bool check_1280x960,
                     bool check_1600x1200) {
  uint32_t buffers = 4;
  uint32_t time_to_capture = 3;
  V4L2Device::IOMethod io = V4L2Device::IO_METHOD_MMAP;
  std::unique_ptr<V4L2Device> device(
      new V4L2Device(dev_name.c_str(), buffers));

  if (!device->OpenDevice())
    return false;

  SupportedFormats supported_formats;
  if (!GetSupportedFormats(device.get(), &supported_formats)) {
    printf("[Error] Get supported formats failed in %s.\n", dev_name.c_str());
    return false;
  }
  SupportedFormat max_resolution = GetMaximumResolution(supported_formats);

  const float kFrameRate = 30.0;
  SupportedFormats required_resolutions;
  required_resolutions.push_back(SupportedFormat(320, 240, 0, kFrameRate));
  required_resolutions.push_back(SupportedFormat(640, 480, 0, kFrameRate));
  required_resolutions.push_back(SupportedFormat(1280, 720, 0, kFrameRate));
  required_resolutions.push_back(SupportedFormat(1920, 1080, 0, kFrameRate));
  if (check_1600x1200) {
    required_resolutions.push_back(SupportedFormat(1600, 1200, 0, kFrameRate));
  }
  if (check_1280x960) {
    required_resolutions.push_back(SupportedFormat(1280, 960, 0, kFrameRate));
  }

  v4l2_streamparm param;
  if (!device->GetParam(&param)) {
    printf("[Error] Can not get stream param on device '%s'\n",
        dev_name.c_str());
    return false;
  }

  for (const auto& test_resolution : required_resolutions) {
    // Skip the resolution that is larger than the maximum.
    if (max_resolution.width < test_resolution.width ||
        max_resolution.height < test_resolution.height) {
      continue;
    }

    const SupportedFormat* test_format = FindFormatByResolution(
        supported_formats, test_resolution.width, test_resolution.height);
    if (test_format == nullptr) {
      printf("[Error] %dx%d not found in %s\n", test_resolution.width,
          test_resolution.height, dev_name.c_str());
      return false;
    }

    bool frame_rate_30_supported = false;
    for (const auto& frame_rate : test_format->frame_rates) {
      if (std::fabs(frame_rate - kFrameRate) <=
          std::numeric_limits<float>::epsilon()) {
        frame_rate_30_supported = true;
        break;
      }
    }
    if (!frame_rate_30_supported) {
      printf("[Error] Cannot test 30 fps for %dx%d (%08X) failed in %s\n",
          test_format->width, test_format->height, test_format->fourcc,
          dev_name.c_str());
      return false;
    }

    if (RunTest(device.get(), io, buffers, time_to_capture,
          test_format->width, test_format->height, test_format->fourcc,
          kFrameRate)) {
      printf("[Error] Could not capture frames for %dx%d (%08X) %.2f fps in "
          "%s\n", test_format->width, test_format->height,
          test_format->fourcc, kFrameRate, dev_name.c_str());
      return false;
    }

    // Make sure the driver didn't adjust the format.
    v4l2_format fmt;
    if (!device->GetV4L2Format(&fmt)) {
      return false;
    }
    if (test_format->width != fmt.fmt.pix.width ||
        test_format->height != fmt.fmt.pix.height ||
        test_format->fourcc != fmt.fmt.pix.pixelformat ||
        std::fabs(kFrameRate - device->GetFrameRate()) >
            std::numeric_limits<float>::epsilon()) {
      printf("[Error] Capture test %dx%d (%08X) %.2f fps failed in %s\n",
          test_format->width, test_format->height, test_format->fourcc,
          kFrameRate, dev_name.c_str());
      return false;
    }
  }
  device->CloseDevice();

  return true;
}

int main(int argc, char** argv) {
  std::string dev_name = "/dev/video";
  std::string usb_info = "";

  for (;;) {
    int32_t index;
    int32_t c = getopt_long(argc, argv, short_options, long_options, &index);
    if (-1 == c)
      break;
    switch (c) {
      case 0:  // getopt_long() flag.
        break;
      case '?':
        PrintUsage(argc, argv);
        exit (EXIT_SUCCESS);
      case 'd':
        // Initialize default v4l2 device name.
        dev_name = strdup(optarg);
        break;
      case 'u':
        usb_info = strdup(optarg);
        break;
      default:
        PrintUsage(argc, argv);
        exit(EXIT_FAILURE);
    }
  }

  std::unordered_map<std::string, std::string> mapping = {{usb_info, dev_name}};
  CameraCharacteristics characteristics;
  DeviceInfos device_infos =
      characteristics.GetCharacteristicsFromFile(mapping);

  bool check_1280x960 = false;
  bool check_1600x1200 = false;
  if (device_infos.size() > 1) {
    printf("[Error] One device should not have multiple configs.\n");
    exit(EXIT_FAILURE);
  }
  if (device_infos.size() == 1) {
    check_1280x960 = !device_infos[0].resolution_1280x960_unsupported;
    check_1600x1200 = !device_infos[0].resolution_1600x1200_unsupported;
  }
  printf("[Info] check 1280x960: %d\n", check_1280x960);
  printf("[Info] check 1600x1200: %d\n", check_1600x1200);

  if (!TestIO(dev_name))
    exit(EXIT_FAILURE);

  if (!TestResolutions(dev_name, check_1280x960, check_1600x1200))
    exit(EXIT_FAILURE);

  return EXIT_SUCCESS;
}
