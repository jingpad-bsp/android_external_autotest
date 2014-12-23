// Copyright 2015 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "base/logging.h"
#include "main.h"
#include "waffle_stuff.h"
#include <stdio.h>

GLint g_width = WINDOW_WIDTH;
GLint g_height = WINDOW_HEIGHT;

scoped_ptr<GLInterface> g_main_gl_interface;

#ifdef USE_OPENGL
namespace gl {
#define F(fun, type) type fun = NULL;
LIST_PROC_FUNCTIONS(F)
#undef F
};
#define GL_API WAFFLE_CONTEXT_OPENGL
#else
#define GL_API WAFFLE_CONTEXT_OPENGL_ES2
#endif

// TODO(fjhenigman): upstream this platform selection stuff to waffle
#define PLATFORM_GLX     1
#define PLATFORM_X11_EGL 2
#define PLATFORM_GBM     3

#define CONCAT(a,b) a ## b
#define STRING(a) #a
#define PLATFORM_NUMBER(x) CONCAT(PLATFORM_, x)
#define PLATFORM_ENUM(x) CONCAT(WAFFLE_PLATFORM_, x)
#define PLATFORM_IS(x) PLATFORM_NUMBER(x) == PLATFORM_NUMBER(PLATFORM)
#define PLATFORM_STRING STRING(PLATFORM)

#if PLATFORM_IS(GLX)
#include "waffle_glx.h"
#elif PLATFORM_IS(X11_EGL)
#include "waffle_x11_egl.h"
#elif PLATFORM_IS(GBM)
#include <xf86drmMode.h>
#include <gbm.h>
#include "waffle_gbm.h"
#else
#error "platform not specified - compile with -DPLATFORM=<platform>"
#endif

#define WAFFLE_CHECK_ERROR do { CHECK(WaffleOK()); } while (0)

GLInterface* GLInterface::Create() {
  return new WaffleInterface;
}

static bool WaffleOK() {
  const waffle_error_info *info = waffle_error_get_info();
  if (info->code == WAFFLE_NO_ERROR)
    return true;
  printf("# Error: %s: %s\n",
         waffle_error_to_string(info->code),
         info->message);
  return false;
}

// TODO(fjhenigman): when waffle allows requesting a full screen window,
//                   this should no longer be necessary
bool WaffleInterface::GetDisplaySize() {
  union waffle_native_display *ndpy = waffle_display_get_native(display_);
  bool ok = false;

  if (!ndpy)
    return false;

#if PLATFORM_IS(GBM)
  // find first in-use connector then
  //   get encoder connected to it
  //   get crtc connected to encoder
  //   get mode from crtc
  // OR
  //   get connector's preferred mode
  int fd = gbm_device_get_fd(ndpy->gbm->gbm_device);
  drmModeModeInfoPtr mode = NULL;
  drmModeResPtr res = drmModeGetResources(fd);
  for (int i = 0; !mode && i < res->count_connectors; ++i) {
    drmModeConnectorPtr conn = drmModeGetConnector(fd, res->connectors[i]);
    drmModeEncoderPtr enc = NULL;
    drmModeCrtcPtr crtc = NULL;
    if (conn && conn->connection == DRM_MODE_CONNECTED) {
      enc = drmModeGetEncoder(fd, conn->encoder_id);
      if (enc)
        crtc = drmModeGetCrtc(fd, enc->crtc_id);
      if (crtc)
        mode = &crtc->mode;
      if (!mode) {
        // display apparently not initialized, use first preferred mode
        // (or last mode if none are preferred)
        for (int j = 0; j < conn->count_modes; ++j) {
          mode = conn->modes + j;
          if (mode->type & DRM_MODE_TYPE_PREFERRED)
            break;
        }
      }
      if (mode) {
        width_ = mode->hdisplay;
        height_ = mode->vdisplay;
        ok = true;
      }
    }
    drmModeFreeConnector(conn);
    drmModeFreeEncoder(enc);
    drmModeFreeCrtc(crtc);
  }
  drmModeFreeResources(res);
#else
#if PLATFORM_IS(GLX)
  Display *xdpy = ndpy->glx->xlib_display;
#elif PLATFORM_IS(X11_EGL)
  Display *xdpy = ndpy->x11_egl->xlib_display;
#endif
  width_ = DisplayWidth(xdpy, DefaultScreen(xdpy));
  height_ = DisplayHeight(xdpy, DefaultScreen(xdpy));
  ok = true;
#endif

  free(ndpy);
  return ok;
}

void WaffleInterface::InitOnce() {
  // Prevent multiple initializations.
  if (surface_)
    return;

  int32_t initAttribs[] = {
    WAFFLE_PLATFORM, PLATFORM_ENUM(PLATFORM),
    0
  };

  waffle_init(initAttribs);
  WAFFLE_CHECK_ERROR;

  display_ = waffle_display_connect(NULL);
  WAFFLE_CHECK_ERROR;

  CHECK(GetDisplaySize());

  if (g_width == -1)
    g_width = width_;
  if (g_height == -1)
    g_height = height_;

  if (g_height > height_ || g_width > width_)
    printf("# Warning: buffer dimensions (%d, %d)"
           "larger than fullscreen (%d, %d)\n",
            g_height, g_width, height_, width_);

  int32_t configAttribs[] = {
    WAFFLE_CONTEXT_API,     GL_API,
    WAFFLE_RED_SIZE,        1,
    WAFFLE_GREEN_SIZE,      1,
    WAFFLE_BLUE_SIZE,       1,
    WAFFLE_DEPTH_SIZE,      1,
    WAFFLE_STENCIL_SIZE,    1,
    WAFFLE_DOUBLE_BUFFERED, true,
    0
  };

  config_ = waffle_config_choose(display_, configAttribs);
  WAFFLE_CHECK_ERROR;

  surface_ = waffle_window_create(config_, g_width, g_height);
  WAFFLE_CHECK_ERROR;

  waffle_window_show(surface_);
  WAFFLE_CHECK_ERROR;
}

bool WaffleInterface::Init() {
  InitOnce();

  context_ = CreateContext();
  CHECK(context_);

  waffle_make_current(display_, surface_, context_);
  WAFFLE_CHECK_ERROR;

#if defined(USE_OPENGL)
#define F(fun, type) fun = reinterpret_cast<type>(waffle_get_proc_address(#fun));
  LIST_PROC_FUNCTIONS(F)
#undef F
#endif

  return true;
}

void WaffleInterface::Cleanup() {
  waffle_make_current(display_, NULL, NULL);
  WAFFLE_CHECK_ERROR;

  waffle_context_destroy(context_);
  WAFFLE_CHECK_ERROR;
}

void WaffleInterface::SwapBuffers() {
  waffle_window_swap_buffers(surface_);
  WAFFLE_CHECK_ERROR;
}

bool WaffleInterface::SwapInterval(int interval) {
  return false;
}

bool WaffleInterface::MakeCurrent(const GLContext& context) {
  return waffle_make_current(display_, surface_, context);
}

const GLContext WaffleInterface::CreateContext() {
  return waffle_context_create(config_, NULL);
}

void WaffleInterface::CheckError() {
}

void WaffleInterface::DeleteContext(const GLContext& context) {
  waffle_context_destroy(context);
  WAFFLE_CHECK_ERROR;
}
