# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

INCLUDE_PATH = -I../../../../../chrome/files/
LINK_PATH = -L../../../../../chrome/
LIBS = -lbase -lpthread -lrt

memory_Throughput: memory_Throughput.cc
	g++ $(INCLUDE_PATH) $(LINK_PATH) -O3 -m32 -o $@ $< $(LIBS)
