# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

INCLUDE =
# libcrash_dumper relies upon libbase.a (for logging) which relies
# upon libpthread.a and librt.a; all of which are static libraries and
# thus need to be explicitly specified here during executable link.
LDFLAGS = -lcrash_dumper -lbase -lpthread -lrt
BIN = crasher
SRC = crasher.cc
OBJS = crasher.o bomb.o
# Enable debugging to get symbols in stack traces.
CXXFLAGS += -ggdb

all: $(BIN).gz

# gzip so that portage does not strip.
$(BIN).gz: $(BIN)
	gzip $^

$(BIN): $(OBJS)
	$(CXX) $(INCLUDE) -o $@ $^ $(LDFLAGS)

clean:
	$(RM) $(BIN) $(BIN).gz
