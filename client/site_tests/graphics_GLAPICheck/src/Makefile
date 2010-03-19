# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

LDFLAGS_GL = -lX11 -lm -lGL
SRCS_GL = gl_APICheck.cc
TARGET_GL = ../gl_APICheck

LDFLAGS_ES = -lX11 -lm -ldl
SRCS_ES = gles_APICheck.cc
TARGET_ES = ../gles_APICheck
INCLUDE_ES = -I$(GCLIENT_ROOT)/src/third_party/khronos/files/include

all: $(TARGET_GL) $(TARGET_ES)

$(TARGET_GL): $(SRCS_GL)
	$(CXX) -O3 -o $@ $^ -Wall $(LDFLAGS_GL)

$(TARGET_ES): $(SRCS_ES)
	$(CXX) -O3 -o $@ $^ $(INCLUDE_ES) -Wall $(LDFLAGS_ES)

clean:
	$(RM) $(TARGET_GL)
	$(RM) $(TARGET_ES)
