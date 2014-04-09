# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

PKG_CONFIG ?= pkg-config
BASE_VER ?= 242728
PC_DEPS = libchrome-$(BASE_VER)
PC_CFLAGS := $(shell $(PKG_CONFIG) --cflags $(PC_DEPS))
PC_LIBS := $(shell $(PKG_CONFIG) --libs $(PC_DEPS))

CPPFLAGS += $(PC_CFLAGS)
LDLIBS += $(PC_LIBS)

TARGET = hardware_MemoryThroughput

all: $(TARGET)

clean:
	$(RM) $(TARGET)
