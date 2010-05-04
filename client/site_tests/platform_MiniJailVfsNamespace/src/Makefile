# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

SRCS = platform_MiniJailVfsNamespace.cc
TARGET = ../platform_MiniJailVfsNamespace

LDFLAGS = -L$(GCLIENT_ROOT)/src/third_party/chrome/ -lbase -lpthread -lrt

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CXX) -O3 -o $@ $^ -Wall $(LDFLAGS)

clean:
	$(RM) $(TARGET)
