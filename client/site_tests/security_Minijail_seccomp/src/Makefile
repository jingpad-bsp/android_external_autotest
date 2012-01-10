# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

CFLAGS =
LDFLAGS =

SRC_OK = ok.c
SRC_FAIL = fail.c

TARGET_OK = ../ok
TARGET_FAIL = ../fail

all: $(TARGET_OK) $(TARGET_FAIL)

$(TARGET_OK): $(SRC_OK)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(TARGET_FAIL): $(SRC_FAIL)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	$(RM) $(TARGET_OK)
	$(RM) $(TARGET_FAIL)
