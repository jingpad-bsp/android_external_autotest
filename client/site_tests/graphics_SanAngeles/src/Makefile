# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

OPTIONS = -O3 -Wall
GLES = -D SAN_ANGELES_OBSERVATION_GLES
NO_IMPORTGL = -D DISABLE_IMPORTGL
HIGH_RES = -D SUPERSHAPE_HIGH_RES

# OpenGL implementation.
LDFLAGS_GL = -lX11 -lm -lGL
SRCS_GL = demo.c app-linux.c importvbo.c
TARGET_GL = SanOGL
GL_FLAG = $(HIGH_RES)

# GLES2 implementation, run-time importation of GL/EGL functions.
LDFLAGS_ES = -lX11 -lm -ldl
SRCS_ES = demo.c app-linux.c importgl.c matrixop.c shader.c
INCLUDE_ES = -I$(GCLIENT_ROOT)/src/third_party/khronos/files/include
TARGET_ES = SanOGLES
ES_FLAG = $(GLES) $(HIGH_RES)

# GLES2 implementation, link to the GLES/EGL libraries.
LDFLAGS_ES_S = -lX11 -lm -lGLESv2 -lEGL
TARGET_ES_S = SanOGLES_S
ES_S_FLAG =  $(GLES) $(NO_IMPORTGL) $(HIGH_RES)

all: $(TARGET_GL) $(TARGET_ES)

$(TARGET_GL): $(SRCS_GL)
	$(CC) $(GL_FLAG) -o $@ $^ $(LDFLAGS_GL) $(OPTIONS)

$(TARGET_ES): $(SRCS_ES)
	$(CC) $(ES_FLAG) -o $@ $^ $(INCLUDE_ES) $(LDFLAGS_ES) $(OPTIONS)

$(TARGET_ES_S): $(SRCS_ES)
	$(CC) $(ES_S_FLAG) -o $@ $^ $(INCLUDE_ES) $(LDFLAGS_ES_S) $(OPTIONS)

clean:
	$(RM) $(TARGET_GL)
	$(RM) $(TARGET_ES)
	$(RM) $(TARGET_ES_S)
