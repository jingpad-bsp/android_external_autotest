# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

INCLUDE =
LDFLAGS =
BIN = crasher
SRC = crasher.cc

all: $(BIN)

$(BIN): $(SRC)
	$(CXX) $(INCLUDE) -o $@ $^ $(LDFLAGS)

clean:
	$(RM) $(BIN)
