# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

TROUSERS_DIR = "$(GCLIENT_ROOT)/src/third_party/trousers"
TESTSUITE_DIR = "$(TROUSERS_DIR)/testsuite"
TCG_DIR = "$(TESTSUITE_DIR)/tcg"
BUILD_TEST_DIR = work

TPM_CATEGORY ?= "nv"

LDFLAGS += -ltspi -lssl -lcrypto -lpthread

all:
	# Copy test sources into a temporary directory for building.
	rm -rf $(BUILD_TEST_DIR)
	mkdir -p $(BUILD_TEST_DIR) bin
	cp -a $(TCG_DIR)/common $(TCG_DIR)/include $(BUILD_TEST_DIR)
	cp -a $(TCG_DIR)/$(TPM_CATEGORY) $(BUILD_TEST_DIR)

	# Always build from scratch.
	$(MAKE) CC="$(CC)" LDFLAGS="$(LDFLAGS)" \
		-C "$(BUILD_TEST_DIR)/common"
	$(MAKE) CC="$(CC)" LDFLAGS="$(LDFLAGS)" \
		-C "$(BUILD_TEST_DIR)/$(TPM_CATEGORY)" all install

	# Delete sources.
	rm -rf $(BUILD_TEST_DIR)

clean:
	rm -rf $(BUILD_TEST_DIR) bin
