# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

LD_OPT_GL = -lX11 -lm -lGL
SRCS_GL = demo.c app-linux.c fixedpoint-funcs.c
TARGET_GL = SanOGL

LD_OPT_ES = -lX11 -lm -ldl
SRCS_ES = demo.c app-linux.c importgl.c
TARGET_ES = SanOGLES
GLES = -D SAN_ANGELES_OBSERVATION_GLES

all: $(TARGET_GL) $(TARGET_ES)

$(TARGET_GL): $(SRCS_GL)
	$(CC) -m32 -O3 -o $@ $^ -Iinclude -Wall $(LD_OPT_GL)

$(TARGET_ES): $(SRCS_ES)
	$(CC) -m32 -O3 $(GLES) -o $@ $^ -Iinclude -Wall $(LD_OPT_ES)

clean:
	$(RM) $(TARGET_GL)
	$(RM) $(TARGET_ES)
	
