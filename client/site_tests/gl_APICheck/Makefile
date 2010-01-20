# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

LD_OPT_GL = -lX11 -lm -lGL
SRCS_GL = gl_APICheck.cc
TARGET_GL = gl_APICheck

LD_OPT_ES = -lX11 -lm
SRCS_ES = gles_APICheck.cc
TARGET_ES = gles_APICheck

all: $(TARGET_GL) 

$(TARGET_GL): $(SRCS_GL)
	$(CXX) -m32 -O3 -o $@ $^ -Wall $(LD_OPT_GL)

$(TARGET_ES): $(SRCS_ES)
	$(CXX) -m32 -O3 -o $@ $^ -Iinclude -Wall $(LD_OPT_ES)

clean:
	$(RM) $(TARGET_GL)
	$(RM) $(TARGET_ES)
