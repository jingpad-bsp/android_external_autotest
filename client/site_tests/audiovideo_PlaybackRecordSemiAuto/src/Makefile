# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

CXXFLAGS += -Wall -Werror -g $(shell pkg-config --cflags-only-other libpulse)
INCLUDE_DIRS += $(shell pkg-config --cflags-only-I libpulse)
LIB_DIRS += $(shell pkg-config --libs-only-L libpulse)
LDFLAGS += $(shell pkg-config --libs-only-l libpulse)
DEPDIR = .deps

TEST_TONES_OBJS = pulse_client.o \
                  test_tones.o \
                  tone_generators.o
TEST_TONES_BIN = test_tones

.PHONY: clean all

all: $(TEST_TONES_BIN)

$(TEST_TONES_BIN): $(TEST_TONES_OBJS)
	$(CXX) -Wall $(CXXFLAGS) $(INCLUDE_DIRS) $(LIB_DIRS) $^ \
	    $(LDFLAGS) -o $@

clean:
	rm -rf .deps $(TEST_TONES_BIN) $(TEST_TONES_OBJS)

# compile and generate dependency info
%.o: %.cc
	@mkdir -p $(shell dirname $(DEPDIR)/$*.d)
	$(CXX) -MMD -MF $(DEPDIR)/$*.d $(CXXFLAGS) $(INCLUDE_DIRS) -c -o $@ $<

-include $(TEST_TONES_OBJS:%.o=$(DEPDIR)/%.d)
