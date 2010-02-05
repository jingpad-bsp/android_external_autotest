# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# OpenGL implementation.
LDFLAGS_GL = -lX11 -lm -lGL
SRCS_GL = demo.c app-linux.c importvbo.c
TARGET_GL = SanOGL

# GLES2 implementation, run-time importation of GL/EGL functions.
LDFLAGS_ES = -lX11 -lm -ldl
SRCS_ES = demo.c app-linux.c importgl.c matrixop.c shader.c
INCLUDE_ES = -I$(GCLIENT_ROOT)/src/third_party/khronos/files/include
TARGET_ES = SanOGLES
GLES_FLAG = -D SAN_ANGELES_OBSERVATION_GLES

# GLES2 implementation, link to the GLES/EGL libraries.
LDFLAGS_ES_S = -lX11 -lm -lGLESv2 -lEGL
TARGET_ES_S = SanOGLES_S
GLES_FLAG_S = -D SAN_ANGELES_OBSERVATION_GLES -D DISABLE_IMPORTGL

all: $(TARGET_GL) $(TARGET_ES_S)

$(TARGET_GL): $(SRCS_GL)
	$(CC) -m32 -O3 -o $@ $^ -Wall $(LDFLAGS_GL)

$(TARGET_ES): $(SRCS_ES)
	$(CC) -m32 -O3 $(GLES_FLAG) -o $@ $^ $(INCLUDE_ES) -Wall $(LDFLAGS_ES)

$(TARGET_ES_S): $(SRCS_ES)
	$(CC) -m32 -O3 $(GLES_FLAG_S) -o $@ $^ $(INCLUDE_ES) -Wall $(LDFLAGS_ES_S)

clean:
	$(RM) $(TARGET_GL)
	$(RM) $(TARGET_ES)
	$(RM) $(TARGET_ES_S)
