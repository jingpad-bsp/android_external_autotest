# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

SRCS = platform_MiniJailPidNamespace.cc
TARGET = ../platform_MiniJailPidNamespace

LDFLAGS = 

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CXX) -O3 -o $@ $^ -Wall $(LDFLAGS)

clean:
	$(RM) $(TARGET)
