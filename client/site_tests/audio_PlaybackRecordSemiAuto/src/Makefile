# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

PKG_CONFIG ?= pkg-config

CFLAGS += -Wall -Werror -g $(shell $(PKG_CONFIG) --cflags-only-other alsa)
INCLUDE_DIRS += $(shell $(PKG_CONFIG) --cflags-only-I alsa)
LIB_DIRS += $(shell $(PKG_CONFIG) --libs-only-L alsa)
LDFLAGS += $(shell $(PKG_CONFIG) --libs-only-l alsa)
DEPDIR = .deps

ALSA_CAPS_OBJS = alsa_caps.o
ALSA_CAPS_BIN = alsa_caps

.PHONY: clean all

all: $(ALSA_CAPS_BIN)

$(ALSA_CAPS_BIN): $(ALSA_CAPS_OBJS)
	$(CC) -Wall $(CFLAGS) $(INCLUDE_DIRS) $(LIB_DIRS) $^ \
	    $(LDFLAGS) -o $@

clean:
	rm -rf .deps $(ALSA_CAPS_BIN) $(ALSA_CAPS_OBJS)

# compile and generate dependency info
%.o: %.c
	@mkdir -p $(shell dirname $(DEPDIR)/$*.d)
	$(CC) -MMD -MF $(DEPDIR)/$*.d $(CFLAGS) $(INCLUDE_DIRS) -c -o $@ $<

-include $(ALSA_CAPS_OBJS:%.o=$(DEPDIR)/%.d)
