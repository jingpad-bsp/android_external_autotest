# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

LINK_OPTION = -L/usr/X11R6/lib -lX11 -lm -ldl
SRCS = demo.c importgl.c app-linux.c

SanOGL: $(SRCS)
	gcc -m32 -O3 -o $@ $^ -Iinclude -Wall $(LINK_OPTION)
