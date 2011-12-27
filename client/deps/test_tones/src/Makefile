# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

PKG_CONFIG ?= pkg-config

CXXFLAGS += -Wall -Werror -g \
	$(shell $(PKG_CONFIG) --cflags-only-other alsa)
INCLUDE_DIRS += $(shell $(PKG_CONFIG) --cflags-only-I alsa) -Iinclude
LIB_DIRS += $(shell $(PKG_CONFIG) --libs-only-L alsa) -Llib
LDFLAGS += $(shell $(PKG_CONFIG) --libs-only-l alsa)
DEPDIR = .deps

OBJS = alsa_client.o \
	tone_generators.o

BIN = audiofuntest test_tones

.PHONY: clean all

audiofuntest: LDFLAGS += -lfftw3 -pthread

all: $(BIN)

audiofuntest: $(OBJS) audiofuntest.cc
	$(CXX) $(CXXFLAGS) $(INCLUDE_DIRS) $(LIB_DIRS) $^ \
	    $(LDFLAGS) -o $@

test_tones: $(OBJS) test_tones.cc
	$(CXX) $(CXXFLAGS) $(INCLUDE_DIRS) $(LIB_DIRS) $^ \
	    $(LDFLAGS) -o $@

clean:
	rm -rf .deps $(BIN) $(OBJS)

# compile and generate dependency info
%.o: %.cc
	@mkdir -p $(shell dirname $(DEPDIR)/$*.d)
	$(CXX) -MMD -MF $(DEPDIR)/$*.d $(CXXFLAGS) $(INCLUDE_DIRS) -c -o $@ $<

-include $(OBJS:%.o=$(DEPDIR)/%.d)
