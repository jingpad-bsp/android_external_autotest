# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

INCLUDE = -I$(GCLIENT_ROOT)/src/third_party/chrome/files/
LDFLAGS = -L$(GCLIENT_ROOT)/src/third_party/chrome/ -lbase -lrt
TARGET = memory_Throughput
SRC = memory_Throughput.cc

$(TARGET): $(SRC)
	$(CXX) $(INCLUDE) -O3 -o $@ $^ $(LDFLAGS)

clean:
	$(RM) $(TARGET)
