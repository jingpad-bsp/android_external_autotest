# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

SRCS = platform_MiniJailPtraceDisabled.cc
TARGET = ../platform_MiniJailPtraceDisabled

LDFLAGS = 

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CXX) -O3 -o $@ $^ -Wall $(LDFLAGS)

clean:
	$(RM) $(TARGET)
