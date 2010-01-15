# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

INCLUDE_PATH = -I../../../../../chrome/files/
LD_OPT = -L../../../../../chrome/ -lbase -lpthread -lrt
TARGET = memory_Throughput
SRC = memory_Throughput.cc

$(TARGET): $(SRC)
	$(CXX) $(INCLUDE_PATH) -O3 -m32 -o $@ $^ $(LD_OPT)

clean:
	$(RM) $(TARGET)
