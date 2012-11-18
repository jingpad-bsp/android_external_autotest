# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

PKG_CONFIG ?= pkg-config

CFLAGS = -g -Wall -Werror `$(PKG_CONFIG)`
LDLIBS = `$(PKG_CONFIG)`

getfb: getfb.c
	$(CXX) $(CFLAGS) $^ -o ../$@ $(LDLIBS)
