# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

CFLAGS		= -Os -g -Wall
OUTDIR		= ..
TARGET		= nvmap_iovmm_stress
OUT		= $(OUTDIR)/$(TARGET)
SOURCE_FILES	= nvmap_iovmm_stress.c
GCC		= $(CROSS_COMPILE)gcc
SCRIPT		= runTest.sh

all:
	$(GCC) -lEGL -lGLESv2 $(CFLAGS) $(SOURCE_FILES) -o $(OUT)
	cp -f $(SCRIPT) $(OUTDIR)

clean:
	rm -f *.o
	rm -rf $(OUT)
	rm -f $(OUTDIR)/$(SCRIPT)
