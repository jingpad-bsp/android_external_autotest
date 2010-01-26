# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

LD_OPT = -lrt
TARGET = ../read_hwclock
SRC = read_hwclock.c

$(TARGET): $(SRC)
	$(CXX) $(INCLUDE_PATH) -O2 -o $@ $^ $(LD_OPT)

clean:
	$(RM) $(TARGET)
