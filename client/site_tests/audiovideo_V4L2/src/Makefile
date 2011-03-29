# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

LDFLAGS =  -lrt -lX11 -ldl

LDFLAGS_UNITTEST = -lrt

SRC = media_v4l2_device.cc  \
      media_v4l2_test.cc

SRC_UNITTEST = media_v4l2_device.cc \
               media_v4l2_unittest.cc

TARGET = ../media_v4l2_test

TARGET_UNITTEST = ../media_v4l2_unittest

all: $(TARGET) $(TARGET_UNITTEST)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) -O3 -o $@ $^ $(LDFLAGS)

$(TARGET_UNITTEST): $(SRC_UNITTEST)
	$(CXX) $(CXXFLAGS) -O3 -o $@ $^ $(LDFLAGS_UNITTEST)


clean:
	$(RM) $(TARGET)
	$(RM) $(TARGET_UNITTEST)
