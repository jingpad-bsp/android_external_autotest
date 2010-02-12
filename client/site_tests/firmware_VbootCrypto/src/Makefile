# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

VBOOT_REFERENCE_DIR = $(GCLIENT_ROOT)/src/platform/vboot_reference
BUILD_TEST_DIR = vboot_reference
# Test Binaries.
TEST_BINS = tests/sha_tests tests/testkeys tests/run_rsa_tests.sh
# Utility Binaries.
UTIL_BINS = utils/verify_data utils/signature_digest

all: 
        # Copy test sources into a temporary directory for building.
	rm -rf $(BUILD_TEST_DIR)
	cp -r $(VBOOT_REFERENCE_DIR) .
        # Always build from scratch.
	$(MAKE) -C $(BUILD_TEST_DIR) clean all
        # Move test binaries for use by the tests.
	mkdir tests
	for i in $(TEST_BINS); do \
	  ( mv $(BUILD_TEST_DIR)/$$i tests/ ) ;\
	done
        # Move utility binaries used by the tests.
	mkdir utils
	for i in $(UTIL_BINS); do \
	  ( mv $(BUILD_TEST_DIR)/$$i utils/ ) ;\
	done
        # Delete sources.
	rm -rf $(BUILD_TEST_DIR)

clean:
	rm -rf utils/ tests/
