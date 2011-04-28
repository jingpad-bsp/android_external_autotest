// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <assert.h>
#include <getopt.h>
#include <signal.h>
#include <X11/Xlib.h>

#include <iostream>
#include <string>

#include "media_v4l2_device.h"

#define CHECK(a) assert(a)

class V4L2DeviceX11 : public V4L2Device {
 public:
  V4L2DeviceX11(const char* dev_name,
                IOMethod io,
                uint32_t buffers)
    : V4L2Device(dev_name, io, buffers),
      xdisplay_(NULL),
      xwindow_(0),
      xrunning_(false) {
  }

  virtual bool OpenDevice() {
    if (!InitX11())
      return false;
    return V4L2Device::OpenDevice();
  }

  virtual void CloseDevice() {
    UninitX11();  // Ignore error.
    return V4L2Device::CloseDevice();
  }

  virtual bool InitDevice(uint32_t width,
                          uint32_t height,
                          uint32_t pixfmt,
                          uint32_t fps) {
    // Only after InitDevice, we know the actual format of capture.
    if (V4L2Device::InitDevice(width, height, pixfmt, fps)) {
      // Resize the window to fit that of the video.
      XResizeWindow(xdisplay_, xwindow_,
                    GetActualWidth(), GetActualHeight());

      // Initialize the XImage to store the output of YUV -> RGBA conversion.
      int size = GetActualWidth() * GetActualHeight() * 4;
      ximage_ = XCreateImage(xdisplay_,
                            DefaultVisual(xdisplay_, DefaultScreen(xdisplay_)),
                            DefaultDepth(xdisplay_, DefaultScreen(xdisplay_)),
                            ZPixmap,
                            0,
                            static_cast<char*>(malloc(size)),
                            GetActualWidth(),
                            GetActualHeight(),
                            32,
                            GetActualWidth() * 4);
      return ximage_ ? true : false;
    }
    return false;
  }

 private:
  bool InitX11() {
    xdisplay_ = XOpenDisplay(NULL);
    if (!xdisplay_) {
      std::cout << "Error - cannot open display" << std::endl;
      return false;
    }

    // Get properties of the screen.
    int32_t screen = DefaultScreen(xdisplay_);
    int32_t root_window = RootWindow(xdisplay_, screen);

    // Creates the window.
    xwindow_ = XCreateSimpleWindow(xdisplay_, root_window, 1, 1, 100, 50, 0,
                                   BlackPixel(xdisplay_, screen),
                                   BlackPixel(xdisplay_, screen));
    XStoreName(xdisplay_, xwindow_, "X11 Media Player");

    XSelectInput(xdisplay_, xwindow_, ExposureMask | ButtonPressMask);
    XMapWindow(xdisplay_, xwindow_);
    return true;
  }

  bool UninitX11() {
    XDestroyWindow(xdisplay_, xwindow_);
    XCloseDisplay(xdisplay_);
    return true;
  }

  virtual void ProcessImage(const void* p) {
    while (XPending(xdisplay_)) {
      // Pump out all pending events.
      XEvent e;
      XNextEvent(xdisplay_, &e);
      if (e.type == ButtonPress)
        Stop();
    }
    if (!ximage_->data)
      return;
    ConvertYUVToRGB32(reinterpret_cast<uint8_t*>(const_cast<void*>(p)),
                      reinterpret_cast<uint8_t*>(ximage_->data),
                      GetActualPixelFormat().fmt.pix.pixelformat,
                      GetActualWidth(), GetActualHeight(),
                      GetActualPixelFormat().fmt.pix.bytesperline,
                      ximage_->bytes_per_line);
    GC gc = XCreateGC(xdisplay_, xwindow_, 0, NULL);
    XPutImage(xdisplay_, xwindow_, gc, ximage_,
              0, 0, 0, 0, GetActualWidth(), GetActualHeight());
    XFlush(xdisplay_);
    XFreeGC(xdisplay_, gc);
  }

  inline int32_t clip(int32_t value, int32_t min, int32_t max) {
    return (value > max ? max : value < min ? min : value);
  }

  void ConvertYUVToRGB32(uint8_t* in, uint8_t* out, int32_t ifmt,
                         int32_t width, int32_t height,
                         int32_t istride, int32_t ostride) {
    if ((ifmt == v4l2_fourcc('Y', 'U', 'Y', 'V')) ||
        (ifmt == v4l2_fourcc('Y', 'V', 'Y', 'U')) ||
        (ifmt == v4l2_fourcc('U', 'Y', 'V', 'Y')) ||
        (ifmt == v4l2_fourcc('V', 'Y', 'U', 'Y'))) {

      int y0_offset;
      int y1_offset;
      int u_offset;
      int v_offset;

      if (ifmt == v4l2_fourcc('Y', 'U', 'Y', 'V')) {
        y0_offset = 0;
        y1_offset = 2;
        u_offset = 1;
        v_offset = 3;
      } else if (ifmt == v4l2_fourcc('Y', 'V', 'Y', 'U')) {
        y0_offset = 0;
        y1_offset = 2;
        u_offset = 3;
        v_offset = 1;
      } else if (ifmt == v4l2_fourcc('U', 'Y', 'V', 'Y')) {
        y0_offset = 1;
        y1_offset = 3;
        u_offset = 0;
        v_offset = 2;
      } else if (ifmt == v4l2_fourcc('V', 'Y', 'U', 'Y')) {
        y0_offset = 1;
        y1_offset = 3;
        u_offset = 2;
        v_offset = 0;
      } else {
        CHECK(0);
      }

      for (int32_t i = 0; i < height; ++i) {
        for (int32_t j = 0; j < width * 2; j += 4) {
          int32_t y0 = in[j + y0_offset];
          int32_t y1 = in[j + y1_offset];
          int32_t u = in[j + u_offset] - 128;
          int32_t v = in[j + v_offset] - 128;

          int32_t r = (298 * y0 + 409 * v + 128) >> 8;
          int32_t g = (298 * y0 - 100 * u - 208 * v + 128) >> 8;
          int32_t b = (298 * y0 + 516 * u + 128) >> 8;

          out[j * 2 + 0] = clip(b, 0, 255);
          out[j * 2 + 1] = clip(g, 0, 255);
          out[j * 2 + 2] = clip(r, 0, 255);
          out[j * 2 + 3] = 255;

          r = (298 * y1 + 409 * v + 128) >> 8;
          g = (298 * y1 - 100 * u - 208 * v + 128) >> 8;
          b = (298 * y1 + 516 * u + 128) >> 8;

          out[j * 2 + 4] = clip(b, 0, 255);
          out[j * 2 + 5] = clip(g, 0, 255);
          out[j * 2 + 6] = clip(r, 0, 255);
          out[j * 2 + 7] = 255;
        }
        in += istride;
        out += ostride;
      }
    } else if ((ifmt == v4l2_fourcc('Y', 'U', '1', '2')) ||
               (ifmt == v4l2_fourcc('Y', 'V', '1', '2'))) {
      // Can't use bytes_per_line for this.  While bytes_per_line is width*1.5,
      // the rest of this part of code is using line stride as the
      // y-plane's line stride, which should just be the width of the image.
      istride = width;

      uint8_t* y_plane = in;
      uint8_t* u_plane = in + height * istride;
      // assumption. stride for uv is half of the y stride.
      uint8_t* v_plane = u_plane + height * istride / 4;

      // YU12 is identical to YV12 except that the U and V planes are swapped.
      if (ifmt == v4l2_fourcc('Y', 'V', '1', '2')) {
        uint8_t* temp = u_plane;
        u_plane = v_plane;
        v_plane = temp;
      }

      for (int32_t i = 0; i < height; ++i) {
        for (int32_t j = 0; j < width; ++j) {
          int32_t y = y_plane[j];
          int32_t u = u_plane[j >> 1] - 128;
          int32_t v = v_plane[j >> 1] - 128;

          int32_t r = (298 * y + 409 * v + 128) >> 8;
          int32_t g = (298 * y - 100 * u - 208 * v + 128) >> 8;
          int32_t b = (298 * y + 516 * u + 128) >> 8;

          out[j * 4 + 0] = clip(b, 0, 255);
          out[j * 4 + 1] = clip(g, 0, 255);
          out[j * 4 + 2] = clip(r, 0, 255);
          out[j * 4 + 3] = 255;
        }
        y_plane += istride;
        if (i & 1) {
          u_plane += istride >> 1;
          v_plane += istride >> 1;
        }
        out += ostride;
      }
    } else {
      CHECK(0);
    }
  }

 private:
  Display* xdisplay_;
  Window xwindow_;
  XImage* ximage_;
  bool xrunning_;
};

static void PrintUsage(int argc, char** argv) {
  printf("Usage: %s [options]\n\n"
         "Options:\n"
         "--device=DEVICE_NAME    Video device name [/dev/video]\n"
         "--help                  Print usage\n"
         "--mmap                  Use memory mapped buffers\n"
         "--read                  Use read() calls\n"
         "--userp                 Use application allocated buffers\n"
         "--buffers=[NUM]         Minimum buffers required\n"
         "--frames=[NUM]          Maximum frame to capture\n"
         "--width=[NUM]           Picture width to capture\n"
         "--height=[NUM]          Picture height to capture\n"
         "--pixel-format=[fourcc] Picture format fourcc code\n"
         "--fps=[NUM]             Frame rate for capture\n"
         "--display               Launch X11 window to preview\n"
         "--time=[NUM]            Time to capture in seconds\n",
         argv[0]);
}

static const char short_options[] = "d:?mrun:f:w:h:t:x:kz:";
static const struct option
long_options[] = {
        { "device",       required_argument, NULL, 'd' },
        { "help",         no_argument,       NULL, '?' },
        { "mmap",         no_argument,       NULL, 'm' },
        { "read",         no_argument,       NULL, 'r' },
        { "userp",        no_argument,       NULL, 'u' },
        { "buffers",      required_argument, NULL, 'n' },
        { "frames",       required_argument, NULL, 'f' },
        { "width",        required_argument, NULL, 'w' },
        { "height",       required_argument, NULL, 'h' },
        { "pixel-format", required_argument, NULL, 't' },
        { "fps",          required_argument, NULL, 'x' },
        { "display",      no_argument,       NULL, 'k' },
        { "time",         required_argument, NULL, 'z' },
        { 0, 0, 0, 0 }
};

int main(int argc, char** argv) {
  std::string dev_name = "/dev/video";
  V4L2Device::IOMethod io = V4L2Device::IO_METHOD_MMAP;
  uint32_t buffers = 4;
  uint32_t frames = 100;
  uint32_t width = 640;
  uint32_t height = 480;
  uint32_t pixfmt = V4L2_PIX_FMT_YUYV;
  uint32_t fps = 0;
  bool display = false;
  uint32_t time_to_capture = 0;

  for (;;) {
    int32_t index;
    int32_t c = getopt_long(argc, argv, short_options, long_options, &index);
    if (-1 == c)
      break;
    switch (c) {
      case 0:  // getopt_long() flag.
        break;
      case 'd':
        // Initialize default v4l2 device name.
        dev_name = strdup(optarg);
        break;
      case '?':
        PrintUsage(argc, argv);
        exit (EXIT_SUCCESS);
      case 'm':
        io = V4L2Device::IO_METHOD_MMAP;
        break;
      case 'r':
        io = V4L2Device::IO_METHOD_READ;
        break;
      case 'u':
        io = V4L2Device::IO_METHOD_USERPTR;
        break;
      case 'n':
        buffers = atoi(optarg);
        break;
      case 'f':
        frames = atoi(optarg);
        break;
      case 'w':
        width = atoi(optarg);
        break;
      case 'h':
        height = atoi(optarg);
        break;
      case 't': {
        std::string fourcc = optarg;
        if (fourcc.length() != 4) {
          PrintUsage(argc, argv);
          exit (EXIT_FAILURE);
        }
        pixfmt = V4L2Device::MapFourCC(fourcc.c_str());
        break;
      }
      case 'x':
        fps = atoi(optarg);
        break;
      case 'k':
        display = true;
        break;
      case 'z':
        time_to_capture = atoi(optarg);
        break;
      default:
        PrintUsage(argc, argv);
        exit(EXIT_FAILURE);
    }
  }

  if (time_to_capture) {
    printf("capture %dx%d %c%c%c%c picture for %d seconds at %d fps\n",
           width, height, (pixfmt >> 0) & 0xff, (pixfmt >> 8) & 0xff,
           (pixfmt >> 16) & 0xff, (pixfmt >> 24) & 0xff, time_to_capture, fps);
  } else {
    printf("capture %dx%d %c%c%c%c picture for %d frames at %d fps\n",
           width, height, (pixfmt >> 0) & 0xff, (pixfmt >> 8) & 0xff,
           (pixfmt >> 16) & 0xff, (pixfmt >> 24) & 0xff, frames, fps);
  }

  V4L2Device* device = NULL;
  if (display) {
    device = new V4L2DeviceX11(dev_name.c_str(), io, buffers);
  } else {
    device = new V4L2Device(dev_name.c_str(), io, buffers);
  }

  int32_t retcode = 0;

  if (!device->OpenDevice())
    retcode = 1;

  if (!retcode && !device->InitDevice(width, height, pixfmt, fps))
    retcode = 2;

  if (!retcode && !device->StartCapture())
    retcode = 3;

  if (!retcode && !device->Run(frames, time_to_capture))
    retcode = 4;

  if (!retcode && !device->StopCapture())
    retcode = 5;

  if (!retcode && !device->UninitDevice())
    retcode = 6;

  device->CloseDevice();

  if (device)
    delete device;

  return retcode;
}

