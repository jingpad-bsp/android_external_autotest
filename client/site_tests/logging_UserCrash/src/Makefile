# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

BINS = crasher_nobreakpad
SRC = crasher.cc
OBJS = crasher.o bomb.o
TGZ = crasher.tgz

all: $(TGZ)

# gzip so that portage does not strip.
$(TGZ): $(BINS)
	tar czf $(TGZ) $^

crasher_nobreakpad: $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $^

.cc.o:
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	$(RM) *.o $(BIN) $(TGZ)
