// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <string>

#include "base/command_line.h"
#include "gflags/gflags.h"
#include "gtest/gtest.h"
#include "media_v4l2_device.h"

class V4L2DeviceTest : public testing::Test {
 public:
  V4L2DeviceTest() {
    CHECK(ParseCommandline(&dev_name, &io));
  }

  static bool ParseCommandline(std::string* dev_name,
                               V4L2Device::IOMethod* io) {
    const CommandLine* cmd_line = CommandLine::ForCurrentProcess();

    // initialize default v4l2 device name.
    if (cmd_line->GetSwitchCount() == 0 || cmd_line->HasSwitch("help")) {
      PrintUsage();
      return false;
    }
    if (cmd_line->HasSwitch("device"))
      *dev_name = cmd_line->GetSwitchValueASCII("device");
    else
      *dev_name = "/dev/video";

    // initialize specified buffer io method.
    if (!cmd_line->HasSwitch("buffer-io")) {
      *io = V4L2Device::IO_METHOD_MMAP;
    } else {
      std::string v4l2_buffer_io;
      v4l2_buffer_io =  cmd_line->GetSwitchValueASCII("buffer-io");
      if (v4l2_buffer_io == "mmap") {
        *io = V4L2Device::IO_METHOD_MMAP;
      } else if (v4l2_buffer_io == "read") {
        *io = V4L2Device::IO_METHOD_READ;
      } else if (v4l2_buffer_io == "userp") {
        *io = V4L2Device::IO_METHOD_USERPTR;
      } else {
        PrintUsage();
        return false;
      }
    }
    return true;
  }

  static void PrintUsage() {
    printf("Usage: media_v4l2_unittest [options]\n\n"
           "Options:\n"
           "--device=DEVICE_NAME   Video device name [/dev/video]\n"
           "--help                 Print usage\n"
           "--buffer-io=mmap       Use memory mapped buffers\n"
           "--buffer-io=read       Use read() calls\n"
           "--buffer-io=userp      Use application allocated buffers\n");
  }

  bool ExerciseControl(V4L2Device* v4l2_dev, uint32_t id) {
    v4l2_queryctrl query_ctrl;
    if (v4l2_dev->QueryControl(id, &query_ctrl)) {
      EXPECT_TRUE(v4l2_dev->SetControl(id, query_ctrl.maximum));
      EXPECT_TRUE(v4l2_dev->SetControl(id, query_ctrl.minimum));
      EXPECT_TRUE(v4l2_dev->SetControl(id, query_ctrl.default_value));
    }
    return true;
  }

 protected:
  std::string dev_name;
  V4L2Device::IOMethod io;
};

TEST_F(V4L2DeviceTest, MultipleOpen) {
  V4L2Device v4l2_dev1(dev_name.c_str(), io, 4);
  V4L2Device v4l2_dev2(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev1.OpenDevice());
  EXPECT_TRUE(v4l2_dev2.OpenDevice());
  v4l2_dev1.CloseDevice();
  v4l2_dev2.CloseDevice();
}

TEST_F(V4L2DeviceTest, MultipleInit) {
  V4L2Device v4l2_dev1(dev_name.c_str(), io, 4);
  V4L2Device v4l2_dev2(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev1.OpenDevice());
  EXPECT_TRUE(v4l2_dev2.OpenDevice());
  EXPECT_TRUE(v4l2_dev1.InitDevice(640, 480, V4L2_PIX_FMT_YUYV, 0));
  // multiple streaming request should fail.
  EXPECT_FALSE(v4l2_dev2.InitDevice(640, 480, V4L2_PIX_FMT_YUYV, 0));
  EXPECT_TRUE(v4l2_dev1.UninitDevice());
  EXPECT_TRUE(v4l2_dev2.UninitDevice());
  v4l2_dev1.CloseDevice();
  v4l2_dev2.CloseDevice();
}

TEST_F(V4L2DeviceTest, EnumInputAndStandard) {
  V4L2Device v4l2_dev1(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev1.OpenDevice());
  v4l2_dev1.EnumInput();
  v4l2_dev1.EnumStandard();
  v4l2_dev1.CloseDevice();
}

TEST_F(V4L2DeviceTest, EnumControl) {
  V4L2Device v4l2_dev(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev.OpenDevice());
  v4l2_dev.EnumControl();
  v4l2_dev.CloseDevice();
}

TEST_F(V4L2DeviceTest, SetControl) {
  V4L2Device v4l2_dev(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev.OpenDevice());
  ExerciseControl(&v4l2_dev, V4L2_CID_BRIGHTNESS);
  ExerciseControl(&v4l2_dev, V4L2_CID_CONTRAST);
  ExerciseControl(&v4l2_dev, V4L2_CID_SATURATION);
  ExerciseControl(&v4l2_dev, V4L2_CID_GAMMA);
  ExerciseControl(&v4l2_dev, V4L2_CID_HUE);
  ExerciseControl(&v4l2_dev, V4L2_CID_GAIN);
  ExerciseControl(&v4l2_dev, V4L2_CID_SHARPNESS);
  v4l2_dev.CloseDevice();
}

TEST_F(V4L2DeviceTest, SetCrop) {
  V4L2Device v4l2_dev(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev.OpenDevice());
  v4l2_cropcap cropcap;
  memset(&cropcap, 0, sizeof(cropcap));
  if (v4l2_dev.GetCropCap(&cropcap)) {
    v4l2_crop crop;
    memset(&crop, 0, sizeof(crop));
    crop.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    crop.c = cropcap.defrect;
    v4l2_dev.SetCrop(&crop);
  }
  v4l2_dev.CloseDevice();
}

TEST_F(V4L2DeviceTest, GetCrop) {
  V4L2Device v4l2_dev(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev.OpenDevice());
  v4l2_crop crop;
  memset(&crop, 0, sizeof(crop));
  crop.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  v4l2_dev.GetCrop(&crop);
  v4l2_dev.CloseDevice();
}

TEST_F(V4L2DeviceTest, ProbeCaps) {
  V4L2Device v4l2_dev(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev.OpenDevice());
  v4l2_capability caps;
  EXPECT_TRUE(v4l2_dev.ProbeCaps(&caps, true));
  v4l2_dev.CloseDevice();
}

TEST_F(V4L2DeviceTest, EnumFormats) {
  V4L2Device v4l2_dev(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev.OpenDevice());
  v4l2_dev.EnumFormat(NULL);
  v4l2_dev.CloseDevice();
}

TEST_F(V4L2DeviceTest, EnumFrameSize) {
  V4L2Device v4l2_dev(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev.OpenDevice());
  uint32_t format_count = 0;
  v4l2_dev.EnumFormat(&format_count);
  for (uint32_t i = 0; i < format_count; ++i) {
    uint32_t pixfmt = v4l2_dev.GetPixelFormat(i);
    EXPECT_NE(pixfmt, 0xFFFFFFFF);
    EXPECT_TRUE(v4l2_dev.EnumFrameSize(pixfmt));
  }
  v4l2_dev.CloseDevice();
}

TEST_F(V4L2DeviceTest, FrameRate) {
  V4L2Device v4l2_dev(dev_name.c_str(), io, 4);
  EXPECT_TRUE(v4l2_dev.OpenDevice());
  v4l2_streamparm param;
  EXPECT_TRUE(v4l2_dev.GetParam(&param));
  EXPECT_TRUE(v4l2_dev.SetParam(&param));

  v4l2_capability caps;
  EXPECT_TRUE(v4l2_dev.ProbeCaps(&caps, true));
  // we only try to adjust frame rate when it claims can.
  if (caps.capabilities & V4L2_CAP_TIMEPERFRAME) {
    EXPECT_TRUE(v4l2_dev.SetFrameRate(15));
    EXPECT_TRUE(v4l2_dev.GetParam(&param));
    EXPECT_EQ(param.parm.capture.timeperframe.denominator,
              param.parm.capture.timeperframe.numerator * 15);

    EXPECT_TRUE(v4l2_dev.SetFrameRate(10));
    EXPECT_TRUE(v4l2_dev.GetParam(&param));
    EXPECT_EQ(param.parm.capture.timeperframe.denominator,
              param.parm.capture.timeperframe.numerator * 10);
  }

  v4l2_dev.CloseDevice();
}

int main(int argc, char** argv) {
  CommandLine::Init(argc, argv);
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}

